// Original procedural light field. No textures, libraries or network requests.
const vertexSource = `
attribute vec2 position;
varying vec2 uv;
void main() {
  uv = position * .5 + .5;
  gl_Position = vec4(position, 0., 1.);
}`;

const fragmentSource = `
precision highp float;
varying vec2 uv;
uniform float time;
uniform vec2 screen;
uniform float workspace;
uniform vec3 tintLow;
uniform vec3 tintMid;
uniform vec3 tintHigh;

float hash(vec2 p) {
  vec3 q = fract(vec3(p.xyx) * .1031);
  q += dot(q, q.yzx + 33.33);
  return fract((q.x + q.y) * q.z);
}
float noise(vec2 p) {
  vec2 cell = floor(p), f = fract(p);
  f = f * f * (3. - 2. * f);
  return mix(mix(hash(cell), hash(cell + vec2(1.,0.)), f.x),
             mix(hash(cell + vec2(0.,1.)), hash(cell + 1.), f.x), f.y);
}
vec3 pool(float distance, float grain) {
  float amount = 1. - smoothstep(.48, 1.16, distance + grain * .085);
  vec3 color = mix(tintLow, tintMid, smoothstep(.05, .78, amount));
  color = mix(color, tintHigh, 1. - smoothstep(.13, .67, distance));
  return color * amount;
}
void main() {
  float t = 8. + (time - 8.) * 2.5;
  // Broad drift and smaller, independent currents reshape different sections of the edges.
  vec2 warp = vec2(noise(uv * 2.7 + vec2(t*.044, -t*.029)),
                   noise(uv * 2.9 + vec2(7.3-t*.027, t*.038))) - .5;
  vec2 fineWarp = vec2(noise(uv * 6.2 + warp*.8 + vec2(-t*.071, t*.053)),
                       noise(uv * 5.4 + warp.yx + vec2(12.1+t*.049, -t*.063))) - .5;
  vec2 p = uv + warp * .25;
  p += .024 * vec2(sin(uv.y*8. + t*.18), cos(uv.x*7. - t*.15));
  vec2 leftCenter = vec2(-.095 + .055*sin(t*.19), .04 + .065*cos(t*.14));
  vec2 rightCenter = vec2(1.045 + .045*cos(t*.16), .98 + .065*sin(t*.13));
  float poolScale = .94 * mix(1., .55, workspace);
  vec2 leftSize = poolScale * vec2(.46 + .065*sin(t*.13), .56 + .06*cos(t*.18));
  vec2 rightSize = poolScale * vec2(.43 + .05*cos(t*.17), .53 + .065*sin(t*.15));
  float a = length((p + fineWarp*.085 - leftCenter) / leftSize);
  float b = length((p - fineWarp.yx*.10 - rightCenter) / rightSize);
  vec2 pixel = floor(uv * screen);
  float grain = hash(pixel) - .5;
  // Mostly anchored grain, with a small amount of fine evolving texture.
  grain = mix(grain, hash(pixel + floor(time*10.) * vec2(17.,29.)) - .5, .16);
  vec3 light = max(pool(a, grain), pool(b, grain));
  float energy = max(light.r, max(light.g, light.b));
  light *= .80 + .40 * (grain + .5);
  light += grain * .10 * smoothstep(.015, .30, energy);
  vec3 black = vec3(.006, .012, .009);
  gl_FragColor = vec4(max(black, light * .72 * mix(1., .19, workspace)), 1.);
}`;

export function startAtmosphere(host) {
  if (!host || host.querySelector('canvas')) return;
  const canvas = document.createElement('canvas');
  canvas.className = 'atmosphere-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  host.append(canvas);
  const gl = canvas.getContext('webgl', {
    alpha: false, antialias: false, depth: false, stencil: false,
    powerPreference: 'low-power', preserveDrawingBuffer: false,
  });
  if (!gl) { canvas.remove(); return; }

  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const palettes = {
    roast: [.29,.78,.51, .30,.82,.76, .24,.59,.77],
    recipes: [.49,.59,.30, .67,.64,.42, .47,.57,.48],
    beans: [.26,.57,.32, .40,.72,.49, .26,.56,.48],
    history: [.32,.48,.57, .43,.62,.68, .44,.47,.65],
  };
  let colors = [...(palettes[host.dataset.page] || palettes.roast)];
  let program, buffer, timeUniform, screenUniform, workspaceUniform, tintUniforms;
  let workspace = host.dataset.mode === 'workspace' ? 1 : 0;
  let raf = 0, last = 0, elapsed = 8, dirty = true, lost = false, suspended = false;
  function compile(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const message = gl.getShaderInfoLog(shader);
      gl.deleteShader(shader);
      throw new Error(message);
    }
    return shader;
  }
  function initialize() {
    let vertex, fragment;
    try {
      vertex = compile(gl.VERTEX_SHADER, vertexSource);
      fragment = compile(gl.FRAGMENT_SHADER, fragmentSource);
      program = gl.createProgram();
      gl.attachShader(program, vertex);
      gl.attachShader(program, fragment);
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
      gl.useProgram(program);
      buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
      const position = gl.getAttribLocation(program, 'position');
      gl.enableVertexAttribArray(position);
      gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
      timeUniform = gl.getUniformLocation(program, 'time');
      screenUniform = gl.getUniformLocation(program, 'screen');
      workspaceUniform = gl.getUniformLocation(program, 'workspace');
      tintUniforms = ['tintLow','tintMid','tintHigh'].map(name => gl.getUniformLocation(program, name));
      dirty = true;
      return true;
    } catch (error) {
      if (buffer) gl.deleteBuffer(buffer);
      if (program) gl.deleteProgram(program);
      host.classList.remove('gpu-ready');
      console.warn('Using the gradient background fallback.', error.message);
      return false;
    } finally {
      if (vertex) gl.deleteShader(vertex);
      if (fragment) gl.deleteShader(fragment);
    }
  }
  function stop() { cancelAnimationFrame(raf); raf = 0; last = 0; }
  function frame(now) {
    raf = 0;
    if (lost || suspended || document.hidden) return;
    // Cap rendering at 30 fps; this decorative layer does not need display-rate redraws.
    if (dirty || !last || now-last >= 1000/30) {
      const dt = last ? Math.min((now-last)/1000, .1) : 1/30;
      if (last && !motion.matches) elapsed += dt;
      last = now;
      const width = host.clientWidth, height = host.clientHeight;
      if (width && height) {
        if (dirty) {
          // One million pixels maximum, independent of high-DPI screen scaling.
          const scale = Math.min(1, Math.sqrt(1000000/(width*height)));
          canvas.width = Math.max(1, Math.round(width*scale));
          canvas.height = Math.max(1, Math.round(height*scale));
          gl.viewport(0, 0, canvas.width, canvas.height);
          gl.uniform2f(screenUniform, canvas.width, canvas.height);
          dirty = false;
        }
        gl.uniform1f(timeUniform, elapsed);
        const target = host.dataset.mode === 'workspace' ? 1 : 0;
        workspace = motion.matches ? target : workspace + (target - workspace) * .055;
        gl.uniform1f(workspaceUniform, workspace);
        // Carry the current colors across navigation, gently approaching the next palette.
        const palette = palettes[host.dataset.page] || palettes.roast;
        const blend = motion.matches ? 1 : 1 - Math.exp(-dt / 2.8);
        colors = colors.map((value, i) => value + (palette[i] - value) * blend);
        tintUniforms.forEach((uniform, i) => gl.uniform3fv(uniform, colors.slice(i*3, i*3+3)));
        gl.drawArrays(gl.TRIANGLES, 0, 3);
        host.classList.add('gpu-ready');
      }
    }
    if (!motion.matches) raf = requestAnimationFrame(frame);
  }
  function resume() {
    stop();
    if (!lost && !suspended && !document.hidden) raf = requestAnimationFrame(frame);
  }
  if (!initialize()) { canvas.remove(); return; }
  new ResizeObserver(() => { dirty = true; resume(); }).observe(host);
  new MutationObserver(() => { dirty = true; resume(); }).observe(host, {attributes:true, attributeFilter:['data-mode','data-page']});
  document.addEventListener('visibilitychange', resume);
  motion.addEventListener('change', () => { dirty = true; resume(); });
  window.addEventListener('pagehide', () => { suspended = true; stop(); });
  window.addEventListener('pageshow', () => { suspended = false; resume(); });
  canvas.addEventListener('webglcontextlost', event => {
    event.preventDefault(); lost = true; stop(); host.classList.remove('gpu-ready');
  });
  canvas.addEventListener('webglcontextrestored', () => {
    lost = !initialize(); resume();
  });
  resume();
}
