"""Actor: A partial implementation of ActorInterface which supplies the trivial implementations.

SyncThreadActor: An actor which orchestrates starting, stopping and communicating with a passed in
SyncAsyncInteractionThread
"""

from abc import ABC
from typing import Any, cast, Generic, Sequence, TypeVar
from gwproto.data_classes.house_0_names import H0N
from gwproto.data_classes.house_0_layout import House0Layout
from gwproto import Message, ShNode
from result import Result

from gwproactor.proactor_interface import (
    ActorInterface,
    Communicator,
    MonitoredName,
    ServicesInterface,
)
from gwproactor.sync_thread import SyncAsyncInteractionThread


class Actor(ActorInterface, Communicator, ABC):
    _node: ShNode

    def __init__(self, name: str, services: ServicesInterface) -> None:
        self._node = services.hardware_layout.node(name)
        self.layout = cast(House0Layout, services.hardware_layout)
        super().__init__(name, services)

    @property
    def name(self) -> str:
        return self._name

    @property
    def node(self) -> ShNode:
        return self._node
    
    def boss(self) -> ShNode:
        if ".".join(self.node.handle.split(".")[:-1]) == "":
            return self.node

        boss_handle = ".".join(self.node.handle.split(".")[:-1])
        return next(
            n for n in self.layout.nodes.values()
            if n.handle == boss_handle
        )

    def is_boss_of(self, node: ShNode) -> bool:
        immediate_boss = ".".join(node.Handle.split(".")[:-1])
        return immediate_boss == self.node.handle
    
    def direct_reports(self) -> list[ShNode]:
        return [n for n in self.layout.nodes.values() if self.is_boss_of(n)]

    def _send_to(self, dst: ShNode, payload) -> None:
        if dst is None:
            return
        message = Message(Src=self.name, Dst=dst.name, Payload=payload)
        if dst.name in set(self.services._communicators.keys()) | {self.services.name}:
            self.services.send(message)
        elif dst.Name == H0N.admin:
            self.services._links.publish_message(self.services.ADMIN_MQTT, message)
        elif dst.Name == H0N.atn:
            self.services._links.publish_upstream(payload)
        else:
            self.services._links.publish_message(self.services.LOCAL_MQTT, message)

    def init(self) -> None:
        """Called after constructor so derived functions can be used in setup."""


SyncThreadT = TypeVar("SyncThreadT", bound=SyncAsyncInteractionThread)


class SyncThreadActor(Actor, Generic[SyncThreadT]):
    _sync_thread: SyncAsyncInteractionThread

    def __init__(
        self,
        name: str,
        services: ServicesInterface,
        sync_thread: SyncAsyncInteractionThread,
    ) -> None:
        super().__init__(name, services)
        self._sync_thread = sync_thread

    def process_message(self, message: Message) -> Result[bool, Exception]:
        raise ValueError(
            f"Error. {self.__class__.__name__} does not process any messages. Received {message.Header}"
        )

    def send_driver_message(self, message: Any) -> None:
        self._sync_thread.put_to_sync_queue(message)

    def start(self) -> None:
        self._sync_thread.set_async_loop_and_start(
            self.services.event_loop, self.services.async_receive_queue
        )

    def stop(self) -> None:
        self._sync_thread.request_stop()

    async def join(self) -> None:
        await self._sync_thread.async_join()

    @property
    def monitored_names(self) -> Sequence[MonitoredName]:
        monitored_names = []
        if self._sync_thread.pat_timeout is not None:
            monitored_names.append(
                MonitoredName(self.name, self._sync_thread.pat_timeout)
            )
        return monitored_names
