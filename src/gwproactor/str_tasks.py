import asyncio
import traceback
from typing import Awaitable
from typing import Iterable
from typing import Optional


def str_tasks(
    loop_: asyncio.AbstractEventLoop,
    tag: str = "",
    tasks: Optional[Iterable[Awaitable]] = None,
) -> str:
    s = ""
    try:
        if tasks is None:
            tasks = asyncio.all_tasks(loop_)
        s += f"Tasks: {len(tasks)}  [{tag}]\n"

        def _get_task_exception(task_):
            try:
                exception_ = task_.exception()
            except asyncio.CancelledError as _e:
                exception_ = _e
            except asyncio.InvalidStateError:
                exception_ = None
            return exception_

        for i, task in enumerate(tasks):
            s += (
                f"\t{i + 1}/{len(tasks)}  "
                f"{task.get_name():20s}  "
                f"done:{task.done()}   "
                f"exception:{_get_task_exception(task)}  "
                f"{task.get_coro()}\n"
            )
    except BaseException as e:
        # noinspection PyBroadException
        try:
            s += f"ERROR in str_tasks:\n"
            s += "".join(traceback.format_exception(e))
            s += "\n"
        except:
            pass
    return s
