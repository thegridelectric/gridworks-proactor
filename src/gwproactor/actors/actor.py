"""Actor: A partial implementation of ActorInterface which supplies the trivial implementations.

SyncThreadActor: An actor which orchestrates starting, stopping and communicating with a passed in
SyncAsyncInteractionThread
"""

from abc import ABC
from typing import Any
from typing import Generic
from typing import Sequence
from typing import TypeVar

from gwproto import Message
from gwproto import ShNode
from result import Result

from gwproactor.proactor_interface import ActorInterface
from gwproactor.proactor_interface import Communicator
from gwproactor.proactor_interface import MonitoredName
from gwproactor.proactor_interface import ServicesInterface
from gwproactor.sync_thread import SyncAsyncInteractionThread


class Actor(ActorInterface, Communicator, ABC):

    _node: ShNode

    def __init__(self, name: str, services: ServicesInterface):
        self._node = services.hardware_layout.node(name)
        super().__init__(name, services)

    @property
    def alias(self):
        return self._name

    @property
    def node(self):
        return self._node

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
    ):
        super().__init__(name, services)
        self._sync_thread = sync_thread

    def process_message(self, message: Message) -> Result[bool, BaseException]:
        raise ValueError(
            f"Error. {self.__class__.__name__} does not process any messages. Received {message.Header}"
        )

    def send_driver_message(self, message: Any) -> None:
        self._sync_thread.put_to_sync_queue(message)

    def start(self):
        self._sync_thread.set_async_loop_and_start(
            self.services.event_loop, self.services.async_receive_queue
        )

    def stop(self):
        self._sync_thread.request_stop()

    async def join(self):
        await self._sync_thread.async_join()

    @property
    def monitored_names(self) -> Sequence[MonitoredName]:
        monitored_names = []
        if self._sync_thread.pat_timeout is not None:
            monitored_names.append(
                MonitoredName(self.name, self._sync_thread.pat_timeout)
            )
        return monitored_names
