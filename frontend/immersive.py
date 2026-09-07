"""
frontend/immersive.py
Full-screen scroll-driven landing experience.

WHY THIS IS ONE COMPONENT
-------------------------
The globe has to react to scrolling, and a Streamlit page cannot do that: each
`components.html` block is an iframe with its own scroll context, so a sticky
canvas in one block knows nothing about the parent page scrolling past it.

So the entire landing page lives inside a single iframe sized to the viewport,
with its own internal scroll. The canvas is `position: sticky` against that
scroll, which means one pinned 3D scene and content panels moving over it -
the pattern the reference site uses, and the only way to get it here.

WHAT DRIVES WHAT
----------------
A single scroll progress value, 0 to 1, drives everything: the globe's
rotation and distance, its drift from centre to the side so text has room,
which layer is emphasised, and the section reveals. One input, many outputs,
so nothing can fall out of sync.

The storm is not decoration. Lightning fires over the Indian domain on its own
schedule and lights the cloud layer from within, because that is the subject.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

import config


def build_immersive_html(sections: List[Dict],
                         boundary_uri: Optional[str] = None,
                         radars: Optional[List[Dict]] = None,
                         satellites: Optional[List[Dict]] = None,
                         height: int = 780) -> str:
    """
    Generate the immersive landing component.

    Args:
        sections: [{'eyebrow','title','body','items':[{'h','b'}]}, ...]
        boundary_uri: data URI of the official India boundary texture.
        radars: [{'code','city','lat','lon','live'}, ...]
        satellites: [{'name','lon','status'}, ...]
        height: iframe height. The component tries to grow itself to the
            parent viewport, and falls back to this.
    """
    payload = {
        "sections": sections,
        "boundary": boundary_uri or "",
        "radars": radars or [],
        "satellites": satellites or [],
        "bbox": list(config.INDIA_BBOX),
    }
    return (
        _TEMPLATE
        .replace("__PAYLOAD__", json.dumps(payload))
        .replace("__HEIGHT__", str(int(height)))
    )


_TEMPLATE = r"""
<div id="stage">
  <div id="sky"></div>
  <div id="globe-layer"><div id="globe-canvas"></div></div>
  <div id="scrim-left"></div>
  <div id="scrim-right"></div>
  <div id="scroll-content"></div>
  <div id="progress"><div id="progress-bar"></div></div>
  <div id="scroll-cue">
    <span>Scroll</span>
    <div id="cue-line"></div>
  </div>
</div>

<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter+Tight:wght@200;300;400;500&display=swap');

  * { box-sizing: border-box; }

  #stage {
    position: relative;
    height: __HEIGHT__px;
    overflow-y: auto;
    overflow-x: hidden;
    background: #03060D;
    font-family: 'Inter Tight', Inter, system-ui, -apple-system, sans-serif;
    scroll-behavior: smooth;
  }
  #stage::-webkit-scrollbar { width: 0; height: 0; }

  /* The night sky sits behind everything and never moves. */
  #sky {
    position: sticky; top: 0; height: 0; z-index: 0;
  }
  #sky::after {
    content: ""; position: fixed; inset: 0;
    background:
      radial-gradient(120% 85% at 78% 8%, #14294B 0%, rgba(20,41,75,0) 58%),
      radial-gradient(90% 70% at 12% 92%, #10203C 0%, rgba(16,32,60,0) 60%),
      linear-gradient(180deg, #050A16 0%, #03060D 100%);
  }

  /* One pinned canvas. Everything scrolls over it. */
  #globe-layer {
    position: fixed; inset: 0;
    z-index: 1;
    pointer-events: none;
  }
  #globe-canvas { position: absolute; inset: 0; }

  /* The globe sits behind the copy, so each side gets a gradient wash to
     guarantee contrast wherever the continent happens to be. */
  #scrim-left, #scrim-right {
    position: fixed; top: 0; bottom: 0; width: 58%;
    z-index: 1; pointer-events: none;
  }
  #scrim-left {
    left: 0;
    background: linear-gradient(90deg, rgba(3,6,13,.94) 0%,
                rgba(3,6,13,.72) 46%, rgba(3,6,13,0) 100%);
  }
  #scrim-right {
    right: 0;
    background: linear-gradient(270deg, rgba(3,6,13,.94) 0%,
                rgba(3,6,13,.72) 46%, rgba(3,6,13,0) 100%);
    opacity: 0;
    transition: opacity .6s ease;
  }
  #stage.alt #scrim-left  { opacity: 0; transition: opacity .6s ease; }
  #stage.alt #scrim-right { opacity: 1; }

  #scroll-content { position: relative; z-index: 2; }

  .panel {
    min-height: 100vh;
    display: flex; align-items: center;
    padding: 0 clamp(28px, 6vw, 92px);
    pointer-events: none;
  }
  .panel-inner {
    max-width: 620px;
    opacity: 0;
    transform: translateY(34px);
    transition: opacity .9s cubic-bezier(.16,1,.3,1),
                transform .9s cubic-bezier(.16,1,.3,1);
  }
  .panel.in .panel-inner { opacity: 1; transform: none; }
  .panel.right { justify-content: flex-end; text-align: left; }

  .eyebrow {
    font-size: 11px; font-weight: 400;
    letter-spacing: .32em; text-transform: uppercase;
    color: rgba(140, 190, 250, .78);
    margin-bottom: 18px;
  }
  .title {
    font-size: clamp(2.1rem, 4.4vw, 3.5rem);
    font-weight: 300; line-height: 1.02; letter-spacing: -.035em;
    color: #FFFFFF; margin: 0 0 20px;
  }
  .body {
    font-size: clamp(.95rem, 1.25vw, 1.16rem);
    font-weight: 300; line-height: 1.62; letter-spacing: -.018em;
    color: rgba(226, 234, 246, .72);
  }

  .items { margin-top: 30px; display: grid; gap: 20px; }
  .items.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .item {
    padding-top: 15px;
    border-top: 1px solid rgba(150, 190, 240, .22);
  }
  .item-h {
    font-size: 1.0rem; font-weight: 400; letter-spacing: -.024em;
    color: #EAF1FB; margin-bottom: 7px;
  }
  .item-b {
    font-size: .84rem; font-weight: 300; line-height: 1.6;
    color: rgba(198, 214, 236, .66);
  }

  .stats { display: flex; flex-wrap: wrap; gap: clamp(24px, 3.4vw, 54px); margin-top: 32px; }
  .stat-v {
    font-size: clamp(1.7rem, 2.7vw, 2.4rem);
    font-weight: 200; letter-spacing: -.038em; line-height: 1; color: #fff;
  }
  .stat-l {
    margin-top: 9px; font-size: 10px; font-weight: 400;
    letter-spacing: .22em; text-transform: uppercase;
    color: rgba(146, 180, 220, .62);
  }

  /* Thin progress rail on the right. */
  #progress {
    position: fixed; right: 16px; top: 50%; transform: translateY(-50%);
    width: 2px; height: 128px; z-index: 5;
    background: rgba(150, 190, 240, .16); border-radius: 2px;
  }
  #progress-bar {
    width: 100%; height: 0%;
    background: linear-gradient(180deg, #6FB6FF, #B79BFF);
    border-radius: 2px;
  }

  #scroll-cue {
    position: fixed; left: clamp(28px, 6vw, 92px); bottom: 26px; z-index: 5;
    display: flex; align-items: center; gap: 12px;
    font-size: 10px; letter-spacing: .28em; text-transform: uppercase;
    color: rgba(150, 190, 240, .58);
    transition: opacity .5s ease;
  }
  #cue-line {
    width: 46px; height: 1px; background: rgba(150, 190, 240, .38);
    position: relative; overflow: hidden;
  }
  #cue-line::after {
    content: ""; position: absolute; inset: 0;
    background: #8CC4FF;
    animation: cueSlide 1.9s ease-in-out infinite;
  }
  @keyframes cueSlide {
    0%   { transform: translateX(-100%); }
    60%  { transform: translateX(100%); }
    100% { transform: translateX(100%); }
  }
</style>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(function () {
  var DATA = __PAYLOAD__;

  var stage   = document.getElementById('stage');
  var content = document.getElementById('scroll-content');
  var host    = document.getElementById('globe-canvas');
  var bar     = document.getElementById('progress-bar');
  var cue     = document.getElementById('scroll-cue');

  // ------------------------------------------------- fill the real viewport
  // components.html fixes the iframe height server-side, but the parent is
  // same-origin here, so the frame can grow itself to the actual viewport.
  // Wrapped because a stricter sandbox must not break the page.
  try {
    var hostFrame = window.frameElement;
    if (hostFrame && window.parent && window.parent.innerHeight) {
      var target = Math.max(560, window.parent.innerHeight - 8);
      hostFrame.style.height = target + 'px';
      stage.style.height = target + 'px';
    }
  } catch (e) { /* keep the server-provided height */ }

  // ------------------------------------------------------------- sections
  DATA.sections.forEach(function (s, i) {
    var panel = document.createElement('section');
    panel.className = 'panel' + (i % 2 === 1 ? ' right' : '');

    var items = '';
    if (s.items && s.items.length) {
      items = '<div class="items' + (s.items.length > 2 ? ' two' : '') + '">' +
        s.items.map(function (it) {
          return '<div class="item"><div class="item-h">' + it.h +
                 '</div><div class="item-b">' + it.b + '</div></div>';
        }).join('') + '</div>';
    }

    var stats = '';
    if (s.stats && s.stats.length) {
      stats = '<div class="stats">' + s.stats.map(function (st) {
        return '<div><div class="stat-v">' + st.value + '</div>' +
               '<div class="stat-l">' + st.label + '</div></div>';
      }).join('') + '</div>';
    }

    panel.innerHTML =
      '<div class="panel-inner">' +
        (s.eyebrow ? '<div class="eyebrow">' + s.eyebrow + '</div>' : '') +
        '<h2 class="title">' + s.title + '</h2>' +
        (s.body ? '<p class="body">' + s.body + '</p>' : '') +
        items + stats +
      '</div>';
    content.appendChild(panel);
  });

  var panels = [].slice.call(content.querySelectorAll('.panel'));

  // Reveal is computed from scroll position rather than delegated to
  // IntersectionObserver. An observer rooted on a scroll container inside an
  // embedded frame did not fire here at all - every panel stayed at opacity 0
  // with the copy invisible. Measuring the rectangle directly is a few lines,
  // is deterministic, and cannot silently do nothing.
  function updateReveals() {
    var viewport = stage.clientHeight;
    panels.forEach(function (panel) {
      var box = panel.getBoundingClientRect();
      // Reveal once the panel has entered the lower part of the frame, and
      // treat anything already scrolled past as revealed. A fast scroll must
      // never leave a panel stranded at opacity 0.
      if (box.top < viewport * 0.82) panel.classList.add('in');
    });
  }

  // ---------------------------------------------------------------- scene
  if (typeof THREE === 'undefined') {
    panels.forEach(function (p) { p.classList.add('in'); });
    return;
  }

  var W = stage.clientWidth || 1200;
  var H = stage.clientHeight || 780;
  var R = 100;

  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(38, W / H, 1, 8000);
  var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(W, H);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.9));
  host.appendChild(renderer.domElement);

  var world = new THREE.Group();
  scene.add(world);

  function toVec(lat, lon, radius) {
    var phi = (90 - lat) * Math.PI / 180;
    var theta = (lon + 180) * Math.PI / 180;
    return new THREE.Vector3(
      -radius * Math.sin(phi) * Math.cos(theta),
       radius * Math.cos(phi),
       radius * Math.sin(phi) * Math.sin(theta)
    );
  }

  // -- ocean -------------------------------------------------------------
  world.add(new THREE.Mesh(
    new THREE.SphereGeometry(R, 72, 72),
    new THREE.MeshPhongMaterial({
      color: 0x143A60, emissive: 0x061224,
      specular: 0x14283C, shininess: 5
    })
  ));

  // -- atmosphere --------------------------------------------------------
  world.add(new THREE.Mesh(
    new THREE.SphereGeometry(R * 1.035, 72, 72),
    new THREE.ShaderMaterial({
      transparent: true, side: THREE.BackSide, depthWrite: false,
      uniforms: { glow: { value: new THREE.Color(0x5AA8F0) } },
      vertexShader:
        'varying float rim;' +
        'void main(){ vec3 n=normalize(normalMatrix*normal);' +
        'vec3 e=normalize((modelViewMatrix*vec4(position,1.0)).xyz);' +
        'rim=pow(clamp(1.0+dot(e,n),0.0,1.0),3.0);' +
        'gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
      fragmentShader:
        'uniform vec3 glow; varying float rim;' +
        'void main(){ gl_FragColor=vec4(glow, rim*0.62); }'
    })
  ));

  // -- graticule ---------------------------------------------------------
  (function graticule() {
    var mat = new THREE.LineBasicMaterial({
      color: 0x6FA8DC, transparent: true, opacity: 0.15
    });
    var g = new THREE.Group(), i, k, pts;
    for (k = -60; k <= 60; k += 20) {
      pts = [];
      for (i = 0; i <= 120; i++) pts.push(toVec(k, -180 + i * 3, R * 1.002));
      g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
    }
    for (k = -180; k < 180; k += 20) {
      pts = [];
      for (i = 0; i <= 90; i++) pts.push(toVec(-90 + i * 2, k, R * 1.002));
      g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
    }
    world.add(g);
  })();

  // -- India, from the official boundary texture -------------------------
  var indiaGroup = new THREE.Group();
  world.add(indiaGroup);

  if (DATA.boundary) {
    var bb = DATA.bbox;
    var rad = Math.PI / 180;
    new THREE.TextureLoader().load(DATA.boundary, function (tex) {
      tex.minFilter = THREE.LinearFilter;
      tex.generateMipmaps = false;
      indiaGroup.add(new THREE.Mesh(
        new THREE.SphereGeometry(
          R * 1.006, 96, 96,
          (bb[0] + 180) * rad, (bb[2] - bb[0]) * rad,
          (90 - bb[3]) * rad, (bb[3] - bb[1]) * rad
        ),
        new THREE.MeshBasicMaterial({
          map: tex, transparent: true, opacity: 0.95, depthWrite: false
        })
      ));
    });
  }

  // -- radar network -----------------------------------------------------
  var radarPins = [];
  DATA.radars.forEach(function (r) {
    var mesh = new THREE.Mesh(
      new THREE.SphereGeometry(1.5, 10, 10),
      new THREE.MeshBasicMaterial({
        color: r.live ? 0x35E08A : 0x5E7A9A, transparent: true, opacity: 0.9
      })
    );
    mesh.position.copy(toVec(r.lat, r.lon, R * 1.014));
    indiaGroup.add(mesh);
    radarPins.push(mesh);
  });

  // -- satellites --------------------------------------------------------
  // Orbit radius is compressed: at the true 6.61 Earth radii the globe
  // becomes a dot. The label says so on screen.
  var GEO = R * 2.5;
  var satGroup = new THREE.Group();
  world.add(satGroup);

  DATA.satellites.forEach(function (s) {
    var pos = toVec(0, s.lon, GEO);
    var body = new THREE.Mesh(
      new THREE.BoxGeometry(7, 5, 5),
      new THREE.MeshPhongMaterial({ color: 0x8FC4F5, emissive: 0x14324F })
    );
    body.position.copy(pos);
    body.lookAt(0, 0, 0);
    satGroup.add(body);

    var beam = new THREE.Mesh(
      new THREE.ConeGeometry(R * 0.5, pos.length() - R, 32, 1, true),
      new THREE.MeshBasicMaterial({
        color: 0x4FA8FF, transparent: true, opacity: 0.045,
        side: THREE.DoubleSide, depthWrite: false
      })
    );
    var target = toVec(22, 79, R);
    var axis = target.clone().sub(pos);
    beam.position.copy(pos.clone().add(axis.clone().multiplyScalar(0.5)));
    beam.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, -1, 0), axis.clone().normalize()
    );
    satGroup.add(beam);
  });

  var orbitPts = [];
  for (var oi = 0; oi <= 180; oi++) orbitPts.push(toVec(0, -180 + oi * 2, GEO));
  satGroup.add(new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(orbitPts),
    new THREE.LineBasicMaterial({ color: 0x3E7FBF, transparent: true, opacity: 0.28 })
  ));

  // -- storm cells over the Indian domain --------------------------------
  // These are the subject, so they get to be the brightest thing on screen
  // when they fire.
  var cells = [];
  for (var c = 0; c < 7; c++) {
    var lat = 10 + Math.random() * 22;
    var lon = 70 + Math.random() * 22;
    var mat = new THREE.MeshBasicMaterial({
      color: 0xBFE0FF, transparent: true, opacity: 0
    });
    var cell = new THREE.Mesh(new THREE.SphereGeometry(2.6, 12, 12), mat);
    cell.position.copy(toVec(lat, lon, R * 1.02));
    indiaGroup.add(cell);

    var haloMat = new THREE.MeshBasicMaterial({
      color: 0x9FD0FF, transparent: true, opacity: 0,
      side: THREE.DoubleSide, depthWrite: false
    });
    var halo = new THREE.Mesh(new THREE.RingGeometry(3.2, 8.5, 28), haloMat);
    halo.position.copy(toVec(lat, lon, R * 1.022));
    halo.lookAt(0, 0, 0);
    indiaGroup.add(halo);

    cells.push({ mat: mat, halo: haloMat, next: Math.random() * 5, level: 0 });
  }

  // -- lights ------------------------------------------------------------
  scene.add(new THREE.AmbientLight(0xFFFFFF, 0.78));
  var key = new THREE.DirectionalLight(0xEAF4FF, 0.55);
  key.position.set(240, 190, 320);
  scene.add(key);
  var fill = new THREE.DirectionalLight(0x3E7FC8, 0.35);
  fill.position.set(-300, -140, -220);
  scene.add(fill);

  // ------------------------------------------------------- scroll driving
  // One progress value drives rotation, distance, drift and emphasis, so
  // the scene can never fall out of step with the copy.
  var progress = 0, targetProgress = 0, targetLean = 1;

  function readScroll() {
    var max = stage.scrollHeight - stage.clientHeight;
    targetProgress = max > 0 ? Math.min(1, Math.max(0, stage.scrollTop / max)) : 0;
    bar.style.height = (targetProgress * 100).toFixed(1) + '%';
    cue.style.opacity = targetProgress > 0.03 ? 0 : 1;

    // Panels alternate sides; the wash follows so the copy always sits on
    // the darkened half and the globe stays visible on the other.
    var index = Math.round(stage.scrollTop / Math.max(1, stage.clientHeight));
    stage.classList.toggle('alt', index % 2 === 1);

    updateReveals();
  }
  stage.addEventListener('scroll', readScroll, { passive: true });
  readScroll();

  // ------------------------------------------------------------- render
  var startedAt = (window.performance || Date).now();
  var lastFrameAt = startedAt, prevDrawAt = startedAt;
  var elapsed = 0;

  function frame() {
    var now = (window.performance || Date).now();
    var dt = Math.min(Math.max((now - prevDrawAt) / 1000, 0.001), 0.12);
    prevDrawAt = now; lastFrameAt = now;
    elapsed = (now - startedAt) / 1000;

    // Ease toward the scroll target so flicks feel weighted, not twitchy.
    progress += (targetProgress - progress) * Math.min(1, dt * 4.5);

    // India faces the camera at rest; scrolling turns the globe a full turn.
    world.rotation.y = 2.967 + progress * Math.PI * 2.0;
    world.rotation.x = 0.30 - progress * 0.34;

    // The globe leans away from whichever side the copy is on, so the two
    // never fight for the same space.
    var panelIndex = progress * (DATA.sections.length - 1);
    var lean = Math.cos(panelIndex * Math.PI) * 0.5 + 0.5;   // 1 -> 0 -> 1
    targetLean += ((panelIndex % 2 < 1 ? 1 : -1) - targetLean) * 0.06;
    world.position.x = targetLean * 46;
    world.position.y = progress * 12;

    camera.position.set(0, 0, 330 + progress * 130);
    camera.lookAt(0, 0, 0);

    // Satellites fade in once the narrative reaches them.
    var satOpacity = Math.min(1, Math.max(0, (progress - 0.42) / 0.22));
    satGroup.traverse(function (o) {
      if (o.material && o.material.transparent !== undefined) {
        if (o.geometry && o.geometry.type === 'ConeGeometry') {
          o.material.opacity = 0.045 * satOpacity;
        } else if (o.material.opacity !== undefined && o.type === 'Line') {
          o.material.opacity = 0.28 * satOpacity;
        }
      }
      if (o.type === 'Mesh' && o.geometry && o.geometry.type === 'BoxGeometry') {
        o.visible = satOpacity > 0.02;
      }
    });

    // Storm cells: independent flashes, brightest in the middle of the story.
    var stormGain = 0.35 + 0.65 * Math.sin(Math.min(1, progress * 1.4) * Math.PI);
    cells.forEach(function (cell) {
      cell.next -= dt;
      if (cell.next <= 0) {
        cell.level = 0.75 + Math.random() * 0.25;
        cell.next = 1.6 + Math.random() * 5.5;
      }
      cell.level *= Math.exp(-dt * 3.1);
      cell.mat.opacity = cell.level * stormGain;
      cell.halo.opacity = cell.level * 0.42 * stormGain;
      var s = 1 + (1 - cell.level) * 0.9;
      cell.halo.parent && cell.halo.scale.set(s, s, s);
    });

    window.__immTime = elapsed;
    window.__immProgress = progress;

    renderer.render(scene, camera);
  }

  function loop() { requestAnimationFrame(loop); frame(); }
  loop();

  // requestAnimationFrame can be throttled to a standstill inside an
  // embedded frame. A timer backstop keeps the scene alive.
  setInterval(function () {
    if ((window.performance || Date).now() - lastFrameAt > 200) frame();
  }, 40);

  window.addEventListener('resize', function () {
    var w = stage.clientWidth, h = stage.clientHeight;
    if (!w || !h) return;
    camera.aspect = w / h; camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  });
})();
</script>
"""
