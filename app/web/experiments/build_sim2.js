const fs = require('fs');

const dir = 'C:\\Users\\Rover\\Downloads\\Tejas-2\\TEJAS\\app\\web\\experiments\\';
const sim1 = fs.readFileSync(dir + 'simulation1.html', 'utf-8');
const flare = fs.readFileSync(dir + 'flare.html', 'utf-8');
const prop = fs.readFileSync(dir + 'propagation.html', 'utf-8');
const earth = fs.readFileSync(dir + 'earth-v9.html', 'utf-8');

// EXTRACT FLARE
const noiseStr = flare.substring(flare.indexOf('const NOISE = `'), flare.indexOf('const sunGeo =') - 1);

// Get the whole sun setup from sunGeo to arcMats push
const sunGeoStart = flare.indexOf('const sunGeo = new THREE.SphereGeometry(SUN_RADIUS, 128, 128);');
const arcMatsEndStr = 'arcMats.push(mat);\n  }';
const sunSetup = flare.substring(sunGeoStart, flare.indexOf(arcMatsEndStr) + arcMatsEndStr.length);

// EXTRACT PROPAGATION
const parkerStart = prop.indexOf('// ── Parker Spiral');
const cmeEndStr = 'scene.add(cmeMesh);';
const propSetup = prop.substring(parkerStart, prop.indexOf(cmeEndStr) + cmeEndStr.length);

// EXTRACT EARTH
const earthNoiseStart = earth.indexOf('const NOISE_GLSL = `');
const earthNoiseEnd = earth.indexOf('// ── Textures');
const earthNoiseStr = earth.substring(earthNoiseStart, earthNoiseEnd);

const texStart = earth.indexOf('const loader   = new THREE.TextureLoader();');
const shockEndStr = 'shockGroup.userData.shockMat = mat;\n})();';
const earthSetup = earth.substring(texStart, earth.indexOf(shockEndStr) + shockEndStr.length);

const masterScript = `
    const canvas = document.getElementById('master-stage');
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setScissorTest(true);

    const clock = new THREE.Clock();

    const SUN_RADIUS = 1.0;
    const SUN_POS_X = 0.0;
    
    // Globals
    const flareState = {
      pos: new THREE.Vector3(0.6, 0.35, 0.72).normalize()
    };

    ${noiseStr}
    ${earthNoiseStr}

    // ==========================================
    // 3 MASTER SCENES
    // ==========================================

    // SCENE 1: SUN
    const sceneSun = new THREE.Scene();
    const sunSystem = new THREE.Group();
    sceneSun.add(sunSystem);
    ${sunSetup.replace(/scene\.add/g, 'sunSystem.add').replace(/SUN_POS_X/g, '0')}

    // SCENE 2: VOID
    const sceneVoid = new THREE.Scene();
    ${propSetup.replace(/scene\.add/g, 'sceneVoid.add')}
    
    // SCENE 3: EARTH
    const sceneEarth = new THREE.Scene();
    const SUN_DIR = new THREE.Vector3(-1, 0, 0);
    const EARTH_R = 1.0;
    const GROUP_X = 0.0;
    const state = { auroraBoost: 1 };
    
    const dirLight = new THREE.DirectionalLight(0xfff5ea, 0.9);
    dirLight.position.set(-100, 0, 0);
    sceneEarth.add(dirLight);

    const earthGroup = new THREE.Group();
    sceneEarth.add(earthGroup);
    const shockGroup = new THREE.Group();
    sceneEarth.add(shockGroup);

    ${earthSetup.replace(/scene\.add/g, 'sceneEarth.add').replace(/shockMesh\.rotation\.y = -Math\.PI \/ 2;/g, '').replace(/shockMesh.scale.set\\(1.2, 3.0, 3.0\\);/, '')}
    
    // Fix Bow Shock scale as requested
    shockGroup.children[0].scale.set(1.2, 3.0, 3.0);

    // ==========================================
    // 7 VIEWPORT CAMERAS
    // ==========================================

    const cam1 = new THREE.PerspectiveCamera(45, 1, 0.1, 100); 
    cam1.position.set(0, 0, 6); // Quiet Sun
    
    const cam2 = new THREE.PerspectiveCamera(45, 1, 0.1, 100); 
    cam2.position.set(1.5, 1.5, 2.5); cam2.lookAt(0, 0, 0); // Mag Build Up
    
    const cam3 = new THREE.PerspectiveCamera(45, 1, 0.1, 100); 
    cam3.position.set(1.5, 1.5, 2.5); cam3.lookAt(0, 0, 0); // Flare
    
    const cam4 = new THREE.PerspectiveCamera(45, 1, 0.1, 100); 
    cam4.position.set(2.5, 0, 4); cam4.lookAt(0, 0, 0); // CME Launch
    
    const cam5 = new THREE.PerspectiveCamera(45, 1, 0.1, 100); 
    cam5.position.set(0, 5, 20); cam5.lookAt(0,0,0); // Propagation
    
    const cam6 = new THREE.PerspectiveCamera(45, 1, 0.1, 100); 
    cam6.position.set(-3, 0, 3); cam6.lookAt(0,0,0); // Mag Impact
    
    const cam7 = new THREE.PerspectiveCamera(45, 1, 0.1, 100); 
    cam7.position.set(0, 4, 1); cam7.lookAt(0,0,0); // Aurora

    // ==========================================
    // PANEL MAPPING
    // ==========================================
    const PANELS = [
      { id: 'panel-1', scene: sceneSun, camera: cam1 },
      { id: 'panel-2', scene: sceneSun, camera: cam2 },
      { id: 'panel-3', scene: sceneSun, camera: cam3 },
      { id: 'panel-4', scene: sceneSun, camera: cam4 },
      { id: 'panel-5', scene: sceneVoid, camera: cam5 },
      { id: 'panel-6', scene: sceneEarth, camera: cam6 },
      { id: 'panel-7', scene: sceneEarth, camera: cam7 },
    ];

    window.addEventListener('resize', () => {
      renderer.setSize(window.innerWidth, window.innerHeight);
    });

    // ==========================================
    // RENDER LOOP
    // ==========================================
    function animate() {
      requestAnimationFrame(animate);
      
      const t = clock.getElapsedTime();

      // Update Sun
      sunSystem.rotation.y += 0.001;
      sunMat.uniforms.time.value = t;
      sunMat.uniforms.arIntensity.value = 0.5; // static for now
      coronaBillboardMat.uniforms.time.value = t;
      
      for (let i = 0; i < promMats.length; i++) promMats[i].uniforms.time.value = t;
      for (let i = 0; i < arcMats.length; i++) {
        arcMats[i].uniforms.time.value = t;
        arcMats[i].uniforms.flarePulse.value = 0.5;
      }

      // Update Void
      spiralMat.uniforms.uTime.value = t;
      cmeMat.uniforms.uTime.value = t;
      const uTransitProgress = (t % 12.0) / 12.0;
      cmeMat.uniforms.uTransitProgress.value = uTransitProgress;
      cmeMesh.position.x = -15.0 + uTransitProgress * 32.0;
      const scale = 1.0 + (uTransitProgress * 2.5);
      cmeMesh.scale.set(scale, scale, scale);

      // Update Earth
      earthGroup.rotation.y += 0.0009;
      auroraMat.uniforms.uTime.value = t;
      cloudMesh.rotation.y += 0.001;
      if (shockGroup.userData.shockMat) {
        shockGroup.userData.shockMat.uniforms.uTime.value = t;
      }

      // The Scissor Pipeline
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
    
    animate();
`;

const scissorStart = sim1.indexOf('<!-- SCISSOR PIPELINE IMPLEMENTATION -->\n  <script>') + '<!-- SCISSOR PIPELINE IMPLEMENTATION -->\n  <script>'.length;
const scissorEnd = sim1.lastIndexOf('</script>');

const finalHTML = sim1.substring(0, scissorStart) + masterScript + sim1.substring(scissorEnd);

fs.writeFileSync(dir + 'simulation2.html', finalHTML, 'utf-8');
console.log('Successfully wrote simulation2.html');
