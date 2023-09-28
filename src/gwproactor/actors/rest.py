"""Code for actors that use a simple rest interaction, converting the response to one or more
REST commands into a message posted to main processing thread.

"""
import asyncio
import time
from typing import Optional

import aiohttp as aiohttp
import yarl
from aiohttp import ClientResponse
from aiohttp import ClientSession
from aiohttp import ClientTimeout
from aiohttp.typedefs import StrOrURL
from gwproto import Message
from gwproto.data_classes.components.rest_poller_component import RESTPollerComponent
from gwproto.types import URLConfig
from result import Result

from gwproactor import Actor
from gwproactor import ServicesInterface
from gwproactor.proactor_interface import INVALID_IO_TASK_HANDLE


class RESTPoller(Actor):
    _task_id: int
    _component: RESTPollerComponent

    def __init__(self, name: str, services: ServicesInterface):
        super().__init__(name, services)
        self._task_id = INVALID_IO_TASK_HANDLE
        component = self.services.hardware_layout.component(self.name)
        if not isinstance(component, RESTPollerComponent):
            display_name = getattr(
                component, "display_name", "MISSING ATTRIBUTE display_name"
            )
            raise ValueError(
                f"ERROR. Component <{display_name}> has type {type(component)}. "
                f"Expected RESTPollerComponent.\n"
                f"  Node: {self.name}\n"
                f"  Component id: {component.component_id}"
            )
        self._component = component

    def process_message(self, message: Message) -> Result[bool, BaseException]:
        raise ValueError("RESTPoller currently processes no messages")

    def _make_base_url(self) -> Optional[yarl.URL]:
        return URLConfig.make_url(self._component.rest.session.base_url)

    def _make_url(self) -> Optional[yarl.URL]:
        return URLConfig.make_url(self._component.rest.request.url)

    def _session_args(self) -> tuple[Optional[StrOrURL], dict]:
        return self._make_base_url(), dict(
            self._component.rest.session.dict(
                exclude={"base_url", "timeout"},
                exclude_unset=True,
            ),
            timeout=ClientTimeout(**self._component.rest.session.timeout.dict()),
        )

    def _request_args(self) -> tuple[str, Optional[StrOrURL], dict]:
        return (
            self._component.rest.request.method,
            self._make_url(),
            dict(
                self._component.rest.request.dict(
                    exclude={"method", "url", "timeout"},
                    exclude_unset=True,
                ),
                timeout=ClientTimeout(**self._component.rest.request.timeout.dict()),
            ),
        )

    async def _make_request(self, session: ClientSession) -> ClientResponse:
        # print("++RESTPoller._make_request")
        method, url, request_kwargs = self._request_args()
        response = await session.request(method, url, **request_kwargs)
        # print(f"--RESTPoller._make_request {response}")
        return response

    async def _convert(self, response: ClientResponse) -> Optional[Message]:  # noqa
        return None

    def _get_next_sleep_seconds(self) -> float:
        return self._component.rest.poll_period_seconds

    async def _act(self):
        try:
            # print("RESTPoller  ++_act")
            # dbg_num_loops = 0
            reconnect = True
            while reconnect:
                base_url, session_kwargs = self._session_args()
                async with aiohttp.ClientSession(base_url, **session_kwargs) as session:
                    while True:
                        # print(f"RESTPoller  ++loop {dbg_num_loops}")
                        try:
                            async with await self._make_request(session) as response:
                                # print(
                                #     f"RESTPoller    loop {dbg_num_loops}  "
                                #     f"response: {response}"
                                # )
                                message = await self._convert(response)
                                # print(
                                #     f"RESTPoller    loop {dbg_num_loops}  "
                                #     f"message: {message}"
                                # )
                            if message is not None:
                                self.services.send_threadsafe(message)
                            sleep_seconds = self._get_next_sleep_seconds()
                            # print(
                            #     f"RESTPoller    loop {dbg_num_loops}  "
                            #     f"sleep_seconds: {sleep_seconds}"
                            # )
                            pre_sleep = time.time()
                            await asyncio.sleep(sleep_seconds)
                            # print(
                            #     f"RESTPoller    loop {dbg_num_loops}  "
                            #     f"awoke after: {time.time() - pre_sleep}"
                            # )
                        except BaseException as e:
                            # print(
                            #     f"RESTPoller  loop {dbg_num_loops}"
                            #     f"  {e}  {type(e)}"
                            # )
                            raise e
                        # print(f"RESTPoller  --loop {dbg_num_loops}")
                        # dbg_num_loops += 1

        except BaseException as e:
            # print(f"RESTPoller  --_act  {e}  {type(e)}")
            raise e

    def start(self) -> None:
        self._task_id = self.services.io_loop_manager.add_io_coroutine(self._act())

    def stop(self) -> None:
        self.services.io_loop_manager.cancel_io_routine(self._task_id)

    async def join(self) -> None:
        """IOLoop will take care of shutting down the associated task."""
