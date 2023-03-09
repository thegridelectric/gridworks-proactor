"""Command-line interface."""
import click


@click.command()
@click.version_option()
def main() -> None:
    """Gridworks Proactor."""


if __name__ == "__main__":
    main(prog_name="gridworks-proactor")  # pragma: no cover
