"""Proactor implementation"""

import asyncio
import sys
import traceback
import uuid
from typing import Any
from typing import Awaitable
from typing import Dict
from typing import List
from typing import Optional
from typing import Sequence

import gwproto
from gwproto.data_classes.hardware_layout import HardwareLayout
from gwproto.data_classes.sh_node import ShNode
from gwproto.messages import Ack
from gwproto.messages import EventBase
from gwproto.messages import EventT
from gwproto.messages import Ping
from gwproto.messages import ProblemEvent
from gwproto.messages import ShutdownEvent
from result import Err
from result import Ok
from result import Result

from gwproactor import ProactorSettings
from gwproactor.external_watchdog import ExternalWatchdogCommandBuilder
from gwproactor.external_watchdog import SystemDWatchdogCommandBuilder
from gwproactor.io_loop import IOLoop
from gwproactor.links import AckWaitInfo
from gwproactor.links import AsyncioTimerManager
from gwproactor.links import LinkManager
from gwproactor.links import LinkManagerTransition
from gwproactor.links import Transition
from gwproactor.logger import ProactorLogger
from gwproactor.message import DBGCommands
from gwproactor.message import DBGEvent
from gwproactor.message import DBGPayload
from gwproactor.message import Message
from gwproactor.message import MQTTConnectFailPayload
from gwproactor.message import MQTTConnectPayload
from gwproactor.message import MQTTDisconnectPayload
from gwproactor.message import MQTTProblemsPayload
from gwproactor.message import MQTTReceiptPayload
from gwproactor.message import MQTTSubackPayload
from gwproactor.message import PatWatchdog
from gwproactor.message import Shutdown
from gwproactor.persister import PersisterInterface
from gwproactor.persister import StubPersister
from gwproactor.proactor_interface import CommunicatorInterface
from gwproactor.proactor_interface import IOLoopInterface
from gwproactor.proactor_interface import MonitoredName
from gwproactor.proactor_interface import Runnable
from gwproactor.proactor_interface import ServicesInterface
from gwproactor.problems import Problems
from gwproactor.stats import ProactorStats
from gwproactor.str_tasks import str_tasks
from gwproactor.watchdog import WatchdogManager


class Proactor(ServicesInterface, Runnable):

    _name: str
    _settings: ProactorSettings
    _node: ShNode
    _layout: HardwareLayout
    _logger: ProactorLogger
    _stats: ProactorStats
    _event_persister: PersisterInterface
    _loop: Optional[asyncio.AbstractEventLoop] = None
    _receive_queue: Optional[asyncio.Queue] = None
    _links: LinkManager
    _communicators: Dict[str, CommunicatorInterface]
    _stop_requested: bool
    _tasks: List[asyncio.Task]
    _io_loop_manager: IOLoop
    _watchdog: WatchdogManager

    def __init__(
        self,
        name: str,
        settings: ProactorSettings,
        hardware_layout: Optional[HardwareLayout] = None,
    ):
        self._name = name
        self._settings = settings
        if hardware_layout is None:
            hardware_layout = HardwareLayout(
                dict(
                    ShNodes=[
                        dict(
                            ShNodeId=str(uuid.uuid4()),
                            Alias=self._name,
                            ActorClassGtEnumSymbol="00000000",
                            RoleGtEnumSymbol="00000000",
                            TypeName="spaceheat.node.gt",
                        )
                    ]
                )
            )
        self._layout = hardware_layout
        self._node = self._layout.node(name)
        self._logger = ProactorLogger(**settings.logging.qualified_logger_names())
        self._stats = self.make_stats()
        self._event_persister = self.make_event_persister(settings)
        self._links = LinkManager(
            publication_name=self.publication_name,
            settings=settings,
            logger=self._logger,
            stats=self._stats,
            event_persister=self._event_persister,
            timer_manager=AsyncioTimerManager(),
            ack_timeout_callback=self._process_ack_timeout,
        )
        self._communicators = dict()
        self._tasks = []
        self._stop_requested = False
        self._watchdog = WatchdogManager(9, self)
        self.add_communicator(self._watchdog)
        self._io_loop_manager = IOLoop(self)
        self.add_communicator(self._io_loop_manager)

    @classmethod
    def make_stats(cls) -> ProactorStats:
        return ProactorStats()

    @classmethod
    def make_event_persister(cls, settings: ProactorSettings) -> PersisterInterface:
        return StubPersister()

    def send(self, message: Message):
        if not isinstance(message.Payload, PatWatchdog):
            self._logger.message_summary(
                "OUT internal",
                message.Header.Src,
                f"{message.Header.Dst}/{message.Header.MessageType}",
                message.Payload,
                message_id=message.Header.MessageId,
            )
        self._receive_queue.put_nowait(message)

    def send_threadsafe(self, message: Message) -> None:
        self._loop.call_soon_threadsafe(self._receive_queue.put_nowait, message)

    def get_communicator(self, name: str) -> CommunicatorInterface:
        return self._communicators[name]

    @property
    def name(self) -> str:
        return self._name

    @property
    def publication_name(self) -> str:
        return self._name

    @property
    def monitored_names(self) -> Sequence[MonitoredName]:
        return []

    @property
    def settings(self) -> ProactorSettings:
        return self._settings

    @property
    def logger(self) -> ProactorLogger:
        return self._logger

    @property
    def stats(self) -> ProactorStats:
        return self._stats

    @property
    def io_loop_manager(self) -> IOLoopInterface:
        return self._io_loop_manager

    @property
    def hardware_layout(self) -> HardwareLayout:
        return self._layout

    @property
    def services(self) -> "ServicesInterface":
        return self

    def get_external_watchdog_builder_class(
        self,
    ) -> type[ExternalWatchdogCommandBuilder]:
        return SystemDWatchdogCommandBuilder

    @property
    def upstream_client(self) -> str:
        return self._links.upstream_client

    @property
    def primary_peer_client(self) -> str:
        return self._links.primary_peer_client

    def _send(self, message: Message):
        self.send(message)

    def generate_event(self, event: EventT) -> Result[bool, BaseException]:
        return self._links.generate_event(event)

    def _process_ack_timeout(self, wait_info: AckWaitInfo) -> None:
        self._logger.message_enter(
            "++Proactor._process_ack_timeout %s", wait_info.message_id
        )
        path_dbg = 0
        result = self._links.process_ack_timeout(wait_info)
        if result.is_ok():
            path_dbg |= 0x00000001
            if result.value.deactivated():
                path_dbg |= 0x00000002
                self._derived_recv_deactivated(result.value)
        else:
            path_dbg |= 0x00000004
            self._report_error(result.err(), msg="Proactor._process_ack_timeout")
        self._logger.message_exit(
            "--Proactor._process_ack_timeout path:0x%08X", path_dbg
        )

    def _process_ack(self, link_name: str, message_id: str):
        self._links.process_ack(link_name, message_id)

    def _process_dbg(self, dbg: DBGPayload):
        self._logger.path("++_process_dbg")
        path_dbg = 0
        count_dbg = 0
        for logger_name in ["message_summary", "lifecycle", "comm_event"]:
            requested_level = getattr(dbg.Levels, logger_name)
            if requested_level > -1:
                path_dbg |= 0x00000001
                count_dbg += 1
                logger = getattr(self._logger, logger_name + "_logger")
                old_level = logger.getEffectiveLevel()
                logger.setLevel(requested_level)
                self._logger.debug(
                    "%s logger level %s -> %s",
                    logger_name,
                    old_level,
                    logger.getEffectiveLevel(),
                )
        match dbg.Command:
            case DBGCommands.show_subscriptions:
                path_dbg |= 0x00000002
                self._links.log_subscriptions("message")
            case _:
                path_dbg |= 0x00000004
        self.generate_event(
            DBGEvent(Command=dbg, Path=f"0x{path_dbg:08X}", Count=count_dbg, Msg="")
        )
        self._logger.path("--_process_dbg  path:0x%08X  count:%d", path_dbg, count_dbg)

    def add_communicator(self, communicator: CommunicatorInterface):
        if communicator.name in self._communicators:
            raise ValueError(
                f"ERROR. Communicator with name [{communicator.name}] already present"
            )
        self._communicators[communicator.name] = communicator
        for monitored in communicator.monitored_names:
            self._watchdog.add_monitored_name(monitored)

    @property
    def async_receive_queue(self) -> Optional[asyncio.Queue]:
        return self._receive_queue

    @property
    def event_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        return self._loop

    async def process_messages(self):
        # noinspection PyBroadException
        try:
            self._start_processing_messages()
            while not self._stop_requested:
                message = await self._receive_queue.get()
                if not self._stop_requested:
                    await self.process_message(message)
                self._receive_queue.task_done()
        except BaseException as e:
            if not isinstance(e, asyncio.exceptions.CancelledError):
                self._logger.exception(f"ERROR in process_message")
                self._logger.error("Stopping proactor")
                # noinspection PyBroadException
                try:
                    self.generate_event(
                        ShutdownEvent(
                            Reason=(
                                f"ERROR in process_message {e}\n"
                                f"{traceback.format_exception(e)}"
                            )
                        )
                    )
                except:
                    self._logger.exception(f"ERROR generating exception event")
        # noinspection PyBroadException
        try:
            self.stop()
        except:
            self._logger.exception(f"ERROR stopping proactor")

    def start_tasks(self):
        self._tasks = [
            asyncio.create_task(self.process_messages(), name="process_messages"),
        ] + self._links.start_ping_tasks()
        self._start_derived_tasks()

    def _start_derived_tasks(self):
        pass

    def _derived_process_message(self, message: Message):
        pass

    def _derived_process_mqtt_message(
        self, message: Message[MQTTReceiptPayload], decoded: Any
    ):
        pass

    @classmethod
    def _second_caller(cls) -> str:
        try:
            # noinspection PyProtectedMember,PyUnresolvedReferences
            return sys._getframe(2).f_back.f_code.co_name
        except BaseException as e:
            return f"[ERROR extracting caller of _report_errors: {e}"

    def _report_error(
        self, error: BaseException, msg: str = ""
    ) -> Result[bool, BaseException]:
        try:
            if not msg:
                msg = self._second_caller()
            self._report_errors([error], msg)
        except BaseException as e2:
            return Err(e2)
        return Ok()

    def _report_errors(
        self, errors: Sequence[BaseException], msg: str = ""
    ) -> Result[bool, BaseException]:
        try:
            if not msg:
                msg = self._second_caller()
            self.generate_event(Problems(errors=errors).problem_event(msg))
        except BaseException as e2:
            return Err(e2)
        return Ok()

    def _start_processing_messages(self):
        """Hook for processing before any messages are pulled from queue"""

    async def process_message(self, message: Message):
        if not isinstance(message.Payload, PatWatchdog):
            self._logger.message_enter(
                "++Proactor.process_message %s/%s",
                message.Header.Src,
                message.Header.MessageType,
            )
        path_dbg = 0
        if not isinstance(message.Payload, (MQTTReceiptPayload, PatWatchdog)):
            path_dbg |= 0x00000001
            self._logger.message_summary(
                "IN  internal",
                self.name,
                f"{message.Header.Src}/{message.Header.MessageType}",
                message.Payload,
                message_id=message.Header.MessageId,
            )
        self._stats.add_message(message)
        match message.Payload:
            case MQTTReceiptPayload():
                path_dbg |= 0x00000002
                self._process_mqtt_message(message)
            case MQTTConnectPayload():
                path_dbg |= 0x00000004
                self._process_mqtt_connected(message)
            case MQTTDisconnectPayload():
                path_dbg |= 0x00000008
                self._process_mqtt_disconnected(message)
            case MQTTConnectFailPayload():
                path_dbg |= 0x00000010
                self._process_mqtt_connect_fail(message)
            case MQTTSubackPayload():
                path_dbg |= 0x00000020
                self._process_mqtt_suback(message)
            case MQTTProblemsPayload():
                path_dbg |= 0x00000040
                self._process_mqtt_problems(message)
            case PatWatchdog():
                path_dbg |= 0x00000080
                self._watchdog.process_message(message)
            case Shutdown():
                path_dbg |= 0x00000100
                self._process_shutdown_message(message)
            case EventBase():
                path_dbg |= 0x00000200
                self.generate_event(message.Payload)
            case _:
                path_dbg |= 0x00000400
                self._derived_process_message(message)
        if not isinstance(message.Payload, PatWatchdog):
            self._logger.message_exit(
                "--Proactor.process_message  path:0x%08X", path_dbg
            )

    def _decode_mqtt_message(self, mqtt_payload) -> Result[Message[Any], BaseException]:
        try:
            result = Ok(
                self._links.decode(
                    mqtt_payload.client_name,
                    mqtt_payload.message.topic,
                    mqtt_payload.message.payload,
                )
            )
        except Exception as e:
            self._logger.exception("ERROR decoding [%s]", mqtt_payload)
            self.generate_event(
                ProblemEvent(
                    ProblemType=gwproto.messages.Problems.warning,
                    Summary=f"Decoding error topic [{mqtt_payload.message.topic}]  error [{type(e)}]",
                    Details=(
                        f"Topic: {mqtt_payload.message.topic}\n"
                        f"Message: {mqtt_payload.message.payload[:70]}"
                        f"{'...' if len(mqtt_payload.message.payload)> 70 else ''}\n"
                        f"{traceback.format_exception(e)}\n"
                        f"Exception: {e}"
                    ),
                )
            )
            result = Err(e)
        return result

    def _process_mqtt_message(
        self, mqtt_receipt_message: Message[MQTTReceiptPayload]
    ) -> Result[Message[Any], BaseException]:
        self._logger.path(
            "++Proactor._process_mqtt_message %s/%s",
            mqtt_receipt_message.Header.Src,
            mqtt_receipt_message.Header.MessageType,
        )
        path_dbg = 0
        self._stats.add_mqtt_message(mqtt_receipt_message)
        decode_result = self._decode_mqtt_message(mqtt_receipt_message.Payload)
        if decode_result.is_ok():
            path_dbg |= 0x00000001
            decoded_message = decode_result.value
            self._logger.message_summary(
                "IN  mqtt    ",
                self.name,
                mqtt_receipt_message.Payload.message.topic,
                decoded_message.Payload,
                message_id=decoded_message.Header.MessageId,
            )
            link_mgr_results = self._links.process_mqtt_message(mqtt_receipt_message)
            if link_mgr_results.is_ok():
                path_dbg |= 0x00000002
                if link_mgr_results.value.recv_activated():
                    path_dbg |= 0x00000004
                    self._derived_recv_activated(link_mgr_results.value)
            else:
                path_dbg |= 0x00000008
                self._report_error(
                    link_mgr_results.err(),
                    "_process_mqtt_message/_link_states.process_mqtt_message",
                )
            match decoded_message.Payload:
                case Ack():
                    path_dbg |= 0x00000010
                    self._process_ack(
                        mqtt_receipt_message.Payload.client_name,
                        decoded_message.Payload.AckMessageID,
                    )
                case Ping():
                    path_dbg |= 0x00000020
                case DBGPayload():
                    path_dbg |= 0x00000040
                    self._process_dbg(decoded_message.Payload)
                case _:
                    path_dbg |= 0x00000080
                    self._derived_process_mqtt_message(
                        mqtt_receipt_message, decoded_message
                    )
            if decoded_message.Header.AckRequired:
                path_dbg |= 0x00000100
                self._links.send_ack(
                    mqtt_receipt_message.Payload.client_name, decoded_message
                )
        self._logger.path(
            "--Proactor._process_mqtt_message:%s  path:0x%08X",
            int(decode_result.is_ok()),
            path_dbg,
        )
        return decode_result

    def _process_mqtt_connected(self, message: Message[MQTTConnectPayload]):
        result = self._links.process_mqtt_connected(message)
        if result.is_err():
            self._report_error(result.err(), "_process_mqtt_connected")

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def _derived_recv_deactivated(
        self, transition: LinkManagerTransition
    ) -> Result[bool, BaseException]:
        return Ok()

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def _derived_recv_activated(
        self, transition: Transition
    ) -> Result[bool, BaseException]:
        return Ok()

    def _process_mqtt_disconnected(
        self, message: Message[MQTTDisconnectPayload]
    ) -> Result[bool, BaseException]:
        link_mgr_result = self._links.process_mqtt_disconnected(message)
        if link_mgr_result.is_ok() and link_mgr_result.value.recv_deactivated():
            result = self._derived_recv_deactivated(link_mgr_result.value)
        else:
            result = Err(link_mgr_result.err())
        return result

    def _process_mqtt_connect_fail(
        self, message: Message[MQTTConnectFailPayload]
    ) -> Result[bool, BaseException]:
        return self._links.process_mqtt_connect_fail(message)

    def _process_mqtt_suback(
        self, message: Message[MQTTSubackPayload]
    ) -> Result[bool, BaseException]:
        self._logger.path(
            "++Proactor._process_mqtt_suback client:%s", message.Payload.client_name
        )
        path_dbg = 0
        link_mgr_result = self._links.process_mqtt_suback(message)
        if link_mgr_result.is_ok():
            path_dbg |= 0x00000001
            if link_mgr_result.value.recv_activated():
                path_dbg |= 0x00000002
                result = self._derived_recv_activated(link_mgr_result.value)
            else:
                path_dbg |= 0x00000004
                result = Ok(True)
        else:
            path_dbg |= 0x00000008
            result = Err(link_mgr_result.err())
        self._logger.path(
            "--Proactor._process_mqtt_suback:%d  path:0x%08X",
            result.is_ok(),
            path_dbg,
        )
        return result

    def _process_mqtt_problems(
        self, message: Message[MQTTProblemsPayload]
    ) -> Result[bool, BaseException]:
        self.generate_event(
            ProblemEvent(
                ProblemType=gwproto.messages.Problems.error,
                Summary=f"Error in mqtt event loop for client [{message.Payload.client_name}]",
                Details=(
                    f"{message.Payload.problems}\n"
                    f"{message.Payload.problems.error_traceback_str()}"
                ),
            )
        )
        return Ok()

    def _process_shutdown_message(self, message: Message[Shutdown]):
        self._stop_requested = True
        self.generate_event(ShutdownEvent(Reason=message.Payload.Reason))
        self._logger.lifecycle(
            f"Shutting down due to ShutdownMessage, [{message.Payload.Reason}]"
        )

    async def run_forever(self):
        self._loop = asyncio.get_running_loop()
        self._receive_queue = asyncio.Queue()
        self._links.start(self._loop, self._receive_queue)
        for communicator in self._communicators.values():
            if isinstance(communicator, Runnable):
                communicator.start()
        self.start_tasks()
        await self.join()

    def start(self):
        raise RuntimeError("ERROR. Proactor must be started by awaiting run_forever()")

    def stop(self):
        self._stop_requested = True
        for task in self._tasks:
            # TODO: CS - Send self a shutdown message instead?
            if not task.done():
                task.cancel()
        self._links.stop()
        for communicator in self._communicators.values():
            if isinstance(communicator, Runnable):
                # noinspection PyBroadException
                try:
                    communicator.stop()
                except:
                    pass

    async def join(self):
        self._logger.lifecycle("++Proactor.join()")
        self._logger.lifecycle(str_tasks(self._loop, "Proactor.join() - all tasks"))
        running: List[Awaitable] = self._tasks[:]
        for communicator in self._communicators.values():
            communicator_name = communicator.name
            if isinstance(communicator, Runnable):
                running.append(
                    self._loop.create_task(
                        communicator.join(), name=f"{communicator_name}.join"
                    )
                )
        # noinspection PyBroadException
        try:
            while running:
                self._logger.lifecycle(
                    str_tasks(self._loop, "WAITING FOR", tasks=running)
                )
                done, running = await asyncio.wait(
                    running, return_when="FIRST_COMPLETED"
                )
                self._logger.lifecycle(str_tasks(self._loop, tag="DONE", tasks=done))
                self._logger.lifecycle(
                    str_tasks(self._loop, tag="PENDING", tasks=running)
                )
                for task in done:
                    if not task.cancelled() and (exception := task.exception()):
                        self._logger.error(
                            f"EXCEPTION in task {task.get_name()}  {exception}"
                        )
                        self._logger.error(traceback.format_tb(exception.__traceback__))
        except BaseException as e:
            self._logger.exception("ERROR in Proactor.join: %s <%s>", type(e), e)
        self._logger.lifecycle("--Proactor.join()")
