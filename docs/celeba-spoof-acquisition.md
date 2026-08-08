# CelebA-Spoof Acquisition — Measured Findings (Plan 01-07, Task 2 Spike)

**Status: the reassembly mechanism was NOT proven this session.** Two independent blockers
stopped this spike before any archive volume could be downloaded — see § Blockers. Everything
below that does not depend on a download was measured live against the real distribution.
This document is the input to the Task 3 decision checkpoint; it does not select or apply an
acquisition option itself.

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

## 9. What this task explicitly did NOT do (scope discipline, not an oversight)

- No eval-tier extraction occurred.
- No manifest was built.
- `zipfile.ZipFile(...).testzip()` on the reassembled archive: **NOT ATTEMPTED** — no volumes
  were downloaded, so there was nothing to concatenate or test.
- No fallback tool (`zip -FF`, `py7zr`/shelled `7z`, the Baidu Drive mirror) was exercised, because
  none had any bytes to operate on.
- No archive member was extracted; none exists locally to extract.

## 10. Disk state at the end of this task

`du -sb "${VERIFACE_DATA_DIR}"` → `0` bytes. `data/celeba_spoof/raw/` was created as an empty
directory (gitignored, confirmed via `git check-ignore -v`) and nothing was written into it.
`git status --short` shows no path under `data/`.
