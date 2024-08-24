# ruff: noqa: ERA001
import dataclasses
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, cast

from gwproto import Message
from gwproto.messages import CommEvent, EventT, PingMessage
from paho.mqtt.client import MQTT_ERR_SUCCESS, MQTTMessageInfo

from gwproactor import Proactor, ProactorSettings, Runnable, ServicesInterface
from gwproactor.config import LoggerLevels
from gwproactor.links import LinkManager, MQTTClients, MQTTClientWrapper
from gwproactor.message import (
    DBGCommands,
    DBGPayload,
    MQTTReceiptPayload,
    MQTTSubackPayload,
)
from gwproactor.stats import LinkStats, ProactorStats


def split_subscriptions(client_wrapper: MQTTClientWrapper) -> Tuple[int, Optional[int]]:
    for topic, qos in client_wrapper.subscription_items():
        MQTTClientWrapper.subscribe(client_wrapper, topic, qos)
    return MQTT_ERR_SUCCESS, None


@dataclass
class RecorderLinkStats(LinkStats):
    comm_events: list[CommEvent] = field(default_factory=list)

    def __str__(self) -> str:
        s = super().__str__()
        if self.comm_events:
            s += "\n  Comm events:"
            for comm_event in self.comm_events:
                s += f"\n    {comm_event}"
        return s


class RecorderStats(ProactorStats):
    @classmethod
    def make_link(cls, link_name: str) -> RecorderLinkStats:
        return RecorderLinkStats(link_name)


ProactorT = TypeVar("ProactorT", bound=Proactor)


class RecorderInterface(ServicesInterface, Runnable):
    @classmethod
    @abstractmethod
    def make_stats(cls) -> RecorderStats: ...

    @abstractmethod
    def split_client_subacks(self, client_name: str) -> None: ...

    @abstractmethod
    def restore_client_subacks(self, client_name: str) -> None: ...

    @abstractmethod
    def pause_subacks(self) -> None: ...

    @abstractmethod
    def release_subacks(self, num_released: int = -1) -> None: ...

    @abstractmethod
    def ping_peer(self) -> None: ...

    @abstractmethod
    def summary_str(self) -> None: ...

    @abstractmethod
    def summarize(self) -> None: ...

    @property
    @abstractmethod
    def mqtt_clients(self) -> MQTTClients: ...

    @abstractmethod
    def mqtt_client_wrapper(self, client_name: str) -> MQTTClientWrapper: ...

    @abstractmethod
    def mqtt_subscriptions(self, client_name: str) -> list[str]: ...

    @abstractmethod
    def disable_derived_events(self) -> None: ...

    @abstractmethod
    def enable_derived_events(self) -> None: ...

    @abstractmethod
    def mqtt_quiescent(self) -> bool: ...


@dataclass
class _PausedAck:
    client: str
    message: Message
    qos: int
    context: Optional[Any]


class RecorderLinks(LinkManager):
    acks_paused: bool
    needs_ack: list[_PausedAck]

    # noinspection PyMissingConstructor
    def __init__(self, other: LinkManager) -> None:
        self.__dict__ = other.__dict__
        self.acks_paused = False
        self.needs_ack = []

    def publish_message(
        self, client: str, message: Message, qos: int = 0, context: Any = None
    ) -> MQTTMessageInfo:
        if self.acks_paused:
            self.needs_ack.append(_PausedAck(client, message, qos, context))
            return MQTTMessageInfo(-1)
        # noinspection PyProtectedMember
        return super().publish_message(client, message, qos=qos, context=context)

    def release_acks(self, clear: bool = False, num_to_release: int = -1) -> int:
        # self._logger.info(
        #     f"++release_acks: clear:{clear}  num_to_release:{num_to_release}"
        # )
        # path_dbg = 0
        if clear or num_to_release < 1:
            # path_dbg |= 0x00000001
            self.acks_paused = False
            needs_ack = self.needs_ack
            self.needs_ack = []
        else:
            # path_dbg |= 0x00000002
            num_to_release = min(num_to_release, len(self.needs_ack))
            needs_ack = self.needs_ack[:num_to_release]
            self.needs_ack = self.needs_ack[num_to_release:]
            # self._logger.info(f"needs_ack: {needs_ack}")
            # self._logger.info(f"self.needs_ack: {self.needs_ack}")
        if not clear:
            # path_dbg |= 0x00000004
            for paused_ack in needs_ack:
                # path_dbg |= 0x00000008
                super().publish_message(**dataclasses.asdict(paused_ack))
        # self._logger.info(
        #     f"--release_acks: clear:{clear}  num_to_release:{num_to_release}  path:0x{path_dbg:08X}"
        # )
        return len(needs_ack)

    def generate_event(self, event: EventT) -> None:
        if isinstance(event, CommEvent):
            cast(
                RecorderLinkStats, self._stats.link(event.PeerName)
            ).comm_events.append(event)
        super().generate_event(event)


def make_recorder_class(  # noqa: C901
    proactor_type: Type[ProactorT],
) -> Callable[..., RecorderInterface]:
    class Recorder(proactor_type):
        subacks_paused: bool
        pending_subacks: list[Message]
        mqtt_messages_dropped: bool

        def __init__(
            self, name: str, settings: ProactorSettings, **kwargs_: Any
        ) -> None:
            super().__init__(name=name, settings=settings, **kwargs_)
            self.subacks_paused = False
            self.pending_subacks = []
            self.mqtt_messages_dropped = False
            self._links = RecorderLinks(self._links)

        @classmethod
        def make_stats(cls) -> RecorderStats:
            return RecorderStats()

        @property
        def needs_ack(self) -> list[_PausedAck]:
            return self._links.needs_ack

        def split_client_subacks(self: ProactorT, client_name: str) -> None:
            client_wrapper = self.mqtt_client_wrapper(client_name)

            def member_split_subscriptions() -> Tuple[int, Optional[int]]:
                return split_subscriptions(client_wrapper)

            client_wrapper.subscribe_all = member_split_subscriptions

        def restore_client_subacks(self: ProactorT, client_name: str) -> None:
            client_wrapper = self.mqtt_client_wrapper(client_name)
            client_wrapper.subscribe_all = MQTTClientWrapper.subscribe_all

        def pause_subacks(self) -> None:
            self.subacks_paused = True

        def release_subacks(self: ProactorT, num_released: int = -1) -> None:
            self.subacks_paused = False
            if num_released < 0:
                num_released = len(self.pending_subacks)
            release = self.pending_subacks[:num_released]
            self.pending_subacks = self.pending_subacks[num_released:]
            for message in release:
                self._receive_queue.put_nowait(message)

        async def process_message(self, message: Message) -> None:
            if self.subacks_paused and isinstance(message.Payload, MQTTSubackPayload):
                self.pending_subacks.append(message)
            else:
                await super().process_message(message)

        def pause_acks(self) -> None:
            self._links.acks_paused = True

        def release_acks(self, clear: bool = False, num_to_release: int = -1) -> int:
            return self._links.release_acks(clear, num_to_release=num_to_release)

        def set_ack_timeout_seconds(self, delay: float) -> None:
            self.links.ack_manager._default_delay_seconds = delay  # noqa: SLF001

        def drop_mqtt(self, drop: bool) -> None:
            self.mqtt_messages_dropped = drop

        def _process_mqtt_message(self, message: Message[MQTTReceiptPayload]) -> None:
            if not self.mqtt_messages_dropped:
                # noinspection PyProtectedMember
                super()._process_mqtt_message(message)

        def summary_str(self: ProactorT) -> str:
            s = str(self.stats)
            s += "\nLink states:\n"
            for link_name in self.stats.links:
                s += f"  {link_name:10s}  {self._links.link_state(link_name).value}\n"
            s += "Pending acks:\n"
            for link_name in self.stats.links:
                s += f"  {link_name:10s}  {self._links.num_acks(link_name):3d}\n"
            s += self._links.get_reuploads_str() + "\n"
            s += f"subacks_paused: {self.subacks_paused}  pending_subacks: {len(self.pending_subacks)}\n"
            return s

        def summarize(self: ProactorT) -> None:
            self._logger.info(self.summary_str())

        def ping_peer(self) -> None:
            self._links.publish_message(
                self.primary_peer_client, PingMessage(Src=self.publication_name)
            )

        @property
        def mqtt_clients(self) -> MQTTClients:
            return self._links.mqtt_clients()

        def mqtt_client_wrapper(self, client_name: str) -> MQTTClientWrapper:
            return self._links.mqtt_client_wrapper(client_name)

        def mqtt_subscriptions(self, client_name: str) -> list[str]:
            return [
                item[0]
                for item in self.mqtt_client_wrapper(client_name).subscription_items()
            ]

        def send_dbg_to_peer(
            self,
            message_summary: int = -1,
            lifecycle: int = -1,
            comm_event: int = -1,
            command: Optional[DBGCommands | str] = None,
        ) -> None:
            if isinstance(command, str):
                command = DBGCommands(command)
            self.send_threadsafe(
                Message(
                    Src=self.name,
                    Dst=self.name,
                    Payload=DBGPayload(
                        Levels=LoggerLevels(
                            message_summary=message_summary,
                            lifecycle=lifecycle,
                            comm_event=comm_event,
                        ),
                        Command=command,
                    ),
                )
            )

        def _derived_process_message(self, message: Message) -> None:
            match message.Payload:
                case DBGPayload():
                    message.Header.Src = self.publication_name
                    message.Header.Dst = self.primary_peer_client
                    self._links.publish_message(self.primary_peer_client, message)
                case _:
                    # noinspection PyProtectedMember
                    super()._derived_process_message(message)

        def mqtt_quiescent(self) -> bool:
            if hasattr(super(), "mqtt_quiescent"):
                return super().mqtt_quiescent()
            return self._links.link(self.upstream_client).active_for_send()

        def _call_super_if_present(self, function_name: str) -> None:
            if hasattr(super(), function_name):
                getattr(super(), function_name)()

        def disable_derived_events(self) -> None:
            self._call_super_if_present("disable_dervived_events")

        def enable_derived_events(self) -> None:
            self._call_super_if_present("enable_dervived_events")

    return Recorder
