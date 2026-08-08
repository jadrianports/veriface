# 0006: Three-package layout with a framework-free core

## Status

accepted

## Context and Problem Statement

Two of this project's own planning documents disagreed with each other. `.claude/CLAUDE.md`
described a single package (`veriface`) with `[server]`/`[demo]` extras layered on top.
`.planning/research/ARCHITECTURE.md` described three top-level packages (`veriface`,
`veriface_server`, `veriface_eval`) under one `src/` tree. These are not two phrasings of the same
design — a single-package-with-extras layout and a three-package layout imply different import
boundaries and different guarantees about what can and cannot depend on what. One had to win
before any code could be written against it, and this record exists so the resolution is visible
rather than an unnoticed inconsistency later phases would have had to rediscover.

## Decision Drivers

- **API-02 (framework-free core)** — `veriface` must be importable and usable with no web
  framework installed; this needs to be a structural property CI can assert, not a habit to
  maintain by discipline.
- **Deployed image weight** — the evaluation harness's dependencies (dataset loaders, plotting)
  must never reach the service's deployed image.
- **Consistency with a document already partially trusted** — `ARCHITECTURE.md` is the source the
  rest of this phase's model registry, sources module, and internal-boundary rules were already
  drawn from.

## Considered Options

- **(a) One package with extras** — `veriface` alone, with `[server]` and `[eval]`/`[demo]` extras
  installing additional dependencies into the same import namespace, per `CLAUDE.md`'s original
  description.
- **(b) Three top-level packages under one `src/` tree and one `pyproject.toml`** — `veriface`
  (core), `veriface_server`, `veriface_eval`, built from a single wheel configuration, per
  `ARCHITECTURE.md`'s description.
- **(c) Three separately published distributions**, each with its own `pyproject.toml` and release
  cadence.

## Decision Outcome

Chosen option: **(b) three top-level packages under one `src/` tree, ARCHITECTURE.md's layout
superseding CLAUDE.md's.** This was a deliberate, recorded resolution of a real contradiction
between two of this project's own documents (D-03), not a default reached because one document
happened to be read first.

- **Option (a) cannot make the framework-free-core requirement structurally testable.** An
  extras-based design still bundles every package's code under the same top-level import name;
  nothing stops a `server`-only code path from being imported even when the `[server]` extra was
  never installed, because there is no second import boundary enforcing it — only the extras
  metadata, which governs what `pip install` fetches, not what a module is allowed to `import`. A
  CI job that installs bare `veriface` and asserts `import veriface` succeeds with **no web
  framework present** (this phase's own CI does exactly this) only proves something meaningful
  under option (b), where `veriface_server` is a physically separate top-level package that could
  not have been imported by accident.
- **Option (b) keeps `veriface_eval`'s heavier dependencies (dataset loaders, evaluation tooling)
  structurally outside the deployed service image** — `veriface_server` never lists
  `veriface_eval` as a dependency, so a production build that only installs `veriface[server]`
  never resolves eval-only packages, satisfying the deployed-image-weight driver without relying on
  extras discipline alone.
- **Option (c), separately published distributions, was rejected as unnecessary overhead for this
  project's scale.** Three independent release cadences and version-compatibility matrices are a
  cost with no corresponding benefit here — nothing about this project's requirements needs
  `veriface_server` or `veriface_eval` to be independently installable from a different source than
  `veriface` itself, and one wheel build configuration already produces all three packages from a
  single `pyproject.toml` (D-03).

### Consequences

- **Good, because** "core imports no web framework" became a CI-enforced fact the moment the
  packages were physically separated, not an aspiration documented in prose.
- **Good, because** `veriface_eval`'s dependency weight is excluded from the service image by
  construction — there is no extras configuration to get wrong, because the dependency simply
  isn't declared on `veriface_server`'s side.
- **Good, because** the internal-boundary rule this phase's registry already follows —
  `models/registry.py` is the only code path permitted to touch HF Hub or construct an
  `InferenceSession` — sits naturally inside `veriface` core precisely because `ARCHITECTURE.md`'s
  package boundaries were adopted wholesale, not partially.
- **Bad, because** collapsing back to a single package later would change every consumer's import
  path (`from veriface_server import app` → something else) and the extras contract simultaneously
  — this is a one-way structural commitment, not a naming preference that can be revisited cheaply.
- **Bad, because** three packages under one `pyproject.toml` still share one version number and one
  release — if a future need arises for `veriface_server` to version independently of `veriface`
  core, that is a second architectural decision this record does not resolve.

## More Information

Source: `.planning/research/ARCHITECTURE.md` §"Recommended Project Structure" and §"Internal
Boundaries"; `.planning/phases/01-foundation-artifacts-data-strategy/01-CONTEXT.md` D-03;
`.claude/CLAUDE.md` §"Technology Stack" (the superseded one-package description, noted in
01-CONTEXT.md as no longer authoritative).
