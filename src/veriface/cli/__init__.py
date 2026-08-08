"""The ``veriface`` console script — composition root (D-11).

A module-level ``app`` mounts each subcommand group explicitly (name
inference from the callback is deprecated in current typer, so every mount
passes ``name=`` explicitly). Later plans mount ``docs`` (plan 01-02) and
``data`` (plan 01-04) here; the ``data`` group is mounted behind
``_try_mount`` because ``veriface_eval`` — and therefore its dependencies —
may not be installed if the ``[eval]`` extra was skipped.
"""

from __future__ import annotations

import importlib
from typing import Any

import typer

from veriface.cli.models import models_app

app = typer.Typer(no_args_is_help=True)
app.add_typer(models_app, name="models")


def _try_mount(module_path: str, attr: str, name: str) -> None:
    """Mount ``module_path.attr`` under ``name`` if ``module_path`` is installed.

    Swallows only ``ModuleNotFoundError`` — any other import-time failure
    (a real bug in the optional module) is not hidden.
    """
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        return
    sub_app: Any = getattr(module, attr)
    app.add_typer(sub_app, name=name)


# Future mounts (not yet implemented — do not pre-declare an import for a
# module that does not exist yet):
#   _try_mount("veriface_eval.cli", "data_app", "data")   — plan 01-04
#   app.add_typer(docs_app, name="docs")                  — plan 01-02


if __name__ == "__main__":
    app()
