import asyncio
from collections import defaultdict
from typing import Any

from aiohttp import web
from aiohttp.typedefs import Handler as HTTPHandler
from aiohttp.web_routedef import RouteDef
from gwproto import Message
from gwproto.types import WebServerGt
from result import Result

from gwproactor.proactor_interface import Communicator
from gwproactor.proactor_interface import Runnable
from gwproactor.proactor_interface import ServicesInterface


def enable_aiohttp_logging() -> None:
    import logging

    for logger_name in [
        "aiohttp.access",
        "aiohttp.client",
        "aiohttp.internal",
        "aiohttp.server",
        "aiohttp.web",
        "aiohttp.websocket",
    ]:
        logger_ = logging.getLogger(logger_name)
        handler_ = logging.StreamHandler()
        handler_.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s.%(msecs)03d   %(message)s",
                datefmt="%Y-%m-%d  %H:%M:%S",
            )
        )
        logger_.addHandler(handler_)
        logger_.setLevel(logging.INFO)
        logger_.setLevel(logging.DEBUG)


class _RunWebServer:
    config: WebServerGt
    routes: list[RouteDef]

    def __init__(
        self,
        config: WebServerGt,
        routes: list[RouteDef],
    ):
        self.config = config
        self.routes = routes[:]

    async def __call__(self) -> None:
        app = web.Application()
        app.add_routes(self.routes)
        runner = web.AppRunner(app)
        try:
            await runner.setup()
            site = web.TCPSite(
                runner,
                host=self.config.Host,
                port=self.config.Port,
                **self.config.Kwargs,
            )
            await site.start()
            while True:
                await asyncio.sleep(10)
        finally:
            try:
                await runner.cleanup()
            except:  # noqa
                pass


class _WebManager(Communicator, Runnable):

    _configs: dict[str, WebServerGt]
    _routes: dict[str, list[RouteDef]]

    def __init__(self, services: ServicesInterface) -> None:
        super().__init__("_WebManager", services)
        self._configs = dict()
        self._routes = defaultdict(list)

    def process_message(self, message: Message) -> Result[bool, BaseException]:
        raise ValueError("_WebManager does not currently process any messages")

    def disable(self):
        self._configs.clear()
        self._routes.clear()

    def start(self) -> None:
        for server_name, server_config in self._configs.items():
            if server_config.Enabled:
                self._services.io_loop_manager.add_io_coroutine(
                    _RunWebServer(
                        config=server_config,
                        routes=self._routes.get(server_name, []),
                    )(),
                    name=f"{self.name}.{server_name}",
                )

    def stop(self) -> None:
        pass

    async def join(self) -> None:
        pass

    def add_web_server_config(
        self, name: str, host: str, port: int, **kwargs: Any
    ) -> None:
        if name in self._configs:
            raise ValueError(f"ERROR: Server with name '{name}' already exists")
        self._configs[name] = WebServerGt(
            Name=name, Host=host, Port=port, Kwargs=kwargs
        )

    def add_web_route(
        self,
        server_name: str,
        method: str,
        path: str,
        handler: HTTPHandler,
        **kwargs: Any,
    ):
        self._routes[server_name].append(
            RouteDef(
                method=method,
                path=path,
                handler=handler,
                kwargs=kwargs,
            )
        )
