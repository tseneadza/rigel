import { useEffect, useRef } from "react";
import * as THREE from "three";
import { stateTone } from "../toolboxView.js";
import {
  scenePositions,
  SCENE_INNER_R,
  SCENE_OUTER_R,
  DEFAULT_TILT,
  DEFAULT_DISTANCE,
  TILT_PER_PX,
  SPIN_PER_PX,
  IDLE_SPIN,
  clampElevation,
  wheelZoom,
  cameraPosition,
  zoomFactor,
  toDegrees,
} from "../toolboxScene.js";

/**
 * 3D ToolBox map (WebGL, three.js). ToolBox is the hub in the middle; servers
 * sit on two tilted rings by state, as in the 2D map. Read-only. Drag left or
 * right to spin, up or down to tilt; scroll to zoom. Labels are HTML over the
 * canvas so they stay readable. The hint and tilt/zoom readout sit in a bar
 * under the map (mockup v8), never over it.
 *
 * `onFail` is called when WebGL cannot start; the parent then shows 2D.
 */
const TONE_HEX = { ok: 0x4ade80, warn: 0xfbbf24, bad: 0xf87171, neutral: 0x64748b };
const DEFAULT_SPIN = -0.6;

function fillLabel(el, title, sub, error) {
  const t = document.createElement("span");
  t.className = "tb-scene-title";
  t.textContent = title;
  const s = document.createElement("span");
  s.className = "tb-scene-sub";
  s.textContent = sub;
  el.replaceChildren(t, s);
  if (error) {
    const e = document.createElement("span");
    e.className = "tb-scene-err";
    e.textContent = error;
    el.appendChild(e);
  }
  el.classList.toggle("tb-scene-label--bad", Boolean(error));
}

export default function ToolBoxScene({ serverRows, hubState, hint = "", onFail }) {
  const wrapRef = useRef(null);
  const readoutRef = useRef(null);
  const labelsRef = useRef(null);
  const sceneRef = useRef(null);
  const failRef = useRef(onFail);
  useEffect(() => {
    failRef.current = onFail;
  });

  // One scene for the life of the component: renderer, camera, rings, hub, input.
  useEffect(() => {
    const wrap = wrapRef.current;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      failRef.current?.();
      return undefined;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    wrap.prepend(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    // The orbit stays flat; tilt and zoom move the camera around it.
    const orbit = new THREE.Group();
    scene.add(orbit);
    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const key = new THREE.DirectionalLight(0xffffff, 0.9);
    key.position.set(3, 6, 4);
    scene.add(key);

    const hub = new THREE.Mesh(
      new THREE.SphereGeometry(0.55, 40, 40),
      new THREE.MeshStandardMaterial({ color: 0x60a5fa, emissive: 0x1e3a8a, roughness: 0.35, metalness: 0.1 }),
    );
    orbit.add(hub);
    for (const [radius, opacity] of [
      [SCENE_INNER_R, 0.9],
      [SCENE_OUTER_R, 0.6],
    ]) {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(radius, 0.012, 8, 180),
        new THREE.MeshBasicMaterial({ color: 0x334155, transparent: true, opacity }),
      );
      ring.rotation.x = Math.PI / 2;
      orbit.add(ring);
    }
    const nodeGroup = new THREE.Group();
    orbit.add(nodeGroup);

    const hubEl = document.createElement("div");
    hubEl.className = "tb-scene-label";
    labelsRef.current.appendChild(hubEl);

    // The readout lives in the bar under the map (rendered below), not over the scene.
    const readout = readoutRef.current;

    const state = {
      renderer,
      scene,
      camera,
      orbit,
      nodeGroup,
      nodes: [],
      hubEl,
      readout,
      readoutText: "",
      spin: DEFAULT_SPIN,
      elevation: DEFAULT_TILT,
      distance: DEFAULT_DISTANCE,
      drag: null,
      frame: 0,
    };
    sceneRef.current = state;

    const size = () => {
      const w = wrap.clientWidth || 1;
      const h = wrap.clientHeight || 1;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    size();
    const resizeObserver = typeof ResizeObserver !== "undefined" ? new ResizeObserver(size) : null;
    resizeObserver?.observe(wrap);

    const projected = new THREE.Vector3();
    const toScreen = (point, w, h) => {
      projected.copy(point).applyMatrix4(orbit.matrixWorld).project(camera);
      return [((projected.x + 1) / 2) * w, ((1 - projected.y) / 2) * h];
    };
    const origin = new THREE.Vector3(0, 0, 0);
    const place = (el, point, w, h) => {
      const [x, y] = toScreen(point, w, h);
      el.style.left = `${x}px`;
      el.style.top = `${y}px`;
    };
    const tick = () => {
      if (state.drag === null) state.spin += IDLE_SPIN;
      orbit.rotation.y = state.spin;
      const pos = cameraPosition(state.elevation, state.distance);
      camera.position.set(pos.x, pos.y, pos.z);
      camera.lookAt(0, 0, 0);
      orbit.updateMatrixWorld(true);
      renderer.render(scene, camera);
      const text = `Tilt ${toDegrees(state.elevation)}° · Zoom ${zoomFactor(state.distance).toFixed(1)}×`;
      if (text !== state.readoutText) {
        state.readoutText = text;
        if (readout) readout.textContent = text;
      }
      const w = wrap.clientWidth || 1;
      const h = wrap.clientHeight || 1;
      for (const node of state.nodes) place(node.el, node.pos, w, h);
      place(hubEl, origin, w, h);
      state.frame = requestAnimationFrame(tick);
    };
    state.frame = requestAnimationFrame(tick);

    const onDown = (e) => {
      state.drag = { x: e.clientX, y: e.clientY };
    };
    const onMove = (e) => {
      if (state.drag === null) return;
      state.spin += (e.clientX - state.drag.x) * SPIN_PER_PX;
      // drag up tilts toward flat; drag down tilts toward edge-on
      state.elevation = clampElevation(state.elevation - (e.clientY - state.drag.y) * TILT_PER_PX);
      state.drag = { x: e.clientX, y: e.clientY };
    };
    const onUp = () => {
      state.drag = null;
    };
    const onWheel = (e) => {
      e.preventDefault();
      state.distance = wheelZoom(state.distance, e.deltaY);
    };
    wrap.addEventListener("pointerdown", onDown);
    wrap.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);

    return () => {
      cancelAnimationFrame(state.frame);
      resizeObserver?.disconnect();
      wrap.removeEventListener("pointerdown", onDown);
      wrap.removeEventListener("wheel", onWheel);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      for (const node of state.nodes) node.el.remove();
      hubEl.remove();
      scene.traverse((obj) => {
        obj.geometry?.dispose();
        obj.material?.dispose();
      });
      renderer.dispose();
      renderer.domElement.remove();
      sceneRef.current = null;
    };
  }, []);

  // Servers and hub label: rebuilt when the server data or hub state changes.
  const signature = serverRows.map((r) => `${r.name}|${r.state}|${r.tools}|${r.error ?? ""}`).join("\n");
  useEffect(() => {
    const state = sceneRef.current;
    if (!state) return;
    fillLabel(state.hubEl, "ToolBox", hubState, null);
    for (const child of [...state.nodeGroup.children]) {
      state.nodeGroup.remove(child);
      child.geometry?.dispose();
      child.material?.dispose();
    }
    for (const node of state.nodes) node.el.remove();
    state.nodes = [];

    const at = scenePositions(serverRows);
    for (const row of serverRows) {
      const p = at.get(row.name);
      if (!p) continue;
      const color = TONE_HEX[stateTone(row.state)] ?? TONE_HEX.neutral;
      const pos = new THREE.Vector3(p.x, p.y, p.z);
      const dot = new THREE.Mesh(
        new THREE.SphereGeometry(0.17, 28, 28),
        new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.25, roughness: 0.4 }),
      );
      dot.position.copy(pos);
      state.nodeGroup.add(dot);
      const spoke = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), pos]),
        new THREE.LineBasicMaterial({ color: 0x334155, transparent: true, opacity: 0.8 }),
      );
      state.nodeGroup.add(spoke);
      const el = document.createElement("div");
      el.className = "tb-scene-label";
      fillLabel(el, row.name, `${row.state} · ${row.tools} tools`, row.error);
      labelsRef.current.appendChild(el);
      state.nodes.push({ pos, el });
    }
    // signature covers serverRows; re-running on every poll would rebuild the scene needlessly
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, hubState]);

  return (
    <>
      <div className="tb-map tb-map--3d">
        <div
          className="tb-scene"
          ref={wrapRef}
          role="img"
          aria-label={`ToolBox ${hubState}, ${serverRows.length} servers`}
        >
          <div className="tb-scene-labels" ref={labelsRef} />
        </div>
      </div>
      <div className="tb-bar">
        <span className="tb-bar-hint">{hint}</span>
        <span className="tb-bar-readout" ref={readoutRef} />
      </div>
    </>
  );
}
