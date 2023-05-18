from gwproactor.logger import ProactorLogger
from gwproactor.persister import PersisterInterface


class Reuploads:
    NUM_INITIAL_EVENTS: int = 100

    _event_persister: PersisterInterface
    _reupload_pending: dict[str, None]
    _num_initial_events: int
    _logger: ProactorLogger

    def __init__(
        self,
        event_persister: PersisterInterface,
        logger: ProactorLogger,
        num_initial_events: int = NUM_INITIAL_EVENTS,
    ):
        self._event_persister = event_persister
        self._reupload_pending = dict()
        self._num_initial_events = num_initial_events
        self._logger = logger

    def __str__(self):
        s = f"Reuploads: {len(self._reupload_pending)}"
        for message_id in self._reupload_pending:
            s += f"\n  {message_id}"
        return s

    def start_reupload(self) -> list[str]:
        reupload_pending = self._event_persister.pending()
        self._reupload_pending = dict.fromkeys(reupload_pending)
        reupload_now = reupload_pending[: self._num_initial_events]
        return reupload_now

    def process_ack_for_reupload(self, message_id: str) -> list[str]:
        reupload_now = []
        self._logger.path(
            f"++process_ack_for_reupload  reuploading:{self.reuploading()}  num_reupload_pending: {self.num_reupload_pending}"
        )
        old_num_dbg = self.num_reupload_pending
        path_dbg = 0
        if message_id in self._reupload_pending:
            path_dbg |= 0x00000001
            self._reupload_pending.pop(message_id)
            if self._reupload_pending:
                path_dbg |= 0x00000002
                reupload_now = [next(iter(self._reupload_pending))]
        self._logger.path(
            f"--process_ack_for_reupload  path:0x{path_dbg:08X}  "
            f"reuploading:{self.reuploading()}  "
            f"num_reupload_pending: {old_num_dbg} -> {self.num_reupload_pending}  "
            f"num reupload_now: {len(reupload_now)}"
        )
        return reupload_now

    @property
    def num_reupload_pending(self) -> int:
        return len(self._reupload_pending)

    def reuploading(self) -> bool:
        return bool(self._reupload_pending)

    def clear(self) -> None:
        self._reupload_pending.clear()
