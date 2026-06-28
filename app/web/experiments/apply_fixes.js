const fs = require('fs');

const path = 'C:\\Users\\Rover\\Downloads\\Tejas-2\\TEJAS\\app\\web\\experiments\\simulation2.html';
let html = fs.readFileSync(path, 'utf-8');

// 1. RESTORE CORONA GLOW
// "Crank its base shader emission multiplier up to 1.6."
html = html.replace('mix(vec3(1.0, 0.3, 0.05), vec3(1.0, 0.65, 0.15), clamp(rayFall, 0.0, 1.0)) * 1.4', 'mix(vec3(1.0, 0.3, 0.05), vec3(1.0, 0.65, 0.15), clamp(rayFall, 0.0, 1.0)) * 1.6');

// 2. UNTANGLE THE DIPOLE
// "When generating the 12 TubeGeometry arcs, ensure their anchor azimuthal angles (phi) are evenly distributed 360 degrees around the Y-axis (i * (Math.PI * 2 / 12))."
// We replace the arc loop:
const arcOldStr = `    const arcMats = [];
    for (let k = 0; k < 20; k++) {
      let d;
      if (k < 15) {
        d = flareState.pos.clone().add(new THREE.Vector3(Math.random() * 0.5 - 0.25, Math.random() * 0.5 - 0.25, Math.random() * 0.5 - 0.25)).normalize();
      } else {
        d = new THREE.Vector3(Math.random() * 2 - 1, Math.random() * 2 - 1, Math.random() * 2 - 1).normalize();
      }

      let a = new THREE.Vector3().crossVectors(d, new THREE.Vector3(0, 1, 0)).normalize();
      if (a.lengthSq() < 0.01) a = new THREE.Vector3(1, 0, 0);

      const sep = 0.15 + Math.random() * 0.15;
      const hgt = 0.2 + Math.random() * 0.35;
      const foot1 = d.clone().multiplyScalar(SUN_RADIUS * 0.95).addScaledVector(a, -sep);
      const foot2 = d.clone().multiplyScalar(SUN_RADIUS * 0.95).addScaledVector(a, sep);
      const apex = d.clone().multiplyScalar(SUN_RADIUS * (1.0 + hgt));

      const geo = new THREE.TubeGeometry(new THREE.QuadraticBezierCurve3(foot1, apex, foot2), 40, 0.005, 4, false);`;

const arcNewStr = `    const arcMats = [];
    for (let i = 0; i < 12; i++) {
      let phi = i * (Math.PI * 2 / 12);
      let d = new THREE.Vector3(Math.cos(phi), 0.2, Math.sin(phi)).normalize();
      
      let a = new THREE.Vector3().crossVectors(d, new THREE.Vector3(0, 1, 0)).normalize();
      if (a.lengthSq() < 0.01) a = new THREE.Vector3(1, 0, 0);

      const sep = 0.15;
      const hgt = 0.3;
      const foot1 = d.clone().multiplyScalar(SUN_RADIUS * 0.95).addScaledVector(a, -sep);
      const foot2 = d.clone().multiplyScalar(SUN_RADIUS * 0.95).addScaledVector(a, sep);
      const apex = d.clone().multiplyScalar(SUN_RADIUS * (1.0 + hgt));

      const geo = new THREE.TubeGeometry(new THREE.QuadraticBezierCurve3(foot1, apex, foot2), 40, 0.008, 4, false);`;

html = html.replace(arcOldStr, arcNewStr);

// 3. Fix CME Propagation (sceneVoid) - SMOOTH THE MEAT CROISSANT & THERMAL GRADIENT
const cmeOldStr = `        vec3 crimson = vec3(0.4, 0.02, 0.0);
        vec3 amber = vec3(1.0, 0.4, 0.05);
        vec3 yellow = vec3(1.0, 0.9, 0.6);

        vec3 col = mix(crimson, amber, max(0.0, noise + 0.5));
        col = mix(col, yellow, ram * 0.9 + max(0.0, noise) * 0.1);
        
        col += yellow * ram * 2.0; // Ram-Pressure Brightening

        float alphaBase = mix(0.85, 0.15, uTransitProgress);

        float edgeFade = 1.0 - abs(normal.y);
        float alpha = alphaBase * smoothstep(0.0, 0.3, edgeFade);

        gl_FragColor = vec4(col, alpha);`;

const cmeNewStr = `        vec3 crimson = vec3(0.35, 0.01, 0.0);
        vec3 amber = vec3(1.0, 0.4, 0.05);
        vec3 yellow = vec3(1.0, 0.85, 0.4);

        vec3 col = mix(crimson, amber, max(0.0, noise + 0.5));
        col = mix(col, yellow, ram * 0.9 + max(0.0, noise) * 0.1);
        
        col += yellow * ram * 2.0; // Ram-Pressure Brightening

        float alpha = smoothstep(0.1, 0.8, noise) * mix(0.9, 0.15, uTransitProgress);

        gl_FragColor = vec4(col, alpha);`;

html = html.replace(cmeOldStr, cmeNewStr);

// 4. Fix Earth Magnetosphere (sceneEarth) - REINSTATE THE BOW SHOCK
const shockOldStr = `        transparent: true, blending: THREE.AdditiveBlending,
        depthWrite: false, side: THREE.DoubleSide, wireframe: false,`;
const shockNewStr = `        transparent: true, blending: THREE.AdditiveBlending, opacity: 0.28,
        depthWrite: false, side: THREE.DoubleSide, wireframe: false,`;
html = html.replace(shockOldStr, shockNewStr);

// Remove any lingering plane geometries in sceneEarth if there were any, but grep found none.
// Instead we'll make sure there's no stray code. "purple rectangle artifact rendering in the background"
// Actually, let's inject the EffectComposer to handle bloom, and set renderer.autoClear = false so we can clear properly.

// 5. BLOOM CHOKE
const scriptsStr = `<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>`;
const newScriptsStr = `<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
  <script src="https://unpkg.com/three@0.128.0/examples/js/shaders/CopyShader.js"></script>
  <script src="https://unpkg.com/three@0.128.0/examples/js/shaders/LuminosityHighPassShader.js"></script>
  <script src="https://unpkg.com/three@0.128.0/examples/js/postprocessing/EffectComposer.js"></script>
  <script src="https://unpkg.com/three@0.128.0/examples/js/postprocessing/RenderPass.js"></script>
  <script src="https://unpkg.com/three@0.128.0/examples/js/postprocessing/ShaderPass.js"></script>
  <script src="https://unpkg.com/three@0.128.0/examples/js/postprocessing/UnrealBloomPass.js"></script>`;
html = html.replace(scriptsStr, newScriptsStr);

// Add composer logic
const rendererStartStr = `const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });`;
const rendererEndStr = `renderer.setScissorTest(true);`;
const newRendererEndStr = `renderer.setScissorTest(true);
    renderer.autoClear = false;

    const renderTarget = new THREE.WebGLRenderTarget(window.innerWidth, window.innerHeight, {
      minFilter: THREE.LinearFilter,
      magFilter: THREE.LinearFilter,
      format: THREE.RGBAFormat,
      stencilBuffer: false
    });
    const composer = new THREE.EffectComposer(renderer, renderTarget);
    
    // We intentionally DO NOT add a RenderPass because we are manually rendering multiple scenes into the readBuffer
    const bloomPass = new THREE.UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 1.35, 0.60, 0.42);
    composer.addPass(bloomPass);
    const copyPass = new THREE.ShaderPass(THREE.CopyShader);
    composer.addPass(copyPass);`;
html = html.replace(rendererEndStr, newRendererEndStr);

// Resize handler
html = html.replace(`renderer.setSize(window.innerWidth, window.innerHeight);`, `renderer.setSize(window.innerWidth, window.innerHeight);
      composer.setSize(window.innerWidth, window.innerHeight);`);

// Render Loop changes
const renderLoopOld = `      // The Scissor Pipeline
      PANELS.forEach(panel => {
        const element = document.getElementById(panel.id);
        if (!element) return;
        
        const rect = element.getBoundingClientRect();
        
        // Convert DOM coordinates to WebGL bottom-up coordinates
        const width = rect.right - rect.left;
        const height = rect.bottom - rect.top;
        const left = rect.left;
        const bottom = renderer.domElement.clientHeight - rect.bottom;

        panel.camera.aspect = width / height;
        panel.camera.updateProjectionMatrix();

        renderer.setViewport(left, bottom, width, height);
        renderer.setScissor(left, bottom, width, height);

        // Render the specific scene & camera for this box
        renderer.render(panel.scene, panel.camera);
      });
    }
    
    animate();`;

const renderLoopNew = `      // The Scissor Pipeline
      renderer.setRenderTarget(composer.readBuffer);
      renderer.setClearColor(0x000000, 1.0);
      renderer.clear(true, true, true);
      
      PANELS.forEach(panel => {
        const element = document.getElementById(panel.id);
        if (!element) return;
        
        const rect = element.getBoundingClientRect();
        
        // Convert DOM coordinates to WebGL bottom-up coordinates
        const width = rect.right - rect.left;
        const height = rect.bottom - rect.top;
        const left = rect.left;
        const bottom = renderer.domElement.clientHeight - rect.bottom;

        panel.camera.aspect = width / height;
        panel.camera.updateProjectionMatrix();

        renderer.setViewport(left, bottom, width, height);
        renderer.setScissor(left, bottom, width, height);

        // Render the specific scene & camera for this box
        renderer.render(panel.scene, panel.camera);
      });
      
      renderer.setScissorTest(false);
      renderer.setRenderTarget(null);
      composer.render();
      renderer.setScissorTest(true);
    }
    
    animate();`;

html = html.replace(renderLoopOld, renderLoopNew);

// UI Z-index fix
// "Ensure UI DOM elements remain strictly on z-index: 2"
// Add it to .dashboard-grid and .header and .sidebar in css if not already there, 
// wait, the CSS already has: .dashboard-grid { z-index: 2; }, .header { z-index: 2; }
// Is there a .ui overlay missing? We can just forcefully do:
html = html.replace(`z-index: 0; pointer-events: none; width: 100vw; height: 100vh;`, `z-index: 0; pointer-events: none; width: 100vw; height: 100vh; position: fixed; left: 0; top: 0;`);

fs.writeFileSync(path, html, 'utf-8');
console.log('Successfully applied all fixes to simulation2.html');
