"""
frontend/hero.py
Cinematic hero for the landing page.

A live storm rather than a picture of one. The scene is a fragment shader
running fractional Brownian motion over animated noise to build a convective
cloud field, lit from within by lightning that fires on its own schedule -
a bright core, a fast decay, and a secondary return stroke, because that is
what real lightning does and the eye knows the difference.

Everything is generated. No video file, no image asset, nothing to load
beyond three.js itself, so it starts instantly and never shows a blank frame.

Typography follows the reference: Inter Tight at weight 300, set large, with
tight negative tracking and near-solid leading. Light weight at display size
reads as confidence; heavy uppercase at the same size reads as shouting.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

import config


def build_hero_html(headline: str,
                    tagline: str,
                    eyebrow: str = "",
                    stats: Optional[List[Dict[str, str]]] = None,
                    height: int = 620) -> str:
    """
    Generate the hero component.

    Args:
        headline: display line. Use <br> for a deliberate break.
        tagline: supporting sentence beneath it.
        eyebrow: small label above the headline.
        stats: [{'value': '0-6', 'label': 'Hour horizon'}, ...]
    """
    payload = {
        "headline": headline,
        "tagline": tagline,
        "eyebrow": eyebrow,
        "stats": stats or [],
    }
    return (
        _TEMPLATE
        .replace("__PAYLOAD__", json.dumps(payload))
        .replace("__HEIGHT__", str(int(height)))
    )


_TEMPLATE = r"""
<div id="hero-root">
  <div id="hero-canvas"></div>
  <div id="hero-scrim"></div>

  <div id="hero-content">
    <div id="hero-eyebrow"></div>
    <h1 id="hero-headline"></h1>
    <p id="hero-tagline"></p>
    <div id="hero-stats"></div>
  </div>
</div>

<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter+Tight:wght@200;300;400;500&display=swap');

  #hero-root {
    position: relative;
    width: 100%;
    height: __HEIGHT__px;
    overflow: hidden;
    background: #04070E;
    border-radius: 4px;
    font-family: 'Inter Tight', Inter, system-ui, -apple-system, sans-serif;
  }
  #hero-canvas { position: absolute; inset: 0; }

  /* Darkens the lower left so text always has contrast, whatever the
     lightning is doing behind it. */
  #hero-scrim {
    position: absolute; inset: 0; pointer-events: none;
    background:
      linear-gradient(100deg, rgba(4,7,14,.90) 0%, rgba(4,7,14,.55) 42%,
                              rgba(4,7,14,0) 72%),
      linear-gradient(0deg, rgba(4,7,14,.88) 0%, rgba(4,7,14,0) 46%);
  }

  #hero-content {
    position: absolute;
    left: clamp(24px, 5vw, 68px);
    bottom: clamp(34px, 6vh, 62px);
    right: clamp(24px, 5vw, 68px);
    z-index: 3;
    pointer-events: none;
  }

  /*
   * Reveals are CSS keyframes, not a JavaScript tween.
   *
   * requestAnimationFrame is unreliable for this component: embedded in a
   * Streamlit iframe it can be throttled to a standstill, which stalls any
   * RAF-driven tween library and leaves the text at opacity 0 - a blank hero.
   * CSS animations are driven by the compositor and still complete, so the
   * copy is always readable no matter what happens to the render loop. A
   * stagger is then just a per-element delay.
   */
  @keyframes riseIn {
    from { opacity: 0; transform: translateY(24px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  #hero-eyebrow {
    font-size: 11.5px; font-weight: 400;
    letter-spacing: .30em; text-transform: uppercase;
    color: rgba(150, 200, 255, .82);
    margin-bottom: 20px;
    opacity: 0;
    animation: riseIn .8s cubic-bezier(.16,1,.3,1) .15s forwards;
  }

  /* Reference metrics: weight 300, tracking -0.035em, line-height 1.02. */
  #hero-headline {
    margin: 0 0 20px;
    font-weight: 300;
    font-size: clamp(2.5rem, 5.6vw, 4.35rem);
    line-height: 1.02;
    letter-spacing: -.035em;
    color: #FFFFFF;
    max-width: 17ch;
  }
  #hero-headline .w {
    display: inline-block;
    opacity: 0;
    will-change: transform, opacity;
    animation: riseIn 1.05s cubic-bezier(.16,1,.3,1) forwards;
    /* per-word delay is set inline as --d */
    animation-delay: var(--d, 0s);
  }

  #hero-tagline {
    margin: 0; font-weight: 300;
    font-size: clamp(.98rem, 1.35vw, 1.28rem);
    line-height: 1.5; letter-spacing: -.02em;
    color: rgba(237, 240, 246, .80);
    max-width: 56ch;
    opacity: 0;
    animation: riseIn .95s cubic-bezier(.16,1,.3,1) var(--d, .8s) forwards;
  }

  #hero-stats {
    display: flex; flex-wrap: wrap;
    gap: clamp(26px, 4vw, 62px);
    margin-top: 34px;
  }
  .hs {
    opacity: 0;
    animation: riseIn .85s cubic-bezier(.16,1,.3,1) var(--d, 1s) forwards;
  }
  .hs-v {
    font-size: clamp(1.5rem, 2.5vw, 2.1rem);
    font-weight: 200; letter-spacing: -.035em; line-height: 1;
    color: #FFFFFF;
  }
  .hs-l {
    margin-top: 9px; font-size: 10.5px; font-weight: 400;
    letter-spacing: .22em; text-transform: uppercase;
    color: rgba(150, 185, 225, .68);
  }

  #hero-fallback {
    position: absolute; inset: 0; z-index: 1;
    background:
      radial-gradient(120% 90% at 68% 18%, #132A4D 0%, rgba(0,0,0,0) 60%),
      linear-gradient(180deg, #0B1A33 0%, #04070E 100%);
  }
</style>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(function () {
  var DATA = __PAYLOAD__;

  var root = document.getElementById('hero-root');
  var host = document.getElementById('hero-canvas');

  // ---------------------------------------------------------------- content
  var eyebrow = document.getElementById('hero-eyebrow');
  var headline = document.getElementById('hero-headline');
  var tagline = document.getElementById('hero-tagline');
  var statsHost = document.getElementById('hero-stats');

  eyebrow.textContent = DATA.eyebrow || '';
  tagline.textContent = DATA.tagline || '';

  // Wrap each word so it can be revealed on its own. Words, not letters:
  // letter-by-letter reveals at this size read as a gimmick and hurt
  // legibility, while word stagger reads as the line arriving.
  var wordIndex = 0;
  headline.innerHTML = (DATA.headline || '')
    .split('<br>')
    .map(function (line) {
      return line.trim().split(/\s+/)
        .map(function (w) {
          var delay = (0.34 + wordIndex * 0.055).toFixed(3);
          wordIndex += 1;
          return '<span class="w" style="--d:' + delay + 's">' + w + '</span>';
        })
        .join(' ');
    })
    .join('<br>');

  var tailDelay = 0.34 + wordIndex * 0.055;
  tagline.style.setProperty('--d', (tailDelay + 0.10).toFixed(3) + 's');

  (DATA.stats || []).forEach(function (s, i) {
    var d = document.createElement('div');
    d.className = 'hs';
    d.style.setProperty('--d', (tailDelay + 0.26 + i * 0.09).toFixed(3) + 's');
    d.innerHTML = '<div class="hs-v">' + s.value + '</div>' +
                  '<div class="hs-l">' + s.label + '</div>';
    statsHost.appendChild(d);
  });

  // ------------------------------------------------------------- the sky
  if (typeof THREE === 'undefined') {
    var fb = document.createElement('div');
    fb.id = 'hero-fallback';
    root.insertBefore(fb, root.firstChild);
    return;   // text still reveals: the animation is pure CSS
  }

  var W = root.clientWidth || 1200;
  var H = root.clientHeight || 620;

  var scene = new THREE.Scene();
  var camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  var renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false });
  renderer.setSize(W, H);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
  host.appendChild(renderer.domElement);

  var uniforms = {
    uTime:      { value: 0 },
    uRes:       { value: new THREE.Vector2(W, H) },
    uFlash:     { value: 0 },                          // 0..1 flash energy
    uFlashPos:  { value: new THREE.Vector2(0.5, 0.62) },
    uScroll:    { value: 0 },
  };

  var material = new THREE.ShaderMaterial({
    uniforms: uniforms,
    vertexShader: [
      'varying vec2 vUv;',
      'void main(){ vUv = uv; gl_Position = vec4(position, 1.0); }'
    ].join('\n'),
    fragmentShader: [
      'precision highp float;',
      'varying vec2 vUv;',
      'uniform float uTime;',
      'uniform vec2  uRes;',
      'uniform float uFlash;',
      'uniform vec2  uFlashPos;',
      '',
      'float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
      '',
      'float noise(vec2 p){',
      '  vec2 i = floor(p), f = fract(p);',
      '  vec2 u = f * f * (3.0 - 2.0 * f);',
      '  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),',
      '             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);',
      '}',
      '',
      // Fractional Brownian motion: layered noise at halving amplitude. This
      // is what gives cloud its self-similar, billowing structure.
      'float fbm(vec2 p){',
      '  float v = 0.0, a = 0.5;',
      '  mat2 rot = mat2(0.80, 0.60, -0.60, 0.80);',
      '  for (int i = 0; i < 6; i++){',
      '    v += a * noise(p);',
      '    p = rot * p * 2.02;',
      '    a *= 0.5;',
      '  }',
      '  return v;',
      '}',
      '',
      'void main(){',
      '  vec2 uv = vUv;',
      '  float aspect = uRes.x / uRes.y;',
      '  vec2 p = vec2(uv.x * aspect, uv.y);',
      '',
      // Two cloud decks drifting at different speeds gives parallax depth.
      '  float t = uTime * 0.026;',
      '  float deck1 = fbm(p * 2.6 + vec2(t, -t * 0.35));',
      '  float deck2 = fbm(p * 5.1 + vec2(-t * 1.7, t * 0.5) + deck1 * 0.8);',
      '  float cloud = mix(deck1, deck2, 0.55);',
      '',
      // Build vertically: heavier, denser cloud low in the frame.
      '  float horizon = smoothstep(0.06, 0.92, 1.0 - uv.y);',
      '  float density = clamp(cloud * 1.25 * (0.45 + horizon * 0.85), 0.0, 1.0);',
      '',
      // Night sky gradient - deep navy above, near-black below.
      '  vec3 skyTop = vec3(0.043, 0.086, 0.180);',
      '  vec3 skyLow = vec3(0.012, 0.020, 0.043);',
      '  vec3 col = mix(skyLow, skyTop, smoothstep(0.0, 1.0, uv.y));',
      '',
      // Ambient cloud body, cool and desaturated.
      '  vec3 cloudCol = mix(vec3(0.055, 0.090, 0.155), vec3(0.16, 0.24, 0.36), density);',
      '  col = mix(col, cloudCol, density * 0.92);',
      '',
      // Lightning. The flash lights the cloud from a point INSIDE the deck,
      // so brightness falls off with distance and is modulated by density -
      // illuminated cloud, not a lamp pointed at the screen.
      '  vec2 fp = vec2(uFlashPos.x * aspect, uFlashPos.y);',
      '  float d = distance(p, fp);',
      '  float core = exp(-d * 5.2) * uFlash;',
      '  float bloom = exp(-d * 1.9) * uFlash * 0.55;',
      '  vec3 boltCol = vec3(0.62, 0.78, 1.0);',
      '  col += boltCol * (core * (0.35 + density * 1.5) + bloom * (0.15 + density * 0.9));',
      '',
      // A cold rim where the flash catches the top of the cloud tops.
      '  float rim = smoothstep(0.55, 0.95, density) * uFlash * exp(-d * 2.6);',
      '  col += vec3(0.75, 0.86, 1.0) * rim * 0.5;',
      '',
      // Vignette and a little grain so flat areas do not band.
      '  float vig = smoothstep(1.25, 0.25, length(uv - 0.5));',
      '  col *= 0.55 + 0.45 * vig;',
      '  col += (hash(uv * uRes + uTime) - 0.5) * 0.014;',
      '',
      '  gl_FragColor = vec4(col, 1.0);',
      '}'
    ].join('\n'),
  });

  scene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material));

  // ------------------------------------------------------------ lightning
  // A real stroke is a bright leader, a fast decay, and often a dimmer
  // return stroke a few tens of milliseconds later. Modelling that, rather
  // than a single fade, is most of why it reads as lightning.
  var flash = 0, nextStrike = 1.4, prevDrawAt = 0;

  function scheduleStrike(clock) {
    nextStrike = clock + 2.6 + Math.random() * 5.4;
    uniforms.uFlashPos.value.set(
      0.18 + Math.random() * 0.72,
      0.42 + Math.random() * 0.42
    );
  }

  var pending = [];

  function strike(clock) {
    var energy = 0.55 + Math.random() * 0.75;
    pending.push({ at: clock, amp: energy });
    // Return stroke, sometimes.
    if (Math.random() < 0.65) {
      pending.push({ at: clock + 0.06 + Math.random() * 0.09,
                     amp: energy * (0.35 + Math.random() * 0.3) });
    }
    if (Math.random() < 0.3) {
      pending.push({ at: clock + 0.20 + Math.random() * 0.12,
                     amp: energy * 0.22 });
    }
  }

  // -------------------------------------------------------------- render
  //
  // Time is read from the wall clock rather than accumulated from frame
  // deltas, and a timer backs up requestAnimationFrame. RAF can be throttled
  // to a standstill when the component is embedded or the window is not
  // foregrounded; accumulating deltas then freezes the scene permanently,
  // whereas an absolute clock simply resumes at the right point. The interval
  // only draws when RAF has visibly stopped, so normally it costs nothing.
  var startedAt = (window.performance || Date).now();
  prevDrawAt = startedAt;
  var elapsed = 0;
  var lastFrameAt = startedAt;

  function frame() {
    var now = (window.performance || Date).now();
    lastFrameAt = now;
    elapsed = (now - startedAt) / 1000;

    if (elapsed > nextStrike) {
      strike(elapsed);
      scheduleStrike(elapsed);
    }

    // Decay, then add any pulses that have become due. The decay uses the
    // real interval since the previous draw so a dropped frame does not
    // leave the flash hanging at full brightness.
    var dt = Math.min(Math.max((now - prevDrawAt) / 1000, 0.001), 0.12);
    prevDrawAt = now;
    flash *= Math.exp(-dt * 11.0);
    for (var i = pending.length - 1; i >= 0; i--) {
      if (elapsed >= pending[i].at) {
        flash = Math.max(flash, pending[i].amp);
        pending.splice(i, 1);
      }
    }

    uniforms.uTime.value = elapsed;
    uniforms.uFlash.value = flash;

    // Exposed so the strike schedule can be measured from outside. A WebGL
    // drawing buffer is cleared after compositing, so reading pixels back
    // reports nothing and tells you only that you cannot read pixels back.
    window.__heroFlash = flash;
    window.__heroTime = elapsed;

    renderer.render(scene, camera);
  }

  function loop() {
    requestAnimationFrame(loop);
    frame();
  }
  loop();

  // Backstop: if RAF has not run for a while, drive the scene from a timer
  // so the sky keeps moving instead of freezing on a single frame.
  setInterval(function () {
    if ((window.performance || Date).now() - lastFrameAt > 200) frame();
  }, 40);

  window.addEventListener('resize', function () {
    var w = root.clientWidth, h = root.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h);
    uniforms.uRes.value.set(w, h);
  });
})();
</script>
"""
