# TEJAS — Aditya-L1 Solar Flare Nowcasting & Forecasting

Automated **detection, classification, fusion, and forecasting** of solar flares
from Aditya-L1's two X-ray payloads — **SoLEXS** (soft X-ray) and **HEL1OS**
(hard X-ray) — cross-validated against **GOES** ground truth, with a live 3D
"command center" interface.

> ISRO problem statement: *"Forecasting and/or Nowcasting of Solar Flares using
> combined Soft and Hard X-ray data from Aditya-L1."*

## Headline results (37 days SoLEXS + 51 days HEL1OS, Sep–Oct 2024, solar max)

| Capability | Result |
|---|---|
| Soft X-ray flares detected & classified | **338** (A–X), **96 % class agreement** with GOES |
| Calibration SoLEXS counts → GOES flux | **r = 0.99** |
| Major-flare recovery vs NOAA catalogue | **100 % of X-class (11/11)** |
| Hard X-ray flares detected (HEL1OS) | **772**, energy-resolved |
| **Soft+hard dual-confirmed** (master catalogue) | **228** flares (80 % of X, 68 % of M) |
| **Neupert precursor** (hard leads soft) | nonthermal hard X-ray peaks **~4–8 min before** the soft peak |
| **Forecast skill** (M+ flare, 15-min lead) | **ROC-AUC 0.89**, all M+ flares caught |
| **Fusion benefit** | hard X-ray cuts the false-alarm rate and **lifts precision ~+10 pts** at every lead time |

## How each problem-statement requirement is met

| Requirement | Where |
|---|---|
| Read SoLEXS & HEL1OS time-series | `tejas/solexs.py`, `tejas/hel1os.py` |
| Detect flares independently in soft **and** hard X-rays | `tejas/detection.py` (one validated detector, both channels) |
| Combine into a **master catalogue** | `tejas/fusion.py` → `outputs/fusion/master_catalog.csv` |
| Detect **low- and high-class** flares | A–X via GOES-calibrated classification (`tejas/calibrate.py`) |
| Forecast probability of a flare in the next N minutes | `tejas/forecast.py` |
| **High TPR / low False-Alarm Rate** | dual-channel confirmation + reported precision/FAR |
| **Lead time** of predictions | skill-vs-lead-time curve + lead-time distribution |
| Interface with light curves + visual alerts | `app/web/` (3D command center) |

## Architecture

A clean dependency DAG (no cycles); `config` is the shared leaf.

```
                 ┌────────────┐
                 │  config.py │  (config.yaml: paths + all parameters)
                 └─────┬──────┘
        ┌──────────────┼───────────────┐
   solexs.py        hel1os.py        goes.py        ← data loaders
   (soft 1 s)    (hard, 5 bands)   (GOES + DONKI)
        └──────┬───────┴────────┬───────┘
            detection.py    calibrate.py            ← detection + classification
          (sliding bg +    (counts→flux→class,
           Poisson S/N)      GOES validation)
                 │               │
            fusion.py        forecast.py            ← science layer
        (Neupert master   (soft+hard precursor
         catalogue)        model, skill curves)
                 └───────┬───────┘
                    pipeline.py                     ← orchestration
                    webexport.py  →  app/web/       ← presentation
```

Data flow: `main.py run` → soft nowcast (+GOES) → hard detect + Neupert fusion →
soft+hard forecasting → export `app/web/data/data.js`.

```
tejas/
  config.py       config loader (resolves paths, exposes sections)
  solexs.py       SoLEXS soft X-ray loader (multi-day, version dedup, QA)
  hel1os.py       HEL1OS hard X-ray loader (5 energy bands, 2 detectors)
  goes.py         GOES flux + DONKI flare list; flux↔class
  detection.py    sliding-background + Poisson detector (channel-agnostic)
  calibrate.py    SoLEXS↔GOES calibration, classification, validation
  fusion.py       hard detection + Neupert effect + master catalogue
  forecast.py     leakage-free forecaster, soft vs soft+hard, skill metrics
  pipeline.py     soft nowcasting orchestration
  webexport.py    builds the dashboard data payload
app/web/          3D-Sun WebGL command center (Three.js + ECharts, offline)
main.py           CLI: run | forecast | web | dashboard | days
```

## Setup & run

```bash
python -m venv .venv && .venv/Scripts/activate     # Windows
pip install -r requirements.txt

python main.py run          # full system → outputs/ + dashboard data
python main.py web          # launch the 3D command center  (recommended)
```

Place data under `data/raw/solexs/` (the `AL1_SLX_L1_*` folders, `SDD2/*.lc.gz`)
and `data/raw/hel1os/` (the `HLS_*` folders, `cdte/lightcurve_cdte*.fits`).
GOES reference data is fetched automatically.

## The science — why soft + hard

The **Neupert effect**: nonthermal hard X-rays (HEL1OS, impulsive phase) track the
*time-derivative* of the soft X-ray flux (SoLEXS, gradual phase) and peak first.
TEJAS confirms this in Aditya-L1 data (median lead ~4–8 min on X-class flares),
which is exactly why the hard channel (a) confirms flares for a low false-alarm
nowcast and (b) provides genuine short-lead precursor signal for forecasting.

Forecasting is reported **honestly**: skill is strong at short lead and decays
with horizon — X-rays capture the flare *response*, not the magnetic *cause*.
All evaluation uses a chronological, leakage-free split with walk-forward CV.

### Model selection (rigorous, `python main.py compare`)

We did not assume a model — we measured. On the same chronological test set
(30-min horizon), with time-aware isotonic calibration:

| Model | ROC-AUC |
|---|---|
| **Logistic (production choice)** | **0.78** (walk-forward 0.77 ± 0.05) |
| Random Forest | 0.75 |
| LightGBM | 0.69 |
| GOES-pretrained Temporal CNN | 0.48 |

We also built the "wild" option — a **1-D CNN pretrained on 563 days of GOES
(2022-2023, ~13,900 flare windows, no overlap with the 2024 test flares)** and
fine-tuned on Aditya-L1. It learns flare dynamics well **on GOES (AUC 0.91)** but
does **not** transfer to Aditya-L1's limited dataset (**AUC 0.48 ≈ chance**). The
0.91-vs-0.48 gap is the finding: the model is capable, the data volume is the
limit. The honest conclusion: on the
current data volume a **calibrated logistic model on physics-informed soft+hard
features** is the better, interpretable forecaster — and the pretrained GOES
representation is ready to fine-tune as more Aditya-L1 data accumulates. The
HEL1OS hard X-ray features (`h_nonth`, `h_hard`, `h_broad`) rank as the model's
top predictors, confirming the value of the combined soft+hard input.
