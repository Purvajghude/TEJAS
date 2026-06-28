# TEJAS — Solar "Mission Control" Visualization Engine — Build & Continuation Brief

You are a **senior ILM-grade graphics engineer + technical art director**. You are continuing
an in-progress, scientifically-believable space visualization for **TEJAS**, an ISRO Bhartiya
Antariksh Hackathon project that forecasts/nowcasts solar flares from Aditya-L1's SoLEXS (soft
X-ray) + HEL1OS (hard X-ray) instruments. The visualization is the storytelling centerpiece of
the dashboard: it must look like **NASA OpenSpace / Space Engine / Interstellar / an Apple
keynote**, NOT a student WebGL demo. "Gorgeous" is not the bar; **"scientifically believable"
is the bar.**

This brief is self-contained. Read it fully before writing any code.

---

## 1. THE PRODUCT — a 7-stage cinematic "Mission Replay", not a widget

It is ONE continuous, event-driven simulation of a solar storm from eruption to Earth impact,
seen as 7 stages on a scrubbable timeline. Reference storyboard (already designed):

1. **Quiet Sun** — boiling plasma photosphere before eruption
2. **Magnetic Build Up** — an active region intensifies; magnetic arcs swell
3. **Solar Flare** — energy release / eruption flash
4. **CME Launch** — a heavy expanding plasma cloud ejected from the corona (NOT a laser beam — it
   expands like a slow-motion explosion)
5. **CME Propagation** — the cloud + particle stream travels interplanetary space toward Earth
6. **Magnetospheric Impact** — CME hits Earth's magnetosphere; bow shock, compressed field
7. **Auroral Response** — auroras light the poles

It is a **dark, full-screen takeover** ("Mission Replay" mode) that is visually separate from the
main light-themed dashboard. The eventual integration: the user clicks "Replay Solar Event" on
the dashboard → the UI fades → this dark cinematic engine takes over → after the replay it
returns. A timeline scrubber (Quiet → Flare → CME → Impact → Aurora), layer toggles
(Sun / Earth / CME / Magnetic Field / Solar Wind / Aurora), live telemetry panels, and camera
choreography (sun fills screen → flare erupts → camera follows CME → Earth appears → aurora)
complete it.

**The whole point:** the simulation is DATA-DRIVEN by the TEJAS AI prediction. The visualization
is another *output* of the model, not decoration — it visually explains the forecast.

---

## 2. HARD ARCHITECTURE RULES (do not violate)

- **Vanilla Three.js r128 via CDN. NO React / React-Three-Fiber. NO build system, NO npm, NO
  bundler.** The existing dashboard is vanilla HTML/JS/CSS and already shipped; we must integrate
  into it with a `<script>` tag, not migrate it. Every experiment is a standalone `.html` file you
  open by double-clicking. This is deliberate: a broken build toolchain the night before the demo
  is the #1 failure risk for a non-dev team.
- **Procedural, no textures** (one allowed exception: an optional NASA Blue Marble texture on
  Earth if photo-realism is wanted later — everything else is GLSL).
- **Bloom is non-negotiable.** Without `UnrealBloomPass` the scene looks dead.
- **Performance budget: must hold 60 FPS on a weak integrated-GPU laptop (venue hardware).**
  Treat this as a hard constraint. Cap `pixelRatio` at 2, use 4-octave fBm, watch overdraw on
  large additive meshes. A single isolated piece should render a frame in well under ~8 ms.

---

## 3. THE WORKFLOW (how we build — follow exactly)

- **One effect per isolated file**, perfected in isolation, THEN integrated. Files live in
  `app/web/experiments/` (e.g. `sun.html`, `earth.html`, `flare.html`, `cme.html`,
  `particles.html`, `magnetic.html`, `camera.html`). ~200–500 lines each. Do NOT build multiple
  effects in one file; do NOT start integrating until each piece is locked.
- **Preserve every version. Delete nothing.** Before changing a working file, copy it to
  `name-vN.html` (e.g. `earth-v2.html`). AI graphics code occasionally produces something
  gorgeous then loses it on the next edit — keep the ladder.
- **Critique loop:** build → screenshot → critique as "senior NASA/ILM graphics engineer, ignore
  the code, tell me why it looks fake" → fix → repeat. Triage critiques; don't blindly apply all
  20 (see §8).
- **Send shader/coordinate MATH as copy-pasteable GLSL, not prose.** Ambiguity in math notes
  costs whole iterations. Prose is fine for color/composition/art-direction.

---

## 4. THE "HOUSE STYLE" — copy this exact setup for EVERY new piece

The Sun is locked as the canonical reference. Match its setup so all pieces feel like one engine.

**CDN includes (in this order):**
```
three r128 (cdnjs)
examples/js/shaders/CopyShader.js
examples/js/shaders/LuminosityHighPassShader.js
examples/js/postprocessing/EffectComposer.js
examples/js/postprocessing/RenderPass.js
examples/js/postprocessing/ShaderPass.js
examples/js/postprocessing/UnrealBloomPass.js
```
(unpkg `three@0.128.0/examples/js/...`)

**Renderer / scene:**
- `WebGLRenderer({ antialias:true, powerPreference:"high-performance" })`,
  `setPixelRatio(Math.min(devicePixelRatio, 2))`
- `toneMapping = ACESFilmicToneMapping`, `toneMappingExposure ≈ 1.0`
- `setClearColor(0x000000,1)`, `scene.background = new THREE.Color(0x000000)` (pitch black — any
  gray tint ruins additive blending)
- `PerspectiveCamera(33, …, 0.1, 100)`, camera pulled back (z ≈ 5) for a flat telephoto feel

**Noise:** inline the Ashima 3D simplex (`snoise(vec3)`) + a **4-octave `fbm`**. Sample on
normalized object-space position so it's seamless on spheres (no UV poles, no texture).

**Blending discipline:**
- Solid bodies (photosphere, Earth surface): `NormalBlending`, `transparent:false`, opaque.
- ALL glow/atmosphere/corona/field-lines/aurora/particles: `transparent:true`,
  `blending:AdditiveBlending`, `depthWrite:false`. Use **Fresnel** (`pow(1-dot(N,viewDir), p)`)
  so shells glow only at grazing edges and fade to invisible at the center — never solid shells.

**Post chain (order):** `RenderPass → UnrealBloomPass → chromatic-aberration ShaderPass →
film-grain ShaderPass`. CA ≈ radial RGB split 0.0018, grain opacity ≈ 0.05.

**UI overlay (HTML/CSS, not WebGL):** fixed 1px translucent frame (`inset:12px`, radius 8px);
mono uppercase telemetry, `font-weight:300`, `letter-spacing:0.2em`, `text-shadow` for legibility;
a blinking green `● LIVE` indicator; an FPS readout that fluctuates 59–61 via `setInterval`;
instrument-style labels (e.g. `FILTER: Fe XVIII 94Å`, `FOV: 1.2 R☉`, `Bz`, `Vsw`, `Kp`).

**Palette:** Sun = ruby `vec3(0.5,0.08,0)` → gold `vec3(1,0.5,0.05)` → incandescent white
`vec3(1,0.98,0.9)`. Magnetic field lines = cyan `vec3(0,0.8,1)`. Auroras = green
`vec3(0.2,1,0.4)` → violet `vec3(0.5,0.1,0.9)`. Bow shock = deep purple/blue `vec3(0.1,0,0.4)`.

**Per-file conventions:** expose `window.__render(t)` (does one synchronous `composer.render()` —
used to verify in headless/hidden tabs where requestAnimationFrame is throttled). Drag-to-orbit +
scroll-zoom. A `requestAnimationFrame` loop driving all `time` uniforms.

---

## 5. CURRENT STATUS (what exists in app/web/experiments/)

- **`sun-geminiv1.html` — Piece #1 LOCKED.** The finished Sun (procedural photosphere with
  ruby→gold→white thermal contrast, domain-warped convection, faculae; a **camera-facing
  billboard corona** with seam-free polar needle-rays via cos/sin circle-trace; crimson smoke
  prominences; cyan magnetic arcs with travelling pulses; bloom + CA + grain; telemetry UI).
  Its dead `BokehShader.js`/`BokehPass.js` includes can be stripped (DoF was dropped).
  Treat THIS file as the house-style source of truth.
- **`sun.html`, `sun-v1..v4.html`** — the iteration ladder that led to it.
- **`earth.html` — Piece #2 (Earth + magnetosphere + aurora), currently at v3, near-final.**
  Procedural dark-marble Earth (strict directional light, night-only amber city lights, ocean
  specular); tight pow-6 Fresnel cyan atmosphere; **hollow Fresnel teardrop bow shock**
  (apex-bright sunward, fades down the tail, stars shine through); **18 closed N→S CubicBezier
  dipole loops** (dayside compressed to an x≈−2 wall, nightside stretched into a teardrop tail to
  x≈+9, opacity fading down-tail); green→violet shimmering aurora ovals; deflected solar-wind
  particles. Earth is offset left so the magnetotail sweeps into the right negative space.
  - **Already wired for data:** `window.__setBz(value)` — negative IMF Bz (storm) brightens
    auroras up to +300% and pushes the bow shock closer. This is the template for data-driven
    pieces.
- **`earth-v1.html`, `earth-v2.html`** — preserved earlier versions.

---

## 6. WHAT TO BUILD NEXT (remaining pieces, then the shell)

Build each as an isolated experiment first, in the house style, reusing the Sun's
NOISE lib + post chain + camera + palette:

1. **`flare.html`** (Stage 2–3) — on a Sun, an active region brightens; magnetic arcs over it
   swell and reconnect; an eruption flash. Reuse the locked Sun verbatim as the base.
2. **`cme.html`** (Stage 4) — a heavy **expanding** plasma cloud (layered alpha-noise spheres /
   billboards that grow, NOT a beam; it should feel like a slow-motion explosion with mass).
3. **`particles.html`** (Stage 5) — GPU-friendly solar-wind particle stream flowing from Sun to
   Earth, following/bending around field lines.
4. **`magnetic.html`** (Stage 2 detail, optional) — the "active region intensifies" dense arc
   build-up (the locked Sun already has baseline cyan arcs; this is the intensifying version).
5. **`mission-replay.html` — THE INTEGRATION SHELL (do this LAST):** a single scene that imports
   the locked pieces, places Sun (left) and Earth (right) as the two anchors, adds the connective
   CME/particles between them, plus: a 7-stage **timeline scrubber**, **layer toggles**, **camera
   choreography** (state machine lerping/slerping the camera through the stages), live data
   panels, and an ETA countdown. This becomes the drop-in replacement for the dashboard's
   `app/web/js/solar-view.js`.

---

## 7. DATA INTEGRATION PLAN (this is the most important part)

Everything must be drivable by the TEJAS model output. Design every piece so its visual intensity
reads from a **single shared event-state object**, never hard-coded. Example contract:

```js
// One object the dashboard updates; the engine reacts to it.
const SolarEvent = {
  stage: 'quiet',          // quiet | buildup | flare | cme_launch | cme_propagation | impact | aurora
  flareClass: 'M2.3',      // B/C/M/X + magnitude (TEJAS multiclass output)
  probability: 0.89,       // forecast probability (drives alert intensity)
  leadTimeMin: 29,         // forecast lead time
  activeRegion: 'AR 13664',
  cme: { speedKms: 1857, widthDeg: 62, etaUtc: '2026-06-16 06:45', densitySpcc: 8.7, confidence: 0.89 },
  impact: { kp: 7.1, dstNt: -135, bzNt: -18.6, vswKms: 782 }
};
```

Mapping rules (intensity comes from data, not constants):
- **Flare class (C/M/X)** → sun flare brightness, arc count, flash strength, particle count.
- **Probability / lead time** → alert UI state + how aggressively the simulation triggers.
- **CME speed / width / density** → CME cloud size, expansion speed, opacity, travel time.
- **CME ETA** → the live countdown timer in the UI.
- **Kp / Dst / Bz / Vsw** → magnetosphere compression, aurora brightness, bow-shock standoff.
  (Earth already implements `window.__setBz(bz)` — generalize this pattern.)

**Keep the existing dashboard API working.** The current `solar-view.js` exposes:
- `window.triggerSolarFlare(flareClass, flareData)`
- `window.setSolarReplayState(isPlaying)`
The new engine must keep these (or wrap them) so `app/web/js/dashboard.js` and the timeline replay
keep working unchanged. The real data source is `app/web/data/data.js` (generated by the Python
`tejas/webexport.py`); it already contains the forecast track, multiclass probabilities, ensemble
metrics, lead times, etc. Bind the engine to that, with the `SolarEvent` object as the adapter so
the visuals never read raw data directly.

**Build order for data:** make every piece accept the state object NOW (even while values are
placeholders), so final integration is just wiring `data.js` → `SolarEvent` → the engine. Do not
hard-code magnitudes you'll later need to vary.

---

## 8. HARD-WON RULES & CORRECT PUSHBACKS (apply these; don't repeat past mistakes)

- **Corona/atmosphere/bow-shock are OPTICAL, not solid.** Always Fresnel-gated, additive,
  depthWrite:false, transparent — the camera-facing center must be ~invisible. Overlap inner glow
  shells with the body to avoid a dark gap ring; never leave concentric "bullseye" bands.
- **Radial corona rays only map straight on a flat camera-facing BILLBOARD, not on a sphere.**
  (Polar coords on a sphere produced a vortex swirl.) Use cos/sin circle-trace to avoid the seam.
- **Magnetosphere field lines must be closed N→S dipole loops** (CubicBezier), asymmetric:
  dayside compressed, nightside stretched into a teardrop tail. Open lines look like "laser beams."
- **DoF / BokehPass is DROPPED** — `BokehPass` re-renders the scene into non-multisampled buffers,
  which destroys anti-aliasing (the #1 quality fix). Do not add it without a depth-texture pass.
- **Keep custom-shader TubeGeometry for field lines/arcs, NOT Line2** — Line2/LineMaterial is
  fixed-function and would kill the per-line travelling-pulse + tail-fade shaders. Thin tubes
  (radius ≈ 0.004) + antialias give the same look and keep the effects.
- **Normal/parallax mapping is pointless on emissive bodies** (the Sun has no external light) —
  fake relief with the noise itself.
- **Performance is a feature.** Fewer fBm octaves and less additive overdraw repeatedly cut frame
  cost by 2–3×. Profile each piece (a frame should be a few ms). If a big additive mesh covers the
  screen, lower its alpha and octaves first.
- **Color:** route any "crimson → white" mix through an orange waypoint (a straight 2-color RGB
  lerp goes muddy pink). Reserve incandescent white for the hottest peaks only.

---

## 9. DEFINITION OF DONE (per piece)

A piece is "locked" when: it matches the house style; zero console errors; holds ~60 FPS on weak
hardware; reads its intensity from the shared state object (no hard-coded magnitudes); and passes
the ILM critique ("scientifically believable," not just gorgeous). Preserve it as `name-vN.html`
and move on. Integrate only after all pieces are locked.

---

### Immediate next task
Finish/confirm **`earth.html` (v3)** if any critique remains, then build **`flare.html`** (the
active-region brightening + magnetic reconnection + eruption flash on the locked Sun), accepting
the `SolarEvent` state object so flare class drives its intensity.
