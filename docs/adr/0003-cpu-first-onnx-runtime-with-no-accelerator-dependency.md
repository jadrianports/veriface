# 0003: CPU-first ONNX Runtime with no accelerator dependency

## Status

accepted

## Context and Problem Statement

The development machine (a Lenovo Yoga Slim 7, Ryzen AI 5 340) has no NVIDIA GPU, has a Radeon
840M integrated GPU, and has an XDNA 2 NPU. The project claims reproducibility on ordinary
hardware — "sub-100ms full pipeline on a thin-and-light laptop CPU" is meant to be a portable claim
a reader can reproduce, not a claim tied to this one machine's accelerator. This record settles
which execution path is the foundation every phase is built on, and which paths (if any) are
allowed to be optional.

## Decision Drivers

- **No CUDA path exists on this hardware** — any option requiring NVIDIA/CUDA is disqualified
  outright, not merely deprioritized.
- **Reproducibility** — a reader without this exact laptop should be able to run the pipeline.
- **Engineering time budget** — this is a solo project; accelerator tooling maturity matters as
  much as theoretical throughput.
- **Environment cleanliness** — `onnxruntime`, `onnxruntime-gpu`, and `onnxruntime-directml` all
  provide the same `onnxruntime` Python import namespace and conflict if installed together in one
  environment.

## Considered Options

- **(a) CPU-only ONNX Runtime** (the default CPU execution provider) as the one supported
  inference path for every phase.
- **(b) `onnxruntime-gpu` with a CUDA dependency** as the primary inference path.
- **(c) The DirectML execution provider** on the Radeon 840M integrated GPU as the primary
  inference path.
- **(d) The Ryzen AI NPU via the Vitis AI execution provider** as the primary inference path.

## Decision Outcome

Chosen option: **(a) CPU-only ONNX Runtime as the floor for every phase**, with (c) and (d) kept
available only as an explicitly-labeled, droppable stretch phase (Phase 7) that no earlier phase
may depend on.

- **Option (b) is disqualified by hardware, not by preference.** There is no NVIDIA GPU on this
  machine to target; `onnxruntime-gpu` would either silently no-op to CPU or hard-fail depending on
  version, and either way is dead weight to depend on.
- **The three `onnxruntime` distributions occupy the same import namespace and cannot coexist in
  one environment.** Choosing (a) as the baseline means the default project environment never
  needs to reconcile that conflict; any DirectML experiment must live in an isolated `uv`
  extra/venv rather than the default install.
- **Option (d), the Vitis AI NPU path, requires AMD Quark quantization (QDQ INT8 format) as a
  precondition** and has shipped multiple Windows-Update-delivered execution-provider point
  releases across 2026 — evidence of active but still-maturing tooling, not a stable target to
  build a roadmap phase around. Spending solo engineering time chasing a moving quantization and
  driver target, for a workload that is already inside its latency budget on plain CPU, is a poor
  trade.
- **Option (c), DirectML, is the more defensible of the two accelerator paths** — it is officially
  "sustained engineering" and broadly compatible with any DX12 GPU, including this Radeon 840M —
  but it is still not the reproducibility floor: a reader cloning this repository on a machine
  without a DX12-capable GPU (a cloud CI runner, for instance) must still get a working pipeline.
  That requirement can only be satisfied by (a).

CPU-only ONNX Runtime keeps the reproducibility claim honest for any reader, keeps CI
(`ubuntu-latest`, no GPU) able to exercise the real inference path rather than a mock, and matches
the measured latency budget already established on this hardware (sub-100ms full pipeline).

### Consequences

- **Good, because** every phase's tests and CI runs exercise the actual inference path with no
  GPU-specific skip logic.
- **Good, because** the accelerator question is fully deferred — nothing about detection,
  embedding, PAD, or matching design needs to anticipate a provider swap; ADR-0017 in Phase 1's
  `ARCHITECTURE.md` design already isolates all `onnxruntime` construction behind
  `models/runtime.py`, which is the natural swap point if Phase 7 happens.
- **Bad, because** this project forgoes any GPU/NPU speedup during core development, even though
  hardware capable of it is sitting in the same laptop — accepted because the workload is already
  well inside its latency budget on CPU.
- **Bad, because** if Phase 7's DirectML experiment is ever promoted out of stretch status, it
  will need its own isolated dependency environment and its own CI job, since the three
  `onnxruntime` variants cannot share one environment.

## More Information

Source: `.claude/CLAUDE.md` §"What NOT to Use" (`onnxruntime-gpu` and Vitis AI EP rows) and
§"Stack Patterns by Variant" (the DirectML-first, Vitis-AI-as-follow-on recommendation);
`.planning/PROJECT.md` §"Hardware and environment" and §"Constraints".
