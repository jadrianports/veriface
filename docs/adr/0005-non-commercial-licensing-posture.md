# 0005: Non-commercial licensing posture

## Status

accepted

## Context and Problem Statement

The strongest openly downloadable face-recognition weights available to this project — InsightFace's
`buffalo_l`/`w600k_r50` (ArcFace) and the SCRFD detector it ships alongside — carry a stated
non-commercial-research-only license, while `veriface` itself is a public portfolio repository the
author intends anyone to be able to clone, read, and run. This record settles what license the
project's own code carries, how the mismatch between "project code" and "bundled model terms" is
represented, and what a reader is and is not entitled to do with the result.

## Decision Drivers

- **Honesty over convenience** — a licensing story that reads clean but misrepresents what a user
  may actually do is worse than one that states a real restriction plainly.
- **Attribution mechanics** — third-party artifact terms must be discoverable without reading this
  project's source code line by line.
- **Portfolio intent** — the repository is meant to be read and evaluated as engineering work, not
  distributed as a ready-to-deploy commercial product.

## Considered Options

- **(a) Apache-2.0 project code with a `NOTICE` file enumerating each third-party artifact's
  actual terms**, separately from the project's own license.
- **(b) Adopt the most restrictive artifact's license as the project's own license** (i.e., mark
  the whole repository non-commercial-only).
- **(c) Choose only artifacts with clean, unambiguous commercial terms** and accept whatever
  accuracy or capability cost that constrains the project to.
- **(d) Say nothing explicit about licensing beyond a generic repository license** and let a user
  work out the artifact terms themselves.

## Decision Outcome

Chosen option: **(a) Apache-2.0 with a `NOTICE` file.**

The Apache-2.0 `NOTICE` mechanism exists precisely for this situation — attributing bundled or
depended-upon components whose terms differ from the covering project's own license — so adopting
it carries the central licensing fact in the license format itself, rather than inventing an ad
hoc convention this project would have to explain from scratch. It also grants an explicit patent
license, which is directly relevant for security/biometric code where a patent claim against a
detection or matching technique is a real (if unlikely) risk category the 2017 tutorial's
implicit-license posture never addressed. Apache-2.0 also matches the one artifact in this stack
with the cleanest license story — Silent-Face-Anti-Spoofing/MiniFASNet is itself Apache-2.0 —
which is a coherent default for the project's own code even though it does not resolve the other
artifacts' terms.

Option (b) was rejected because marking the whole repository non-commercial would misstate the
actual situation: the project's *own* code (the registry, the CLI, the FastAPI adapter, the
matching logic) has no such restriction — only specific bundled model weights do. Blurring that
distinction makes the license less informative, not more honest.

Option (c) was rejected in ADR 0001 already, in effect: the whole point of choosing ArcFace over a
demonstrably weaker but cleanly licensed alternative was that the engineering value of this
project is in the system built around the embedding, not in re-deriving a weaker one to dodge a
license. Revisiting that tradeoff here would contradict ADR 0001's own reasoning.

Option (d) was rejected because it fails the honesty driver directly — a reader should not have to
independently research four separate upstream license pages to learn that the default profile is
not commercially usable as shipped.

**What this posture forecloses, stated plainly:** the default model profile (SCRFD, ArcFace
`buffalo_l`, and any InsightFace-sourced artifact) is **not commercially usable** as configured. A
commercial deployment would need either a commercial license from InsightFace for the affected
weights, or a swap to a profile built entirely from artifacts with clean commercial terms — which
this project's source-agnostic, profile-keyed spec design (ADR 0004; D-10) makes a data change
rather than an architectural one, but which has not been done here.

**The licence-laundering caveat, named explicitly as a trap:** a permissive code license on a
model's *repository* does not transfer to weights trained on restricted data. A repository stating
"MIT" for its code is not evidence that its published weights are unrestricted — several
community model ports (documented in `.claude/CLAUDE.md`'s licensing table, e.g. GhostFaceNets)
carry an MIT code license over weights trained on MS1MV2/MS1MV3, which is itself governed by
InsightFace's non-commercial data policy. Verify the *weights'* provenance and terms per artifact,
never infer it from the surrounding code's license file.

This record states licensing **structure**, not legal advice. The actual current terms of every
bundled artifact must be read directly from its upstream source before this repository, or any
fork of it, is used commercially.

### Consequences

- **Good, because** the `NOTICE` file gives every reader a single place to see which components
  carry which terms, generated directly from the same artifact specs that drive fetching and
  verification (ADR 0004), so it cannot silently drift from what is actually fetched.
- **Good, because** Apache-2.0's explicit patent grant covers this project's own code even though
  it says nothing about the bundled models' patent posture, which remains whatever InsightFace's
  own terms state.
- **Bad, because** the default profile cannot be presented as "commercially usable" in any
  marketing or portfolio framing without a caveat — this must be repeated everywhere the project
  is described (README, this ADR, any future release notes), not stated once and assumed to
  travel.
- **Bad, because** a future contributor adding a new artifact to a profile must re-verify its
  weight license independently of its code license every time — this is not a one-time cost this
  ADR discharges, it is a standing obligation the `NOTICE` generator's required-fields check
  (D-37) only partially automates (it enforces that a license field is *present*, not that it was
  *correctly researched*).

## More Information

Source: `.claude/CLAUDE.md` §"Licensing — first-class deliverable" (the per-artifact verdict table
and the GhostFaceNets license-laundering example); `.planning/phases/01-foundation-artifacts-data-strategy/01-CONTEXT.md`
D-36 and D-37; `.planning/research/PITFALLS.md` §"Pitfall 6".
