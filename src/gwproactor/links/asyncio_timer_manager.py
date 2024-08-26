import asyncio
import typing
from typing import Any, Callable

from gwproactor.links.timer_interface import TimerManagerInterface


class AsyncioTimerManager(TimerManagerInterface):
    def start_timer(
        self, delay_seconds: float, callback: Callable[[], None]
    ) -> asyncio.TimerHandle:
        return asyncio.get_running_loop().call_later(delay_seconds, callback)

    def cancel_timer(self, timer_handle: Any) -> None:
        typing.cast(asyncio.TimerHandle, timer_handle).cancel()
