import json
from typing import Any
from typing import Optional
from typing import Sequence
from typing import Tuple

from gwproto import Message
from gwproto import MQTTCodec
from gwproto.messages import CommEvent
from gwproto.messages import EventT
from gwproto.messages import ProblemEvent
from paho.mqtt.client import MQTTMessageInfo
from result import Err
from result import Ok
from result import Result

from gwproactor.config import MQTTClient
from gwproactor.config import ProactorSettings
from gwproactor.links.acks import AckManager
from gwproactor.links.acks import AckTimerCallback
from gwproactor.links.link_state import InvalidCommStateInput
from gwproactor.links.link_state import LinkState
from gwproactor.links.link_state import LinkStates
from gwproactor.links.link_state import StateName
from gwproactor.links.link_state import Transition
from gwproactor.links.message_times import LinkMessageTimes
from gwproactor.links.message_times import MessageTimes
from gwproactor.links.timer_interface import TimerManagerInterface
from gwproactor.logger import ProactorLogger
from gwproactor.message import MQTTConnectFailPayload
from gwproactor.message import MQTTConnectPayload
from gwproactor.message import MQTTDisconnectPayload
from gwproactor.message import MQTTReceiptPayload
from gwproactor.mqtt import QOS
from gwproactor.mqtt import MQTTClients
from gwproactor.persister import JSONDecodingError
from gwproactor.persister import PersisterInterface
from gwproactor.persister import UIDMissingWarning
from gwproactor.problems import Problems
from gwproactor.stats import ProactorStats


class Links:

    PERSISTER_ENCODING = "utf-8"

    publication_name: str
    _settings: ProactorSettings
    _logger: ProactorLogger
    _stats: ProactorStats
    _event_persister: PersisterInterface
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
        self._mqtt_clients = MQTTClients()
        self._mqtt_codecs = dict()
        self._states = LinkStates()
        self._message_times = MessageTimes()
        self._acks = AckManager(timer_manager, ack_timeout_callback)

    def add_mqtt_link(
        self,
        name: str,
        mqtt_config: MQTTClient,
        codec: Optional[MQTTCodec] = None,
        upstream: bool = False,
        primary_peer: bool = False,
    ):
        self._mqtt_clients.add_client(
            name, mqtt_config, upstream=upstream, primary_peer=primary_peer
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
            "OUT mqtt    ", message.Header.Src, topic, message.Payload
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

    @property
    def upstream_client(self) -> str:
        return self._mqtt_clients.upstream_client

    @property
    def primary_peer_client(self) -> str:
        return self._mqtt_clients.primary_peer_client

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

    def upload_pending_events(self) -> Result[bool, BaseException]:
        errors = []
        for message_id in self._event_persister.pending():
            match self._event_persister.retrieve(message_id):
                case Ok(event_bytes):
                    if event_bytes is None:
                        errors.append(
                            UIDMissingWarning("_upload_pending_events", uid=message_id)
                        )
                    else:
                        try:
                            event = json.loads(
                                event_bytes.decode(encoding=self.PERSISTER_ENCODING)
                            )
                        except BaseException as e:
                            errors.append(e)
                            errors.append(
                                JSONDecodingError(
                                    "_upload_pending_events", uid=message_id
                                )
                            )
                        else:
                            self.publish_upstream(event, AckRequired=True)
                case Err(error):
                    errors.append(error)
        if errors:
            return Err(Problems(errors=errors))
        return Ok()

    def link(self, name) -> Optional[LinkState]:
        return self._states.link(name)

    def link_state(self, name) -> Optional[StateName]:
        return self._states.link_state(name)

    def start_all(self) -> Result[bool, Sequence[BaseException]]:
        return self._states.start_all()

    def start(self, name: str) -> Result[Transition, InvalidCommStateInput]:
        return self._states.start(name)

    def stop(self, name: str) -> Result[Transition, InvalidCommStateInput]:
        return self._states.stop(name)

    def process_mqtt_connected(
        self, message: Message[MQTTConnectPayload]
    ) -> Result[Transition, InvalidCommStateInput]:
        return self._states.process_mqtt_connected(message)

    def process_mqtt_disconnected(
        self, message: Message[MQTTDisconnectPayload]
    ) -> Result[Transition, InvalidCommStateInput]:
        return self._states.process_mqtt_disconnected(message)

    def process_mqtt_connect_fail(
        self, message: Message[MQTTConnectFailPayload]
    ) -> Result[Transition, InvalidCommStateInput]:
        return self._states.process_mqtt_connect_fail(message)

    def process_mqtt_suback(
        self, name: str, num_pending_subscriptions: int
    ) -> Result[Transition, InvalidCommStateInput]:
        return self._states.process_mqtt_suback(name, num_pending_subscriptions)

    def process_mqtt_message(
        self, message: Message[MQTTReceiptPayload]
    ) -> Result[Transition, InvalidCommStateInput]:
        return self._states.process_mqtt_message(message)

    def process_ack_timeout(
        self, name: str
    ) -> Result[Transition, InvalidCommStateInput]:
        return self._states.process_ack_timeout(name)

    def __contains__(self, name: str) -> bool:
        return name in self._states

    def __getitem__(self, name: str) -> LinkState:
        return self._states[name]

    def get_message_times(self, link_name: str) -> LinkMessageTimes:
        return self._message_times.get_copy(link_name)
