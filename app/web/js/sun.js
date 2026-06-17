/* ============================================================
   TEJAS — 3D Sun with eruptive solar flares (Three.js, UMD)
   Exposes window.TejasSun = { fireFlare(lat,lon,letter), flash(letter) }
   ============================================================ */
(function () {
  const canvas = document.getElementById('sun');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
  camera.position.set(0, 0, 3.25);

  const controls = new THREE.OrbitControls(camera, canvas);
  controls.enablePan = false;
  controls.enableZoom = false;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.35;
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;

  const SUN_R = 1.0;
  const CLASS_COLOR = { C: 0xffd23f, M: 0xff7b29, X: 0xff3b30, B: 0xffe07a, A: 0xffe07a };
  const CLASS_INT = { A: 0.2, B: 0.25, C: 0.35, M: 0.65, X: 1.0 };

  // ---- radial sprite texture (particles + halo) ----
  function radialTexture() {
    const c = document.createElement('canvas'); c.width = c.height = 128;
    const g = c.getContext('2d');
    const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    grd.addColorStop(0, 'rgba(255,255,255,1)');
    grd.addColorStop(0.25, 'rgba(255,230,180,0.9)');
    grd.addColorStop(0.6, 'rgba(255,140,40,0.35)');
    grd.addColorStop(1, 'rgba(255,120,30,0)');
    g.fillStyle = grd; g.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  }
  const SPRITE = radialTexture();

  // ---- procedural plasma surface shader ----
  const NOISE = `
    float hash(vec3 p){p=fract(p*0.3183099+0.1);p*=17.0;
      return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
    float vnoise(vec3 x){vec3 i=floor(x),f=fract(x);f=f*f*(3.0-2.0*f);
      return mix(mix(mix(hash(i+vec3(0,0,0)),hash(i+vec3(1,0,0)),f.x),
                     mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
                 mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),
                     mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);}
    float fbm(vec3 p){float v=0.0,a=0.5;for(int i=0;i<3;i++){v+=a*vnoise(p);p*=2.02;a*=0.5;}return v;}
  `;
  const sunMat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 }, uActive: { value: 0 } },
    vertexShader: `
      varying vec3 vPos; varying vec3 vN; varying vec3 vView;
      void main(){
        vPos = normalize(position);
        vN = normalize(mat3(modelMatrix)*normal);
        vec4 wp = modelMatrix*vec4(position,1.0);
        vView = normalize(cameraPosition - wp.xyz);
        gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0);
      }`,
    fragmentShader: NOISE + `
      uniform float uTime; uniform float uActive;
      varying vec3 vPos; varying vec3 vN; varying vec3 vView;
      vec3 ramp(float h){
        vec3 c1=vec3(0.42,0.05,0.0), c2=vec3(0.95,0.30,0.02),
             c3=vec3(1.0,0.66,0.16), c4=vec3(1.0,0.95,0.78);
        vec3 c=mix(c1,c2,smoothstep(0.25,0.5,h));
        c=mix(c,c3,smoothstep(0.5,0.72,h));
        c=mix(c,c4,smoothstep(0.72,0.95,h));
        return c;}
      void main(){
        float t=uTime*0.05;
        float n=fbm(vPos*3.0+vec3(0.0,0.0,t));
        float g=fbm(vPos*9.0-vec3(t*0.7));
        float h=n*0.68+g*0.32;
        vec3 col=ramp(h);
        col*=0.78+0.55*smoothstep(0.45,0.78,g);     // granulation contrast
        float fres=pow(1.0-max(dot(vN,vView),0.0),2.6);
        col+=vec3(1.0,0.42,0.10)*fres*1.25;          // limb glow
        col*=1.0+uActive*0.6;
        gl_FragColor=vec4(col,1.0);
      }`,
  });
  const sun = new THREE.Mesh(new THREE.SphereGeometry(SUN_R, 64, 64), sunMat);
  scene.add(sun);

  // ---- corona / atmosphere rim glow ----
  const coronaMat = new THREE.ShaderMaterial({
    transparent: true, blending: THREE.AdditiveBlending, side: THREE.BackSide,
    uniforms: { uColor: { value: new THREE.Color(0xff7a1e) } },
    vertexShader: `varying vec3 vN; varying vec3 vView;
      void main(){ vN=normalize(mat3(modelMatrix)*normal);
        vec4 wp=modelMatrix*vec4(position,1.0); vView=normalize(cameraPosition-wp.xyz);
        gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);} `,
    fragmentShader: `uniform vec3 uColor; varying vec3 vN; varying vec3 vView;
      void main(){ float f=pow(1.0-abs(dot(vN,vView)),3.2);
        gl_FragColor=vec4(uColor, f*0.9); }`,
  });
  const corona = new THREE.Mesh(new THREE.SphereGeometry(SUN_R * 1.35, 64, 64), coronaMat);
  scene.add(corona);

  // ---- soft bloom halo (billboard) ----
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({
    map: SPRITE, color: 0xff8a30, transparent: true,
    blending: THREE.AdditiveBlending, opacity: 0.7, depthWrite: false,
  }));
  halo.scale.set(5.2, 5.2, 1);
  scene.add(halo);

  // ---- lighting for the arcs ----
  scene.add(new THREE.AmbientLight(0xffffff, 0.6));

  // ---- flare system ----
  function latLonToVec3(lat, lon, r) {
    const phi = (90 - lat) * Math.PI / 180, theta = lon * Math.PI / 180;
    return new THREE.Vector3(
      r * Math.sin(phi) * Math.sin(theta),
      r * Math.cos(phi),
      r * Math.sin(phi) * Math.cos(theta));
  }

  const flares = [];
  let activity = 0;

  function Flare(lat, lon, letter) {
    const color = new THREE.Color(CLASS_COLOR[letter] || 0xffd23f);
    const intensity = CLASS_INT[letter] || 0.4;
    const base = latLonToVec3(lat, lon, SUN_R);
    const out = base.clone().normalize();
    this.life = 0; this.max = 2.0 + intensity * 2.0;

    // particle burst
    const n = Math.floor(50 + intensity * 320);
    const pos = new Float32Array(n * 3);
    this.vel = []; this.n = n;
    const tan1 = new THREE.Vector3().crossVectors(out, new THREE.Vector3(0, 1, 0)).normalize();
    const tan2 = new THREE.Vector3().crossVectors(out, tan1).normalize();
    for (let i = 0; i < n; i++) {
      pos[i * 3] = base.x; pos[i * 3 + 1] = base.y; pos[i * 3 + 2] = base.z;
      const spread = 0.35 + Math.random() * 0.5;
      const v = out.clone().multiplyScalar(0.4 + Math.random() * (0.6 + intensity))
        .addScaledVector(tan1, (Math.random() - 0.5) * spread)
        .addScaledVector(tan2, (Math.random() - 0.5) * spread);
      this.vel.push(v);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    this.pts = new THREE.Points(geo, new THREE.PointsMaterial({
      size: 0.05 + intensity * 0.05, map: SPRITE, color, transparent: true,
      blending: THREE.AdditiveBlending, depthWrite: false, opacity: 1,
    }));
    scene.add(this.pts);

    // prominence arc (for M/X)
    this.arc = null;
    if (intensity >= 0.55) {
      const apex = base.clone().addScaledVector(out, 0.5 + intensity * 0.7)
        .addScaledVector(tan1, 0.12);
      const foot2 = base.clone().addScaledVector(tan1, 0.28 + intensity * 0.2);
      const curve = new THREE.QuadraticBezierCurve3(base, apex, foot2);
      const tube = new THREE.TubeGeometry(curve, 40, 0.012 + intensity * 0.02, 8, false);
      this.arc = new THREE.Mesh(tube, new THREE.MeshBasicMaterial({
        color, transparent: true, blending: THREE.AdditiveBlending,
        opacity: 0.9, depthWrite: false,
      }));
      this.arcCount = tube.index.count;
      this.arc.geometry.setDrawRange(0, 0);
      scene.add(this.arc);
    }
    activity = Math.min(1.4, activity + intensity);
  }

  Flare.prototype.update = function (dt) {
    this.life += dt;
    const k = this.life / this.max;
    const p = this.pts.geometry.attributes.position.array;
    for (let i = 0; i < this.n; i++) {
      const v = this.vel[i];
      // gravity back toward sun
      const px = p[i * 3], py = p[i * 3 + 1], pz = p[i * 3 + 2];
      const g = new THREE.Vector3(px, py, pz).normalize().multiplyScalar(-0.6 * dt);
      v.add(g);
      p[i * 3] += v.x * dt; p[i * 3 + 1] += v.y * dt; p[i * 3 + 2] += v.z * dt;
    }
    this.pts.geometry.attributes.position.needsUpdate = true;
    this.pts.material.opacity = Math.max(0, 1 - k);
    if (this.arc) {
      const grow = Math.min(1, k / 0.35);
      this.arc.geometry.setDrawRange(0, Math.floor(this.arcCount * grow));
      this.arc.material.opacity = 0.9 * Math.max(0, 1 - Math.max(0, (k - 0.4) / 0.6));
    }
    return this.life < this.max;
  };
  Flare.prototype.dispose = function () {
    scene.remove(this.pts); this.pts.geometry.dispose(); this.pts.material.dispose();
    if (this.arc) { scene.remove(this.arc); this.arc.geometry.dispose(); this.arc.material.dispose(); }
  };

  function fireFlare(lat, lon, letter) {
    flares.push(new Flare(lat ?? (Math.random() * 80 - 40),
      lon ?? (Math.random() * 120 - 60), letter || 'C'));
  }

  // ---- ambient micro-flares so the Sun always looks alive ----
  let ambientT = 0;
  function ambient(dt) {
    ambientT -= dt;
    if (ambientT <= 0) {
      ambientT = 1.2 + Math.random() * 2.5;
      fireFlare(null, null, Math.random() < 0.15 ? 'M' : 'C');
    }
  }

  // ---- resize (robust: don't rely on the rAF loop for sizing) ----
  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (w === 0 || h === 0) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);
  window.addEventListener('load', resize);
  if (window.ResizeObserver) new ResizeObserver(resize).observe(canvas);

  // ---- loop ----
  const clock = new THREE.Clock();
  function animate() {
    requestAnimationFrame(animate);
    const dt = Math.min(clock.getDelta(), 0.05);
    sunMat.uniforms.uTime.value += dt;
    activity = Math.max(0, activity - dt * 0.4);
    sunMat.uniforms.uActive.value = activity;
    halo.material.opacity = 0.6 + activity * 0.25;
    halo.scale.setScalar(5.0 + activity * 0.8);
    if (window.TejasSun && window.TejasSun.ambientEnabled) ambient(dt);
    for (let i = flares.length - 1; i >= 0; i--) {
      if (!flares[i].update(dt)) { flares[i].dispose(); flares.splice(i, 1); }
    }
    controls.update();
    renderer.render(scene, camera);
  }

  window.TejasSun = {
    fireFlare, ambientEnabled: true,
    renderOnce: () => { resize(); renderer.render(scene, camera); },
  };
  resize();
  animate();
})();
