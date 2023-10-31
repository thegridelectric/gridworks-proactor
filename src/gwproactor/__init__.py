"""This packages provides infrastructure for running a proactor on top of asyncio with support multiple MQTT clients
and and sub-objects which support their own threads for synchronous operations.

This packages is not GridWorks-aware (except that it links actors with multiple mqtt clients). This separation between
communication / action infrastructure and GridWorks semantics is intended to allow the latter to be more focussed.

This package is not polished and the separation is up for debate.

Particular questions:

* Is the programming model still clean after more concrete actors are implemented and more infrastructure are added.
* Does the separation add value or just complicate analysis.
* MQTTClients should be made async.
* Semantics of building message type namespaces should be spelled out / further worked out.
* Test support should be implemented / cleaner.
"""

from gwproactor.actors import Actor
from gwproactor.actors import SyncThreadActor
from gwproactor.actors import SyncThreadT
from gwproactor.config import ProactorSettings
from gwproactor.external_watchdog import ExternalWatchdogCommandBuilder
from gwproactor.links.mqtt import QOS
from gwproactor.links.mqtt import MQTTClients
from gwproactor.links.mqtt import MQTTClientWrapper
from gwproactor.links.mqtt import Subscription
from gwproactor.logger import ProactorLogger
from gwproactor.logging_setup import format_exceptions
from gwproactor.logging_setup import setup_logging
from gwproactor.proactor_implementation import Proactor
from gwproactor.proactor_interface import INVALID_IO_TASK_HANDLE
from gwproactor.proactor_interface import ActorInterface
from gwproactor.proactor_interface import Communicator
from gwproactor.proactor_interface import CommunicatorInterface
from gwproactor.proactor_interface import MonitoredName
from gwproactor.proactor_interface import Runnable
from gwproactor.proactor_interface import ServicesInterface
from gwproactor.problems import Problems
from gwproactor.sync_thread import AsyncQueueWriter
from gwproactor.sync_thread import SyncAsyncInteractionThread
from gwproactor.sync_thread import SyncAsyncQueueWriter
from gwproactor.sync_thread import responsive_sleep


__all__ = [
    "Actor",
    "ActorInterface",
    "AsyncQueueWriter",
    "Communicator",
    "CommunicatorInterface",
    "ExternalWatchdogCommandBuilder",
    "format_exceptions",
    "INVALID_IO_TASK_HANDLE",
    "MonitoredName",
    "MQTTClients",
    "MQTTClientWrapper",
    "Proactor",
    "ProactorLogger",
    "ProactorSettings",
    "Problems",
    "QOS",
    "responsive_sleep",
    "Runnable",
    "ServicesInterface",
    "setup_logging",
    "Subscription",
    "SyncAsyncInteractionThread",
    "SyncAsyncQueueWriter",
    "SyncThreadT",
    "SyncThreadActor",
]
