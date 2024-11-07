import typer
from trogon import Trogon
from typer.main import get_group

from gwproactor_test.dummies.tree import scada1_cli

app = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    rich_markup_mode="rich",
    help="GridWorks Proactor Test CLI",
)

app.add_typer(scada1_cli.app, name="scada1", help="Use dummy scada1")


@app.command()
def helper(ctx: typer.Context) -> None:
    """CLI command builder."""
    Trogon(get_group(app), click_context=ctx).run()


@app.callback()
def main_app_callback() -> None: ...


# For sphinx:
typer_click_object = typer.main.get_command(app)

if __name__ == "__main__":
    app()
