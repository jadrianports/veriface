# 0001: Rebuild rather than refresh the 2017 stack

## Status

accepted

## Context and Problem Statement

`veriface` is a deliberate 2026 rebuild of Cole Murray's 2017 HackerNoon tutorial "Building a
Facial Recognition Pipeline with Deep Learning in Tensorflow": LFW → Dlib HOG detector (largest
face only) → 68-point landmarks → affine alignment → Inception-ResNet-V1 / FaceNet frozen
TensorFlow 1 `.pb` graph → 128-D triplet-loss embedding → a scikit-learn SVM classifier. The
conceptual spine — faces map to embeddings in a shared vector space, distance is similarity — is
still correct. The question this record settles is whether that spine should be kept running under
its original 2017 components, or rebuilt on a different set of components entirely. This decision
is the one DOCS-04 names explicitly: the ADR trail exists to prove the 2017 design was understood
and weighed, not merely dismissed.

## Decision Drivers

- **Buildability today** — does the code path still run on a current toolchain?
- **Open-set capability** — can the system say "unknown" without retraining?
- **Embedding quality** — how good is the representation on modern benchmarks?
- **CPU viability** — this project has no NVIDIA GPU; every component must run acceptably on a
  6-core/12-thread CPU.

## Considered Options

- **(a) Refresh the 2017 stack in place** — port the TensorFlow 1 frozen graph forward onto a
  current TensorFlow release, keep Dlib HOG for detection and 68-point landmarks for alignment,
  keep the 128-D triplet-loss FaceNet embedder, keep the closed-set SVM.
- **(b) Rebuild on the modern ONNX spine** — SCRFD for detection (5-point landmarks included),
  ArcFace `buffalo_l`/`w600k_r50` for 512-D embeddings, ONNX Runtime (CPU execution provider) as
  the inference engine, with the classifier question deferred to ADR 0002.
- **(c) Adopt a hosted face-recognition API** (a cloud vendor's face-match endpoint) instead of
  running any local model.

## Decision Outcome

Chosen option: **(b) rebuild on the modern ONNX spine**, because each component of option (a) has
a specific, named failure that option (b) does not share, and option (c) forecloses the project's
own stated purpose.

- **TensorFlow 1 frozen graphs and the `tf.train` queue API were removed from modern TensorFlow.**
  This is not a performance regression to tolerate — the 2017 pipeline is literally unbuildable on
  a current TensorFlow install. There is no "refresh," only a from-scratch reimplementation of a
  graph-freezing and queue-based input pipeline that upstream TensorFlow no longer supports.
- **Dlib HOG detection fails on profile, small, and low-light faces.** SCRFD was designed
  specifically to match RetinaFace-level detection accuracy at 3–10x the speed via sample and
  computation redistribution, and ships 5-point landmarks natively — the exact input ArcFace's
  standard alignment expects — so no separate landmark model is needed.
  In a system whose core value includes rejecting spoofs, a missed detection at the front of the
  pipeline is a silent false rejection downstream, not a cosmetic weakness.
- **128-D triplet-loss embeddings are inferior to 512-D margin-softmax embeddings on every modern
  benchmark.** ArcFace's additive angular margin loss, at 512 dimensions, is the reference
  architecture underpinning nearly every open-weight face model shipped as of this decision
  (AdaFace, GhostFaceNets, and EdgeFace all train the same margin-loss family on top of it) — this
  is a two-generation gap in representation quality, not an incremental one.
- **Option (c) is rejected outright.** A hosted API removes the CPU-first reproducibility claim,
  introduces a third-party data-processing dependency for biometric images (in direct tension with
  the project's consent/deletion requirements), and eliminates the actual engineering surface —
  quality gating, calibration, PAD, template protection — that is this project's stated purpose.
  "Call someone else's face API" is not a rebuild of the 2017 pipeline; it is a different project.

Every onnxruntime-based component in option (b) is CPU-viable within the sub-100ms full-pipeline
budget already measured on this hardware, satisfying the CPU-viability driver that ruled out
keeping any GPU-only path.

### Consequences

- **Good, because** the pipeline is buildable today, on this hardware, with no CUDA dependency, and
  the recognition backbone is a materially stronger representation than the 2017 tutorial's.
- **Good, because** SCRFD's native 5-point landmark output removes an entire model (68-point
  landmarking) from the pipeline rather than replacing it with an equivalent.
- **Bad, because** the modern spine's strongest openly available weights (ArcFace `buffalo_l`)
  carry a non-commercial research license the 2017 stack's components did not — see ADR 0005 for
  the licensing posture this forces and what it forecloses.
- **Bad, because** rebuilding rather than refreshing means none of the 2017 tutorial's code is
  reusable; this is a from-scratch implementation across detection, alignment, embedding, and
  matching (matching is ADR 0002's decision).

## More Information

Source: `.claude/CLAUDE.md` §"What NOT to Use" (the three rejected 2017 components and their
specific reasons) and §"Technology Stack" (SCRFD/ArcFace rationale); `.planning/PROJECT.md`
§"Why it needs replacing, not refreshing".
