(function() {

  // --- CONFIG ---
  const CANVAS_ID = 'solarCanvas';
  const SUN_RADIUS = 1.8;

  // --- SCENE SETUP ---
  const canvas = document.getElementById(CANVAS_ID);
  if (!canvas) return;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
  camera.position.z = 5;

  function resizeRenderer() {
    const w = canvas.parentElement.clientWidth;
    renderer.setSize(w, w);
    camera.aspect = 1.0;
    camera.updateProjectionMatrix();
  }
  resizeRenderer();
  window.addEventListener('resize', resizeRenderer);

  // --- SUN GEOMETRY ---
  const sunGeo = new THREE.SphereGeometry(SUN_RADIUS, 64, 64);

  const textureLoader = new THREE.TextureLoader();
  const sunTexture = textureLoader.load('assets/images/sun_texture.jpg', function() {
    sunTexture.wrapS = THREE.RepeatWrapping;
    sunTexture.wrapT = THREE.RepeatWrapping;
    sunTexture.repeat.set(1, 1);
    sunMat.uniforms.hasTexture.value = true;
  });

  const sunMat = new THREE.ShaderMaterial({
    uniforms: {
      time: { value: 0 },
      flareIntensity: { value: 0.0 },
      flarePoint: { value: new THREE.Vector3(1, 0, 0) },
      sunTexture: { value: sunTexture },
      hasTexture: { value: false }
    },
    vertexShader: `
      varying vec2 vUv;
      varying vec3 vNormal;
      varying vec3 vPosition;
      void main() {
        vUv = uv;
        vNormal = normalize(normalMatrix * normal);
        vPosition = position;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform float time;
      uniform float flareIntensity;
      uniform vec3 flarePoint;
      uniform sampler2D sunTexture;
      uniform bool hasTexture;
      varying vec2 vUv;
      varying vec3 vNormal;
      varying vec3 vPosition;

      // Hash function
      float hash(float n) { return fract(sin(n) * 43758.5453123); }
      float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

      // Smooth noise
      float noise(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        return mix(
          mix(hash(i), hash(i + vec2(1,0)), f.x),
          mix(hash(i + vec2(0,1)), hash(i + vec2(1,1)), f.x),
          f.y
        );
      }

      // Fractal brownian motion — 6 octaves for detail
      float fbm(vec2 p) {
        float val = 0.0;
        float amp = 0.5;
        float freq = 1.0;
        for (int i = 0; i < 6; i++) {
          val += amp * noise(p * freq);
          freq *= 2.1;
          amp *= 0.48;
          p += vec2(0.3, 0.7);
        }
        return val;
      }

      void main() {
        // Animated UV coordinates — different speeds for layering
        vec2 uv1 = vUv * 3.0 + vec2(time * 0.04, time * 0.02);
        vec2 uv2 = vUv * 6.0 - vec2(time * 0.03, time * 0.05);
        vec2 uv3 = vUv * 1.5 + vec2(time * 0.01, time * 0.06);

        // Three layers of fbm for complexity
        float n1 = fbm(uv1);
        float n2 = fbm(uv2 + n1 * 0.8);
        float n3 = fbm(uv3 + n2 * 0.6);

        // Final combined noise — domain warping makes it look turbulent
        float plasma = fbm(uv1 + vec2(n2, n3) * 1.2);

        // Solar color palette
        vec3 darkCore    = vec3(0.55, 0.08, 0.0);
        vec3 midOrange   = vec3(0.92, 0.32, 0.0);
        vec3 brightFlame = vec3(1.0,  0.72, 0.05);
        vec3 hotYellow   = vec3(1.0,  0.95, 0.45);
        vec3 whitehot    = vec3(1.0,  0.98, 0.85);

        // Map noise to color — multi-stop gradient
        vec3 col;
        if (plasma < 0.3) {
          col = mix(darkCore, midOrange, plasma / 0.3);
        } else if (plasma < 0.55) {
          col = mix(midOrange, brightFlame, (plasma - 0.3) / 0.25);
        } else if (plasma < 0.75) {
          col = mix(brightFlame, hotYellow, (plasma - 0.55) / 0.2);
        } else {
          col = mix(hotYellow, whitehot, (plasma - 0.75) / 0.25);
        }

        if (hasTexture) {
          // Replace vUv with position-derived UV to avoid pole distortion
          vec3 pos = normalize(vPosition);
          float u = atan(pos.z, pos.x) / (2.0 * 3.14159) + 0.5;
          float v = asin(pos.y) / 3.14159 + 0.5;
          vec2 sphereUV = vec2(u + time * 0.005, v);

          // Sample the real texture
          vec4 texColor = texture2D(sunTexture, sphereUV);
          
          // The texture adds granulation and sunspot detail
          vec3 texCol = texColor.rgb;
          texCol = pow(texCol, vec3(1.2));
          
          // Blend procedural plasma with real texture
          col = mix(col, col * texCol * 1.8, 0.65);
          
          // Add texture-based granulation on top
          float texLuminance = dot(texCol, vec3(0.299, 0.587, 0.114));
          col += (texLuminance - 0.5) * 0.15;
          
          // Add normal/bump effect
          vec4 texOffset = texture2D(sunTexture, vec2(u + 0.002 + time * 0.005, v + 0.002));
          float bumpStrength = (texColor.r - texOffset.r) * 2.0;
          col += bumpStrength * 0.08;
          
          // Emission map effect
          float emission = smoothstep(0.7, 1.0, texLuminance);
          col += vec3(1.0, 0.8, 0.3) * emission * 0.4;
          
          // Animated sunspot drift using blue channel
          float sunspotMask = 1.0 - smoothstep(0.0, 0.25, texColor.b);
          col = mix(col, col * 0.2, sunspotMask * 0.7);
        } else {
          // Fallback if texture fails to load
          float spot1 = smoothstep(0.08, 0.0, length(vUv - vec2(0.3, 0.6)));
          float spot2 = smoothstep(0.06, 0.0, length(vUv - vec2(0.7, 0.35)));
          float spot3 = smoothstep(0.04, 0.0, length(vUv - vec2(0.5, 0.75)));
          float spots = spot1 + spot2 + spot3;
          col = mix(col, vec3(0.08, 0.02, 0.0), spots * 0.85);
          
          float gran = noise(vUv * 40.0 + time * 0.1) * 0.12;
          col += gran;
        }

        // Limb darkening — edges of sphere darker like real sun
        float NdotV = dot(normalize(vNormal), vec3(0.0, 0.0, 1.0));
        float limb = pow(max(NdotV, 0.0), 0.4);
        col *= (0.3 + 0.7 * limb);

        // Flare hotspot — bright eruption point
        float flareProximity = 1.0 - smoothstep(0.0, 0.6, distance(normalize(vPosition), normalize(flarePoint)));
        col += vec3(1.0, 0.65, 0.1) * flareProximity * flareIntensity * 3.0;

        gl_FragColor = vec4(col, 1.0);
      }
    `
  });

  const sunMesh = new THREE.Mesh(sunGeo, sunMat);
  scene.add(sunMesh);

  // --- CORONA GLOW ---
  const baseCoronaMat = new THREE.ShaderMaterial({
    uniforms: {
      time: { value: 0 },
      flareIntensity: { value: 0.0 },
      opacityScale: { value: 1.0 },
      colorOuter: { value: new THREE.Color(0.6, 0.1, 0.0) },
      colorInner: { value: new THREE.Color(1.0, 0.7, 0.15) },
    },
    vertexShader: `
      varying vec3 vNormal;
      varying vec3 vPosition;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        vPosition = position;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform float time;
      uniform float flareIntensity;
      uniform float opacityScale;
      uniform vec3 colorOuter;
      uniform vec3 colorInner;
      varying vec3 vNormal;
      varying vec3 vPosition;

      void main() {
        vec3 viewDir = vec3(0.0, 0.0, 1.0);
        float rim = 1.0 - abs(dot(normalize(vNormal), viewDir));
        
        // Softer falloff — power 4 instead of 2.5
        float corona = pow(rim, 4.0);
        
        // Thin sharp inner glow
        float innerGlow = pow(rim, 8.0) * 1.5;
        
        // Add subtle turbulence to corona edge
        float turb = sin(vPosition.y * 8.0 + time * 0.5) * 0.05 + 0.95;
        corona *= turb;
        
        // Color — inner is bright amber, outer fades to deep red then transparent
        vec3 col = mix(colorOuter, colorInner, innerGlow);
        
        float alpha = corona * 0.55 * (1.0 + flareIntensity * 0.4) * opacityScale;
        
        gl_FragColor = vec4(col, alpha);
      }
    `,
    transparent: true,
    side: THREE.BackSide,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const corona1Geo = new THREE.SphereGeometry(1.85, 32, 32);
  const corona1Mat = baseCoronaMat.clone();
  corona1Mat.uniforms.opacityScale.value = 1.0;
  corona1Mat.uniforms.colorOuter.value.set(0.7, 0.2, 0.0);
  const corona1Mesh = new THREE.Mesh(corona1Geo, corona1Mat);
  scene.add(corona1Mesh);

  const corona2Geo = new THREE.SphereGeometry(2.1, 32, 32);
  const corona2Mat = baseCoronaMat.clone();
  corona2Mat.uniforms.opacityScale.value = 0.6;
  corona2Mat.uniforms.colorOuter.value.set(0.6, 0.1, 0.0);
  const corona2Mesh = new THREE.Mesh(corona2Geo, corona2Mat);
  scene.add(corona2Mesh);

  const corona3Geo = new THREE.SphereGeometry(2.6, 32, 32);
  const corona3Mat = baseCoronaMat.clone();
  corona3Mat.uniforms.opacityScale.value = 0.3;
  corona3Mat.uniforms.colorOuter.value.set(0.4, 0.0, 0.0);
  const corona3Mesh = new THREE.Mesh(corona3Geo, corona3Mat);
  scene.add(corona3Mesh);

  // --- FLARE SPRITE GENERATOR ---
  let flareSpriteTexture = null;
  function getFlareSpriteTexture() {
    if (flareSpriteTexture) return flareSpriteTexture;
    const canvas = document.createElement('canvas');
    canvas.width = 128; canvas.height = 128;
    const ctx = canvas.getContext('2d');
    const grad = ctx.createRadialGradient(64,64,0,64,64,64);
    grad.addColorStop(0.0, 'rgba(255,245,200,1.0)');
    grad.addColorStop(0.2, 'rgba(255,160,30,0.8)');
    grad.addColorStop(0.5, 'rgba(200,60,0,0.3)');
    grad.addColorStop(1.0, 'rgba(0,0,0,0.0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0,0,128,128);
    flareSpriteTexture = new THREE.CanvasTexture(canvas);
    return flareSpriteTexture;
  }

  // --- FLARE ARC SYSTEM ---
  let activeArcs = [];

  function createFlareArc(intensity) {
    const angle = Math.random() * Math.PI * 2;
    const lat = (Math.random() - 0.5) * Math.PI * 0.8;

    const startDir = new THREE.Vector3(
      Math.cos(lat) * Math.cos(angle),
      Math.sin(lat),
      Math.cos(lat) * Math.sin(angle)
    ).normalize();

    // Rotate startDir by current sunMesh rotation to attach to the surface
    startDir.applyEuler(sunMesh.rotation);

    const arcPoints = [];
    const arcHeight = SUN_RADIUS * (0.3 + intensity * 0.8);
    const perpDir = new THREE.Vector3(-startDir.y, startDir.x, 0).normalize();
    const segments = 40;

    for (let i = 0; i <= segments; i++) {
      const t = i / segments;
      const h = Math.sin(t * Math.PI) * arcHeight;
      const pos = startDir.clone().multiplyScalar(SUN_RADIUS)
        .add(perpDir.clone().multiplyScalar((t - 0.5) * arcHeight * 1.2))
        .add(startDir.clone().multiplyScalar(h));
      arcPoints.push(pos);
    }

    const curve = new THREE.CatmullRomCurve3(arcPoints);
    const arcRadius = 0.025 * (1 + intensity);
    const tubeGeo = new THREE.TubeGeometry(curve, 40, arcRadius, 6, false);

    const arcMat = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: performance.now() * 0.001 },
        opacity: { value: 1.0 },
        flareColor: { value: new THREE.Color(1.0, 0.45, 0.05) }
      },
      vertexShader: `
        varying vec2 vUv;
        varying vec3 vNormal;
        void main() {
          vUv = uv;
          vNormal = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        uniform float time;
        uniform float opacity;
        uniform vec3 flareColor;
        varying vec2 vUv;
        varying vec3 vNormal;
        
        void main() {
          // Core of arc is bright white-yellow, edges are orange-red
          float edge = 1.0 - abs(dot(normalize(vNormal), vec3(0.0,0.0,1.0)));
          vec3 coreColor = vec3(1.0, 0.95, 0.6);
          vec3 edgeColor = flareColor;
          vec3 col = mix(coreColor, edgeColor, edge);
          
          // Pulse along arc length
          float pulse = 0.85 + 0.15 * sin(vUv.x * 12.0 - time * 4.0);
          col *= pulse;
          
          // Fade at tips of arc
          float tipFade = smoothstep(0.0, 0.12, vUv.x) * smoothstep(1.0, 0.88, vUv.x);
          
          gl_FragColor = vec4(col, opacity * tipFade);
        }
      `,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
    });

    const arc = new THREE.Mesh(tubeGeo, arcMat);
    scene.add(arc);

    // Glow halo tube
    const haloGeo = new THREE.TubeGeometry(curve, 40, arcRadius * 3, 6, false);
    const haloMat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(1.0, 0.3, 0.0),
      transparent: true,
      opacity: 0.15,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const halo = new THREE.Mesh(haloGeo, haloMat);
    scene.add(halo);

    // Eruption flash point sprite
    const spriteMat = new THREE.SpriteMaterial({
      map: getFlareSpriteTexture(),
      blending: THREE.AdditiveBlending,
      transparent: true,
      opacity: 0.9,
      depthWrite: false,
    });
    const flareSprite = new THREE.Sprite(spriteMat);
    flareSprite.scale.set(0.8 + intensity * 0.8, 0.8 + intensity * 0.8, 1.0);
    flareSprite.position.copy(startDir.clone().multiplyScalar(SUN_RADIUS));
    scene.add(flareSprite);

    // Update flare point on sun surface (inverse local space)
    const localDir = startDir.clone().applyEuler(new THREE.Euler(-sunMesh.rotation.x, -sunMesh.rotation.y, -sunMesh.rotation.z, 'ZYX'));
    sunMat.uniforms.flarePoint.value.copy(localDir);

    activeArcs.push({
      mesh: arc,
      mat: arcMat,
      haloMesh: halo,
      haloMat: haloMat,
      sprite: flareSprite,
      spriteMat: spriteMat,
      born: performance.now(),
      duration: 2000 + intensity * 1500,
      startDir,
    });
  }

  // --- PARTICLES (M/X class) ---
  let particleSystem = null;

  function spawnParticles(startDir, intensity) {
    if (particleSystem) {
      scene.remove(particleSystem);
      particleSystem.geometry.dispose();
    }

    const worldDir = startDir.clone().applyEuler(sunMesh.rotation);

    const count = Math.floor(80 + intensity * 120);
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const velocities = [];

    for (let i = 0; i < count; i++) {
      const spread = worldDir.clone()
        .add(new THREE.Vector3(
          (Math.random() - 0.5) * 0.8,
          (Math.random() - 0.5) * 0.8,
          (Math.random() - 0.5) * 0.8
        )).normalize().multiplyScalar(SUN_RADIUS);
      positions[i * 3] = spread.x;
      positions[i * 3 + 1] = spread.y;
      positions[i * 3 + 2] = spread.z;
      velocities.push(spread.clone().normalize().multiplyScalar(0.02 + Math.random() * 0.03 * intensity));
    }

    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const mat = new THREE.PointsMaterial({
      size: 0.04,
      color: new THREE.Color(1.0, 0.65, 0.2),
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    particleSystem = new THREE.Points(geo, mat);
    particleSystem._velocities = velocities;
    particleSystem._born = performance.now();
    particleSystem._duration = 3000;
    scene.add(particleSystem);
  }

  // --- MOUSE & TOUCH ROTATION ---
  let autoRotate = true;
  document.getElementById('autoRotateToggle').addEventListener('change', function() {
    autoRotate = this.checked;
  });

  let isDragging = false;
  let lastMouseX = 0;
  let lastMouseY = 0;
  let lastDragEndTime = 0;

  function onPointerDown(x, y) {
    isDragging = true;
    lastMouseX = x;
    lastMouseY = y;
    canvas.style.cursor = 'grabbing';
  }

  function onPointerMove(x, y, e) {
    if (isDragging) {
      if (e && e.preventDefault) e.preventDefault();
      const deltaX = x - lastMouseX;
      const deltaY = y - lastMouseY;
      
      sunMesh.rotation.y += deltaX * 0.005;
      sunMesh.rotation.x += deltaY * 0.005;
      
      const limit = Math.PI / 2.5;
      sunMesh.rotation.x = Math.max(-limit, Math.min(limit, sunMesh.rotation.x));
      
      lastMouseX = x;
      lastMouseY = y;
    }
  }

  function onPointerUp() {
    if (isDragging) {
      isDragging = false;
      lastDragEndTime = performance.now();
      canvas.style.cursor = 'grab';
    }
  }

  canvas.addEventListener('mousedown', (e) => onPointerDown(e.clientX, e.clientY));
  canvas.addEventListener('mousemove', (e) => onPointerMove(e.clientX, e.clientY, null));
  canvas.addEventListener('mouseup', onPointerUp);
  canvas.addEventListener('mouseleave', onPointerUp);

  canvas.addEventListener('touchstart', (e) => {
    onPointerDown(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });
  
  canvas.addEventListener('touchmove', (e) => {
    onPointerMove(e.touches[0].clientX, e.touches[0].clientY, e);
  }, { passive: false });
  
  canvas.addEventListener('touchend', onPointerUp);
  canvas.addEventListener('touchcancel', onPointerUp);

  // --- ZOOM ---
  let currentZoom = 5.0;
  const MIN_ZOOM = 3.0;
  const MAX_ZOOM = 8.0;
  let targetZoom = 5.0;
  let zoomBadgeTimeout = null;
  const zoomBadge = document.getElementById('solarZoomBadge');

  function showZoomBadge(text) {
    if (!zoomBadge) return;
    zoomBadge.textContent = text || (5.0 / targetZoom).toFixed(1) + '×';
    zoomBadge.classList.add('visible');
    if (zoomBadgeTimeout) clearTimeout(zoomBadgeTimeout);
    zoomBadgeTimeout = setTimeout(() => {
      zoomBadge.classList.remove('visible');
    }, 1500);
  }

  canvas.addEventListener('wheel', function(e) {
    e.preventDefault();
    const delta = e.deltaY * 0.01;
    targetZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, targetZoom + delta));
    showZoomBadge();
  }, { passive: false });

  let lastPinchDistance = 0;
  canvas.addEventListener('touchstart', function(e) {
    if (e.touches.length === 2) {
      lastPinchDistance = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
    }
  }, { passive: true });

  canvas.addEventListener('touchmove', function(e) {
    if (e.touches.length === 2) {
      e.preventDefault();
      const dist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      const delta = (lastPinchDistance - dist) * 0.05;
      targetZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, targetZoom + delta));
      lastPinchDistance = dist;
      showZoomBadge();
    }
  }, { passive: false });

  canvas.addEventListener('dblclick', function(e) {
    targetZoom = 5.0;
    showZoomBadge();
  });
  
  if (!sessionStorage.getItem('solarZoomTooltipShown')) {
    canvas.addEventListener('mouseenter', function showTooltip() {
      showZoomBadge('Double-click to reset zoom');
      if (zoomBadgeTimeout) clearTimeout(zoomBadgeTimeout);
      zoomBadgeTimeout = setTimeout(() => zoomBadge.classList.remove('visible'), 2500);
      sessionStorage.setItem('solarZoomTooltipShown', '1');
      canvas.removeEventListener('mouseenter', showTooltip);
    }, { once: true });
  }

  // --- ANIMATION LOOP ---
  let flareDecay = 0;

  function animate() {
    requestAnimationFrame(animate);
    const t = performance.now() * 0.001;

    currentZoom += (targetZoom - currentZoom) * 0.08;
    camera.position.z = currentZoom;

    sunMat.uniforms.time.value = t;
    corona1Mat.uniforms.time.value = t;
    corona2Mat.uniforms.time.value = t;
    corona3Mat.uniforms.time.value = t;

    if (autoRotate && !isDragging && (performance.now() - lastDragEndTime > 2000)) {
      sunMesh.rotation.y += 0.0015;
    }

    corona1Mesh.rotation.copy(sunMesh.rotation);
    corona2Mesh.rotation.copy(sunMesh.rotation);
    corona3Mesh.rotation.copy(sunMesh.rotation);

    if (flareDecay > 0) {
      flareDecay = Math.max(0, flareDecay - 0.008);
      sunMat.uniforms.flareIntensity.value = flareDecay;
      corona1Mat.uniforms.flareIntensity.value = flareDecay;
      corona2Mat.uniforms.flareIntensity.value = flareDecay;
      corona3Mat.uniforms.flareIntensity.value = flareDecay;
    }

    const now = performance.now();
    activeArcs = activeArcs.filter(arc => {
      const progress = (now - arc.born) / arc.duration;
      if (progress >= 1) {
        scene.remove(arc.mesh);
        arc.mesh.geometry.dispose();
        scene.remove(arc.haloMesh);
        arc.haloMesh.geometry.dispose();
        if (arc.sprite) {
           scene.remove(arc.sprite);
        }
        return false;
      }
      
      const op = progress < 0.3
        ? (progress / 0.3) * 0.9
        : (1 - (progress - 0.3) / 0.7) * 0.9;
      
      arc.mat.uniforms.opacity.value = op;
      arc.mat.uniforms.time.value = t;
      arc.haloMat.opacity = op * 0.15;
      
      if (arc.sprite) {
         const spriteProg = (now - arc.born) / 1500;
         if (spriteProg >= 1) {
            scene.remove(arc.sprite);
            arc.sprite = null;
         } else {
            arc.spriteMat.opacity = (1 - spriteProg) * 0.9;
         }
      }

      return true;
    });

    if (particleSystem) {
      const p = (now - particleSystem._born) / particleSystem._duration;
      if (p >= 1) {
        scene.remove(particleSystem);
        particleSystem = null;
      } else {
        particleSystem.material.opacity = (1 - p) * 0.85;
        const pos = particleSystem.geometry.attributes.position;
        for (let i = 0; i < particleSystem._velocities.length; i++) {
          pos.array[i * 3] += particleSystem._velocities[i].x;
          pos.array[i * 3 + 1] += particleSystem._velocities[i].y;
          pos.array[i * 3 + 2] += particleSystem._velocities[i].z;
        }
        pos.needsUpdate = true;
      }
    }

    renderer.render(scene, camera);
  }

  animate();

  // --- UI UPDATER ---
  function updateFlareUI(data) {
    const classEl = document.getElementById('solarFlareClass');
    const typeEl = document.getElementById('solarFlareType');
    const startEl = document.getElementById('solarFlareStart');
    const peakEl = document.getElementById('solarFlarePeak');
    const durEl = document.getElementById('solarFlareDuration');
    const dotEl = document.getElementById('solarIntensityDot');
    const syncDot = document.getElementById('solarSyncDot');
    const syncText = document.getElementById('solarSyncText');
    const quietState = document.getElementById('solarQuietState');
    const activeState = document.getElementById('solarActiveState');
    
    if (quietState) quietState.style.display = 'none';
    if (activeState) activeState.style.display = 'grid';

    syncDot.className = 'swc-sync-dot active';
    syncText.textContent = 'Visualization synchronized with timeline replay';

    classEl.className = 'swc-flare-class';
    classEl.textContent = data.flareClass || 'QUIET';

    const cls = (data.flareClass || '').charAt(0).toUpperCase();
    const typeMap = { 'B': 'Minor', 'C': 'Moderate', 'M': 'Strong', 'X': 'Extreme' };
    typeEl.textContent = typeMap[cls] || 'No activity';

    startEl.textContent = data.startTime || '—';
    peakEl.textContent = data.peakTime || '—';
    durEl.textContent = data.duration ? data.duration + ' min' : '—';

    document.getElementById('solarRotationVal').textContent = data.solarRotation || '—';
    document.getElementById('activeRegionVal').textContent = data.activeRegion || '—';

    const intensityMap = { 'B': '15%', 'C': '35%', 'M': '65%', 'X': '90%' };
    dotEl.style.left = intensityMap[cls] || '5%';
    
    if (cls === 'X') {
        const card = document.getElementById('solarWidgetCard');
        card.style.transition = 'border-color 0.1s, box-shadow 0.1s';
        card.style.borderColor = 'rgba(212, 168, 67, 0.5)';
        card.style.boxShadow = '0 0 20px rgba(212, 168, 67, 0.2)';
        setTimeout(() => {
            card.style.transition = 'border-color 1.5s, box-shadow 1.5s';
            card.style.borderColor = '';
            card.style.boxShadow = '';
        }, 300);
    }
  }

  function resetFlareUI() {
    const quietState = document.getElementById('solarQuietState');
    const activeState = document.getElementById('solarActiveState');
    if (quietState) quietState.style.display = 'flex';
    if (activeState) activeState.style.display = 'none';
    
    document.getElementById('solarIntensityDot').style.left = '5%';
    document.getElementById('solarSyncDot').className = 'swc-sync-dot paused';
    document.getElementById('solarSyncText').textContent = 'Replay paused';
  }

  // --- PUBLIC API ---
  window.triggerSolarFlare = function(flareClass, flareData) {
    const cls = (flareClass || 'C').charAt(0).toUpperCase();
    const intensityMap = { 'B': 0.2, 'C': 0.5, 'M': 0.8, 'X': 1.0 };
    const intensity = intensityMap[cls] || 0.5;

    flareDecay = intensity;

    const arcCount = cls === 'X' ? 3 : cls === 'M' ? 2 : 1;
    for (let i = 0; i < arcCount; i++) {
      setTimeout(() => createFlareArc(intensity), i * 300);
    }

    if (cls === 'M' || cls === 'X') {
      const dir = sunMat.uniforms.flarePoint.value.clone().applyEuler(sunMesh.rotation);
      setTimeout(() => spawnParticles(dir, intensity), 200);
    }

    if (cls === 'X') {
      const overlay = document.getElementById('solarFlareOverlay');
      overlay.classList.remove('flash');
      void overlay.offsetWidth;
      overlay.classList.add('flash');
    }

    if (flareData) updateFlareUI({ flareClass, ...flareData });
  };

  window.setSolarReplayState = function(isPlaying) {
    const dot = document.getElementById('solarSyncDot');
    const text = document.getElementById('solarSyncText');
    if (isPlaying) {
      dot.className = 'swc-sync-dot active';
      text.textContent = 'Visualization synchronized with timeline replay';
    } else {
      dot.className = 'swc-sync-dot paused';
      text.textContent = 'Replay paused';
      resetFlareUI();
    }
  };

})();
