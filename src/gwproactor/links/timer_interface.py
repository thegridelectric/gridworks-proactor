import abc
from abc import abstractmethod
from typing import Any, Callable


class TimerManagerInterface(abc.ABC):
    """
    Simple interface to infrastructure which can start timers, run callbacks on timer completion, and cancel timers.
    """

    @abstractmethod
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

    @abstractmethod
    def cancel_timer(self, timer_handle: Any) -> None:
        """
        Cancel callback associated with _timer_handle_.

        Note that callback might still run after this call returns.

        Args:
            timer_handle: The value returned by start_timer()

        """
