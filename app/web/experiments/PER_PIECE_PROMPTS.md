# TEJAS Viz — Per-Piece Starter Prompts (for Antigravity)

Each prompt is standalone. Paste one at a time. They all assume `ANTIGRAVITY_BRIEF.md` is in
context (house style, rules, `SolarEvent` object, perf budget). Build → screenshot → ILM critique
→ fix → preserve as `name-vN.html` → lock → next.

Every piece MUST: match the house style exactly (Three.js r128 CDN, inline Ashima snoise + 4-oct
fbm, ACES + bloom + chromatic aberration + film grain, additive Fresnel-gated glow, pitch-black
scene, mono telemetry UI, `window.__render(t)`, drag-orbit + zoom); read intensity from the
shared `SolarEvent` object (no hard-coded magnitudes); hold ~60 FPS on a weak integrated GPU.

---

## PIECE A — `flare.html`  (Stages 2–3: Magnetic Build Up + Solar Flare)

Start from the LOCKED Sun (`sun-geminiv1.html`) verbatim as the base scene — do not redesign the
Sun. Add an eruption sequence on top:

- **Active region**: pick a point on the Sun surface (from `SolarEvent.activeRegion` / a unit
  vector); brighten the photosphere there over ~2 s (a hot white-gold patch that blooms).
- **Magnetic build-up**: a cluster of cyan CubicBezier arcs over that region that grow taller and
  brighter, then **reconnect** (snap/flash) at the flare moment.
- **Flare flash**: a short, intense white-gold radial flash + a bright loop-top kernel, driven
  hard into the bloom. Add a brief screen-wide exposure bump.
- **Post-flare**: a coronal loop arcade (several bright thin loops) that lingers and fades.
- **Data hook**: `SolarEvent.flareClass` (C/M/X + magnitude) drives flash intensity, arc count,
  bloom strength, and flash radius; `SolarEvent.probability` gates whether it triggers. Expose
  `window.triggerSolarFlare(flareClass, data)` (keep the existing dashboard signature) to fire it.
- Keep `window.setSolarReplayState(isPlaying)` as a no-op stub for API compatibility.

Believability notes: reconnection should look like field lines snapping to a lower-energy loop,
not a cartoon spark. The flash is brief; the gradual phase (loops) is what lingers. ILM bar.

---

## PIECE B — `cme.html`  (Stage 4: CME Launch)

A heavy coronal mass ejection erupting from a Sun on the left. This is where most projects fail —
**it must EXPAND like a slow-motion explosion with mass, NOT shoot like a laser/beam.**

- **Cloud**: layered, expanding alpha-noise — several nested transparent additive shells/billboards
  with domain-warped fbm that grow outward from the launch point, leading edge brightest, trailing
  material more diffuse. Think a billowing plasma lobe, not a cone.
- **Flux-rope structure**: a faint twisting helical filament threading the cloud (subtle).
- **Shock front**: a brighter leading arc on the cloud's outer edge.
- **Launch**: anchored at the Sun's active-region direction; the cloud accelerates then coasts.
- **Data hook**: `SolarEvent.cme.speedKms` → expansion speed; `widthDeg` → angular size of the
  lobe; `densitySpcc` → opacity/brightness; `confidence` → edge sharpness. `flareClass` → overall
  scale. Loop/replayable.

Believability notes: real CMEs are wide, slow-looking, and three-part (bright front, dark cavity,
bright core). Heaviness sells it — ease-out expansion, never a constant-velocity dart.

---

## PIECE C — `particles.html`  (Stage 5: CME / Solar-Wind Propagation)

The particle stream crossing interplanetary space from Sun (left) toward Earth (right).

- **Stream**: thousands of GPU-friendly additive points flowing left→right, with turbulence and a
  density gradient (denser at the CME front). Use a BufferGeometry + a small custom point shader
  (size attenuation + soft round sprite + slight flicker).
- **Field-guided motion**: particles weave along gentle Parker-spiral-ish curved paths, not
  straight lines; some lead (fast), most trail.
- **Optional**: a faint volumetric "river" glow behind the particles for body.
- **Data hook**: `SolarEvent.cme.speedKms` → flow speed; `densitySpcc` → particle count/opacity;
  the front's arrival aligns with `cme.etaUtc`. Reads `stage` to start/stop.

Believability notes: it should feel like a vast diffuse flow with internal structure, not confetti.
Keep particle count high but cheap (no per-particle CPU work beyond position integration).

---

## PIECE D — `magnetic.html`  (Stage 2 detail, OPTIONAL — skip if flare.html covers it)

The "active region intensifies" close-up: dense cyan/gold magnetic arcs over one region of the Sun
swelling and shearing before reconnection. Only build this if `flare.html`'s build-up isn't enough
on its own. Same house style; arcs are thin custom-shader tubes (NOT Line2) with travelling pulses.

---

## PIECE E — `mission-replay.html`  (THE INTEGRATION SHELL — build LAST, after A–C are locked)

One scene that assembles the locked pieces into the full cinematic. Do NOT start until Sun + Earth
+ flare + cme + particles are individually locked.

- **Layout**: Sun anchored left, Earth anchored right (reuse the locked builds; import their
  geometry/shader code as modules/functions). CME + particle stream occupy the space between.
- **Single source of truth**: the `SolarEvent` object. Every sub-system reads from it. A central
  `setStage(stage)` advances the story and cross-fades systems in/out.
- **Timeline scrubber**: 7 stage markers (Quiet → Build Up → Flare → CME Launch → Propagation →
  Impact → Aurora). Dragging it sets `SolarEvent.stage` + camera target + a normalized progress
  used to drive transitions. Play/pause + speed control.
- **Camera choreography**: a state machine that lerps position + slerps orientation per stage
  (Sun fills screen → flare erupts → pull back, follow the CME rightward → Earth enters → push in
  on the aurora). Ease everything; never snap.
- **Layer toggles**: Sun / Earth / CME Front / Magnetic Field / Solar Wind / Aurora (show/hide).
- **Telemetry panels**: flare class, probability, lead time, Kp/Dst/Bz/Vsw, and a live **ETA
  countdown** ticking toward `cme.etaUtc`.
- **Dashboard API (keep working)**: `window.triggerSolarFlare(flareClass, flareData)` jumps to the
  flare stage and plays forward; `window.setSolarReplayState(isPlaying)` controls play/pause. This
  file is the drop-in replacement for `app/web/js/solar-view.js`.
- **Data binding (final step)**: read `app/web/data/data.js` (generated by `tejas/webexport.py`)
  and map it into `SolarEvent` once — the visuals already react.

Believability + performance: only the active stage's systems should run at full cost; cull/disable
off-stage systems. Must hold 60 FPS on weak hardware with the full scene assembled.

---

### Reminder of the non-negotiables (from the brief)
Additive Fresnel-gated glow (never solid shells) · corona rays on a flat billboard (cos/sin,
no seam) · closed N→S dipole loops (no laser beams) · NO DoF/Bokeh · NO Line2 (custom-shader thin
tubes) · no normal-mapping emissive bodies · crimson→white via an orange waypoint · GLSL for math,
prose for art · preserve every version · perf is a feature.
