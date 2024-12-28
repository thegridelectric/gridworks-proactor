import contextlib
import datetime
import logging
from typing import Any, Optional


class MessageSummary:
    """Helper class for formating message summaries message receipt/publication single line summaries."""

    DEFAULT_FORMAT = (
        "  {direction:15s}  {src_dst:50s}  {broker_flag}  {arrow:2s}  {topic:80s}"
        "  {payload_type:25s}{message_id}"
    )

    @classmethod
    def format(  # noqa: PLR0913
        cls,
        direction: str,
        src: str,
        dst: str,
        topic: str,
        *,
        payload_object: Any = None,
        broker_flag: str = " ",
        timestamp: Optional[datetime.datetime] = None,
        include_timestamp: bool = False,
        message_id: str = "",
    ) -> str:
        """
        Formats a single line summary of message receipt/publication.

        Args:
            direction: "IN" or "OUT"
            src: The node name of the sending or receiving actor.
            dst: The node name of the inteded recipient
            topic: The destination or source topic.
            payload_object: The payload of the message.
            broker_flag: "*" for the "gw" broker.
            timestamp: datetime.dateime.now(tz=datetime.timezone.utc) by default.
            include_timestamp: whether timestamp is prepended to output.
            message_id: The message id. Ignored if empty.

        Returns:
            Formatted string.
        """
        with contextlib.suppress(Exception):
            if timestamp is None:
                timestamp = datetime.datetime.now(tz=datetime.timezone.utc)
            if include_timestamp:
                format_ = "{timestamp}  " + cls.DEFAULT_FORMAT
            else:
                format_ = cls.DEFAULT_FORMAT
            direction = direction.strip()
            if direction.startswith(("OUT", "SND")):
                arrow = "->"
            elif direction.startswith(("IN", "RCV")):  # noqa: PIE810
                arrow = "<-"
            else:
                arrow = "? "
            if hasattr(payload_object, "payload"):
                payload_object = payload_object.payload
            if hasattr(payload_object, "__class__"):
                payload_str = payload_object.__class__.__name__
            else:
                payload_str = type(payload_object)
            max_msg_id_len = 11
            if message_id and len(message_id) > max_msg_id_len:
                message_id = f" {message_id[:max_msg_id_len-3]}..."
            src_dst = f"{src} to {dst}"
            return format_.format(
                timestamp=timestamp.isoformat(),
                direction=direction,
                src_dst=src_dst,
                broker_flag=broker_flag,
                arrow=arrow,
                topic=f"[{topic}]",
                payload_type=payload_str,
                message_id=message_id,
            )
        return ""


class ProactorLogger(logging.LoggerAdapter):
    MESSAGE_DELIMITER_WIDTH = 88
    MESSAGE_ENTRY_DELIMITER = "+" * MESSAGE_DELIMITER_WIDTH
    MESSAGE_EXIT_DELIMITER = "-" * MESSAGE_DELIMITER_WIDTH

    message_summary_logger: logging.Logger
    lifecycle_logger: logging.Logger
    comm_event_logger: logging.Logger

    def __init__(
        self,
        base: str,
        message_summary: str,
        lifecycle: str,
        comm_event: str,
        extra: Optional[dict] = None,
    ) -> None:
        super().__init__(logging.getLogger(base), extra=extra)
        self.message_summary_logger = logging.getLogger(message_summary)
        self.lifecycle_logger = logging.getLogger(lifecycle)
        self.comm_event_logger = logging.getLogger(comm_event)

    @property
    def general_enabled(self) -> bool:
        return self.logger.isEnabledFor(logging.INFO)

    @property
    def message_summary_enabled(self) -> bool:
        return self.message_summary_logger.isEnabledFor(logging.INFO)

    @property
    def path_enabled(self) -> bool:
        return self.message_summary_logger.isEnabledFor(logging.DEBUG)

    @property
    def lifecycle_enabled(self) -> bool:
        return self.lifecycle_logger.isEnabledFor(logging.INFO)

    @property
    def comm_event_enabled(self) -> bool:
        return self.comm_event_logger.isEnabledFor(logging.INFO)

    def message_summary(  # noqa: PLR0913
        self,
        *,
        direction: str,
        src: str,
        dst: str,
        topic: str,
        payload_object: Any = None,
        broker_flag: str = " ",
        timestamp: Optional[datetime.datetime] = None,
        message_id: str = "",
    ) -> None:
        if self.message_summary_logger.isEnabledFor(logging.INFO):
            self.message_summary_logger.info(
                MessageSummary.format(
                    direction=direction,
                    src=src,
                    dst=dst,
                    topic=topic,
                    payload_object=payload_object,
                    broker_flag=broker_flag,
                    timestamp=timestamp,
                    message_id=message_id,
                )
            )

    def path(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.message_summary_logger.debug(msg, *args, **kwargs)

    def lifecycle(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.lifecycle_logger.info(msg, *args, **kwargs)

    def comm_event(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.comm_event_logger.info(msg, *args, **kwargs)

    def message_enter(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.path_enabled:
            self.path("")
            self.path(self.MESSAGE_ENTRY_DELIMITER)
            self.path(msg, *args, **kwargs)

    def message_exit(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self.path_enabled:
            self.path(msg, *args, **kwargs)
            self.path(self.MESSAGE_EXIT_DELIMITER)

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"{self.logger.name}, "
            f"{self.message_summary_logger.name}, "
            f"{self.lifecycle_logger.name}, "
            f"{self.comm_event_logger.name}>"
        )
