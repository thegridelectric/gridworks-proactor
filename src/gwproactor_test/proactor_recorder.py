import dataclasses
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Callable
from typing import Optional
from typing import Tuple
from typing import Type
from typing import TypeVar
from typing import cast

from gwproto import Message
from gwproto.messages import CommEvent
from gwproto.messages import EventT
from gwproto.messages import PingMessage
from paho.mqtt.client import MQTT_ERR_SUCCESS
from paho.mqtt.client import MQTTMessageInfo

from gwproactor import Proactor
from gwproactor import ProactorSettings
from gwproactor import Runnable
from gwproactor import ServicesInterface
from gwproactor.config import LoggerLevels
from gwproactor.links import LinkManager
from gwproactor.links import MQTTClients
from gwproactor.links import MQTTClientWrapper
from gwproactor.message import DBGCommands
from gwproactor.message import DBGPayload
from gwproactor.message import MQTTReceiptPayload
from gwproactor.message import MQTTSubackPayload
from gwproactor.stats import LinkStats
from gwproactor.stats import ProactorStats


def split_subscriptions(client_wrapper: MQTTClientWrapper) -> Tuple[int, Optional[int]]:
    for i, (topic, qos) in enumerate(client_wrapper.subscription_items()):
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
    def make_stats(cls) -> RecorderStats:
        ...

    @abstractmethod
    def split_client_subacks(self, client_name: str):
        ...

    @abstractmethod
    def restore_client_subacks(self, client_name: str):
        ...

    @abstractmethod
    def pause_subacks(self):
        ...

    @abstractmethod
    def release_subacks(self, num_released: int = -1):
        ...

    @abstractmethod
    def ping_peer(self):
        ...

    @abstractmethod
    def summary_str(self):
        ...

    @abstractmethod
    def summarize(self):
        ...

    @property
    @abstractmethod
    def mqtt_clients(self) -> MQTTClients:
        ...

    @abstractmethod
    def mqtt_client_wrapper(self, client_name: str) -> MQTTClientWrapper:
        ...

    @abstractmethod
    def mqtt_subscriptions(self, client_name: str) -> list[str]:
        ...


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
    def __init__(self, other: LinkManager):
        self.__dict__ = other.__dict__
        self.acks_paused = False
        self.needs_ack = []

    def publish_message(
        self, client, message: Message, qos: int = 0, context: Any = None
    ) -> MQTTMessageInfo:
        if self.acks_paused:
            self.needs_ack.append(_PausedAck(client, message, qos, context))
            return MQTTMessageInfo(-1)
        else:
            # noinspection PyProtectedMember
            return super().publish_message(client, message, qos=qos, context=context)

    def release_acks(self, clear: bool = False):
        self.acks_paused = False
        needs_ack = self.needs_ack
        self.needs_ack = []
        if not clear:
            for paused_ack in needs_ack:
                self.publish_message(**dataclasses.asdict(paused_ack))

    def generate_event(self, event: EventT) -> None:
        if isinstance(event, CommEvent):
            cast(
                RecorderLinkStats, self._stats.link(event.PeerName)
            ).comm_events.append(event)
        super().generate_event(event)


def make_recorder_class(
    proactor_type: Type[ProactorT],
) -> Callable[..., RecorderInterface]:
    class Recorder(proactor_type):

        subacks_paused: bool
        pending_subacks: list[Message]
        mqtt_messages_dropped: bool

        def __init__(self, name: str, settings: ProactorSettings, **kwargs_):
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

        def split_client_subacks(self: ProactorT, client_name: str):
            client_wrapper = self.mqtt_client_wrapper(client_name)

            def member_split_subscriptions():
                return split_subscriptions(client_wrapper)

            client_wrapper.subscribe_all = member_split_subscriptions

        def restore_client_subacks(self: ProactorT, client_name: str):
            client_wrapper = self.mqtt_client_wrapper(client_name)
            client_wrapper.subscribe_all = MQTTClientWrapper.subscribe_all

        def pause_subacks(self):
            self.subacks_paused = True

        def release_subacks(self: ProactorT, num_released: int = -1):
            self.subacks_paused = False
            if num_released < 0:
                num_released = len(self.pending_subacks)
            release = self.pending_subacks[:num_released]
            self.pending_subacks = self.pending_subacks[num_released:]
            for message in release:
                self._receive_queue.put_nowait(message)

        async def process_message(self, message: Message):
            if self.subacks_paused and isinstance(message.Payload, MQTTSubackPayload):
                self.pending_subacks.append(message)
            else:
                await super().process_message(message)

        def pause_acks(self):
            self._links.acks_paused = True

        def release_acks(self, clear: bool = False):
            self._links.release_acks(clear)

        def set_ack_timeout_seconds(self, delay: float) -> None:
            self._links._acks._default_delay_seconds = delay  # noqa

        def drop_mqtt(self, drop: bool):
            self.mqtt_messages_dropped = drop

        def _process_mqtt_message(self, message: Message[MQTTReceiptPayload]):
            if not self.mqtt_messages_dropped:
                # noinspection PyProtectedMember
                super()._process_mqtt_message(message)

        def summary_str(self: ProactorT):
            s = str(self.stats)
            s += f"\nsubacks_paused: {self.subacks_paused}  pending_subacks: {len(self.pending_subacks)}\n"
            s += "Link states:\n"
            for link_name in self.stats.links:
                s += f"  {link_name:10s}  {self._links.link_state(link_name).value}\n"
            return s

        def summarize(self: ProactorT):
            self._logger.info(self.summary_str())

        def ping_peer(self):
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
        ):
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

        def _derived_process_message(self, message: Message):
            match message.Payload:
                case DBGPayload():
                    message.Header.Src = self.publication_name
                    message.Header.Dst = self.primary_peer_client
                    self._links.publish_message(self.primary_peer_client, message)
                case _:
                    # noinspection PyProtectedMember
                    super()._derived_process_message(message)

    return Recorder
