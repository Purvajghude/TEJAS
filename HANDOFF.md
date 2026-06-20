# TEJAS — Session Handoff & Thinking Log

A detailed record of the reasoning, decisions, pivots, and scrapped/parked plans from
the big build session, so the next session (or a teammate) can pick up with full context.
Project = ISRO BAH 2026 hackathon: **Forecasting/Nowcasting solar flares from combined
SoLEXS (soft X-ray) + HEL1OS (hard X-ray) on Aditya-L1.** Team: Code Catalyst.

---

## 0. TL;DR of current state

- **Repo:** `github.com/Purvajghude/TEJAS` (remote `mine`). Teammate's repo
  `github.com/PATILPARTH1500/TEJAS` (remote `origin`, no push access for Purvajghude).
  Latest pushed commit: `c0bd0f0`.
- **Data (NOT in repo):** SoLEXS Feb 2024–Jun 2026 (739 days) + HEL1OS Jul 2024–Jun 2026
  (1206 chunks), in `C:/Users/Rover/Downloads/Solex Files` and `.../Helios`. Pointed to via
  git-ignored `config.local.yaml`. venv is **outside** the repo: `C:/Users/Rover/tejas-venv`.
- **Every ISRO milestone is covered and pushed.** Headline: leakage-free TCN+LightGBM
  ensemble, AUC **0.847**, ~29 min lead; multi-class C/M/X; QPP detection; SHARP validated.
- **Immediate open task:** move the repo OUT of OneDrive (sync was corrupting `.gitignore`)
  to `C:/Users/Rover/GitHub/TEJAS` — must be done manually after closing Claude (the session
  holds the folder open). Destination parent already created.

---

## 1. Starting point & the expert's advice (brainstorming)

We began from a 2-month demo (Sep–Oct 2024) where **logistic regression won** (AUC 0.78)
and a GOES-pretrained TCN **collapsed to AUC 0.51** on Aditya — because there were only
~228 events. Plan: expand to ~2 years.

An external expert recommended (and we adopted): **don't just swap logistic→CNN; build a
TCN + LightGBM hybrid ensemble**, keep logistic as baseline/calibrator. Key insight that
shaped everything: *what matters is the number of independent flare EVENTS, not rows.*
Thresholds: <500 M+ → LightGBM wins; 500–2000 → ensemble; >2000 → deep models. Also:
predict **onset not peak**, multi-task heads, chronological leak-free eval, and add
SUIT/magnetograms for longer horizons. This all later proved correct against real data.

---

## 2. Ideas explored and how they were triaged

- **GAF/CWT → image → ViT, then next-frame prediction (a "vibe-code past the competition"
  idea).** Verdict: GAF→ViT *classifier* is legitimate and novel for Aditya; the **next-frame
  prediction part was SCRAPPED** — it hides the hard classification inside a generative step
  (you still need a classifier on the generated frame). Parked GAF as a dashboard/visual idea.
- **VELC/SUIT cameras + interpolated "video".** Led to the SUIT track (see §8). VELC full
  imaging parked (too heavy).
- **"Predict nuclear fission" confusion** — corrected: flares are **magnetic reconnection**,
  not fission. Useful framing: tokamak disruption prediction is the closest analogy.
- **Which sensor predicts reconnection?** None on Aditya directly measure the coronal magnetic
  field. SUIT (UV) is the closest *precursor*; magnetograms (SDO/HMI) are what NOAA uses but
  Aditya has no magnetograph. This seeded the SUIT and SHARP work.
- **"Epic" maximalist additions** (SDO/AIA 15-yr pretraining, conformal prediction,
  multi-mission consensus ensemble). Discussed, then **deliberately deprioritized** during the
  hackathon-strategy step — wrong scope for the X-ray-focused PS; they dilute focus.

---

## 3. Hardware & data constraints (shaped every decision)

Laptop: RTX 4050 (6 GB), 16 GB RAM, ~80 GB free SSD; external HDD ~300 GB. Consequences:
- **Process-and-delete** everywhere (never keep raw images/packages).
- HEL1OS full archive is ~130 GB zipped but only ~5% (CdTe+CZT light curves) is used.
- Keep multi-GB data **outside** the OneDrive-synced repo.

---

## 4. Data cleaning (executed)

`tools/clean_hel1os.py` — strips each HEL1OS package to just `lightcurve_cdte*/czt*`,
extracts light curves out of any `.zip` first (so no day is lost), dry-run by default.
Cleaned Sets 1–6: e.g. Set 1+2 166 GB → 31 GB; **~428 GB reclaimed total.** Decision:
keep **CdTe + CZT** (CZT adds >60 keV bands) = "best data".

---

## 5. Wiring 2 years of data + the deciding number

Wired `config.local.yaml` → Downloads. `python main.py run` over the full set produced the
master catalogue: **15,459 events, 4,123 soft+hard dual-confirmed, 6,464 C+, 1,072 M+, 68 X.**
**M+ = 1,072 → squarely "ensemble territory" (500–2000).** Decision locked: build the
TCN + LightGBM ensemble.

---

## 6. The ensemble + the audit + the leakage fix (the most important arc)

- Built `tejas/ensemble.py` (TCN + LightGBM → logistic meta-learner + isotonic) and a proper
  **CausalTCN** in `tcn.py` (causal chomp, residual, dilations 1,2,4,8,16,32). 3-way
  chronological split (train/val/test).
- **First (leaky) result:** ensemble AUC **0.905**, Brier 0.0062; crucially the **TCN now
  works (0.882 vs old 0.51)** — the data-expansion thesis was validated.
- **Full audit of all 15 modules** found the big one: **nowcasting leakage** — samples *during*
  a flare's rise were labelled positive, so the model "predicted" flares already underway.
  The expert had warned of exactly this.
- **Fix:** exclude in-flare samples as prediction points (`forecast.flare_intervals` /
  `in_flare_mask`). Tabular path drops them; ensemble keeps them as TCN *input history* but
  excludes them from train/val/test sample sets. Also vectorised `make_labels` &
  `_contiguous_idx` (proven byte-identical) and made the RNG reproducible.
- **Honest retrain:** AUC **0.905 → 0.847**, recall 0.93 → 0.75. BUT the ensemble now
  *genuinely beats* both base models (was a tie), and Brier stayed ~0.006 (great calibration).
  The reliability curve showed high-confidence alarms only ~50% right → **X-ray-only PRE-ONSET
  forecasting is fundamentally hard** (SoLEXS/HEL1OS see the radiative onset, not the magnetic
  cause). This honest finding became the scientific motivation for SUIT/magnetograms.

---

## 7. Hackathon strategy reframe + FAR fix + live dashboard

Strategy discussion concluded: core is well-aligned, but stop chasing "epic" tangents; the
**scored weak spot was False-Alarm Rate** and the **real-time alert interface**. USP =
the **Neupert precursor** (hard X-ray peaks ~3 min before soft; median lead +184 s) +
**leakage-free rigor** + **calibrated probabilities**.

Built (Tier 1):
- PR-AUC in the scorer; **event-based false-alarms/day** + episode precision
  (`forecast.event_skill`); **two operating points** (recall-max vs **≤1 false alarm/day**).
- Dashboard live **NOWCAST vs FORECAST alerts** in the replay + a forecast-risk track
  (ECharts; verified in-browser, zero console errors).

---

## 8. SUIT (explored, partially built, deprioritized to "bonus")

- Strategy: target only flare days, process-and-delete. Built `tools/suit_flux.py` (disk-
  integrate NB03 → exposure-normalize → CSV → delete; records `visible_frac` for off-pointing).
- **Reality discovered from real PRADAN data:** NB03 full-frame is ~2 h cadence at ~64 MB/file,
  but on flare days SUIT's onboard flare trigger ramps to ~1-min (1004 frames/day = ~64 GB/day).
  **SCRAPPED downloading it all.** Pivot: SUIT is a **coarse precursor demonstrator** (a few
  flagship flares), NOT a 1-min forecasting input (cadence mismatch).
- Artefacts ready but not run at scale: `outputs/suit/suit_download_worklist.csv` (61 tiered
  rows with exact `ImageTime` windows), `suit_flux.py`. PV phase (06 Jan–01 Jun 2024) is
  caveated — prefer post-June dates. `precursor_figure.py` makes the ISRO slide-5 style plot.
- **PARKED future work:** SUIT active-region tracking; SUIT as an early-warning UV channel.

---

## 9. ISRO livestream alignment → multi-class + QPP (the gap-closers)

User shared the ISRO livestream brief + reference slides. Two real gaps surfaced:
- **Forecasting Milestone 2 = multi-class** → built `tejas/multiclass.py`: leak-free
  P(C+)/P(M+)/P(X+). Test AUC **C+ 0.691 / M+ 0.797 / X+ 0.665** (honest gradient — M+ is the
  sweet spot; X is rare so noisy). This is the dashboard-facing forecaster.
- **QPP (quasi-periodic pulsations)** explicitly called out → built `tejas/qpp.py`
  (Lomb-Scargle on HEL1OS hard). **Iterated 3×:** v1 median 24.8 s (Nyquist-floor artifact);
  v2 median 463 s (long-trend artifact); **v3 fixed** with a polynomial detrend + **≥3-cycle
  credibility criterion** → **3.2% of flares pulsate, ~5.5 min median**. Caveat: 10 s binning
  limits us to ≥30 s periods (native 1 s would resolve shorter QPPs — future work).
- Wired both into the dashboard (live C/M/X bars + QPP panel). Built `fetch_sharp.py`.

---

## 10. SHARP magnetograms (integrated, calibrated, honestly placed)

- Fetched SDO/HMI SHARP keywords via `drms` (monthly-chunked to dodge JSOC timeouts).
- **Timeline calibration (explicitly requested):** SHARP `T_REC` is TAI → converted to UTC
  (−37 leap s) to match the X-ray clock. **Data accuracy:** missing SHARP kept as NaN
  (LightGBM-native) with a `sharp_available` flag, not 0-filled.
- **Validation:** magnetic complexity (TOTUSJH) is **1.79× higher 6 h before M+ flares**
  (81% above quiet baseline) — confirms both the timeline alignment and physical predictiveness.
- **Honest ablation finding (important):** as a disk-aggregated 30-min feature, SHARP is
  **neutral-to-negative** (ΔAUC −0.026; the earlier apparent +0.009 was a **0-fill artifact**
  the calibration exposed; X+ overfit on 9 extra features). **Decision:** keep the production
  forecaster **X-ray-only** (M+ 0.797); SHARP is shipped as a *validated supplement* + dashboard
  panel + `main.py sharp`. Its real value is **longer-horizon / per-active-region** (future work).

---

## 11. GitHub, collaborator benchmark bundle, and the OneDrive hazard

- Repo hygiene: removed old `src/`, clean `tejas/` package, MIT license, rewritten README,
  portable `config.yaml` + git-ignored `config.local.yaml`, fixed `requirements.txt`
  (`lightgbm`/`torch`/`drms` were missing).
- **Branch divergence:** teammate's `origin/main` "DONE WITH UI" was an *older parallel snapshot*
  of the same rework. Merged with `-s ours` (kept our superset tree, preserved their commit in
  history). Push to `origin` was **denied** (Purvajghude not a collaborator on PATILPARTH1500's
  repo) → created and pushed to **Purvajghude/TEJAS** instead.
- **Collaborator benchmark bundle** (so a friend can verify accuracy WITHOUT the un-shareable
  multi-GB data): committed the small trained models (via **Git LFS**: `ensemble.joblib`,
  `ensemble_tcn.pt`, `tcn_pretrained.pt`; the 47 MB `flare_forecaster.joblib` stays ignored) +
  `eval/test_predictions.parquet` (223k held-out predictions + labels) + `eval/*.json` +
  `tools/evaluate.py`. `python main.py evaluate` reproduces C+ 0.691 / M+ 0.797 / X+ 0.665.
- **OneDrive hazard (recurring!):** OneDrive sync **clobbered `.gitignore`** to a stripped
  version that no longer ignored `data/`+`outputs/` — caught before it committed ~80 GB. Restore
  with `git checkout HEAD -- .gitignore` if `git status` ever shows `data/raw` as untracked.
  → Decision to move the repo out of OneDrive entirely (see §0).

---

## 12. Open items / next-session TODO

1. **Move repo out of OneDrive** → `C:/Users/Rover/GitHub/TEJAS` (manual, after closing Claude;
   parent dir already created). Ends the sync corruption permanently.
2. **PPT (ISRO BAH idea template, 10 slides).** Slides 1–2 done by user. Slides 3–9 content +
   design were drafted in chat (Opportunity/USP, Features, Process flow, Wireframes=real
   dashboard screenshots, Architecture, Technologies, Cost≈₹0). **Offer still open: generate the
   architecture + flow diagrams and fresh dashboard screenshots.**
3. **Reconcile with teammate's repo** (PATILPARTH1500/TEJAS) — decide which is the official
   submission; get collaborator access to push the superset there, or keep Purvajghude's as canon.
4. **Optional/parked:** SUIT precursor demonstrator (3–5 flagship flares via the worklist);
   fusion one-hard→many-soft exclusivity fix; a real test suite; SUIT/SHARP longer-horizon work;
   GAF→ViT branch; NOAA SWPC benchmark comparison.

## 13. Key commands

```
python main.py run         # nowcast -> fusion -> forecast -> dashboard export
python main.py ensemble    # TCN + LightGBM stacking ensemble
python main.py multiclass  # P(C+/M+/X+)  (Forecasting M2)
python main.py qpp         # QPP detection on HEL1OS hard X-ray
python main.py sharp       # SHARP magnetogram ablation
python main.py evaluate    # reproduce test accuracy from eval/ (no data needed)
python main.py web         # serve the live dashboard (localhost:8531)
tools/clean_hel1os.py · tools/suit_flux.py · tools/fetch_sharp.py · tools/precursor_figure.py
```

## 14. Honest headline results (leak-free, untouched test)

- Ensemble M+: **AUC 0.847**, Brier 0.0062, ~29 min median lead; beats both base models.
- Multi-class: C+ 0.691 / M+ 0.797 / X+ 0.665.
- Operating points: recall-max (high recall, ~8 FA/day) **or** ≤1 false-alarm/day (precision).
- Neupert precursor: hard X-ray leads soft by median +184 s. QPP in 3.2% of flares (~5.5 min).
- SHARP validated (1.79× pre-flare elevation) but not helpful as a 30-min feature (honest).
- Nowcast master catalogue: 15,459 events; 97% GOES letter-class agreement.

> Guiding principle this whole session: **honest, leakage-free, calibrated science beats
> inflated numbers** — the rigor (and the willingness to report negative results like the SHARP
> ablation) is itself the differentiator for ISRO judges.
