import abc
import dataclasses
import time
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Callable
from typing import Optional

from gwproactor.config.proactor_settings import MQTT_LINK_POLL_SECONDS


import_time = time.time()


@dataclass
class LinkMessageTimes:
    last_send: float = field(default_factory=time.time)
    last_recv: float = field(default_factory=time.time)

    def next_ping_second(self, link_poll_seconds: float) -> float:
        return self.last_send + link_poll_seconds

    def seconds_until_next_ping(self, link_poll_seconds: float) -> float:
        return self.next_ping_second(link_poll_seconds) - time.time()

    def time_to_send_ping(self, link_poll_seconds: float) -> bool:
        return time.time() > self.next_ping_second(link_poll_seconds)

    def get_str(
        self, link_poll_seconds: float = MQTT_LINK_POLL_SECONDS, relative: bool = True
    ) -> str:
        if relative:
            adjust = import_time
        else:
            adjust = 0
        return (
            f"n:{time.time() - adjust:5.2f}  lps:{link_poll_seconds:5.2f}  "
            f"ls:{self.last_send - adjust:5.2f}  lr:{self.last_recv - adjust:5.2f}  "
            f"nps:{self.next_ping_second(link_poll_seconds) - adjust:5.2f}  "
            f"snp:{self.next_ping_second(link_poll_seconds):5.2f}  "
            f"tsp:{int(self.time_to_send_ping(link_poll_seconds))}"
        )

    def __str__(self) -> str:
        return self.get_str()


class MessageTimes:
    _links: dict[str, LinkMessageTimes]

    def __init__(self):
        self._links = dict()

    def add_link(self, name: str) -> None:
        self._links[name] = LinkMessageTimes()

    def get_copy(self, link_name: str) -> LinkMessageTimes:
        return dataclasses.replace(self._links[link_name])

    def update_send(self, link_name: str, now: Optional[float] = None) -> None:
        if now is None:
            now = time.time()
        self._links[link_name].last_send = now

    def update_recv(self, link_name: str, now: Optional[float] = None) -> None:
        if now is None:
            now = time.time()
        self._links[link_name].last_recv = now

    def link_names(self) -> list[str]:
        return list(self._links.keys())


class TimerManagerInterface(abc.ABC):
    """
    Simple interface to infrastructure which can start timers, run callbacks on timer completion, and cancel timers.
    """

    @abc.abstractmethod
    def start_timer(self, delay_seconds: float, callback: Callable[[], None]) -> Any:
        """
        Start a timer. Implementation is expected to call _callback_ after approximately _delay_sceonds_.

        The execution context (e.g. the thread) of the callback must be specified by the implemntation.

        The callback must have sufficient context available to it do its work as well as to detect if it is no longer
        relevant. Note a callback might run after cancelation if the callack was already "in-flight" at time of
        cancellation and it is up to the callback to tolerate this situation.

        Args:
            delay_seconds: The approximate delay before the callback is called.
            callback: The function called after delay_seconds.

        Returns:
            A timer handle which can be passed to _cancel_timer()_ to cancel the callback.
        """

    @abc.abstractmethod
    def cancel_timer(self, timer_handle) -> None:
        """
        Cancel callback associated with _timer_handle_.

        Note that callback might still run after this call returns.

        Args:
            timer_handle: The value returned by start_timer()

        """


# class AckManager:
