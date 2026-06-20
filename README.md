# TEJAS — Aditya-L1 Solar Flare Nowcasting & Forecasting

Automated **detection, classification, fusion, and forecasting** of solar flares
from Aditya-L1's two X-ray payloads — **SoLEXS** (soft X-ray) and **HEL1OS**
(hard X-ray) — cross-validated against **GOES** ground truth, with a live
browser **command-center** that fires nowcast and forecast alerts.

> **ISRO problem statement:** *"Forecasting and/or Nowcasting of Solar Flares
> using combined Soft and Hard X-ray data from Aditya-L1."*

---

## Headline results

Trained and evaluated on **~24 months of Aditya-L1 data** (SoLEXS Feb 2024 → Jun 2026,
HEL1OS Jul 2024 → Jun 2026), with a strict chronological, **leakage-free** split.

| Capability | Result |
|---|---|
| Soft + hard master catalogue | **15,459 events**, **4,123 soft+hard dual-confirmed** |
| Flares by class | **6,464 C+**, **1,072 M+**, **68 X** |
| GOES letter-class agreement | **97 %** |
| **Neupert precursor** (hard leads soft) | nonthermal hard X-ray peaks **minutes before** the soft peak (median lead ~+184 s) |
| **Forecast model** (M+, 30-min horizon) | **TCN + LightGBM ensemble, ROC-AUC 0.847**, Brier **0.0062** (well-calibrated) |
| Median warning lead time | **~29 min** |
| Operational false-alarm rate | tunable: **0.31 false alarms/day** at the precision operating point |

> **Honesty first.** Forecasting is evaluated with in-flare samples *excluded*, so
> the model is graded on genuine pre-onset prediction — not on detecting flares
> already in progress. This is rarer than most flare-forecast write-ups and is what
> makes the numbers trustworthy. See [The science](#the-science--why-soft--hard).

---

## How each problem-statement requirement is met

| Requirement | Where |
|---|---|
| Read SoLEXS & HEL1OS time-series | [`tejas/solexs.py`](tejas/solexs.py), [`tejas/hel1os.py`](tejas/hel1os.py) |
| Detect flares independently in soft **and** hard X-rays | [`tejas/detection.py`](tejas/detection.py) (one validated detector, both channels) |
| Combine into a **master catalogue** | [`tejas/fusion.py`](tejas/fusion.py) → `outputs/fusion/master_catalog.csv` |
| Detect **low- and high-class** flares | A–X via GOES-calibrated classification ([`tejas/calibrate.py`](tejas/calibrate.py)) |
| Forecast probability of a flare in the next N minutes | [`tejas/ensemble.py`](tejas/ensemble.py), [`tejas/forecast.py`](tejas/forecast.py) |
| **High TPR / low False-Alarm Rate** | event-based FA/day + two operating points ([`tejas/ensemble.py`](tejas/ensemble.py)) |
| **Lead time** of predictions | skill-vs-lead-time + per-event lead-time distribution |
| Interface with light curves + visual alerts | [`app/web/`](app/web/) — live nowcast/forecast alert replay |

---

## Architecture

A clean dependency DAG (no cycles); `config` is the shared leaf.

```
                 ┌────────────┐
                 │  config.py │   (config.yaml: paths + all parameters)
                 └─────┬──────┘
        ┌──────────────┼───────────────┐
   solexs.py        hel1os.py        goes.py          ← data loaders
   (soft 1 s)    (hard, 5 bands)   (GOES + DONKI)
        └──────┬───────┴────────┬───────┘
            detection.py    calibrate.py              ← detection + classification
          (sliding bg +    (counts→flux→class,
           Poisson S/N)      GOES validation)
                 │               │
            fusion.py        forecast.py              ← science layer
        (Neupert master   (leakage-free features,
         catalogue)        skill curves, FAR)
                 └───────┬───────┘
                    ensemble.py                       ← TCN + LightGBM stacking
                         │
                    pipeline.py / webexport.py        ← orchestration + UI export
                         │
                    app/web/  (live command center)
```

`main.py run` → soft nowcast (+GOES) → hard detect + Neupert fusion → forecasting →
export `app/web/data/data.js`. `main.py ensemble` trains the deep ensemble.

```
tejas/
  config.py       config loader (resolves paths, merges config.local.yaml)
  solexs.py       SoLEXS soft X-ray loader (multi-day, version dedup, QA)
  hel1os.py       HEL1OS hard X-ray loader (5 energy bands, 2 detectors)
  goes.py         GOES flux + DONKI flare list; flux↔class
  detection.py    sliding-background + Poisson detector (channel-agnostic)
  calibrate.py    SoLEXS↔GOES calibration, classification, validation
  fusion.py       hard detection + Neupert effect + master catalogue
  forecast.py     leakage-free features, event-based skill (TPR / FA-per-day)
  models.py       model factory, time-aware isotonic calibration, scoring
  tcn.py          causal residual TCN (dilations 1,2,4,8,16,32)
  pretrain.py     GOES windowing helpers / transfer-learning support
  ensemble.py     TCN + LightGBM → logistic meta-learner (production model)
  compare.py      head-to-head model ranking
  pipeline.py     soft nowcasting orchestration
  webexport.py    builds the dashboard data payload
app/web/          browser command center (ECharts, offline) with live alerts
tools/            data-prep utilities (e.g. clean_hel1os.py)
main.py           CLI: run | ensemble | forecast | tcn | compare | web | dashboard | days
```

---

## Setup & run

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows  (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt

python main.py run              # nowcast + fusion + forecast + dashboard export
python main.py ensemble        # train the TCN + LightGBM forecasting ensemble
python main.py web             # serve the live command center (http://localhost:8531)
```

### Data

Download SoLEXS (Level-1/2) and HEL1OS (Level-1) from the ISRO **ISSDC PRADAN**
portal and place them under:

- `data/raw/solexs/` — the `AL1_SLX_L1_*` folders (`SDD2/*.lc.gz`)
- `data/raw/hel1os/` — the `HLS_*` packages (`cdte/lightcurve_cdte*.fits`)

GOES reference data is fetched automatically from NOAA NCEI / NASA DONKI.

The HEL1OS download is large; `tools/clean_hel1os.py` strips each package down to
just the light curves TEJAS uses (≈ 5 % of the archive).

> **Storing data elsewhere?** Create a git-ignored `config.local.yaml` to override
> paths without touching the committed config:
> ```yaml
> paths:
>   raw_solexs: D:/AdityaL1/Solex
>   raw_hel1os: D:/AdityaL1/Helios
> ```

---

## The science — why soft + hard

**The Neupert effect.** Nonthermal hard X-rays (HEL1OS, impulsive phase) track the
*time-derivative* of the soft X-ray flux (SoLEXS, gradual phase) and peak first.
TEJAS confirms this in Aditya-L1 data — so the hard channel both (a) confirms flares
for a low-false-alarm nowcast, and (b) provides genuine short-lead precursor signal.
**This is the core answer to "why combine soft and hard."**

**Leakage-free forecasting.** Samples taken while a flare is already in progress are
*excluded* as prediction points (the TCN still sees them as input history). Without
this, a model trivially "predicts" flares that have already started — inflating the
score. Removing it lowers the headline number but makes it honest.

**The model.** A stacking ensemble — a **causal residual TCN** on the raw 120-min
soft/hard/hardness sequence + **LightGBM** on engineered physics features — combined
by a logistic meta-learner with isotonic calibration. On the untouched test set the
ensemble beats both base models on every discrimination metric and is far better
calibrated (Brier 0.0062). Train it with `python main.py ensemble`.

**Honest limitation → next step.** Once leakage is removed, X-ray-only *pre-onset*
forecasting is hard: SoLEXS and HEL1OS observe the flare's radiative **onset**, not
the magnetic **cause**. The natural next step is adding upstream precursors —
Aditya-L1 **SUIT** near-UV imaging and/or photospheric magnetograms.

---

## Benchmark the models — no data download needed

The raw Aditya-L1 archive is multi-GB and can't be redistributed, so the repo ships
the **trained models** and a **held-out test set** (the models' predictions + ground
truth) so anyone can verify the accuracy independently:

```bash
git lfs install          # models + eval bundle are stored via Git LFS
git clone https://github.com/Purvajghude/TEJAS && cd TEJAS
pip install -r requirements.txt
python main.py evaluate
```

> The trained models and `eval/` bundle are tracked with **Git LFS** — install it
> (`git lfs install`) before cloning, or run `git lfs pull` after, to fetch the real
> files instead of pointer stubs.

This recomputes ROC-AUC / PR-AUC / Brier per class from `eval/test_predictions.parquet`
and prints them next to the reported numbers (they match). What's committed:

- `outputs/models/ensemble.joblib`, `ensemble_tcn.pt`, `tcn_pretrained.pt` — trained models
- `eval/test_predictions.parquet` — held-out test predictions + labels (Nov 2025 → Jun 2026)
- `eval/*.json` — the reported metrics (multiclass, ensemble, SHARP ablation, QPP)

## For collaborators — full reproduction

To retrain or extend, you need the source data (not in the repo):

1. Download SoLEXS (L1/2) + HEL1OS (L1) from **ISSDC PRADAN** into `data/raw/solexs` and
   `data/raw/hel1os` — or point elsewhere via a git-ignored `config.local.yaml`.
2. `python main.py run` (nowcast → fusion → forecast → dashboard export)
3. `python main.py ensemble` · `multiclass` · `qpp` · `sharp` (optional: `fetch_sharp.py` first)
4. `python main.py web` to serve the dashboard.

Generated outputs (`data/`, `outputs/`, `sharp.csv`) are git-ignored and regenerate from these steps.

---

## License

MIT — see [LICENSE](LICENSE). Built for the ISRO Aditya-L1 hackathon.
