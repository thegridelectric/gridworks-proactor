import argparse
import logging
import warnings
from typing import Any

from gwproactor import ProactorLogger, ProactorSettings, setup_logging
from gwproactor.config import Paths
from gwproactor_test import LoggerGuards


def test_proactor_logger(caplog: Any) -> None:
    paths = Paths()
    paths.mkdirs()
    settings = ProactorSettings()
    with LoggerGuards():
        errors = []
        setup_logging(argparse.Namespace(), settings, errors=errors)
        assert len(errors) == 0
        logger = ProactorLogger(**settings.logging.qualified_logger_names())
        assert not logger.isEnabledFor(logging.INFO)
        assert not logger.message_summary_enabled
        assert logger.message_summary_logger.level == logging.WARNING
        assert not logger.path_enabled
        logger.message_summary(direction="", src="", dst="", topic="")
        assert len(caplog.records) == 0
        logger.path("foo")
        assert len(caplog.records) == 0
        assert logger.lifecycle_enabled
        assert logger.comm_event_enabled

    errors = []
    setup_logging(
        argparse.Namespace(verbose=True),
        settings,
        errors=errors,
        add_screen_handler=False,
    )
    assert len(errors) == 0
    logger = ProactorLogger(**settings.logging.qualified_logger_names())
    assert logger.isEnabledFor(logging.INFO)
    assert logger.message_summary_enabled
    assert logger.message_summary_logger.level == logging.DEBUG
    assert logger.path_enabled
    assert logger.lifecycle_enabled
    assert logger.comm_event_enabled
    logger.info("info")
    if len(caplog.records) != 1:
        warnings.warn(
            f"len(caplog.records) ({len(caplog.records)}) != 1  (#1)",
            stacklevel=2,
        )
    caplog.clear()
    for function_name in ["path", "lifecycle", "comm_event"]:
        getattr(logger, function_name)(function_name)
        if len(caplog.records) != 1:
            warnings.warn(
                f"len(caplog.records) ({len(caplog.records)}) != 1  (#2)",
                stacklevel=2,
            )
        caplog.clear()
    logger.message_summary(
        direction="IN",
        src="x",
        dst="y",
        topic="z",
    )
    if len(caplog.records) != 1:
        warnings.warn(
            f"len(caplog.records) ({len(caplog.records)}) != 1  (#3)",
            stacklevel=2,
        )
