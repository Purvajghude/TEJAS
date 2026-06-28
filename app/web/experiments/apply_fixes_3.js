const fs = require('fs');

const path = 'C:\\Users\\Rover\\Downloads\\Tejas-2\\TEJAS\\app\\web\\experiments\\simulation2.html';
let html = fs.readFileSync(path, 'utf-8');

// 1. Eradicate the Sun Mentos (Fixing Panels 2, 3, & 4)
const oldFlare = `    const flareFlash = new THREE.Mesh(
      new THREE.SphereGeometry(0.12, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0xffffff })
    );
    flareFlash.position.set(0.72, 0.35, 0.45);
    sceneSun.add(flareFlash);`;

const newFlare = `    const canvasSprite = document.createElement('canvas');
    canvasSprite.width = 128; canvasSprite.height = 128;
    const ctx = canvasSprite.getContext('2d');
    const grad = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
    grad.addColorStop(0.2, 'rgba(255, 200, 50, 0.8)');
    grad.addColorStop(1, 'rgba(255, 100, 0, 0)');
    ctx.fillStyle = grad; ctx.fillRect(0, 0, 128, 128);

    const flareFlash = new THREE.Sprite(
      new THREE.SpriteMaterial({ 
        map: new THREE.CanvasTexture(canvasSprite), 
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        transparent: true
      })
    );
    flareFlash.scale.set(0.8, 0.8, 1.0);
    flareFlash.position.set(0.72, 0.35, 0.45); // AR13664
    flareFlash.visible = false;
    sceneSun.add(flareFlash);`;

html = html.replace(oldFlare, newFlare);

// Render loop flare visibility toggle for Panel 3
const oldRender = `renderer.render(panel.scene, panel.camera);`;
const newRender = `
        if (panel.camera === cam3) {
          flareFlash.visible = true;
        }
        renderer.render(panel.scene, panel.camera);
        if (panel.camera === cam3) {
          flareFlash.visible = false;
        }`;
html = html.replace(oldRender, newRender); // Will only replace the first occurrence which is in the render loop

// 2. Summon the Missing CME (Fixing Panel 5)
html = html.replace(`cmeMesh.position.set(0, 1.5, 0);`, `cmeMesh.position.set(0, 0, 0);\n    cmeMesh.frustumCulled = false;`);
html = html.replace(`cam5.position.set(0, 14, 35); cam5.lookAt(0, 0, 0); // Propagation`, `cam5.position.set(0, 15, 30); cam5.lookAt(0, 0, 0);\n    cam5.near = 0.1;\n    cam5.far = 1000;\n    cam5.updateProjectionMatrix(); // Propagation`);

// 3. Heal the Guillotine Cut (Fixing Panel 7)
html = html.replace(`cam7.position.set(sceneEarth.position.x, 2.8, 0.0); cam7.lookAt(sceneEarth.position); // Aurora`, `cam7.fov = 22;\n    cam7.position.set(sceneEarth.position.x, 3.5, 3.5);\n    cam7.lookAt(sceneEarth.position);\n    cam7.near = 0.05;\n    cam7.updateProjectionMatrix(); // Aurora`);

// 4. Ignite the Magnetic Arcs (Panels 1–4)
// "Scale the TubeGeometry dipole loops up so their major radius extends to 1.4 * SUN_RADIUS, and ensure their material uses depthTest: false"
html = html.replace(`const hgt = 0.3;`, `const hgt = 0.4; // 1.4 * SUN_RADIUS`);
html = html.replace(`transparent: true, blending: THREE.AdditiveBlending, depthWrite: false`, `transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false`); // This will replace the arc material because it's the exact string used in that material setup

fs.writeFileSync(path, html, 'utf-8');
console.log('Successfully applied fixes 3 to simulation2.html');
