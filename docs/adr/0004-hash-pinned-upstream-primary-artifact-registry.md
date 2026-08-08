# 0004: Hash-pinned, upstream-primary artifact registry

## Status

accepted

## Context and Problem Statement

The 2017 tutorial's failure mode for artifacts was structural, not incidental: download an opaque
binary, trust it, never re-check it. This project's four default-profile artifacts (SCRFD
detector, ArcFace embedder, and two MiniFASNet PAD variants) need an identity that is checkable
end to end — what exact bytes are loaded, where they came from, and whether they still match what
was pinned. This record settles how artifacts are sourced, verified, and (deliberately) never
redistributed.

## Decision Drivers

- **OPS-04** — no biometric-adjacent binary is committed to the repository.
- **Provenance as a first-class deliverable** — the license matrix's source column must name a
  real, checkable upstream location, not a personal restatement of one.
- **Recoverability** — an upstream URL moving or disappearing should be a fast fix, not a project
  blocker.
- **Verification cost** — must be cheap enough to run unconditionally, every load, with no
  environment escape hatch to justify or review later.

## Considered Options

- **(a) Commit the weights to the repository.**
- **(b) Self-mirror the weights under a personal namespace** (e.g. a personal Hugging Face Hub
  account) and fetch from there.
- **(c) Fetch upstream-primary at runtime, with a pinned revision and a pinned SHA-256 digest,
  redistributing nothing.**
- **(d) Fetch upstream at runtime with no pinning** (always the latest release/tag).

## Decision Outcome

Chosen option: **(c) fetch upstream-primary with pinned revision and pinned digest.**

- **(a) is disqualified by OPS-04 and by licensing.** ArcFace's `buffalo_l` weights carry a
  non-commercial research license (see ADR 0005); committing them to a public repository makes the
  repository itself a redistribution channel for restricted-license binaries, not merely a
  convenience.
- **(b) would rewrite the exact artifact this phase exists to produce.** The license matrix's
  source column is meant to say `InsightFace model zoo @ revision X` — a claim a reader can
  independently verify against the real upstream. Rewriting that to `personal mirror @ revision Y`
  degrades the provenance record from a checkable fact to an assertion resting on this project's
  own credibility, which is the opposite of what a provenance table is for.
- **(d) leaves nothing to verify.** Without a pinned revision and digest, "the artifact loaded
  correctly" is unfalsifiable — a silently different upstream release would be indistinguishable
  from the one actually evaluated.
- **(c) is the only option that keeps the artifact checkable, redistributes nothing, and survives
  an upstream move.** A URL or hosting change becomes a spec repoint (one row in
  `src/veriface/models/specs.py`), and a re-release with different bytes at the same pinned
  location is a loud `ArtifactIntegrityError` naming the expected and computed digests, never a
  silent substitution.

**Verification design.** Every artifact is re-verified with a full SHA-256 over its bytes on
*every* `ModelRegistry.load()` call — no caching of a prior result, no `mtime`/size shortcut, and
no environment-variable bypass. Measured cost is roughly 0.2–0.4s per process for artifacts in the
tens-to-hundreds-of-MB range, negligible next to constructing the ONNX session itself. That cost
being genuinely trivial is what makes the strict version (always re-verify, no bypass) the easy
choice rather than a tradeoff to defend.

**Be honest about the asymmetry between the two source legs — this is the fact this record exists
to preserve.** The registry has two source mechanisms (`hf` and `https`), and they do not carry
the same integrity guarantee:

- The one artifact fetched through the `hf` leg (a MiniFASNet PAD ONNX port on Hugging Face Hub)
  is pinned by full commit hash *and* was cross-checked at pinning time against the Hub's own
  recorded LFS object hash for that file — an independent second source for the digest, not just
  the value this project itself computed.
- The three artifacts fetched through the `https` leg — the SCRFD detector and ArcFace embedder,
  both extracted from InsightFace's own `buffalo_l.zip` release archive, and the second MiniFASNet
  PAD variant, a direct-file GitHub Release asset — have **no independently published checksum to
  cross-check against**. Their pins are **trust-on-first-use**: the SHA-256 recorded in
  `specs.py` is exactly the digest of the bytes this project observed at the moment they were
  first downloaded and pinned, re-verified identically on every subsequent load, but with no
  second party's checksum to corroborate that the bytes were correct *at that first moment*. This
  is mitigated by re-verification on every load (so corruption or tampering *after* pinning is
  always caught) and by a private, offsite archive of the exact verified bytes — maintained
  separately by the author, referenced nowhere in this repository and not part of any code path —
  so recovering from an upstream disappearance never depends on trusting a second download.

Do not read this record as claiming uniform integrity across all four artifacts: one leg has an
independent corroborating source for its digest, the other three do not, and the registry's design
(full re-verification, every load, no bypass) is what carries the weight for the trust-on-first-use
legs rather than a second-source checksum.

### Consequences

- **Good, because** an upstream URL move is a minutes-long spec repoint, not a blocker — the
  registry's design already treats "where do I fetch this from" as data, not code.
- **Good, because** an upstream re-release with different bytes at the same pinned location fails
  loudly (`ArtifactIntegrityError` naming spec, expected digest, and computed digest) rather than
  silently substituting a different model into a running system.
- **Bad, because** three of the four default-profile artifacts have no independent checksum to
  corroborate the pin — an attacker or a corrupted download in the narrow window between "the
  project resolves the upstream URL" and "the project computes and records the digest" would not
  be caught by this design alone. The private offsite archive and the never-cached re-verification
  are the accepted mitigations, not a claim this gap doesn't exist.
- **Bad, because** the registry can never present a single uniform provenance-strength claim for
  the whole default profile — any future documentation (README, license matrix, this ADR) must
  keep stating the two legs' guarantees separately rather than rounding them together.

## More Information

Source: `.planning/phases/01-foundation-artifacts-data-strategy/01-CONTEXT.md` D-06 through D-09;
`.planning/phases/01-foundation-artifacts-data-strategy/01-01-SUMMARY.md` (the `minifasnet_v2se`
Hub cross-check); `.planning/phases/01-foundation-artifacts-data-strategy/01-02-SUMMARY.md`
Deviations §1 and Issues Encountered (the `minifasnet_v1se` substitution and its trust-on-first-use
provenance chain, and the InsightFace `buffalo_l.zip` archive's lack of a published checksum);
`.planning/research/PITFALLS.md` §"Pitfall 6" (download-at-runtime-never-redistribute).
