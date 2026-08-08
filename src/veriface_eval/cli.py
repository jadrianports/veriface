"""``veriface data`` subcommand group (D-11).

Mounted behind ``veriface.cli``'s ``_try_mount`` seam — this module (and
therefore anything importing it) must never be imported unconditionally by
``veriface`` core.
"""

from __future__ import annotations

import typer

from veriface.config import get_settings
from veriface.errors import VerifaceError
from veriface_eval.datasets.lfw import fetch_lfw

data_app = typer.Typer(no_args_is_help=True)

_KNOWN_DATASETS = ("lfw", "celeba-spoof")


@data_app.command()
def fetch(dataset: str, tier: str = "eval") -> None:
    """Materialize ``dataset`` under ``VERIFACE_DATA_DIR`` (D-24).

    Never accepts a raw destination path — the destination is always
    resolved through ``get_settings().data_dir`` so a caller cannot write
    outside the configured data tree.
    """
    if dataset not in _KNOWN_DATASETS:
        typer.echo(
            f"{dataset}  FAILED  Unknown dataset {dataset!r}; known: {', '.join(_KNOWN_DATASETS)}"
        )
        raise typer.Exit(code=1)

    settings = get_settings()

    if dataset == "lfw":
        try:
            dest = fetch_lfw(settings.data_dir, allow_download=True)
        except VerifaceError as exc:
            typer.echo(f"lfw  FAILED  {exc}")
            raise typer.Exit(code=1) from exc
        typer.echo(f"lfw  {dest}")
        return

    # dataset == "celeba-spoof": not yet materialised in this plan — plan
    # 01-07 replaces this body with a real fetcher wired to the real
    # CelebA-Spoof label index and the `--tier` option declared above.
    typer.echo(f"celeba-spoof  NOT YET MATERIALISED (tier={tier!r}) — see plan 01-07")
    raise typer.Exit(code=1)
