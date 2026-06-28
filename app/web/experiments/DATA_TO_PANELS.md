# TEJAS — Data → Panels Brief (for Antigravity)

**Read this fully before building anything.** You (the agent) have no prior context on this project.
This document tells you (1) what TEJAS is, (2) the EXACT data it produces, (3) the one law you must
never break, and (4) exactly which panels to build, what data drives each, and how to show it.

---

## 0. What TEJAS is (30 seconds)

TEJAS is an ISRO hackathon project that **detects and forecasts solar flares** from **Aditya-L1's
two X-ray instruments — SoLEXS (soft X-ray) + HEL1OS (hard X-ray)** — cross-checked against GOES.
Its novel result: **hard X-rays peak ~184 s BEFORE soft X-rays (the Neupert effect)**, which gives
an early-warning signal, plus a leakage-free ML forecast of the next flare.

**Critical limitation (this governs everything):** these are X-ray instruments. They observe the
flare's *radiative onset*. They DO NOT measure: CME speed/direction, solar wind, the interplanetary
magnetic field (Bz), geomagnetic indices (Kp/Dst), or auroras. They also have **no imaging**, so
the *location* of a flare on the solar disk is unknown.

---

## 1. The data you actually have: `window.TEJAS`

The page loads `app/web/data/data.js`, which defines a global `window.TEJAS`. This is the ONLY source
of truth. Code defensively — any top-level key can be `null` if that stage wasn't run. Schema:

```
TEJAS.meta        { dateStart, dateEnd, nDays }
TEJAS.kpis        { nFlares, nX, nM, nC, agreement /*GOES letter-class %*/, calibR, recallOverall }
TEJAS.flares[]    { id, t /*peak ISO*/, start, end, cls /*SoLEXS e.g. "M2.3"*/, clsGoes, letter,
                    counts, flux, fluxGoes, sig /*S/N*/, durMin, lon, lat /*⚠ ILLUSTRATIVE, fake*/ }
TEJAS.light       { t[], counts[] /*SoLEXS soft*/, xrsb[] /*GOES flux*/, hard[] /*HEL1OS hard*/ }   ← the dual light curve
TEJAS.dist        { A, B, C, M, X }   /* flare counts by class */
TEJAS.fusion      { nSoft, nHard, nDualConfirmed, dualByClass,
                    neupertLeadMedianS /* ~184, hard leads soft */, neupertN }
TEJAS.forecast    { primaryHorizon, skillCurve[ {h,auc,aucSoft,tss,precision,far,lead} ],
                    leadMedian, eventRecall, fusionBenefit, ... }
TEJAS.ensemble    { auc /*0.847*/, tss /*0.541*/, brier, horizon,
                    leadMedianToPeak, leadMedianToOnset, pctAlertsBeforeOnset,
                    precisionOp /* {threshold, recall, fa/day≈0.31, episode precision} */,
                    recallOp, tcnCalibrationGain,
                    track { t[], p[] } }   ← the LIVE forecast probability curve over time
TEJAS.multiclass  { horizon, classes { C:{auc,recall,lead,label}, M:{...}, X:{...} },
                    track { t[], p_C[], p_M[], p_X[] } }   ← LIVE per-class probability over time
TEJAS.qpp         { fraction, nDetected, nAnalysed, medianPeriodS, periodRangeS, literatureContext }
TEJAS.benchmark   { horizon_min, baselines[ {model, TSS, AUC} ], literature[], literatureCaveat }
TEJAS.sharp       { coverage, xrayAuc, sharpAuc, benefitAuc, benefitTss, topFeatures[], validation }
```

**There is NO cme / kp / dst / bz / vsw / aurora / solarwind anywhere in this object. They do not
exist. Do not invent them as if they were model outputs.**

---

## 2. THE LAW (never break this)

**Every number on screen carries a provenance badge.** Put a permanent legend on the page and a
small badge on every panel:

- 🟢 **LIVE** — read directly from `window.TEJAS` (real Aditya-L1 / TEJAS result)
- 🟡 **MODELLED** — computed from a *cited* empirical relationship (must show the citation)
- ⚪ **ILLUSTRATIVE** — scenario for visual context; not measured by TEJAS

If a value can't be 🟢 or honestly 🟡, it is ⚪ and must be visibly watermarked, or cut. This single
rule converts your biggest weakness (made-up CME/Kp numbers) into a credibility *strength*.

---

## 3. What to build: TWO MODES sharing one data source

### MODE A — "EVIDENCE VIEW" (the HERO — build this FIRST)
A data-faithful instrument board. Every panel below is 🟢 LIVE and binds to a real `TEJAS.*` field.
This is what wins the technical Q&A and it currently doesn't exist.

### MODE B — "MISSION REPLAY" (the cinematic HOOK — already in progress, demote + label)
The 3D Sun→Earth story (files `simulation*.html`, `sun-geminiv1.html`, `earth*.html`). Keep it, but:
stages driven by real data = 🟢; the CME→Earth→aurora stages = ⚪ watermarked scenario. A toggle
flips between the two modes.

---

## 4. PANEL-BY-PANEL SPEC (build the 🟢 ones first)

| # | Panel | Data source (from `window.TEJAS`) | How to show it | Tier |
|---|---|---|---|---|
| 1 | **Dual X-ray light curve + Neupert lag** ⭐ | `light.t/counts/xrsb/hard` + `fusion.neupertLeadMedianS`, `fusion.neupertN` | Time-series: SoLEXS soft (blue), HEL1OS hard (green), GOES (amber). On a flare, annotate the hard peak leading the soft peak by ~184 s. **This is the signature panel — biggest, most prominent.** | 🟢 |
| 2 | **Forecast risk curve** ⭐ | `ensemble.track.{t,p}` + `ensemble.precisionOp.threshold` | Probability(t) line with the alert threshold; fire an alert marker when p crosses it. Show `ensemble.leadMedianToOnset` as the lead. | 🟢 |
| 3 | **Live P(C/M/X) bars** | `multiclass.track.{t,p_C,p_M,p_X}` | Three bars that update as the timeline scrubs; label each with `multiclass.classes[*].auc`. | 🟢 |
| 4 | **Skill scorecard + baseline bars** ⭐ | `ensemble.auc/tss/brier`, `benchmark.baselines[]`, `ensemble.precisionOp` (≈0.31 FA/day), `kpis.agreement` (GOES 97%) | Big numbers + a small bar chart: ensemble TSS vs persistence vs climatology (the **4.5×** story). | 🟢 |
| 5 | **Flare event card** | `flares[]` (`cls,clsGoes,t,start,end,durMin,sig,flux`) | Class / peak time / duration / S/N. ⚠ **Do NOT show a precise solar-disk location** — `lon/lat` are illustrative. If you place a marker on the 3D Sun, badge it ⚪. | 🟢 (card) |
| 6 | **QPP panel** | `qpp.fraction/medianPeriodS/periodRangeS/literatureContext` | Pulsation indicator + the honest `literatureContext` text (why our rate differs from literature). | 🟢 |
| 7 | **Mission KPIs / coverage** | `meta`, `kpis`, `dist` | Total flares, C/M/X distribution, date range, days observed. | 🟢 |
| 8 | **SHARP magnetogram context** (optional) | `sharp.*` | Honest ablation: X-ray-only vs +SHARP; mark SHARP as **SDO/HMI (NASA), not Aditya-L1**. | 🟡 |
| 9 | **The 3D Sun itself** | flare flash ← `flares[].cls` + Neupert timing from `light`; corona/active-region glow ← `ensemble.track.p` | Make the Sun a *data display*: its flare flash and risk-glow are bound to real numbers, not decoration. | 🟢 (driven) |
| 10 | **CME association** (if you must show CME) | `flares[].cls` → CME-association probability via published flare–CME statistics (cite it) | A probability/likelihood only — **never a hard speed/width**. | 🟡 |
| 11 | CME kinematics, ETA, Kp, Dst, Bz, Vsw, aurora, Earth impact | ❌ none — not in `TEJAS` | Scenario only, watermarked "Illustrative — downstream space-weather context, not measured by Aditya-L1 X-ray payloads." | ⚪ |

---

## 5. What to CUT or WATERMARK (do this now)

- ❌ **Delete any hard CME number** presented as output (speed 1857 km/s, width 62°, density 8.7).
- ❌ **Delete Kp 7.1 / Dst −135 / Bz −18.6 / Vsw 782** as outputs. They're ⚪ scenario at most.
- ⚠ **Drop precise flare disk coordinates / "AR 13664"** unless cross-referenced from NOAA/DONKI
  (then 🟡). The `lon/lat` in the data are seeded fakes.
- ⚠ The whole **CME→Earth→Aurora** sequence stays as the ⚪ cinematic hook — watermark it, don't
  present its numbers as TEJAS results.

---

## 6. What to do with the existing experiment files

- `sun-geminiv1.html` — **the locked Sun**. House-style reference. Reuse it; bind its flare/glow to
  real data (panel 9).
- `earth*.html` (up to v9) — the Earth/magnetosphere/aurora piece. Keep for the ⚪ cinematic;
  watermark it; **do not surface its Kp/Bz/aurora numbers as real.**
- `flare.html`, `propagation.html`, `simulation*.html`, `build_sim2.js` — integration attempts.
  Fold them into the Mode B cinematic. The Mode A Evidence View is new and is the priority.
- House style for any new file: vanilla Three.js r128 via CDN (no build), inline Ashima simplex +
  4-octave fbm, ACES tonemap + UnrealBloom + chromatic aberration + film grain, additive
  Fresnel-gated glow (never solid shells), pitch-black scene, mono telemetry UI, ~60 FPS on weak
  GPUs. (See `ANTIGRAVITY_BRIEF.md` for the full house-style spec.)

---

## 7. The wiring (one adapter, provenance built in)

Read `window.TEJAS` once and fan it into a single state object the visuals consume. The tier travels
with every field, so the badge is automatic:

```js
const S = {
  live: {
    light:      TEJAS.light,                 // dual light curve
    forecast:   TEJAS.ensemble?.track,       // {t[],p[]}
    threshold:  TEJAS.ensemble?.precisionOp?.threshold,
    cmx:        TEJAS.multiclass?.track,     // {t,p_C,p_M,p_X}
    neupertS:   TEJAS.fusion?.neupertLeadMedianS,
    skill:      { auc:TEJAS.ensemble?.auc, tss:TEJAS.ensemble?.tss, brier:TEJAS.ensemble?.brier },
    baselines:  TEJAS.benchmark?.baselines,
    flares:     TEJAS.flares,
    qpp:        TEJAS.qpp,
    kpis:       TEJAS.kpis,
  },
  modelled:    { cmeAssocProb: /* from flares[].cls via cited stats */ null },
  illustrative:{ cme:null, kp:null, dst:null, bz:null, vsw:null, aurora:null }, // scenario knobs only
};
```

Scrubbing the timeline = moving an index through `light.t` / `ensemble.track.t`; every 🟢 panel and
the 3D Sun read from that index. Final integration is just this mapping — the visuals already react.

---

### Immediate task for the agent
Build **MODE A — Evidence View** first, panels 1→4 (dual light curve + Neupert, forecast risk curve,
P(C/M/X) bars, skill scorecard), bound to `window.TEJAS`, each with a provenance badge and the global
legend. Only after that, return to the Mode B cinematic and **watermark** its CME/Earth/aurora stages.
