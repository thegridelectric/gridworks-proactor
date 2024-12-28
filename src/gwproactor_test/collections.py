# ruff: noqa: PLR2004, ERA001

from typing import Type

import pytest

from gwproactor_test.awaiting_setup_tests import ProactorCommAwaitingSetupTests
from gwproactor_test.basic_tests import ProactorCommBasicTests
from gwproactor_test.comm_test_helper import CommTestHelper
from gwproactor_test.reupload_tests import ProactorReuploadTests
from gwproactor_test.timeout_tests import ProactorCommTimeoutTests
from gwproactor_test.tree_comm_test_helper import TreeCommTestHelper
from gwproactor_test.tree_tests import ProactorTreeCommBasicTests


@pytest.mark.asyncio
class ProactorCommTests(
    ProactorCommBasicTests,
    ProactorCommAwaitingSetupTests,
    ProactorCommTimeoutTests,
    ProactorReuploadTests,
):
    CTH: Type[CommTestHelper]


class ProactorTreeCommTests(ProactorTreeCommBasicTests):
    CTH: Type[TreeCommTestHelper]
