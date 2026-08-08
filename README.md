# veriface

[![CI](https://github.com/jadrianports/veriface/actions/workflows/ci.yml/badge.svg)](https://github.com/jadrianports/veriface/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![License: Apache-2.0](https://img.shields.io/github/license/jadrianports/veriface)](LICENSE)
[![Model weights: non-commercial research](https://img.shields.io/badge/model_weights-non--commercial_research-critical)](#licensing)

Open-set face recognition + presentation-attack detection for Python.
CPU-only, ONNX Runtime, `pip install`-able.

- Explicit **unknown** rejection, not a closed-set classifier
- Passive PAD + active challenge–response
- FMR/FNMR · DET · APCER/BPCER/ACER — no bare accuracy

> ⚠️ Non-commercial research use only — see Licensing.

## Quickstart

Nothing downloads implicitly: `import veriface` never touches the network. Every model and
dataset artifact arrives only through an explicit, named command below.

```bash
git clone https://github.com/jadrianports/veriface
cd veriface
uv sync --all-extras

uv run veriface models fetch      # downloads + hash-verifies the default model profile
uv run veriface models verify     # re-checks every cached artifact's SHA-256
uv run veriface data fetch lfw    # downloads + hash-verifies the LFW benchmark set
```

`veriface` is not yet published to PyPI (see `docs/adr/0006-*.md` for the package layout that
Phase 6 publishes); until then, installing from a clone as above is the supported path.

## Licensing

`veriface`'s own source code is licensed under [Apache-2.0](LICENSE). Several of the model
artifacts in the default profile are **not**: they carry a non-commercial-research-only license
from their own publisher, independent of this project's Apache-2.0 grant. A permissive *code*
license on a model's repository does not transfer to weights trained on restricted data — see
[ADR 0005](docs/adr/0005-non-commercial-licensing-posture.md) for the full reasoning and exactly
what this forecloses. Every third-party artifact's terms are also enumerated verbatim in
[`NOTICE`](NOTICE), generated from the same spec table this matrix is generated from.

**The default profile, as configured, is not commercially usable.** A commercial deployment would
need either a commercial license from InsightFace for the affected weights, or a swap to a profile
built entirely from artifacts with clean commercial terms.

The table below is generated directly from `src/veriface/models/specs.py` by
`veriface docs licenses --format matrix` and re-diffed by
[`tests/unit/test_docs_generated.py`](tests/unit/test_docs_generated.py) on every run — it cannot
drift from what `veriface models fetch` actually fetches without failing that test.

<!-- BEGIN licence-matrix -->
| Artifact | Source | Revision | Licence | Training data |
| --- | --- | --- | --- | --- |
| scrfd_10g_bnkps | https (github.com) | v0.7 | InsightFace model zoo — non-commercial research use only | InsightFace-curated detection training sets |
| arcface_w600k_r50 | https (github.com) | v0.7 | InsightFace model zoo — non-commercial research use only | MS1MV2/MS1MV3-family refined sets, cleaned derivatives of the withdrawn MS-Celeb-1M |
| minifasnet_v1se | https (github.com) | weights | Apache-2.0 | Minivision AI's own presentation-attack-detection dataset, via minivision-ai/Silent-Face-Anti-Spoofing (MiniFASNetV1SE, 4.0_80x80). ONNX conversion by yakhyo/face-anti-spoofing (Apache-2.0), a direct re-export of the same upstream .pth weights — no HF Hub ONNX port of V1SE exists (verified during plan 01-02; see 01-02-SUMMARY.md). Not derived from MS-Celeb-1M or any face-recognition training corpus. |
| minifasnet_v2se | hf (huggingface.co) | d29c87568ca9 | Apache-2.0 | Minivision AI's own presentation-attack-detection dataset, via minivision-ai/Silent-Face-Anti-Spoofing (MiniFASNetV2, 2.7_80x80). ONNX conversion by garciafido/minifasnet-v2-anti-spoofing-onnx on Hugging Face Hub, weights bit-equivalent to upstream .pth, format-converted only. Not derived from MS-Celeb-1M or any face-recognition training corpus. |
<!-- END licence-matrix -->

## Artifact recovery

Every artifact is identified by its spec row in `src/veriface/models/specs.py` — `source`,
`locator`, `revision`, and a pinned SHA-256 digest — not by wherever it currently happens to live.
If an upstream URL moves or a release disappears, recovery is a one-line spec repoint: update
`locator`/`revision` to the new location, keep the recorded `sha256` if the replacement bytes are
identical, or pin a freshly verified digest if they are not, then run `veriface models verify`
against the repointed spec. The digest is what identifies the correct bytes; the URL is only where
they currently happen to be found.

### Recovering a corrupted local cache

`veriface models verify --profile <profile>` hashes every cached artifact against its pin and
prints `<name>  MISMATCH expected=<pin> actual=<computed>` for anything that fails, exiting
non-zero. `veriface models fetch --profile <profile>` is the repair command: it hashes each cached
artifact before reporting it as fetched, re-downloads exactly the ones that fail their pin, and
prints `<name>  REPAIRED  <path>` for anything it had to repair — an already-correct artifact still
prints the plain `<name>  <path>` line, unchanged. Re-run `veriface models verify` afterward to
confirm the repair.

If `fetch` still reports an artifact as `FAILED` after that re-download, the freshly downloaded
bytes miss the pin too — that is upstream drift, not local corruption, and a re-download loop
cannot fix it. Do not edit the recorded `sha256` to match whatever arrived. Treat it as the spec-
repoint case above: verify the correct digest independently first, then repoint the spec.

## Status

Phase 1 (foundation, artifacts, and data strategy) is in progress. No detection, alignment,
embedding, matching, or PAD inference code exists yet — this phase proves that model artifacts and
datasets load and verify, nothing more. Capability claims, accuracy numbers, and latency figures
arrive with the phases that measure them.
