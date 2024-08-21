# """Test communication issues"""
from gwproactor_test import CommTestHelper, ProactorCommTests
from gwproactor_test.dummies import (
    DummyChild,
    DummyChildSettings,
    DummyParent,
    DummyParentSettings,
)


class DummyCommTestHelper(CommTestHelper):
    parent_t = DummyParent
    child_t = DummyChild
    parent_settings_t = DummyParentSettings
    child_settings_t = DummyChildSettings


class TestDummyProactorComm(ProactorCommTests):
    CTH = DummyCommTestHelper
