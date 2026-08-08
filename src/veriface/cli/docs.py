"""``veriface docs`` subcommand group — renders the license matrix and NOTICE (D-37)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from veriface.licensing import render_license_matrix, render_notice

docs_app = typer.Typer(no_args_is_help=True)

DocsFormat = Literal["matrix", "notice"]


@docs_app.command()
def licenses(
    format: Annotated[DocsFormat, typer.Option("--format", help="matrix or notice")] = "matrix",
    out: Annotated[
        Path | None, typer.Option("--out", help="Write to this path instead of stdout")
    ] = None,
) -> None:
    """Render the per-artifact license matrix or the Apache-2.0 NOTICE body.

    With no ``--out``, prints to stdout. With ``--out``, writes the file and
    prints the path — used by plan 01-05 to generate README's matrix section
    and the NOTICE file, and by its drift test to re-run this command and
    diff the result.
    """
    content = render_license_matrix() if format == "matrix" else render_notice()
    if out is not None:
        out.write_text(content, encoding="utf-8")
        typer.echo(str(out))
    else:
        typer.echo(content, nl=False)
