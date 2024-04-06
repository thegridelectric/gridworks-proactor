import functools
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


async def _run_web_server(config: WebServerGt, routes: list[RouteDef]) -> None:
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    try:
        await runner.setup()
        site = web.TCPSite(runner, host=config.Host, port=config.Port, **config.Kwargs)
        await site.start()
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

    def start(self) -> None:
        for server_name, server_config in self._configs.items():
            if server_config.Enabled:
                self._services.io_loop_manager.add_io_coroutine(
                    functools.partial(
                        _run_web_server,
                        config=self._configs,
                        routes=self._routes.get(server_name, []),
                    ),
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
