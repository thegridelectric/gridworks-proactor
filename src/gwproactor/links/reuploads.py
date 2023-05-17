from types import NoneType

from gwproactor.logger import ProactorLogger
from gwproactor.persister import PersisterInterface


class Reuploads:
    NUM_INITIAL_EVENTS: int = 100

    _event_persister: PersisterInterface
    _reupload_pending: dict[str, NoneType]
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

    def start_reupload(self) -> list[str]:
        reupload_pending = self._event_persister.pending()
        reupload_now = reupload_pending[: self._num_initial_events]
        self._reupload_pending = dict.fromkeys(reupload_pending[len(reupload_now) :])
        return reupload_now

    def process_ack_for_reupload(self, message_id: str) -> list[str]:
        reupload_now = ""
        if message_id in self._reupload_pending:
            self._reupload_pending.pop(message_id)
            if self._reupload_pending:
                reupload_now = next(iter(self._reupload_pending))
                self._reupload_pending.pop(reupload_now)
        return [reupload_now]

    def reuploading(self) -> bool:
        return bool(self._reupload_pending)

    def clear(self) -> None:
        self._reupload_pending.clear()
