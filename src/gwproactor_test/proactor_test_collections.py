# ruff: noqa: PLR2004, ERA001

from typing import Type

import pytest

from gwproactor_test.comm_test_helper import CommTestHelper
from gwproactor_test.proactor_awaiting_setup_tests import ProactorCommAwaitingSetupTests
from gwproactor_test.proactor_basic_tests import ProactorCommBasicTests
from gwproactor_test.proactor_reupload_tests import ProactorReuploadTests
from gwproactor_test.proactor_timeout_tests import ProactorCommTimeoutTests


@pytest.mark.asyncio
class ProactorCommTests(
    ProactorCommBasicTests,
    ProactorCommAwaitingSetupTests,
    ProactorCommTimeoutTests,
    ProactorReuploadTests,
):
    CTH: Type[CommTestHelper]
