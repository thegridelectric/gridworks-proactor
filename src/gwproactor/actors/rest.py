"""Code for actors that use a simple rest interaction, converting the response to one or more
REST commands into a message posted to main processing thread.

"""
import asyncio
from typing import Optional

import aiohttp as aiohttp
import yarl
from aiohttp import ClientResponse
from aiohttp import ClientSession
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
        return URLConfig.make_url(self._component.rest.Session.base_url)

    def _make_url(self) -> Optional[yarl.URL]:
        return URLConfig.make_url(self._component.rest.Request.url)

    def _session_args(self) -> dict:
        return dict(
            self._component.rest.Session.dict(
                exclude={"base_url"},
                exclude_unset=True,
            ),
            base_url=self._make_base_url(),
        )

    def _request_args(self) -> dict:
        return dict(
            self._component.rest.Request.dict(
                exclude={"method", "url"},
                exclude_unset=True,
            ),
            url=self._make_url(),
        )

    async def _make_request(self, session: ClientSession) -> ClientResponse:
        return await session.request(**self._request_args())

    async def _convert(self, response: ClientResponse) -> Optional[Message]:  # noqa
        return None

    def _get_next_sleep_seconds(self) -> float:
        return self._component.rest.PollPeriodSeconds

    async def _act(self):
        async with aiohttp.ClientSession(**self._session_args()) as session:
            while True:
                async with self._make_request(session) as response:
                    message = await self._convert(response)
                if message is not None:
                    self.services.send_threadsafe(message)
                await asyncio.sleep(self._get_next_sleep_seconds())

    def start(self) -> None:
        self._task_id = self.services.io_loop_manager.add_io_coroutine(self._act())

    def stop(self) -> None:
        self.services.io_loop_manager.cancel_io_routine(self._task_id)

    async def join(self) -> None:
        """IOLoop will take care of shutting down the associated task."""
