"""``veriface data`` subcommand group (D-11).

Mounted behind ``veriface.cli``'s ``_try_mount`` seam — this module (and
therefore anything importing it) must never be imported unconditionally by
``veriface`` core.
"""

from __future__ import annotations

import typer

from veriface.config import get_settings
from veriface.errors import VerifaceError
from veriface_eval.datasets import config as dataset_config
from veriface_eval.datasets.lfw import fetch_lfw

data_app = typer.Typer(no_args_is_help=True)
manifest_app = typer.Typer(no_args_is_help=True)
data_app.add_typer(manifest_app, name="manifest")

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


@manifest_app.command()
def verify(tier: str = typer.Option(..., "--tier", help="Dataset tier (eval or extended)")) -> None:
    """Re-check ``tier``'s committed manifest digest against its recorded pin (D-25)."""
    try:
        dataset_config.load_dataset_config(tier)
    except VerifaceError as exc:
        typer.echo(f"{tier}  MISMATCH  {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(f"{tier}  OK")


@manifest_app.command()
def build(
    tier: str = typer.Option(..., "--tier", help="Dataset tier (eval or extended)"),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing committed manifest"),
) -> None:
    """Regenerate ``tier``'s manifest from an extracted label index.

    Refuses to overwrite an existing committed manifest unless ``--force`` is
    passed — regenerating invalidates every metric computed against the old
    manifest (D-19). This plan wires only the refusal path; plan 01-07 wires
    the real CelebA-Spoof label index that a successful build consumes.
    """
    try:
        manifest_path = dataset_config.manifest_path_for(tier)
    except VerifaceError as exc:
        typer.echo(f"{tier}  FAILED  {exc}")
        raise typer.Exit(code=1) from exc

    if manifest_path.exists() and not force:
        typer.echo(
            f"{tier}  REFUSED  {manifest_path} already exists; pass --force to overwrite "
            "(regenerating invalidates every metric computed against the old manifest)."
        )
        raise typer.Exit(code=1)

    typer.echo(f"{tier}  NOT YET IMPLEMENTED — see plan 01-07 for the real label index source")
    raise typer.Exit(code=1)
