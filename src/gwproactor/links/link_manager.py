import asyncio
import json
import logging
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Optional
from typing import Tuple
from typing import Union

from gwproto import Message
from gwproto import MQTTCodec
from gwproto.messages import Ack
from gwproto.messages import CommEvent
from gwproto.messages import EventT
from gwproto.messages import MQTTConnectEvent
from gwproto.messages import MQTTDisconnectEvent
from gwproto.messages import MQTTFullySubscribedEvent
from gwproto.messages import PeerActiveEvent
from gwproto.messages import PingMessage
from gwproto.messages import ProblemEvent
from gwproto.messages import ResponseTimeoutEvent
from gwproto.messages import StartupEvent
from paho.mqtt.client import MQTTMessageInfo
from result import Err
from result import Ok
from result import Result

from gwproactor.config import MQTTClient
from gwproactor.config import ProactorSettings
from gwproactor.links import AckWaitInfo
from gwproactor.links.acks import AckManager
from gwproactor.links.acks import AckTimerCallback
from gwproactor.links.link_state import InvalidCommStateInput
from gwproactor.links.link_state import LinkState
from gwproactor.links.link_state import LinkStates
from gwproactor.links.link_state import StateName
from gwproactor.links.link_state import Transition
from gwproactor.links.message_times import LinkMessageTimes
from gwproactor.links.message_times import MessageTimes
from gwproactor.links.mqtt import QOS
from gwproactor.links.mqtt import MQTTClients
from gwproactor.links.mqtt import MQTTClientWrapper
from gwproactor.links.reuploads import Reuploads
from gwproactor.links.timer_interface import TimerManagerInterface
from gwproactor.logger import ProactorLogger
from gwproactor.message import MQTTConnectFailPayload
from gwproactor.message import MQTTConnectPayload
from gwproactor.message import MQTTDisconnectPayload
from gwproactor.message import MQTTReceiptPayload
from gwproactor.message import MQTTSubackPayload
from gwproactor.persister import JSONDecodingError
from gwproactor.persister import PersisterInterface
from gwproactor.persister import UIDMissingWarning
from gwproactor.problems import Problems
from gwproactor.stats import ProactorStats


@dataclass
class LinkManagerTransition(Transition):
    canceled_acks: list[AckWaitInfo] = field(default_factory=list)


class LinkManager:
    PERSISTER_ENCODING = "utf-8"
    publication_name: str
    _settings: ProactorSettings
    _logger: ProactorLogger
    _stats: ProactorStats
    _event_persister: PersisterInterface
    _reuploads: Reuploads
    _mqtt_clients: MQTTClients
    _mqtt_codecs: dict[str, MQTTCodec]
    _states: LinkStates
    _message_times: MessageTimes
    _acks: AckManager

    def __init__(
        self,
        publication_name: str,
        settings: ProactorSettings,
        logger: ProactorLogger,
        stats: ProactorStats,
        event_persister: PersisterInterface,
        timer_manager: TimerManagerInterface,
        ack_timeout_callback: AckTimerCallback,
    ):
        self.publication_name = publication_name
        self._settings = settings
        self._logger = logger
        self._stats = stats
        self._event_persister = event_persister
        self._reuploads = Reuploads(
            self._event_persister,
            self._logger,
            self._settings.num_initial_event_reuploads,
        )
        self._mqtt_clients = MQTTClients()
        self._mqtt_codecs = dict()
        self._states = LinkStates()
        self._message_times = MessageTimes()
        self._acks = AckManager(
            timer_manager, ack_timeout_callback, delay=settings.ack_timeout_seconds
        )

    @property
    def upstream_client(self) -> str:
        return self._mqtt_clients.upstream_client

    @property
    def primary_peer_client(self) -> str:
        return self._mqtt_clients.primary_peer_client

    @property
    def num_pending(self) -> int:
        return self._event_persister.num_pending

    @property
    def num_reupload_pending(self) -> int:
        return self._reuploads.num_reupload_pending

    @property
    def num_reuploaded_unacked(self) -> int:
        return self._reuploads.num_reuploaded_unacked

    def reuploading(self) -> bool:
        return self._reuploads.reuploading()

    def num_acks(self, link_name: str) -> int:
        return self._acks.num_acks(link_name)

    def subscribed(self, link_name: str) -> bool:
        return self._mqtt_clients.subscribed(link_name)

    def mqtt_clients(self) -> MQTTClients:
        return self._mqtt_clients

    def mqtt_client_wrapper(self, client_name: str) -> MQTTClientWrapper:
        return self._mqtt_clients.client_wrapper(client_name)

    def enable_mqtt_loggers(
        self, logger: Optional[Union[logging.Logger, logging.LoggerAdapter]] = None
    ):
        return self._mqtt_clients.enable_loggers(logger)

    def disable_mqtt_loggers(self):
        return self._mqtt_clients.disable_loggers()

    def decoder(self, link_name: str) -> Optional[MQTTCodec]:
        return self._mqtt_codecs.get(link_name, None)

    def decode(self, link_name: str, topic: str, payload: bytes) -> Message[Any]:
        return self._mqtt_codecs[link_name].decode(topic, payload)

    def link(self, name) -> Optional[LinkState]:
        return self._states.link(name)

    def link_state(self, name) -> Optional[StateName]:
        return self._states.link_state(name)

    def link_names(self) -> list[str]:
        return self._states.link_names()

    def __contains__(self, name: str) -> bool:
        return name in self._states

    def __getitem__(self, name: str) -> LinkState:
        return self._states[name]

    def get_message_times(self, link_name: str) -> LinkMessageTimes:
        return self._message_times.get_copy(link_name)

    def stopped(self, name: str) -> bool:
        return self._states.stopped(name)

    def add_mqtt_link(
        self,
        name: str,
        mqtt_config: MQTTClient,
        codec: Optional[MQTTCodec] = None,
        upstream: bool = False,
        primary_peer: bool = False,
    ):
        self._mqtt_clients.add_client(
            name,
            mqtt_config,
            upstream=upstream,
            primary_peer=primary_peer,
        )
        if codec is not None:
            self._mqtt_codecs[name] = codec
        self._states.add(name)
        self._message_times.add_link(name)
        self._stats.add_link(name)

    def subscribe(self, client: str, topic: str, qos: int) -> Tuple[int, Optional[int]]:
        return self._mqtt_clients.subscribe(client, topic, qos)

    def log_subscriptions(self, tag=""):
        if self._logger.lifecycle_enabled:
            s = f"Subscriptions: [{tag}]]\n"
            for client in self._mqtt_clients.clients:
                s += f"\t{client}\n"
                for subscription in self._mqtt_clients.client_wrapper(
                    client
                ).subscription_items():
                    s += f"\t\t[{subscription}]\n"
            self._logger.lifecycle(s)

    def publish_message(
        self, client, message: Message, qos: int = 0, context: Any = None
    ) -> MQTTMessageInfo:
        topic = message.mqtt_topic()
        payload = self._mqtt_codecs[client].encode(message)
        self._logger.message_summary(
            "OUT mqtt    ",
            message.Header.Src,
            topic,
            message.Payload,
            message_id=message.Header.MessageId,
        )
        if message.Header.AckRequired:
            self._acks.start_ack_timer(
                client, message.Header.MessageId, context=context
            )
        self._message_times.update_send(client)
        return self._mqtt_clients.publish(client, topic, payload, qos)

    def publish_upstream(
        self, payload, qos: QOS = QOS.AtMostOnce, **message_args: Any
    ) -> MQTTMessageInfo:
        message = Message(Src=self.publication_name, Payload=payload, **message_args)
        return self.publish_message(
            self._mqtt_clients.upstream_client, message, qos=qos
        )

    def generate_event(self, event: EventT) -> Result[bool, BaseException]:
        if isinstance(event, CommEvent):
            self._stats.link(event.PeerName).comm_event_counts[event.TypeName] += 1
        if isinstance(event, ProblemEvent) and self._logger.path_enabled:
            self._logger.info(event)
        if not event.Src:
            event.Src = self.publication_name
        if (
            self._mqtt_clients.upstream_client
            and self._states[self._mqtt_clients.upstream_client].active_for_send()
        ):
            self.publish_upstream(event, AckRequired=True)
        return self._event_persister.persist(
            event.MessageId,
            event.json(sort_keys=True, indent=2).encode(self.PERSISTER_ENCODING),
        )

    def _start_reupload(self) -> None:
        self._logger.path("++_start_reupload reuploading: %s", self.reuploading())
        path_dbg = 0
        if not self._reuploads.reuploading():
            path_dbg |= 0x00000001
            events_to_reupload = self._reuploads.start_reupload()
            self._reupload_events(events_to_reupload)
            if self._logger.isEnabledFor(logging.INFO):
                path_dbg |= 0x00000002
                if self._reuploads.reuploading():
                    path_dbg |= 0x00000004
                    state_str = f"{self._reuploads.num_reupload_pending} reupload events pending."
                else:
                    path_dbg |= 0x00000008
                    state_str = "reupload complete."
                self._logger.info(
                    f"_start_reupload: reuploaded {len(events_to_reupload)} events. "
                    f"{state_str} "
                    f"Total pending events: {self._event_persister.num_pending}."
                )
        self._logger.path(
            "--_start_reupload reuploading: %s  path:0x%08X",
            self.reuploading(),
            path_dbg,
        )

    def _reupload_events(self, event_ids: list[str]) -> Result[bool, BaseException]:
        errors = []
        for message_id in event_ids:
            match self._event_persister.retrieve(message_id):
                case Ok(event_bytes):
                    if event_bytes is None:
                        errors.append(
                            UIDMissingWarning("reupload_events", uid=message_id)
                        )
                    else:
                        try:
                            event = json.loads(
                                event_bytes.decode(encoding=self.PERSISTER_ENCODING)
                            )
                        except BaseException as e:
                            errors.append(e)
                            errors.append(
                                JSONDecodingError("reupload_events", uid=message_id)
                            )
                        else:
                            self.publish_upstream(event, AckRequired=True)
                case Err(error):
                    errors.append(error)
        if errors:
            return Err(Problems(errors=errors))
        return Ok()

    def start(
        self, loop: asyncio.AbstractEventLoop, async_queue: asyncio.Queue
    ) -> None:
        self._mqtt_clients.start(loop, async_queue)
        self.generate_event(StartupEvent())
        self._states.start_all()

    def stop(self) -> Result[bool, Problems]:
        problems: Optional[Problems] = None
        for link_name in self._states.link_names():
            ret = self._states.stop(link_name)
            if ret.is_err():
                if problems is None:
                    problems = Problems(errors=[ret.err()])
                else:
                    problems.errors.append(ret.err())
        self._mqtt_clients.stop()
        if problems is None:
            return Ok(True)
        return Err(problems)

    def process_mqtt_connected(
        self, message: Message[MQTTConnectPayload]
    ) -> Result[Transition, InvalidCommStateInput]:
        state_result = self._states.process_mqtt_connected(message)
        if state_result.is_ok():
            self._logger.comm_event(str(state_result.value))
        self.generate_event(MQTTConnectEvent(PeerName=message.Payload.client_name))
        self._mqtt_clients.subscribe_all(message.Payload.client_name)
        return state_result

    def process_mqtt_disconnected(
        self, message: Message[MQTTDisconnectPayload]
    ) -> Result[LinkManagerTransition, InvalidCommStateInput]:
        state_result = self._states.process_mqtt_disconnected(message)
        if state_result.is_ok():
            result = Ok(LinkManagerTransition(**(asdict(state_result.value))))
            self.generate_event(
                MQTTDisconnectEvent(PeerName=message.Payload.client_name)
            )
            self._logger.comm_event(str(result.value))
            if result.value.recv_deactivated() or result.value.send_deactivated():
                result.value.canceled_acks = self._acks.cancel_ack_timers(
                    message.Payload.client_name
                )
                self._reuploads.clear()
        else:
            result = state_result
        return result

    def process_mqtt_connect_fail(
        self, message: Message[MQTTConnectFailPayload]
    ) -> Result[Transition, InvalidCommStateInput]:
        return self._states.process_mqtt_connect_fail(message)

    def process_mqtt_message(
        self, message: Message[MQTTReceiptPayload]
    ) -> Result[Transition, InvalidCommStateInput]:
        result = self._states.process_mqtt_message(message)
        if result.is_ok():
            self.update_recv_time(message.Payload.client_name)
        if result.value:
            self._logger.comm_event(str(result.value))
        if result.value.recv_activated():
            self._recv_activated(result.value)
        return result

    def process_ack_timeout(
        self, wait_info: AckWaitInfo
    ) -> Result[LinkManagerTransition, BaseException]:
        self._logger.path("++LinkManager.process_ack_timeout %s", wait_info.message_id)
        path_dbg = 0
        self._stats.link(wait_info.link_name).timeouts += 1
        state_result = self._states.process_ack_timeout(wait_info.link_name)
        if state_result.is_ok():
            result = Ok(
                LinkManagerTransition(
                    canceled_acks=[wait_info], **(asdict(state_result.value))
                )
            )
            path_dbg |= 0x00000001
            if result.value.deactivated():
                path_dbg |= 0x00000002
                self._reuploads.clear()
                self.generate_event(
                    ResponseTimeoutEvent(PeerName=result.value.link_name)
                )
                self._logger.comm_event(str(result.value))
                result.value.canceled_acks.extend(
                    self._acks.cancel_ack_timers(wait_info.link_name)
                )
        else:
            result = Err(state_result.err())
        self._logger.path("--LinkManager.process_ack_timeout path:0x%08X", path_dbg)
        return result

    def process_ack(self, link_name: str, message_id: str):
        self._logger.path("++LinkManager.process_ack  %s", message_id)
        path_dbg = 0
        wait_info = self._acks.cancel_ack_timer(link_name, message_id)
        if wait_info is not None and message_id in self._event_persister:
            path_dbg |= 0x00000001
            self._event_persister.clear(message_id)
            if self._reuploads.reuploading() and link_name == self.upstream_client:
                path_dbg |= 0x00000002
                reupload_now = self._reuploads.process_ack_for_reupload(message_id)
                if reupload_now:
                    path_dbg |= 0x00000004
                    self._reupload_events(reupload_now)
                self._logger.path(
                    "events pending: %d  reupload pending: %d",
                    self._event_persister.num_pending,
                    self._reuploads.num_reupload_pending,
                )
                if not self._reuploads.reuploading():
                    path_dbg |= 0x00000008
                    self._logger.info("reupload complete.")
        self._logger.path("--LinkManager.process_ack path:0x%08X", path_dbg)

    def send_ack(self, link_name: str, message: Message[Any]) -> None:
        if message.Header.MessageId:
            self.publish_message(
                link_name,
                Message(
                    Src=self.publication_name,
                    Payload=Ack(AckMessageID=message.Header.MessageId),
                ),
            )

    def start_ping_tasks(self) -> list[asyncio.Task]:
        return [
            asyncio.create_task(
                self.send_ping(link_name), name=f"send_ping<{link_name}>"
            )
            for link_name in self.link_names()
        ]

    async def send_ping(self, link_name: str):
        while not self._states.stopped(link_name):
            message_times = self._message_times.get_copy(link_name)
            link_state = self._states[link_name]
            if (
                message_times.time_to_send_ping(self._settings.mqtt_link_poll_seconds)
                and link_state.active_for_send()
            ):
                self.publish_message(link_name, PingMessage(Src=self.publication_name))
            await asyncio.sleep(
                message_times.seconds_until_next_ping(
                    self._settings.mqtt_link_poll_seconds
                )
            )

    def update_recv_time(self, link_name: str) -> None:
        self._message_times.update_recv(link_name)

    def _recv_activated(self, transition: Transition):
        if transition.link_name == self.upstream_client:
            self._start_reupload()
        self.generate_event(PeerActiveEvent(PeerName=transition.link_name))

    def process_mqtt_suback(
        self, message: Message[MQTTSubackPayload]
    ) -> Result[Transition, InvalidCommStateInput]:
        self._logger.path(
            "++LinkManager.process_mqtt_suback client:%s", message.Payload.client_name
        )
        path_dbg = 0
        state_result = self._states.process_mqtt_suback(
            message.Payload.client_name,
            self._mqtt_clients.handle_suback(message.Payload),
        )
        if state_result.is_ok():
            path_dbg |= 0x00000001
            if state_result.value:
                path_dbg |= 0x00000002
                self._logger.comm_event(str(state_result.value))
            if state_result.value.send_activated():
                path_dbg |= 0x00000004
                self.generate_event(
                    MQTTFullySubscribedEvent(PeerName=message.Payload.client_name)
                )
                self.publish_message(
                    message.Payload.client_name,
                    PingMessage(Src=self.publication_name),
                )
            if state_result.value.recv_activated():
                path_dbg |= 0x00000008
                self._recv_activated(state_result.value)
        self._logger.path(
            "--LinkManager.process_mqtt_suback:%d  path:0x%08X",
            state_result.is_ok(),
            path_dbg,
        )
        return state_result
