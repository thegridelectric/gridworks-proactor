"""Local pytest configuration"""
from pathlib import Path

import pytest

from gwproactor_test import clean_test_env  # noqa
from gwproactor_test import default_test_env  # noqa
from gwproactor_test import restore_loggers  # noqa
from gwproactor_test.certs import set_test_certificate_cache_dir


set_test_certificate_cache_dir(Path(__file__).parent / ".certificate_cache")


@pytest.fixture(autouse=True)
def always_restore_loggers(restore_loggers) -> None:
    ...
