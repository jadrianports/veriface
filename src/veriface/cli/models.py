"""``veriface models`` subcommand group — drives ``ModelRegistry`` (D-11)."""

from __future__ import annotations

import typer

from veriface.config import get_settings
from veriface.errors import ArtifactNotCachedError, VerifaceError
from veriface.hashing import sha256_file
from veriface.models.registry import ModelRegistry
from veriface.models.sources import resolve_source
from veriface.models.specs import PROFILES

models_app = typer.Typer(no_args_is_help=True)


@models_app.command()
def fetch(profile: str = "default") -> None:
    """Download every artifact declared in ``profile``."""
    settings = get_settings()
    failed = False
    for spec in PROFILES[profile]:
        try:
            source = resolve_source(spec)
            resolved_path = source.materialize(spec, settings.cache_dir, allow_download=True)
        except VerifaceError as exc:
            typer.echo(f"{spec.name}  FAILED  {exc}")
            failed = True
            continue
        typer.echo(f"{spec.name}  {resolved_path}")
    if failed:
        raise typer.Exit(code=1)


@models_app.command()
def verify(profile: str = "default") -> None:
    """Verify every cached artifact declared in ``profile`` against its pin.

    Iterates ``PROFILES[profile]`` in tuple order — never sorted or
    set-ified — so repeated runs produce byte-identical stdout ordering.
    """
    registry = ModelRegistry(get_settings())
    any_failed = False
    for spec in PROFILES[profile]:
        try:
            cached_path = registry.path(spec)
        except ArtifactNotCachedError as exc:
            typer.echo(f"{spec.name}  MISSING  {exc}")
            any_failed = True
            continue
        computed = sha256_file(cached_path)
        if computed == spec.sha256:
            typer.echo(f"{spec.name}  OK")
        else:
            typer.echo(f"{spec.name}  MISMATCH expected={spec.sha256} actual={computed}")
            any_failed = True
    if any_failed:
        raise typer.Exit(code=1)
