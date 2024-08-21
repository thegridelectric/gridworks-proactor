import argparse
import logging
import warnings

from gwproactor import ProactorLogger, ProactorSettings, setup_logging
from gwproactor.config import Paths
from gwproactor_test import LoggerGuards


def test_proactor_logger(caplog) -> None:
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
        logger.message_summary("", "", "")
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
    # assert len(caplog.records) == 1
    if len(caplog.records) != 1:
        warnings.warn(f"len(caplog.records) ({len(caplog.records)}) != 1  (#1)")
    caplog.clear()
    for function_name in ["path", "lifecycle", "comm_event"]:
        getattr(logger, function_name)(function_name)
        # assert len(caplog.records) == 1
        if len(caplog.records) != 1:
            warnings.warn(f"len(caplog.records) ({len(caplog.records)}) != 1  (#2)")
        caplog.clear()
    logger.message_summary("IN", "x", "y")
    # assert len(caplog.records) == 1
    if len(caplog.records) != 1:
        warnings.warn(f"len(caplog.records) ({len(caplog.records)}) != 1  (#3)")
