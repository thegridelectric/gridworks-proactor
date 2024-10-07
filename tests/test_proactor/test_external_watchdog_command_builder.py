"""Test ExternalWatchdogCommandBuilder"""

import os
from typing import Any

from gwproactor import ExternalWatchdogCommandBuilder
from gwproactor.external_watchdog import SystemDWatchdogCommandBuilder


def test_external_watchdog_command_building(monkeypatch: Any) -> None:
    """Test ExternalWatchdogCommandBuilder and SystemDWatchdogCommandBuilder"""
    assert ExternalWatchdogCommandBuilder.default_pat_args() == []
    service_name = "foo"
    variable_name = ExternalWatchdogCommandBuilder.service_variable_name(service_name)
    assert variable_name == "FOO_RUNNING_AS_SERVICE"
    monkeypatch.setenv(variable_name, "")
    assert not ExternalWatchdogCommandBuilder.running_as_service(service_name)
    assert not SystemDWatchdogCommandBuilder.running_as_service(service_name)
    assert ExternalWatchdogCommandBuilder.pat_args(service_name) == []
    assert SystemDWatchdogCommandBuilder.pat_args(service_name) == []
    monkeypatch.setenv(variable_name, "1")
    assert ExternalWatchdogCommandBuilder.running_as_service(service_name)
    assert SystemDWatchdogCommandBuilder.running_as_service(service_name)
    assert ExternalWatchdogCommandBuilder.pat_args(service_name) == []
    args = ["x"]
    assert ExternalWatchdogCommandBuilder.pat_args(service_name, args=args) == args
    exp_sysd_args = [
        "systemd-notify",
        f"--pid={os.getpid()}",
        "WATCHDOG=1",
    ]
    assert SystemDWatchdogCommandBuilder.pat_args(service_name) == exp_sysd_args
    pid = 99
    exp_sysd_args = [
        "systemd-notify",
        f"--pid={pid}",
        "WATCHDOG=1",
    ]
    assert (
        SystemDWatchdogCommandBuilder.pat_args(service_name, pid=pid) == exp_sysd_args
    )
