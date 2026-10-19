"""The ``plate`` command line.

The application is assembled from the command modules listed in :data:`COMMANDS`; each
module exposes ``HELP`` and either ``app`` (a command group) or ``command`` (a single
command). Modules import their heavy dependencies (OpenCV, PyTorch, Ultralytics) inside
the command bodies, so ``plate --help`` and the light commands start quickly.
"""

from __future__ import annotations

import importlib
from typing import Final, Literal

import typer

app = typer.Typer(
    name="plate",
    help="Moroccan licence-plate reading platform. Runs fully offline.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)

Kind = Literal["group", "command"]

#: (module, command name, kind). A module that does not exist yet is skipped, so a
#: milestone's commands land together with the module that implements them.
COMMANDS: Final[tuple[tuple[str, str, Kind], ...]] = (
    ("read", "read", "command"),
    ("data", "data", "group"),
    ("docs", "docs", "group"),
    ("synth", "synth", "group"),
    ("evaluate", "eval", "command"),
    ("eval_detector", "eval-detector", "command"),
    ("compare", "compare-crnn", "command"),
    ("train", "train", "group"),
    ("export", "export", "group"),
    ("registry", "registry", "group"),
    ("sweep", "sweep", "command"),
)


@app.command("version")
def version() -> None:
    """Print the package version."""
    from .. import __version__

    typer.echo(__version__)


def _register() -> list[str]:
    registered: list[str] = []
    for module_name, name, kind in COMMANDS:
        qualified = f"{__name__}.{module_name}"
        try:
            module = importlib.import_module(qualified)
        except ModuleNotFoundError as exc:
            if exc.name != qualified:
                raise
            continue
        if kind == "group":
            app.add_typer(module.app, name=name, help=module.HELP)
        else:
            app.command(name, help=module.HELP)(module.command)
        registered.append(name)
    return registered


REGISTERED: Final = tuple(_register())


def main() -> None:
    app()


__all__ = ["COMMANDS", "REGISTERED", "app", "main"]
