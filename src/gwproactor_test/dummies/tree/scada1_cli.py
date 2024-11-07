import asyncio
from pathlib import Path

import dotenv
import rich
import typer

from gwproactor.command_line_utils import (
    check_tls_paths_present,
    get_settings,
    run_async_main,
)
from gwproactor_test.dummies import DUMMY_SCADA1_NAME
from gwproactor_test.dummies.tree.scada1 import DummyScada1
from gwproactor_test.dummies.tree.scada1_settings import DummyScada1Settings

app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    rich_markup_mode="rich",
    help="GridWorks Dummy Scada1",
)


@app.command()
def run(
    env_file: str = ".env",
    dry_run: bool = False,
    verbose: bool = False,
    message_summary: bool = False,
) -> None:
    asyncio.run(
        run_async_main(
            name=DUMMY_SCADA1_NAME,
            proactor_type=DummyScada1,
            settings_type=DummyScada1Settings,
            env_file=env_file,
            dry_run=dry_run,
            verbose=verbose,
            message_summary=message_summary,
        )
    )


@app.command()
def config(
    env_file: str = ".env",
) -> None:
    dotenv_file = dotenv.find_dotenv(env_file)
    rich.print(
        f"Env file: <{dotenv_file}>  exists:{env_file and Path(dotenv_file).exists()}"
    )
    settings = get_settings(settings_type=DummyScada1Settings, env_file=dotenv_file)
    rich.print(settings)
    missing_tls_paths = check_tls_paths_present(settings, raise_error=False)
    if missing_tls_paths:
        rich.print(missing_tls_paths)


@app.callback()
def _main() -> None: ...


if __name__ == "__main__":
    app()
