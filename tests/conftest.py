"""Local pytest configuration"""

import pytest

from gwproactor_test import restore_loggers  # noqa
from gwproactor_test import default_test_env  # noqa
from gwproactor_test import clean_test_env  # noqa


@pytest.fixture(autouse=True)
def always_restore_loggers(restore_loggers):
    ...
