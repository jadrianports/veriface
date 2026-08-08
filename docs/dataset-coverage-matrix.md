# Dataset coverage matrix

Which claimed capability is backed by which dataset (D-27), stated plainly so a reader does not
have to infer coverage from prose scattered across the README, ROADMAP, or ADRs. `live`, `print`,
and `screen replay` are the attack classes in v1 scope; `video replay` and `3D mask` are listed
below as explicitly not covered, with the reason for each.

| Attack class | Dataset backing the claim | What is validated | What is not |
| --- | --- | --- | --- |
| live | Phase 3 personal acceptance set (real webcam captures of consenting enrollees, per PROJECT.md's consent-and-deletion requirement) | Genuine-presentation acceptance in the actual deployment conditions (this project's own camera, lighting, and enrollees) | Generalization to cameras, lighting, or demographics outside the personal acceptance set — see the demographic-fairness note below |
| print | CelebA-Spoof eval tier (plan 01-04's committed manifest, subject-first attack-balanced sampling) | Passive PAD rejection of printed-photo presentation attacks, at the eval tier's sample size | Print attacks produced with materials, printers, or lighting outside CelebA-Spoof's own capture protocol |
| screen replay | CelebA-Spoof eval tier (same manifest as print, above) | Passive PAD rejection of screen-replay presentation attacks (photo or video played back on a second screen), at the eval tier's sample size | Screen-replay attacks using display hardware or capture angles outside CelebA-Spoof's own protocol |

## Explicitly not covered in v1

| Attack class | Status | Reason |
| --- | --- | --- |
| video replay | **out of v1 scope** | PAD-03 (video-replay rejection) was shelved out of v1 by user decision (D-39). The passive-PAD architecture is the same mechanism screen-replay uses, so the marginal engineering cost was low, but the decision stands as made. Revisit in v2 alongside the injection/deepfake work, where motion and stream-integrity analysis already belong. `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, and `.planning/PROJECT.md` still name video replay as of this writing — D-39 assigns those edits to a follow-up process step outside this plan; this matrix reflects the decision already made, not those pending document edits. |
| 3D mask | **architecturally covered, unvalidated** | The PAD model class (MiniFASNet) is architecturally capable of contributing signal against 3D/silicone mask presentation attacks, but no obtainable dataset exists to validate that capability — the gated benchmark corpora that would support this (OULU-NPU, SiW, CASIA-FASD) require signed institutional agreements this project cannot obtain (see `docs/data-requests.md`), and physical masks are not available for a personal acceptance-set capture. This will be documented as explicitly unvalidated wherever PAD capability is described, never silently claimed. |

## Demographic-fairness source

Bias/fairness evaluation across demographic subgroups (EVAL-06, Phase 2) is backed by **BFW
(Balanced Faces in the Wild)**. As recorded in `docs/data-requests.md`, BFW turned out to be a
direct, ungated download (verified live 2026-08-08) rather than the request-gated dataset earlier
research assumed — so the risk to EVAL-06's timeline is now low. Phase 2's caveated in-house slice
(demographic diversity within the real gallery + LFW, explicitly marked underpowered with
confidence intervals) remains the named fallback if BFW turns out to be unusable for a reason not
yet discovered (e.g. a licensing or data-quality issue found during Phase 2's actual materialization),
but is not expected to be needed on access grounds alone.
