"""OPS-04, direct test: no weight, archive, or dataset image byte is trackable by git.

Shells out through ``subprocess`` for every assertion — a non-zero exit from
the git invocation itself is a test failure, never silently swallowed into a
passing assertion (the plan's own instruction for this file).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Weight, archive, and dataset-image extensions OPS-04 must keep out of
# `git ls-files` forever. `.tar.gz` is checked separately below since the
# regex would otherwise need to special-case the two-extension suffix.
_FORBIDDEN_EXTENSION_PATTERN = re.compile(r"\.(onnx|pb|pth|pkl|zip|zip\.\d+|tgz|jpg|jpeg|png)$")


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"git {' '.join(args)} failed (exit {result.returncode}): {result.stderr}"
    )
    return result


def test_no_forbidden_extension_is_tracked() -> None:
    tracked = _run_git("ls-files").stdout.splitlines()
    offenders = [path for path in tracked if _FORBIDDEN_EXTENSION_PATTERN.search(path)]
    offenders += [path for path in tracked if path.endswith(".tar.gz")]
    assert offenders == [], f"Forbidden dataset/model paths tracked by git: {offenders}"


def test_data_directory_is_ignored() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "data/lfw/lfw_funneled/dummy.jpg"],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0, "data/ is not gitignored"


def test_models_directory_is_ignored() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "models/foo.onnx"],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0, "models/ is not gitignored"


def test_dataset_archive_extensions_are_ignored_anywhere() -> None:
    """The archive-extension patterns added this plan are unanchored on purpose.

    Checked against a path that is *not* under an already-anchored directory
    (`data/`, `models/`) to prove the extension patterns themselves do the
    work, not the directory anchors.
    """
    for candidate in (
        "scratch/lfw-funneled.tgz",
        "scratch/CelebA_Spoof.zip",
        "scratch/CelebA_Spoof.zip.001",
        "scratch/lfw.tar.gz",
    ):
        result = subprocess.run(
            ["git", "check-ignore", "-q", candidate],
            cwd=REPO_ROOT,
            check=False,
        )
        assert result.returncode == 0, f"{candidate} is not gitignored"


def test_committed_manifest_directory_is_not_ignored() -> None:
    """The negation added this plan actually works.

    A manifest path does not need to exist on disk yet (plan 01-07 commits
    the first real one) for `git check-ignore` to answer the question — it
    operates purely on the pattern match.
    """
    result = subprocess.run(
        ["git", "check-ignore", "-q", "src/veriface_eval/datasets/manifests/celeba_spoof_eval.csv"],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 1, (
        "the committed manifest directory is ignored — the negation pattern did not take effect"
    )


def test_model_cache_directory_is_structurally_outside_the_repo() -> None:
    """D-13's cache dir is an OS-user-global location, never a repo-relative path.

    ``git check-ignore`` cannot answer "is the cache directory excluded" for
    a path outside the working tree at all — git fatally refuses to evaluate
    ignore rules against a path outside the repository (confirmed live this
    session; invoking it here would be exactly the "swallowed non-zero exit"
    this file's docstring forbids). The correct, stronger guarantee for an
    out-of-tree default is structural: no `git add` can ever reach it,
    regardless of any ignore pattern, because it is never inside the working
    tree to begin with.
    """
    from veriface.config import default_cache_dir

    cache_dir = default_cache_dir().resolve()
    repo_root = REPO_ROOT.resolve()
    assert repo_root != cache_dir and repo_root not in cache_dir.parents, (
        f"default_cache_dir() {cache_dir} resolves inside the repository {repo_root} — "
        "D-13 requires the model cache to live outside the working tree entirely"
    )
