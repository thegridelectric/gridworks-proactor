import asyncio
import threading
import time
import traceback
from typing import Coroutine
from typing import Optional
from typing import Sequence

from gwproto import Message
from result import Result

from gwproactor.actors.actor import MonitoredName
from gwproactor.message import KnownNames
from gwproactor.message import PatInternalWatchdogMessage
from gwproactor.message import ShutdownMessage
from gwproactor.proactor_interface import INVALID_IO_TASK_HANDLE
from gwproactor.proactor_interface import Communicator
from gwproactor.proactor_interface import IOLoopInterface
from gwproactor.proactor_interface import ServicesInterface
from gwproactor.problems import Problems
from gwproactor.str_tasks import str_tasks
from gwproactor.sync_thread import SyncAsyncInteractionThread
from gwproactor.sync_thread import async_polling_thread_join


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
    pat_timeout: float = SyncAsyncInteractionThread.PAT_TIMEOUT
    _last_pat_time: float = 0.0

    def __init__(self, services: ServicesInterface) -> None:
        super().__init__(KnownNames.io_loop_manager.value, services)
        self._lock = threading.RLock()
        self._tasks = dict()
        self._id2task = dict()
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
            self._add_no_more = True
            tasks = self._started_tasks()
        try:
            for task in tasks:
                self._io_loop.call_soon_threadsafe(task.cancel)
        finally:
            self._io_loop.stop()

    async def join(self):
        await async_polling_thread_join(self._io_thread)

    def _thread_run(self) -> None:
        try:
            self._main_task = self._io_loop.create_task(self._async_run())
            self._io_loop.run_forever()
        except BaseException as e:  # noqa
            try:
                summary = f"Unexpected IOLoop exception <{e}>"
            except:  # noqa
                summary = "Unexpected IOLoop exception"
            try:
                self._services.send_threadsafe(
                    Message(
                        Payload=Problems(errors=[e]).problem_event(
                            summary=summary, src=self.name
                        )
                    )
                )
            except:  # noqa
                ...
            try:
                self._services.send_threadsafe(
                    ShutdownMessage(
                        Src=self.name,
                        Reason=summary,
                    )
                )
            except:  # noqa
                ...
        finally:
            self._io_loop.stop()

    async def _async_run(self):
        try:
            dbg_wait = 0
            while True:
                # print(f"\n_async_run  ++loop {dbg_wait}")
                with self._lock:
                    tasks = self._started_tasks()
                if not tasks:
                    await asyncio.sleep(1)
                else:
                    # print(str_tasks(self._io_loop, tag="ALL"))
                    # print(f"_async_run  waiting for {len(tasks)} tasks")
                    done, running = await asyncio.wait(
                        tasks, timeout=1.0, return_when="FIRST_COMPLETED"
                    )
                    # print(f"_async_run  done:{len(done)}  running:{len(running)}")
                    with self._lock:
                        for task in done:
                            task_id = self._id2task.pop(task)
                            self._completed_tasks[task_id] = self._tasks.pop(task_id)

                    # print(str_tasks(self._io_loop, tag="DONE", tasks=done))
                    # print(str_tasks(self._io_loop, tag="PENDING", tasks=running))

                    for task in done:
                        if not task.cancelled() and (exception := task.exception()):
                            # print(f"\n\nEXCEPTION IN _async_run loop: {exception}  {type(exception)}")
                            # traceback.print_exception(exception)
                            # print("\nRE-RAISING 0\n\n")
                            raise exception

                if self.time_to_pat():
                    self.pat_watchdog()

                # print(f"_async_run  --loop {dbg_wait}\n")
                dbg_wait += 1
        except BaseException as e:
            # print(f"\n\nEXCEPTION IN _async_run: {e}  {type(e)}")
            # traceback.print_exception(e)
            # print("\nRE-RAISING 1\n\n")
            raise e

    def time_to_pat(self) -> bool:
        return time.time() >= (self._last_pat_time + (self.pat_timeout / 2))

    def pat_watchdog(self):
        self._last_pat_time = time.time()
        self._services.send_threadsafe(PatInternalWatchdogMessage(src=self.name))

    def process_message(self, message: Message) -> Result[bool, BaseException]:
        raise ValueError("IOLoop does not currently process any messages")

    def _send(self, message: Message) -> None:
        """Ensure this routine from base class does not make unsafe call."""
        self._services.send_threadsafe(message)

    @property
    def monitored_names(self) -> Sequence[MonitoredName]:
        return [MonitoredName(self.name, self.pat_timeout)]
