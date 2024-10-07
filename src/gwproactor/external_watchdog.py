import os
from typing import Optional


class ExternalWatchdogCommandBuilder:
    """Create arguments which will be passed to subprocess.run() to pat the external watchdog.

    If the returned list is empty, pat process will be run.

    By default an empty list is returned if the environment variable named by sevice_variable_name() is not set to
    1 or true.
    """

    @classmethod
    def service_variable_name(cls, service_name: str) -> str:
        return f"{service_name.upper()}_RUNNING_AS_SERVICE"

    @classmethod
    def running_as_service(cls, service_name: str) -> bool:
        return os.getenv(cls.service_variable_name(service_name), "").lower() in [
            "1",
            "true",
        ]

    @classmethod
    def default_pat_args(cls, pid: Optional[int] = None) -> list[str]:  # noqa: ARG003
        return []

    @classmethod
    def pat_args(
        cls,
        service_name: str,
        args: Optional[list[str]] = None,
        pid: Optional[int] = None,
    ) -> list[str]:
        """Return arguments to be passed to subprocess.run() to pat the external watchdog."""
        if cls.running_as_service(service_name):
            if args is None:
                args = cls.default_pat_args(pid=pid)
            return args
        return []


class SystemDWatchdogCommandBuilder(ExternalWatchdogCommandBuilder):
    @classmethod
    def default_pat_args(cls, pid: Optional[int] = None) -> list[str]:
        if pid is None:
            pid = os.getpid()
        return [
            "systemd-notify",
            f"--pid={pid}",
            "WATCHDOG=1",
        ]
