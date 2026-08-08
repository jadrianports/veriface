# CelebA-Spoof Acquisition — Measured Findings (Plan 01-07)

**Status: ACQUISITION DEFERRED TO PHASE 2.** Decided by the user on 2026-08-08, on the measured
numbers this document records. The full corpus (~71.7-77.0 GB) does not fit this machine's
measured free disk (~74-76 GiB) inside the mandated 10 GB safety floor, under any of the four
candidate acquisition sequences evaluated at the Task 3 decision checkpoint (§ 6) — the developer
decision was to defer rather than force it. **No CelebA-Spoof bytes were downloaded, no volume
was reassembled, no eval-tier subset was extracted, and no manifest was committed.** The
measurements below are the deliverable of this plan; they are what Phase 2 starts from.

The fetcher mechanism itself (`src/veriface_eval/datasets/celeba_spoof.py`) was implemented in
full against these measurements, wired into `veriface data fetch celeba-spoof`, and degrades
honestly today: it checks for the corpus's local presence before doing anything else and raises a
clear `AcquisitionDeferredError` naming this deferral and pointing back at this document, rather
than attempting a download, silently skipping, or faking success.

Measured: 2026-08-08, this repository, live network access to `raw.githubusercontent.com` and
`drive.google.com`.

## 1. Distribution shape (confirmed live)

Fetched `raw.githubusercontent.com/ZhangYuanhan-AI/CelebA-Spoof/master/README.md` directly this
session. It reconfirms 01-RESEARCH.md's Pitfall 1 finding, not stale:

- Two download routes only: a Google Drive folder and a Baidu Drive folder (password `61fd`). No
  third "annotations only" link exists.
- Per-image annotation is a single JSON file per image with a 43-field vector, shipped *inside*
  the same archive as the images — quoted verbatim from the README: `[0:40]: Face attribute
  labels # [40]: Spoof type label # [41]: Illumination condition label # [42]: Environment label
  # [43]: Live/Spoof label`. This is metadata *per image*, not a compact separate manifest — it
  cannot be fetched before touching image bytes.
- License: non-commercial research only; redistribution of any portion is explicitly forbidden by
  the dataset's own agreement.

**Per-image annotation field layout vs. this session's observation:** the field layout above was
read from the README text only. No annotation JSON file was actually opened this session — the
Blockers below prevented downloading anything the field layout could be checked against. This
task's acceptance criterion ("observed per-image annotation field layout compared against the
README") is therefore only partially satisfied: the README's own description is recorded and
quoted verbatim, but it was not cross-checked against a real extracted annotation file.

## 2. Volume list and measured sizes

Listed via `gdown --folder --json` against the Google Drive folder ID
`1OW_1bawO79pRqdVEVmBzp8HSxdSwln_Z` (no download — this call only lists folder contents). **74
volumes**, `CelebA_Spoof.zip.001` through `CelebA_Spoof.zip.074`.

Per-volume size measured by GET-requesting each file's individual download URL and reading the
size Google Drive prints on its "can't scan this file for viruses" confirmation page (e.g.
`CelebA_Spoof.zip.001 (1,000M)`). This is a **cheap, non-download probe** — each request returns
a ~2.4 KB HTML page, not the file itself, so measuring all 74 volumes this way cost under 200 KB
of network traffic total, not gigabytes.

| Volumes | Displayed size (each) |
|---|---|
| `.001`–`.073` (73 volumes) | `1,000M` — identical for every one of the 73, strongly suggesting a fixed-size split at upload time (e.g. `split -b 1000M` or equivalent) |
| `.074` (final volume) | `432M` |

**Precision caveat:** `1,000M` and `432M` are Google Drive's own rounded UI display, not a
byte-exact `Content-Length`. Getting an exact byte count would require either downloading the
file (blocked — see § Blockers) or an authenticated Google Drive API v3 `files.get` call with an
API key (none configured in this environment). Both interpretations of "M" are carried through
the arithmetic below because the ambiguity is large enough to matter at this scale.

## 3. Total compressed size

73 × 1,000M + 432M = **73,432 "M" units** (Google's display unit).

- If `M` = decimal MB (10⁶ bytes): **73.43 GB** (SI/decimal)
- If `M` = MiB (2²⁰ bytes, consistent with how `df -h` and most OS size displays work): **71.71
  GiB = 77.00 GB** (decimal)

**Total compressed size of the corpus is therefore approximately 71.7–77.0 GB**, depending on
unit interpretation — both ends of that range are treated as live possibilities below because
neither can be ruled out without downloading.

## 4. Free space on the target volume

`df -h .` measured three times this session (drive `C:`, 475G total):

| Time (UTC, approx.) | Free |
|---|---|
| Start of this task | 74G |
| After the folder listing + size probes | 74G |
| Just before the blocked download attempts | 76G |

Free space fluctuated 74–76 GiB across the session (other processes on this machine writing/
freeing disk independently of this spike). **74 GiB is used as the conservative free-space
figure below** — using the smaller of the two observed values is the safer assumption for a
disk-budget decision.

## 5. Peak-disk arithmetic per candidate sequence

All four sequences below require the *entire* corpus to be locally present at some point, because
(per § 1) the per-image labels needed to build the manifest live inside the same archive as the
images, and (per the GitHub issue 01-RESEARCH.md already found, `cat CelebA_Spoof.zip.0* > 
CelebA_Spoof.zip` then `unzip`) the volumes are strongly implied to be a **raw byte-level split**
of one file, not a zip-aware multi-disk archive with independent per-entry disk metadata — see the
open question in § 8. Under that (unconfirmed but implied) assumption, no entry's compressed
bytes can be read until every volume up to and including the one containing that entry is
present, and the central directory that indexes every entry sits in the final volume.

| Strategy | Peak disk (low estimate, 71.71 GiB corpus) | Peak disk (high estimate, 77.00 GB corpus) | Fits in 74 GiB free with a 10 GB floor? |
|---|---|---|---|
| Naive `cat` all volumes into a new concatenated file while originals still present | ~2× corpus ≈ 143.4 GiB | ~2× corpus ≈ 154.0 GB | **NO** — roughly double the entire free-disk budget |
| Streaming download → append each volume to a growing combined file → delete each source volume immediately after it is appended (never holds all raw volumes at once, but the combined file itself grows to the full corpus size) | ≈ corpus + 1 volume ≈ 72.7 GiB | ≈ corpus + 1 volume ≈ 78.0 GB | **NO** — already exceeds or nearly exhausts all free disk before the 10 GB floor or the extracted subset are counted |
| All volumes downloaded and kept as separate files (no physical concatenation), extracted via a multi-volume-aware tool if the archive format supports it (7-Zip; **untested — see § 8**) | ≈ corpus (all volumes resident) + ~5 GB eval-tier extract ≈ 76.7 GiB | ≈ corpus + ~5 GB ≈ 82.0 GB | **NO** — exceeds the entire 74 GiB free disk even before subtracting a floor |
| Any variant that must hold the full corpus resident in any form simultaneously | ≥ corpus alone ≈ 71.7 GiB | ≥ corpus alone ≈ 77.0 GB | **NO** — the corpus alone already consumes 97–104% of currently free disk, leaving at most ~2.3 GiB and at worst a deficit, nowhere near the required 10 GB floor |

**Conclusion: no version of "download the full corpus, in any arrangement" fits inside this
machine's current free disk under the mandated 10 GB floor.** This holds across both unit
interpretations of the Drive-displayed sizes, and it is the dominant constraint regardless of
which extraction tool eventually proves to work.

## 6. Per-option feasibility against the four Task 3 candidate sequences

All four options named in the plan's decision checkpoint require downloading the full set of 74
volumes before any manifest-building or extraction can begin (per § 1 and § 5) — none of them
avoid the corpus-sized download. Evaluated against § 5's arithmetic:

| Option | Requires full-corpus download? | Fits 74 GiB free / 10 GB floor? |
|---|---|---|
| `corrected-full-then-subset` | Yes | **No** |
| `reduced-eval-tier` | Yes — the *download* phase is identical; only the amount *retained after extraction* shrinks | **No** |
| `manifest-only-defer-images` | Yes — plan's own text: "still requires downloading and reassembling every volume once to reach the labels" | **No** |
| `baidu-mirror` | Yes — same archive shape and size, different transport only | **No** |

**None of the four pre-scoped options are disk-feasible as literally written, given the measured
numbers.** This is flagged explicitly for the Task 3 decision rather than silently picking the
"least bad" one — see the recommendation carried into that checkpoint.

## 6.5. Rejected alternative: a binary-labeled Hugging Face mirror

While this spike was blocked on the download-permission wall (§ 7, Blocker A), the orchestrator
independently investigated whether an HF-hosted mirror of CelebA-Spoof could sidestep the disk
problem entirely. One was found: **`Ar4ikov/celebA_spoof`** on Hugging Face — the full corpus (72
GB, `download_size` 72,011,056,582 bytes) re-published as **167 individually-addressable parquet
shards** (train 93 / valid 9 / test 65, ~500 MB each). This would completely dissolve the § 5
disk problem: selective shard download, ~5 GB peak, reusing the project's existing
`HuggingFaceSource` resolver and per-shard LFS digests instead of a from-scratch `gdown` fetcher.

**It is nonetheless unusable for this project, and this is the important part.** Its schema is
only `Filepath` (image), `Bbox` (int64 sequence), `Class` (string) — and `Class` is **binary**.
Verified via the HF datasets-server statistics endpoint on the test split: `n_unique: 2`,
frequencies `{"live": 2944, "spoof": 7077}`. The entire spoof-type taxonomy (print / replay /
paper-cut / 3D-mask, illumination, environment) present in the official 43-field annotation is
gone — collapsed to a single live/spoof bit.

**Consequences if this mirror were adopted instead of the official distribution:**
- 01-04's **attack-balanced** sampler would silently degrade to a live/spoof binary sampler while
  still passing every one of its existing tests — nothing in the sampler's own test suite asserts
  against a specific *number* of classes, only that classes present are balanced, so this
  degradation would not be caught by re-running the existing suite.
- **D-39's video-replay exclusion becomes unenforceable.** You cannot exclude a class the labels
  cannot identify. The `SpoofClass` `Literal`-typed structural exclusion in
  `veriface_eval/datasets/manifest.py` would become decorative — technically still present in the
  type, but never actually doing the exclusion work it was built for, because the binary label
  never distinguishes a video-replay sample from any other spoof sample in the first place.
- The mirror also states **no license** — no redistribution terms recorded on the dataset card at
  all, which is a materially worse licensing position than the official distribution's clearly
  stated (if restrictive) non-commercial-research terms.

**Recorded here so a future phase under disk pressure does not rediscover this the hard way and
adopt it believing it is a free win.** It is not a substitute for the official distribution for
any metric this project reports as attack-type-resolved — see also
`docs/dataset-coverage-matrix.md` § "Attack-type resolution depends on the official annotation
set". If disk pressure returns in Phase 2, the right lever is freeing headroom or using scratch
storage (§ recommendation below), not swapping to a mirror that quietly removes the labels the
whole manifest/sampler design depends on.

## 7. Blockers encountered this session

### Blocker A — harness Bash tool-permission denial (not a disk-budget failure)

Every attempt to download **any** volume — including a single, smallest, ~450 MB volume
(`.074`), an amount that would not itself breach the 10 GB floor — was denied by the runtime's
Bash auto-mode classifier with "Blocked by classifier" / "Stage 2 classifier error". This was
tried three times: once as part of a longer chained command, once as an isolated single `gdown`
invocation, and once as a retry after a stage-2 error explicitly labeled itself as "usually
transient." All three attempts were denied identically. **No archive bytes were downloaded this
session.**

This is a distinct blocker from the disk-budget finding in § 5–6 — resolving it requires either
the user adding a Bash permission rule that allows this shape of network download, or a human
downloading volume(s) manually via a browser and placing them under
`${VERIFACE_DATA_DIR}/celeba_spoof/raw/` for a future automated step to pick up from there.

### Blocker B — even the "smallest sufficient set" proof is not obviously safe

Because (per § 1, § 5) the archive appears to be a raw byte-level split rather than a zip-aware
multi-disk format, proving `cat` + `zipfile.ZipFile(...).testzip()` end-to-end plausibly requires
**all 74 volumes** present simultaneously (§ 8 is the open question that would change this). That
alone (~71.7–77.0 GB) already leaves under the 10 GB floor on this machine today. Resolving
Blocker A does not by itself make the full-reassembly proof safe to run without first freeing
disk elsewhere or acquiring against a separate volume/drive.

## 8. Open question this session could not resolve

**Is this a raw byte-level split, or a true ZIP multi-disk/multi-volume archive?** The GitHub
issue 01-RESEARCH.md already found (`cat CelebA_Spoof.zip.0* > CelebA_Spoof.zip` then `unzip`)
implies the former — a byte-level split requires all volumes physically concatenated in order
before any entry is readable. If it is instead a true multi-disk zip (created with `zip -s`, or
7-Zip's own volume format with per-entry disk-number metadata in the central directory), a
disk-aware tool could extract specific manifest-listed entries from specific volumes without ever
holding the full corpus locally — which would substantially change the § 5 arithmetic for the
better. **This distinction could not be tested this session** because Blocker A prevented
downloading even the single smallest volume (`.074`) to inspect with `7z l` / `zipfile`.
Recommend testing this specifically, with only `.074`, once Blocker A is resolved, before
attempting anything larger.

## 9. What this plan explicitly did NOT do (deferral, not an oversight)

- No eval-tier extraction occurred.
- No manifest was built or committed (`src/veriface_eval/datasets/manifests/celeba_spoof_eval.csv`
  does not exist; `DATASET_CONFIGS["eval"].manifest_sha256` in `config.py` remains the sentinel
  `load_dataset_config` already rejects — no digest was invented for a manifest that does not
  exist).
- `zipfile.ZipFile(...).testzip()` on the reassembled archive: **NOT ATTEMPTED** — no volumes
  were downloaded, so there was nothing to concatenate or test.
- No fallback tool (`zip -FF`, `py7zr`/shelled `7z`, the Baidu Drive mirror) was exercised, because
  none had any bytes to operate on.
- No archive member was extracted; none exists locally to extract.
- `tests/integration/test_celeba_spoof_fetch.py` (which asserts against a materialized tier) was
  not written this plan — there is nothing materialized for it to assert against yet.

## 10. What this plan DID deliver (byte-independent)

`src/veriface_eval/datasets/celeba_spoof.py` implements the full fetch/reassembly/label-index/
extraction/cleanup mechanism for real — `CELEBA_SPOOF_VOLUMES` (the 74-volume list and drive IDs
measured in § 2), `download_volumes`, `reassemble`, `build_label_index`, `extract_subset`,
`cleanup`, and the orchestrating `fetch_celeba_spoof`. It is wired into
`veriface data fetch celeba-spoof --tier`. `extract_subset`'s member-path-containment guard
(reusing `veriface.models.sources.validate_member_path`, not reimplementing it) is fully unit
tested against synthetic archives in `tests/unit/test_celeba_extract_safety.py` — no CelebA bytes
needed. `fetch_celeba_spoof` checks for the corpus's local presence before doing anything else and
raises `AcquisitionDeferredError` (pointing back at this document) when it is absent, which is the
case for every invocation today. This is what Phase 2 calls once the deferral is lifted.

`build_label_index`'s exact Spoof-Type-value → class mapping is inferred from the CelebA-Spoof
README's documented field layout only (§ 1) — no real annotation JSON was ever opened this
session, so this mapping is unverified pending Phase 2's first real download. This is flagged
in the function's own docstring as the first thing to re-check once real data exists.

## 11. Disk state at the end of this plan

`du -sb "${VERIFACE_DATA_DIR}"` → `0` bytes. `data/celeba_spoof/raw/` was created as an empty
directory (gitignored, confirmed via `git check-ignore -v`) and nothing was written into it.
`git status --short` shows no path under `data/`.

## 12. Decision record

**Acquisition deferred to Phase 2 — decided by the user, 2026-08-08, on the measured numbers in
this document.** The user explicitly directed: do not download the corpus, do not attempt any of
the four candidate options, do not retry the blocked downloads. This plan closes with the
byte-independent portion of the fetcher delivered (§ 10) and the extraction eval tier / committed
manifest recorded as deferred, not done. Whoever picks this up in Phase 2 should start by
re-reading § 5 (peak-disk arithmetic), § 6.5 (why the HF mirror is not a shortcut), and § 8 (the
still-open raw-split-vs-multi-disk question) before choosing a sequence.
