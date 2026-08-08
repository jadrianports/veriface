# 0002: Open-set matching over a closed-set classifier

## Status

accepted

## Context and Problem Statement

The system's core value statement requires it to answer "who is this, and is it actually a live
human" — including the case where the answer is nobody it knows. The 2017 tutorial ended its
pipeline with a scikit-learn SVM trained on the embeddings of a fixed set of enrolled classes.
This record settles what replaces that classifier and why the replacement is not merely a
different model of the same shape.

## Decision Drivers

- **Open-set requirement** — the system must be able to output "unknown," not just a best guess
  among enrolled identities.
- **Enrollment cost** — adding a new identity should not require retraining anything.
- **Calibration honesty** — a score threshold must be explainable and tunable against a stated
  false-match/false-non-match operating point, not baked into an opaque classifier boundary.

## Considered Options

- **(a) A scikit-learn SVM over embeddings**, as the 2017 tutorial used — one classifier trained
  on the enrolled gallery's labeled embeddings.
- **(b) Calibrated cosine similarity against gallery embeddings**, with an explicit unknown
  threshold — every enrolled identity contributes a gallery embedding (or centroid); a probe is
  compared by cosine distance to the gallery, and a calibrated threshold decides match vs.
  unknown.
- **(c) A learned open-set classifier** (e.g., an out-of-distribution detector trained alongside
  the recognition embedding) that outputs both an identity and an explicit unknown class.

## Decision Outcome

Chosen option: **(b) calibrated cosine similarity against gallery embeddings**, because option (a)
is not a weaker version of the open-set requirement — it is architecturally incompatible with it.

An SVM forces the system **closed-set**: every input must be assigned to one of the classes seen
at training time, enrolling a new identity requires retraining the classifier from scratch, and
there is no "unknown" output at all — the model always predicts *something*. This is fatal for
anything auth-shaped: an auth system that predicts a false identity for a stranger, rather than
saying "I don't recognize you," is not a smaller version of the target behavior, it is the wrong
behavior.

Cosine similarity against a gallery, with a calibrated threshold, makes both "unknown" and
"new-identity enrollment" free: enrollment is inserting a new gallery embedding, not retraining a
model, and the threshold decision is a single comparable number this project can calibrate and
report honestly (FMR/FNMR at a stated operating point), rather than an opaque classifier boundary.
1:1 verification falls out of 1:N identification for free — it is the same comparison restricted
to one gallery entry.

Option (c) was considered as a stronger version of (b) — a model trained explicitly to detect
out-of-distribution probes — but was rejected for this phase: it introduces a second model with
its own training data and calibration requirements, on top of what is already a from-scratch
rebuild, for a benefit (better unknown-rejection than a well-calibrated threshold) that has not
yet been shown to be necessary. Nothing in option (b)'s design forecloses adding (c) later.

### Consequences

- **Good, because** enrolling a new identity is an insertion, not a retraining run — this is a
  structural requirement of the open-set claim, not an optimization.
- **Good, because** the match/unknown decision is a single calibratable number, letting the
  project report FMR/FNMR at a stated operating point instead of an unqualified accuracy figure.
- **Bad, because** the calibration threshold becomes a first-class versioned artifact that must be
  re-validated whenever the gallery size or embedding model changes (tracked downstream as
  MTCH-03/MTCH-04) — a closed-set classifier has no equivalent artifact to version.
- **Bad, because** a vector index becomes a necessary component once the gallery grows past
  trivial linear-scan size, whereas an SVM's decision boundary is fixed cost regardless of gallery
  size.

## More Information

Source: `.planning/PROJECT.md` §"Methodologically broken" (the SVM's closed-set failure named
explicitly) and §"Core Value"; `.claude/CLAUDE.md` §"What NOT to Use" (the SVM row and its stated
reason).
