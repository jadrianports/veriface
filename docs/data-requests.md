# Gated-dataset access tracker

This file is the committed record of every dataset access request or verification this project
has made (D-26). `.planning/` is gitignored, so a note kept only in planning notes is invisible to
any reviewer and disappears if planning context resets — this table lives in the repository
instead.

| Dataset | Date submitted | Route / contact | Status | Follow-up date | Outcome |
| --- | --- | --- | --- | --- | --- |
| BFW (Balanced Faces in the Wild) | 2026-08-08 | Dropbox direct download: `https://www.dropbox.com/scl/fo/i2gj82qewyikts2d55xo5/AK5cY0nmJ7Of-iHmD6eF9E4?rlkey=ebj8bbq0giwk30v75r51vsw75&st=slcmpmbn&dl=0` (from `github.com/visionjo/facerec-bias-bfw`) | direct download (no request required) | 2026-09-07 | Verified live 2026-08-08 — the URL 302-redirects straight to an archive stream, no login/account/consent step. Not yet downloaded; materializing BFW for demographic-fairness evaluation is Phase 2 work (EVAL-06). Follow-up date is a link-liveness re-check, not a pending-request chase. |
| RFW (Racial Faces in the Wild) | — | Request form from the original authors (see `.planning/research/PITFALLS.md` § Pitfall 4) | not requested | — | Reorganizes MS-Celeb-1M images; inherits both the access-gating problem and an indirect MS-Celeb-1M provenance question. Treated as unlikely to be obtainable for a solo project on a reasonable timeline; BFW (above) is the realistic demographic-fairness source instead. |
| CASIA-FASD | — | Direct researcher request, Institute of Automation, Chinese Academy of Sciences | not requested | — | No open self-serve download confirmed. Considered for PAD cross-dataset evaluation and not pursued; CelebA-Spoof (eval tier) is the print/screen-replay source instead. |
| Replay-Attack (Idiap) | — | idiap.ch dataset page; EULA/registration mechanics not confirmed by public sources | not requested | — | Considered for PAD cross-dataset evaluation and not pursued for the same reason as CASIA-FASD. |
| OULU-NPU | — | Signed End User License Agreement; signatory must hold a permanent position at a research institution | not requested | — | Confirmed not obtainable by an independent/solo developer without academic affiliation. |
| SiW | — | Michigan State University, institutional-request model | not requested | — | Same posture as OULU-NPU/CASIA-FASD — gated, not pursued. |
| IJB-B / IJB-C | — | NIST (official distribution) | not requested | — | NIST has discontinued distribution of IJB-A, IJB-B, and IJB-C entirely. Not obtainable through the official channel at all. |

## Note on the BFW row

`.planning/research/PITFALLS.md` § Pitfall 4 describes BFW access as "via a download-request form
on the project's GitHub." That description is **superseded** by what was verified live on
2026-08-08 (see above): the maintainer's repository currently offers a direct, ungated Dropbox
download, with no request form found on any page. A second route, IEEE DataPort
(`https://ieee-dataport.org/documents/balanced-faces-wild`), also hosts the data but requires a
**paid IEEE DataPort subscription** to access the face-sample archive — that route is deliberately
not used, given this project's zero-cost posture, and is named here only so a future reader does
not wander into the paid path by mistake.

**Disk-budget note:** the BFW archive is 2.9 GB (confirmed via the Dropbox redirect's
`Content-Length: 2897919784`). Free disk on the development machine is 76 GB (measured, not the
78.5 GB figure in `.claude/CLAUDE.md`), and CelebA-Spoof's eval-tier subset (plan 01-07) already
claims a share of that budget — BFW's 2.9 GB competes with the CelebA-Spoof allocation and should
be accounted for when Phase 2 actually materializes it, not assumed free.

Updating `.planning/research/PITFALLS.md` § Pitfall 4 and `.planning/ROADMAP.md`'s Phase 2 EVAL-06
notes to reflect this finding is deferred to a follow-up outside this plan.
