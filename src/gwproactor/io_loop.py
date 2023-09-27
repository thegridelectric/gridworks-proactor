import asyncio
import threading
from typing import Coroutine
from typing import Optional

from gwproto import Message
from result import Result

from gwproactor.message import KnownNames
from gwproactor.proactor_interface import INVALID_IO_TASK_HANDLE
from gwproactor.proactor_interface import Communicator
from gwproactor.proactor_interface import IOLoopInterface
from gwproactor.proactor_interface import ServicesInterface
from gwproactor.problems import Problems


class IOLoop(Communicator, IOLoopInterface):

    _io_loop: asyncio.AbstractEventLoop
    _io_thread: Optional[threading.Thread] = None
    _main_task: Optional[asyncio.Task] = None
    _tasks: dict[int, Optional[asyncio.Task]]
    _id2task: dict[asyncio.Task, int]
    _completed_tasks: dict[int, asyncio.Task]
    _lock: threading.RLock
    _add_no_more: bool = False
    _next_id = INVALID_IO_TASK_HANDLE + 1

    def __init__(self, services: ServicesInterface) -> None:
        super().__init__(KnownNames.io_loop_manager.value, services)
        self._lock = threading.RLock()
        self._tasks = dict()
        self._completed_tasks = dict()
        self._io_loop = asyncio.new_event_loop()

    def add_io_coroutine(self, coro: Coroutine, name: str = "") -> int:
        with self._lock:
            if self._add_no_more:
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

    async def _add_task(self, coro: Coroutine, name: str, task_id: int) -> None:
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
            self._add_no_more = True
            tasks = self._started_tasks()
        try:
            for task in tasks:
                self._io_loop.call_soon_threadsafe(task.cancel)
        finally:
            self._io_loop.stop()

    async def join(self) -> None:
        if self._main_task is not None:
            await self._main_task

    def _thread_run(self) -> None:
        try:
            self._main_task = self._io_loop.create_task(self._async_run())
            self._io_loop.run_forever()
        except BaseException as e:  # noqa
            self._services.send_threadsafe(
                Message(
                    Payload=Problems(errors=[e]).problem_event(
                        summary=f"Unexpected IOLoop exception <{e}>", src=self.name
                    )
                )
            )
        finally:
            self._io_loop.stop()

    async def _async_run(self):
        while True:
            with self._lock:
                tasks = self._started_tasks()
            done, running = await asyncio.wait(
                tasks, timeout=0.25, return_when="FIRST_COMPLETED"
            )
            with self._lock:
                for task in done:
                    task_id = self._id2task.pop(task)
                    self._completed_tasks[task_id] = self._tasks.pop(task_id)
            for task in done:
                if not task.cancelled() and (exception := task.exception()):
                    raise exception

    def process_message(self, message: Message) -> Result[bool, BaseException]:
        raise ValueError("IOLoop does not currently process any messages")

    def _send(self, message: Message) -> None:
        """Ensure this routine from base class does not make unsafe call."""
        self._services.send_threadsafe(message)
