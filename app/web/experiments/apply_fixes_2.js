const fs = require('fs');

const path = 'C:\\Users\\Rover\\Downloads\\Tejas-2\\TEJAS\\app\\web\\experiments\\simulation2.html';
let html = fs.readFileSync(path, 'utf-8');

// 1. Bring back the CME (Panel 5)
// cmeMesh.position.set(0, 1.5, 0);
html = html.replace(`const cmeMesh = new THREE.Mesh(cmeGeo, cmeMat);\n    sceneVoid.add(cmeMesh);`, `const cmeMesh = new THREE.Mesh(cmeGeo, cmeMat);\n    cmeMesh.position.set(0, 1.5, 0);\n    sceneVoid.add(cmeMesh);`);

// cam5.position.set(0, 14, 35); cam5.lookAt(0, 0, 0);
html = html.replace(`cam5.position.set(0, 5, 20); cam5.lookAt(0, 0, 0); // Propagation`, `cam5.position.set(0, 14, 35); cam5.lookAt(0, 0, 0); // Propagation`);

// 2. Unhide the Bow Shock (Panel 6)
// On the Bow Shock mesh, explicitly set: bowShockMesh.renderOrder = 999; bowShockMaterial.depthWrite = false; bowShockMaterial.side = THREE.DoubleSide;
// The shock material is defined as 'mat' and mesh as 'new THREE.Mesh(geo, mat)'. Let's find it.
const shockOld = `        transparent: true, blending: THREE.AdditiveBlending, opacity: 0.28,
        depthWrite: false, side: THREE.DoubleSide, wireframe: false,
      });

      shockGroup.add(new THREE.Mesh(geo, mat));
      shockGroup.userData.shockMat = mat;
    })();`;
const shockNew = `        transparent: true, blending: THREE.AdditiveBlending, opacity: 0.28,
        depthWrite: false, side: THREE.DoubleSide, wireframe: false,
      });

      const bowShockMesh = new THREE.Mesh(geo, mat);
      bowShockMesh.renderOrder = 999;
      shockGroup.add(bowShockMesh);
      shockGroup.userData.shockMat = mat;
    })();`;
html = html.replace(shockOld, shockNew);

// 3. Fix the Panel 7 Guillotine Cut
// cam7.position.set(sceneEarth.position.x, 2.8, 0.0); cam7.lookAt(sceneEarth.position);
html = html.replace(`cam7.position.set(0, 4, 1); cam7.lookAt(0, 0, 0); // Aurora`, `cam7.position.set(sceneEarth.position.x, 2.8, 0.0); cam7.lookAt(sceneEarth.position); // Aurora`);

// 4. Detonate the Solar Flare (Panel 3)
// const flareFlash = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 16), new THREE.MeshBasicMaterial({ color: 0xffffff }));
// flareFlash.position.set(0.72, 0.35, 0.45); sceneSun.add(flareFlash);
// Wrap flareFlash in a point light: const fLight = new THREE.PointLight(0xffaa00, 3.0, 5.0); fLight.position.copy(flareFlash.position); sceneSun.add(fLight);
const flareStr = `
    const flareFlash = new THREE.Mesh(
      new THREE.SphereGeometry(0.12, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0xffffff })
    );
    flareFlash.position.set(0.72, 0.35, 0.45);
    sunSystem.add(flareFlash); // Add to sunSystem so it rotates with the sun, or sceneSun as requested
    const fLight = new THREE.PointLight(0xffaa00, 3.0, 5.0);
    fLight.position.copy(flareFlash.position);
    sunSystem.add(fLight);
`;
// Let's add it right after sunSystem is created or right before sceneVoid.
html = html.replace(`// SCENE 2: VOID`, `${flareStr}\n    // SCENE 2: VOID`);

// 5. Fix the Sun Dipole Earmuffs (Panels 1–4)
// arcGroup.rotation.y = (i * Math.PI) / 6;
// In simulation2.html, the arcs are added directly to sunSystem. We can just set the mesh rotation.
const arcOldStr = `      const geo = new THREE.TubeGeometry(new THREE.QuadraticBezierCurve3(foot1, apex, foot2), 40, 0.008, 4, false);
      const mat = new THREE.ShaderMaterial({
        uniforms: { time: { value: 0 }, phase: { value: Math.random() * 6.28 }, flarePulse: { value: 0.0 } },
        vertexShader: \`varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);} \`,
        fragmentShader: \`
        uniform float time, phase, flarePulse; varying vec2 vUv;
        void main(){
          float tip = smoothstep(0.0, 0.1, vUv.x) * smoothstep(1.0, 0.9, vUv.x);
          float pulse = sin(time * 5.0 - vUv.x * 20.0 + phase) * 0.5 + 0.5;
          vec3 col = mix(vec3(0.0, 0.6, 1.0), vec3(0.8, 0.9, 1.0), pulse);
          gl_FragColor = vec4(col, tip * (0.3 + 0.7 * pulse + flarePulse * 0.5));
        }
      \`,
        transparent: true, blending: THREE.AdditiveBlending, depthWrite: false
      });
      sunSystem.add(new THREE.Mesh(geo, mat));
      arcMats.push(mat);
    }`;

const arcNewStr = `      const geo = new THREE.TubeGeometry(new THREE.QuadraticBezierCurve3(foot1, apex, foot2), 40, 0.008, 4, false);
      const mat = new THREE.ShaderMaterial({
        uniforms: { time: { value: 0 }, phase: { value: Math.random() * 6.28 }, flarePulse: { value: 0.0 } },
        vertexShader: \`varying vec2 vUv; void main(){ vUv=uv; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);} \`,
        fragmentShader: \`
        uniform float time, phase, flarePulse; varying vec2 vUv;
        void main(){
          float tip = smoothstep(0.0, 0.1, vUv.x) * smoothstep(1.0, 0.9, vUv.x);
          float pulse = sin(time * 5.0 - vUv.x * 20.0 + phase) * 0.5 + 0.5;
          vec3 col = mix(vec3(0.0, 0.6, 1.0), vec3(0.8, 0.9, 1.0), pulse);
          gl_FragColor = vec4(col, tip * (0.3 + 0.7 * pulse + flarePulse * 0.5));
        }
      \`,
        transparent: true, blending: THREE.AdditiveBlending, depthWrite: false
      });
      const arcMesh = new THREE.Mesh(geo, mat);
      arcMesh.rotation.y = (i * Math.PI) / 6;
      sunSystem.add(arcMesh);
      arcMats.push(mat);
    }`;
html = html.replace(arcOldStr, arcNewStr);

// To ensure we exactly match what the user requested "sceneSun.add(flareFlash)" vs "sunSystem.add", I added it to sunSystem because AR13664 is on the sun and the sun rotates. The user said sceneSun.add(flareFlash) but usually these are attached to the sun. I'll change it to sceneSun.add to strictly follow the prompt if needed, but sunSystem is usually what they mean so it rotates with the sun. Wait, in their prompt: "sceneSun.add(flareFlash)". I will use sceneSun.add but note it might not rotate. Actually, the user specifically said sceneSun.add, so I will do sceneSun.add.

html = html.replace('sunSystem.add(flareFlash); // Add to sunSystem so it rotates with the sun, or sceneSun as requested', 'sceneSun.add(flareFlash);');
html = html.replace('sunSystem.add(fLight);', 'sceneSun.add(fLight);');

fs.writeFileSync(path, html, 'utf-8');
console.log('Successfully applied all fixes to simulation2.html');
