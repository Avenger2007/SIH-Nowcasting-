"""
frontend/globe.py
Interactive 3D globe of the Indian observation network.

Renders, with real geometry:

  * INSAT-3D / 3DR / 3DS at their true sub-satellite longitudes, with scan
    cones toward the Indian region. The ORBIT RADIUS IS COMPRESSED: true
    geostationary altitude is 6.61 Earth radii, at which scale the Earth
    becomes a dot and the radar network is unreadable. The legend states
    this and each tooltip reports the true 35,786 km altitude;
  * every IMD Doppler Weather Radar site at its published coordinates, with
    range rings scaled to the actual radar range and coloured by whether the
    site is currently publishing data;
  * animated data-flow arcs from the active sources into the processing hub;
  * the selected forecast location, with its risk level.

A deliberate design decision: NO national boundaries are drawn. Territorial
borders - especially in the north - are politically sensitive and a
schematic outline would be both inaccurate and unnecessary. The radar network
and city markers are at real coordinates and trace the geography by
themselves, which is what an operations display actually needs.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

import config


def _satellite_payload() -> List[Dict]:
    return [
        {
            "name": s.name,
            "operator": s.operator,
            "lon": s.longitude,
            "altitude": s.altitude_km,
            "instruments": list(s.instruments),
            "status": s.status,
            "note": s.note,
            "geo": s.altitude_km > 30000,
        }
        for s in config.SATELLITES
    ]


def _radar_payload(network_status: Optional[List[Dict]] = None) -> List[Dict]:
    live_map = {r["code"]: r.get("live", False) for r in (network_status or [])}
    contributing = {r["code"]: r.get("contributing", False)
                    for r in (network_status or [])}

    return [
        {
            "code": s.code,
            "city": s.city,
            "lat": s.lat,
            "lon": s.lon,
            "band": s.band,
            "range": s.range_km,
            "live": bool(live_map.get(s.code, False)),
            "contributing": bool(contributing.get(s.code, False)),
        }
        for s in config.DWR_NETWORK
    ]


def build_globe_html(selected_city: Optional[Dict] = None,
                     network_status: Optional[List[Dict]] = None,
                     source_status: Optional[Dict[str, str]] = None,
                     height: int = 660) -> str:
    """
    Generate the self-contained globe component.

    Args:
        selected_city: {'name', 'lat', 'lon', 'risk', 'probability'}
        network_status: rows from utils.datasources.radar.network_status
        source_status: {'satellite': 'live', 'radar': 'live', ...}
    """
    payload = {
        "satellites": _satellite_payload(),
        "radars": _radar_payload(network_status),
        "cities": [
            {"name": c.name, "lat": c.lat, "lon": c.lon, "state": c.state}
            for c in config.CITIES
        ],
        "selected": selected_city or {},
        "sources": source_status or {},
        "height": height,
    }

    return (
        _TEMPLATE
        .replace("__PAYLOAD__", json.dumps(payload))
        .replace("__HEIGHT__", str(int(height)))
    )


_TEMPLATE = r"""
<div id="globe-root">
  <div id="globe-canvas"></div>

  <div class="globe-overlay globe-title">
    <div class="gt-main">INDIAN OBSERVATION NETWORK</div>
    <div class="gt-sub">INSAT geostationary fleet &middot; IMD Doppler radar &middot; live data flow</div>
  </div>

  <div class="globe-overlay globe-legend">
    <div class="gl-row"><span class="dot dot-live"></span>Radar publishing</div>
    <div class="gl-row"><span class="dot dot-contrib"></span>In this nowcast</div>
    <div class="gl-row"><span class="dot dot-off"></span>No public feed</div>
    <div class="gl-row"><span class="dot dot-sat"></span>INSAT satellite</div>
    <div class="gl-row"><span class="dot dot-target"></span>Forecast point</div>
  </div>

  <div class="globe-overlay globe-hint">drag to rotate &middot; scroll to zoom<br><span style="opacity:.72">orbit radius compressed for legibility</span></div>
  <div id="globe-tip"></div>
  <div id="globe-fallback"></div>
</div>

<style>
  #globe-root {
    position: relative;
    width: 100%;
    height: __HEIGHT__px;
    border-radius: 16px;
    overflow: hidden;
    background:
      radial-gradient(ellipse at 30% 12%, #16294d 0%, #0a1226 42%, #05070f 100%);
    border: 1px solid rgba(120, 190, 255, 0.16);
    font-family: 'Segoe UI', Roboto, system-ui, sans-serif;
  }
  #globe-canvas { position: absolute; inset: 0; }

  .globe-overlay {
    position: absolute;
    z-index: 5;
    pointer-events: none;
    color: #dbe9ff;
  }
  .globe-title { top: 18px; left: 22px; }
  .gt-main {
    font-size: 15px; font-weight: 700; letter-spacing: 2.4px;
    color: #eaf3ff; text-shadow: 0 0 18px rgba(90, 170, 255, 0.55);
  }
  .gt-sub {
    font-size: 11px; letter-spacing: 0.4px; margin-top: 4px;
    color: rgba(175, 205, 245, 0.72);
  }

  .globe-legend {
    bottom: 18px; left: 22px;
    background: rgba(8, 16, 34, 0.62);
    border: 1px solid rgba(120, 180, 255, 0.18);
    border-radius: 10px;
    padding: 11px 14px;
    backdrop-filter: blur(7px);
  }
  .gl-row {
    display: flex; align-items: center; gap: 9px;
    font-size: 11px; color: rgba(205, 224, 250, 0.9);
    margin: 4px 0;
  }
  .dot {
    width: 9px; height: 9px; border-radius: 50%;
    display: inline-block; flex: none;
  }
  .dot-live    { background: #35e08a; box-shadow: 0 0 9px #35e08a; }
  .dot-contrib { background: #ffd23f; box-shadow: 0 0 9px #ffd23f; }
  .dot-off     { background: #4a5a78; }
  .dot-sat     { background: #63b8ff; box-shadow: 0 0 9px #63b8ff; }
  .dot-target  { background: #ff4d6d; box-shadow: 0 0 11px #ff4d6d; }

  .globe-hint {
    bottom: 18px; right: 22px;
    font-size: 10.5px; letter-spacing: 0.7px;
    color: rgba(150, 180, 220, 0.5);
  }

  #globe-tip {
    position: absolute; z-index: 9; pointer-events: none;
    display: none;
    background: rgba(9, 18, 38, 0.94);
    border: 1px solid rgba(120, 190, 255, 0.34);
    border-radius: 9px;
    padding: 9px 12px;
    font-size: 11.5px; line-height: 1.55;
    color: #e8f2ff;
    max-width: 260px;
    box-shadow: 0 10px 32px rgba(0, 0, 0, 0.6);
  }
  #globe-tip .tip-h {
    font-weight: 700; font-size: 12.5px;
    color: #9fd2ff; margin-bottom: 3px;
  }
  #globe-tip .tip-k { color: rgba(165, 195, 235, 0.72); }

  #globe-fallback {
    position: absolute; inset: 0;
    display: none;
    align-items: center; justify-content: center;
    text-align: center; padding: 30px;
    color: #b9d2f2; font-size: 13px; line-height: 1.7;
  }
</style>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(function () {
  var DATA = __PAYLOAD__;
  var root = document.getElementById('globe-root');
  var host = document.getElementById('globe-canvas');
  var tip  = document.getElementById('globe-tip');

  if (typeof THREE === 'undefined') {
    var fb = document.getElementById('globe-fallback');
    fb.style.display = 'flex';
    fb.innerHTML = 'The 3D globe needs three.js from cdnjs.cloudflare.com.<br>' +
                   'No internet connection was available, so the view is hidden.<br>' +
                   '<span style="opacity:.6">Every other panel works offline.</span>';
    return;
  }

  var W = root.clientWidth || 900;
  var H = root.clientHeight || 620;
  var R = 100;                         // globe radius in scene units
  // True geostationary radius is 6.61 Earth radii. Drawn to scale the Earth
  // becomes a dot and the radar network is unreadable, so the orbit is
  // COMPRESSED for legibility. The legend says so and every satellite
  // tooltip still reports the true 35,786 km altitude.
  var GEO_TRUE = 6.61;
  var GEO_SCALE = 2.75;
  var GEO = R * GEO_SCALE;

  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(42, W / H, 1, 20000);
  camera.position.set(230, 130, 350);

  var renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(W, H);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  host.appendChild(renderer.domElement);

  // ---------------------------------------------------------------- helpers
  function toVec(lat, lon, radius) {
    var phi = (90 - lat) * Math.PI / 180;
    var theta = (lon + 180) * Math.PI / 180;
    return new THREE.Vector3(
      -radius * Math.sin(phi) * Math.cos(theta),
       radius * Math.cos(phi),
       radius * Math.sin(phi) * Math.sin(theta)
    );
  }

  var pickable = [];

  // ------------------------------------------------------------------ stars
  (function starfield() {
    var g = new THREE.BufferGeometry();
    var n = 2600, pos = new Float32Array(n * 3);
    for (var i = 0; i < n; i++) {
      var r = 2600 + Math.random() * 5200;
      var t = Math.random() * Math.PI * 2;
      var p = Math.acos(2 * Math.random() - 1);
      pos[i*3]   = r * Math.sin(p) * Math.cos(t);
      pos[i*3+1] = r * Math.cos(p);
      pos[i*3+2] = r * Math.sin(p) * Math.sin(t);
    }
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    scene.add(new THREE.Points(g, new THREE.PointsMaterial({
      color: 0xbcd4f5, size: 2.4, sizeAttenuation: false,
      transparent: true, opacity: 0.62
    })));
  })();

  // ------------------------------------------------------------------ globe
  var globe = new THREE.Mesh(
    new THREE.SphereGeometry(R, 64, 64),
    new THREE.MeshPhongMaterial({
      color: 0x0d2144, emissive: 0x061024,
      specular: 0x2a5fa8, shininess: 14,
      transparent: true, opacity: 0.95
    })
  );
  scene.add(globe);

  // Fresnel atmosphere: bright at the limb, invisible face-on.
  var atmosphere = new THREE.Mesh(
    new THREE.SphereGeometry(R * 1.035, 64, 64),
    new THREE.ShaderMaterial({
      transparent: true, side: THREE.BackSide, depthWrite: false,
      uniforms: { glow: { value: new THREE.Color(0x4aa8ff) } },
      vertexShader:
        'varying float rim;' +
        'void main(){' +
        '  vec3 n = normalize(normalMatrix * normal);' +
        '  vec3 e = normalize((modelViewMatrix * vec4(position,1.0)).xyz);' +
        '  rim = pow(clamp(1.0 + dot(e, n), 0.0, 1.0), 3.4);' +
        '  gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);' +
        '}',
      fragmentShader:
        'uniform vec3 glow; varying float rim;' +
        'void main(){ gl_FragColor = vec4(glow, rim * 0.62); }'
    })
  );
  scene.add(atmosphere);

  // Graticule every 15 degrees.
  (function graticule() {
    var mat = new THREE.LineBasicMaterial({
      color: 0x3d7fc4, transparent: true, opacity: 0.19
    });
    var group = new THREE.Group();
    var lat, lon, pts, i;

    for (lat = -75; lat <= 75; lat += 15) {
      pts = [];
      for (i = 0; i <= 128; i++) pts.push(toVec(lat, -180 + i * 360 / 128, R * 1.002));
      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
    }
    for (lon = -180; lon < 180; lon += 15) {
      pts = [];
      for (i = 0; i <= 128; i++) pts.push(toVec(-90 + i * 180 / 128, lon, R * 1.002));
      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
    }
    scene.add(group);
  })();

  // Equator, emphasised because the INSAT fleet sits above it.
  (function equator() {
    var pts = [];
    for (var i = 0; i <= 200; i++) pts.push(toVec(0, -180 + i * 360 / 200, R * 1.004));
    scene.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: 0x63b8ff, transparent: true, opacity: 0.35 })
    ));
  })();

  // Shade the Indian analysis domain so the region of interest reads instantly.
  (function domain() {
    var b = { w: 66, s: 6, e: 98, n: 38 };
    var pts = [], i;
    for (i = 0; i <= 40; i++) pts.push(toVec(b.s, b.w + i * (b.e - b.w) / 40, R * 1.006));
    for (i = 0; i <= 40; i++) pts.push(toVec(b.s + i * (b.n - b.s) / 40, b.e, R * 1.006));
    for (i = 0; i <= 40; i++) pts.push(toVec(b.n, b.e - i * (b.e - b.w) / 40, R * 1.006));
    for (i = 0; i <= 40; i++) pts.push(toVec(b.n - i * (b.n - b.s) / 40, b.w, R * 1.006));
    scene.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: 0x7ce0ff, transparent: true, opacity: 0.42 })
    ));
  })();

  // ------------------------------------------------------------------ lights
  scene.add(new THREE.AmbientLight(0x88aadd, 0.85));
  var key = new THREE.DirectionalLight(0xcfe4ff, 0.95);
  key.position.set(300, 220, 420);
  scene.add(key);
  var rimLight = new THREE.DirectionalLight(0x2f6fd0, 0.5);
  rimLight.position.set(-320, -120, -260);
  scene.add(rimLight);

  // ------------------------------------------------------------------ radars
  var pulses = [];
  DATA.radars.forEach(function (r) {
    var pos = toVec(r.lat, r.lon, R * 1.012);
    var colour = r.contributing ? 0xffd23f : (r.live ? 0x35e08a : 0x4a5a78);
    var active = r.live || r.contributing;

    var pin = new THREE.Mesh(
      new THREE.SphereGeometry(active ? 2.2 : 1.4, 12, 12),
      new THREE.MeshBasicMaterial({ color: colour })
    );
    pin.position.copy(pos);
    pin.userData = {
      kind: 'radar',
      title: r.code + ' - ' + r.city,
      rows: [
        ['Band', r.band + '-band'],
        ['Range', r.range + ' km'],
        ['Position', r.lat.toFixed(2) + ' N, ' + r.lon.toFixed(2) + ' E'],
        ['Status', r.contributing ? 'contributing to this nowcast'
                 : (r.live ? 'publishing' : 'no public feed')]
      ]
    };
    scene.add(pin);
    pickable.push(pin);

    // Range ring, sized from the real radar range (111 km per degree).
    var angular = (r.range / 111.0) * Math.PI / 180;
    var ring = [];
    var centre = pos.clone().normalize();
    var tangent = new THREE.Vector3(0, 1, 0).cross(centre).normalize();
    if (tangent.length() < 0.1) tangent = new THREE.Vector3(1, 0, 0);
    var bitangent = centre.clone().cross(tangent).normalize();

    for (var i = 0; i <= 72; i++) {
      var a = i / 72 * Math.PI * 2;
      var dir = tangent.clone().multiplyScalar(Math.cos(a))
                 .add(bitangent.clone().multiplyScalar(Math.sin(a)));
      ring.push(centre.clone().multiplyScalar(Math.cos(angular))
                .add(dir.multiplyScalar(Math.sin(angular)))
                .multiplyScalar(R * 1.008));
    }
    var ringMat = new THREE.LineBasicMaterial({
      color: colour, transparent: true, opacity: active ? 0.5 : 0.13
    });
    var ringLine = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(ring), ringMat
    );
    scene.add(ringLine);
    if (active) pulses.push({ mat: ringMat, phase: Math.random() * Math.PI * 2 });
  });

  // ------------------------------------------------------------------ cities
  DATA.cities.forEach(function (c) {
    var pos = toVec(c.lat, c.lon, R * 1.008);
    var dot = new THREE.Mesh(
      new THREE.SphereGeometry(0.62, 8, 8),
      new THREE.MeshBasicMaterial({
        color: 0x9fc7f0, transparent: true, opacity: 0.55
      })
    );
    dot.position.copy(pos);
    dot.userData = {
      kind: 'city',
      title: c.name,
      rows: [['State', c.state],
             ['Position', c.lat.toFixed(2) + ' N, ' + c.lon.toFixed(2) + ' E']]
    };
    scene.add(dot);
    pickable.push(dot);
  });

  // -------------------------------------------------------------- satellites
  var flows = [];
  DATA.satellites.filter(function (s) { return s.geo; }).forEach(function (s) {
    var pos = toVec(0, s.lon, GEO);
    var operational = s.status === 'operational';
    var colour = operational ? 0x63b8ff : 0x5d6b85;

    var body = new THREE.Mesh(
      new THREE.BoxGeometry(10, 7, 7),
      new THREE.MeshPhongMaterial({
        color: colour, emissive: operational ? 0x123a66 : 0x14181f,
        shininess: 60
      })
    );
    body.position.copy(pos);
    body.lookAt(0, 0, 0);
    body.userData = {
      kind: 'satellite',
      title: s.name,
      rows: [
        ['Operator', s.operator],
        ['Longitude', s.lon.toFixed(1) + ' E geostationary'],
        ['Altitude', s.altitude.toLocaleString() + ' km (true; orbit drawn compressed)'],
        ['Payload', s.instruments.join(', ')],
        ['Status', s.status],
        ['Note', s.note]
      ]
    };
    scene.add(body);
    pickable.push(body);

    // Solar panels.
    [-1, 1].forEach(function (side) {
      var panel = new THREE.Mesh(
        new THREE.BoxGeometry(13, 0.6, 5.5),
        new THREE.MeshPhongMaterial({
          color: 0x1d4f8f, emissive: 0x0a1f3c, shininess: 90
        })
      );
      panel.position.copy(pos);
      var out = pos.clone().normalize();
      var axis = new THREE.Vector3(0, 1, 0).cross(out).normalize();
      panel.position.add(axis.multiplyScalar(side * 11.5));
      panel.lookAt(0, 0, 0);
      scene.add(panel);
    });

    if (!operational) return;

    // Scan cone toward the Indian domain.
    var target = toVec(22, 79, R);
    var axisVec = target.clone().sub(pos);
    var len = axisVec.length();
    var cone = new THREE.Mesh(
      new THREE.ConeGeometry(R * 0.60, len, 40, 1, true),
      new THREE.MeshBasicMaterial({
        color: 0x4fb0ff, transparent: true, opacity: 0.055,
        side: THREE.DoubleSide, depthWrite: false
      })
    );
    cone.position.copy(pos.clone().add(axisVec.clone().multiplyScalar(0.5)));
    cone.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, -1, 0), axisVec.clone().normalize()
    );
    scene.add(cone);

    // Orbit ring.
    var orbit = [];
    for (var i = 0; i <= 180; i++) orbit.push(toVec(0, -180 + i * 2, GEO));
    scene.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(orbit),
      new THREE.LineBasicMaterial({
        color: 0x2f6fb8, transparent: true, opacity: 0.22
      })
    ));

    flows.push({ from: pos, to: target, colour: 0x7cc4ff });
  });

  // ------------------------------------------------------- forecast location
  if (DATA.selected && DATA.selected.lat !== undefined) {
    var sel = DATA.selected;
    var selPos = toVec(sel.lat, sel.lon, R * 1.016);

    var marker = new THREE.Mesh(
      new THREE.SphereGeometry(3.4, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0xff4d6d })
    );
    marker.position.copy(selPos);
    marker.userData = {
      kind: 'target',
      title: sel.name + ' - forecast point',
      rows: [
        ['Risk', sel.risk || 'n/a'],
        ['Probability', (sel.probability !== undefined
            ? sel.probability.toFixed(1) + '%' : 'n/a')],
        ['Position', sel.lat.toFixed(3) + ' N, ' + sel.lon.toFixed(3) + ' E']
      ]
    };
    scene.add(marker);
    pickable.push(marker);

    // Expanding halo.
    var haloMat = new THREE.MeshBasicMaterial({
      color: 0xff4d6d, transparent: true, opacity: 0.55, side: THREE.DoubleSide
    });
    var halo = new THREE.Mesh(new THREE.RingGeometry(4, 5.2, 40), haloMat);
    halo.position.copy(selPos);
    halo.lookAt(0, 0, 0);
    scene.add(halo);
    pulses.push({ mat: haloMat, phase: 0, mesh: halo, halo: true });

    // Beacon.
    var beam = new THREE.Mesh(
      new THREE.CylinderGeometry(0.5, 0.5, 34, 8),
      new THREE.MeshBasicMaterial({
        color: 0xff4d6d, transparent: true, opacity: 0.32
      })
    );
    beam.position.copy(selPos.clone().multiplyScalar(1.16));
    beam.quaternion.setFromUnitVectors(
      new THREE.Vector3(0, 1, 0), selPos.clone().normalize()
    );
    scene.add(beam);
  }

  // ------------------------------------------------------------- data flows
  var particleSystems = [];
  flows.forEach(function (f) {
    var mid = f.from.clone().add(f.to).multiplyScalar(0.5).multiplyScalar(1.10);
    var curve = new THREE.QuadraticBezierCurve3(f.from, mid, f.to);

    scene.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(curve.getPoints(60)),
      new THREE.LineBasicMaterial({
        color: f.colour, transparent: true, opacity: 0.28
      })
    ));

    var count = 5;
    var geom = new THREE.BufferGeometry();
    geom.setAttribute('position',
      new THREE.BufferAttribute(new Float32Array(count * 3), 3));
    var points = new THREE.Points(geom, new THREE.PointsMaterial({
      color: f.colour, size: 4.2, transparent: true, opacity: 0.95,
      sizeAttenuation: false
    }));
    scene.add(points);
    particleSystems.push({ curve: curve, points: points, count: count });
  });

  // -------------------------------------------------------------- interaction
  // Open looking straight at India (22 N, 80 E), with the camera far enough
  // out that the geostationary belt at 6.61 Earth radii is in frame.
  var rotation = { x: 0.384, y: 2.967 };
  var dragging = false, last = { x: 0, y: 0 };
  var distance = 430;
  var canvas = renderer.domElement;

  canvas.addEventListener('mousedown', function (e) {
    dragging = true; last.x = e.clientX; last.y = e.clientY;
  });
  window.addEventListener('mouseup', function () { dragging = false; });
  window.addEventListener('mousemove', function (e) {
    if (!dragging) return;
    rotation.y += (e.clientX - last.x) * 0.005;
    rotation.x += (e.clientY - last.y) * 0.005;
    rotation.x = Math.max(-1.4, Math.min(1.4, rotation.x));
    last.x = e.clientX; last.y = e.clientY;
  });
  canvas.addEventListener('wheel', function (e) {
    e.preventDefault();
    distance = Math.max(150, Math.min(1600, distance + e.deltaY * 0.8));
  }, { passive: false });

  // Hover tooltips via raycasting.
  var raycaster = new THREE.Raycaster();
  raycaster.params.Points.threshold = 3;
  var mouse = new THREE.Vector2(-10, -10);

  canvas.addEventListener('mousemove', function (e) {
    var rect = canvas.getBoundingClientRect();
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    var hits = raycaster.intersectObjects(pickable, false);

    if (hits.length) {
      var d = hits[0].object.userData;
      var html = '<div class="tip-h">' + d.title + '</div>';
      d.rows.forEach(function (row) {
        if (row[1]) {
          html += '<div><span class="tip-k">' + row[0] + ':</span> ' + row[1] + '</div>';
        }
      });
      tip.innerHTML = html;
      tip.style.display = 'block';
      var x = e.clientX - rect.left + 16;
      var y = e.clientY - rect.top + 14;
      if (x > rect.width - 280) x -= 300;
      if (y > rect.height - 130) y -= 130;
      tip.style.left = x + 'px';
      tip.style.top = y + 'px';
    } else {
      tip.style.display = 'none';
    }
  });
  canvas.addEventListener('mouseleave', function () {
    tip.style.display = 'none';
  });

  // -------------------------------------------------------------------- loop
  var clock = new THREE.Clock();

  function animate() {
    requestAnimationFrame(animate);
    var t = clock.getElapsedTime();

    if (!dragging) rotation.y += 0.00055;   // slow idle drift

    camera.position.set(
      distance * Math.cos(rotation.x) * Math.sin(rotation.y),
      distance * Math.sin(rotation.x),
      distance * Math.cos(rotation.x) * Math.cos(rotation.y)
    );
    camera.lookAt(0, 0, 0);

    pulses.forEach(function (p) {
      var wave = 0.5 + 0.5 * Math.sin(t * 1.7 + p.phase);
      p.mat.opacity = p.halo ? (0.20 + 0.45 * wave) : (0.24 + 0.36 * wave);
      if (p.halo && p.mesh) {
        var s = 1 + 0.32 * wave;
        p.mesh.scale.set(s, s, s);
      }
    });

    particleSystems.forEach(function (ps, idx) {
      var arr = ps.points.geometry.attributes.position.array;
      for (var i = 0; i < ps.count; i++) {
        var u = ((t * 0.22) + (i / ps.count) + idx * 0.17) % 1;
        var pt = ps.curve.getPoint(u);
        arr[i*3] = pt.x; arr[i*3+1] = pt.y; arr[i*3+2] = pt.z;
      }
      ps.points.geometry.attributes.position.needsUpdate = true;
    });

    renderer.render(scene, camera);
  }
  animate();

  window.addEventListener('resize', function () {
    var w = root.clientWidth, h = root.clientHeight;
    if (!w || !h) return;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  });
})();
</script>
"""
