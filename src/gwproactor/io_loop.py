import asyncio
import contextlib
import threading
import time
from typing import Coroutine, Optional, Sequence

from gwproto import Message
from result import Result

from gwproactor import ProactorLogger
from gwproactor.actors.actor import MonitoredName
from gwproactor.message import KnownNames, PatInternalWatchdogMessage, ShutdownMessage
from gwproactor.proactor_interface import (
    INVALID_IO_TASK_HANDLE,
    Communicator,
    IOLoopInterface,
    ServicesInterface,
)
from gwproactor.problems import Problems
from gwproactor.sync_thread import SyncAsyncInteractionThread


class IOLoop(Communicator, IOLoopInterface):
    _io_loop: asyncio.AbstractEventLoop
    _io_thread: Optional[threading.Thread] = None
    _tasks: dict[int, Optional[asyncio.Task]]
    _id2task: dict[asyncio.Task, int]
    _completed_tasks: dict[int, asyncio.Task]
    _lock: threading.RLock
    _stop_requested: bool = False
    _next_id = INVALID_IO_TASK_HANDLE + 1
    _pat_timeout: float = SyncAsyncInteractionThread.PAT_TIMEOUT
    _last_pat_time: float = 0.0
    _lg: ProactorLogger

    def __init__(self, services: ServicesInterface) -> None:
        super().__init__(KnownNames.io_loop_manager.value, services)
        self._lg = services.logger
        self._lock = threading.RLock()
        self._tasks = {}
        self._id2task = {}
        self._completed_tasks = {}
        self._io_loop = asyncio.new_event_loop()

    def add_io_coroutine(self, coro: Coroutine, name: str = "") -> int:
        with self._lock:
            if self._stop_requested:
                return INVALID_IO_TASK_HANDLE
            task_id = self._next_id
            self._next_id += 1
            self._tasks[task_id] = None
        self._io_loop.call_soon_threadsafe(self._add_task, coro, name, task_id)
        return task_id

    def cancel_io_routine(self, handle: int) -> None:
        with self._lock:
            task = self._tasks.pop(handle, None)
        if task is not None:
            self._io_loop.call_soon_threadsafe(task.cancel)

    def _add_task(self, coro: Coroutine, name: str, task_id: int) -> None:
        if not name:
            name = coro.__name__
        task = self._io_loop.create_task(
            coro,
            name=name,
        )
        with self._lock:
            self._tasks[task_id] = task
            self._id2task[task] = task_id

    def start(self) -> None:
        self._io_thread = threading.Thread(
            name=self.name, target=self._thread_run, daemon=True
        )
        self._io_thread.start()

    def _started_tasks(self) -> list[asyncio.Task]:
        with self._lock:
            return [task for task in self._tasks.values() if task is not None]

    def stop(self) -> None:
        with self._lock:
            self._stop_requested = True
            tasks = self._started_tasks()
        for task in tasks:
            self._io_loop.call_soon_threadsafe(task.cancel)

    async def join(self) -> None:
        pass
        # this often generates errors, although tests pass:
        # await async_polling_thread_join(self._io_thread)  # noqa: ERA001

    def _thread_run(self) -> None:
        try:
            self._io_loop.run_until_complete(self._async_run())
        except Exception as e:  # noqa: BLE001
            try:
                summary = f"Unexpected IOLoop exception <{e}>"
            except:  # noqa: E722
                summary = "Unexpected IOLoop exception"
            with contextlib.suppress(Exception):
                self._services.send_threadsafe(
                    Message(
                        Payload=Problems(errors=[e]).problem_event(
                            summary=summary, src=self.name
                        )
                    )
                )
            with contextlib.suppress(Exception):
                self._services.send_threadsafe(
                    ShutdownMessage(
                        Src=self.name,
                        Reason=summary,
                    )
                )
        finally:
            self._io_loop.stop()

    async def _async_run(self) -> None:  # noqa: PLR0912
        try:  # noqa: PLR1702
            while not self._stop_requested:
                with self._lock:
                    tasks = self._started_tasks()
                if not self._stop_requested and not tasks:
                    try:
                        await asyncio.sleep(1)
                    except asyncio.CancelledError:
                        pass
                    except GeneratorExit:
                        pass
                else:
                    done, running = await asyncio.wait(
                        tasks, timeout=1.0, return_when="FIRST_COMPLETED"
                    )
                    if self._stop_requested:
                        break
                    with self._lock:
                        for task in done:
                            task_id = self._id2task.pop(task)
                            self._completed_tasks[task_id] = self._tasks.pop(task_id)
                    errors = []
                    for task in done:
                        if not task.cancelled():
                            try:
                                exception = task.exception()
                                if exception is not None:
                                    errors.append(exception)
                            except Exception as retrieve_exception:  # noqa: BLE001
                                errors.append(retrieve_exception)
                    if errors:
                        raise Problems(
                            f"IOLoop caught {len(errors)}.",
                            errors=errors,
                        )
                if self.time_to_pat():
                    self.pat_watchdog()
        finally:
            self._io_loop.stop()

    def time_to_pat(self) -> bool:
        return time.time() >= (self._last_pat_time + (self._pat_timeout / 2))

    def pat_watchdog(self) -> None:
        if not self._stop_requested:
            self._last_pat_time = time.time()
            self._services.send_threadsafe(PatInternalWatchdogMessage(src=self.name))

    def process_message(self, message: Message) -> Result[bool, Exception]:
        raise ValueError("IOLoop does not currently process any messages")

    def _send(self, message: Message) -> None:
        """Ensure this routine from base class does not make unsafe call."""
        self._services.send_threadsafe(message)

    @property
    def monitored_names(self) -> Sequence[MonitoredName]:
        return [MonitoredName(self.name, self._pat_timeout)]
