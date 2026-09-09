import { useEffect, useRef } from "react";
import type { MutableRefObject } from "react";
import * as THREE from "three";

export type AuthVisualState = "idle" | "typing" | "error" | "success";

export type AuthSceneSignals = {
  pointer: MutableRefObject<{ x: number; y: number }>;
  lastInputAt: MutableRefObject<number>;
};

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const smoother = (value: number) => value * value * value * (value * (value * 6 - 15) + 10);

function createLogoGeometries() {
  const outer = 2.7;
  const inner = 1.5;
  const depth = 0.44;
  const segments = 96;
  const archShape = new THREE.Shape();

  archShape.moveTo(-outer, 0);
  for (let index = 0; index <= segments; index += 1) {
    const angle = Math.PI - (Math.PI * index) / segments;
    archShape.lineTo(Math.cos(angle) * outer, Math.sin(angle) * outer);
  }
  archShape.lineTo(inner, 0);
  for (let index = 0; index <= segments; index += 1) {
    const angle = (Math.PI * index) / segments;
    archShape.lineTo(Math.cos(angle) * inner, Math.sin(angle) * inner);
  }
  archShape.closePath();

  const headShape = new THREE.Shape();
  headShape.absarc(0, 0, 0.88, 0, Math.PI * 2, false);

  const settings: THREE.ExtrudeGeometryOptions = {
    depth,
    bevelEnabled: true,
    bevelSegments: 4,
    steps: 1,
    bevelSize: 0.055,
    bevelThickness: 0.06,
    curveSegments: 64,
  };
  const arch = new THREE.ExtrudeGeometry(archShape, settings);
  const head = new THREE.ExtrudeGeometry(headShape, settings);
  arch.translate(0, -2.52, -depth / 2);
  head.translate(0, 1.95, -depth / 2);
  arch.computeVertexNormals();
  head.computeVertexNormals();
  return { arch, head };
}

export default function AuthScene({
  visualState,
  signals,
  onReady,
}: {
  visualState: AuthVisualState;
  signals: AuthSceneSignals;
  onReady: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<AuthVisualState>(visualState);
  const stateStartedAt = useRef(performance.now());
  const onReadyRef = useRef(onReady);

  useEffect(() => {
    stateRef.current = visualState;
    stateStartedAt.current = performance.now();
  }, [visualState]);

  useEffect(() => {
    onReadyRef.current = onReady;
  }, [onReady]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.04;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(39, 1, 0.1, 30);
    camera.position.set(0, 0, 8.9);

    const actor = new THREE.Group();
    actor.position.set(0.2, 0.42, 0);
    actor.scale.setScalar(0.58);
    scene.add(actor);

    const geometries = createLogoGeometries();
    const material = new THREE.MeshPhysicalMaterial({
      color: "#f7f7ff",
      emissive: "#302c80",
      emissiveIntensity: 0.1,
      metalness: 0.24,
      roughness: 0.4,
      clearcoat: 0.38,
      clearcoatRoughness: 0.27,
      envMapIntensity: 1,
      transparent: true,
    });
    actor.add(new THREE.Mesh(geometries.arch, material));
    actor.add(new THREE.Mesh(geometries.head, material));

    scene.add(new THREE.HemisphereLight("#f3f3ff", "#151171", 1.65));
    const keyLight = new THREE.DirectionalLight("#ffffff", 5.4);
    keyLight.position.set(4.8, 6.4, 6.2);
    scene.add(keyLight);
    const rimLight = new THREE.PointLight("#8582ff", 12, 11, 2);
    rimLight.position.set(-3.4, 1.2, 3.6);
    scene.add(rimLight);
    const responseLight = new THREE.PointLight("#aaa8ff", 4, 9, 2);
    responseLight.position.set(0, 0.3, 1.2);
    actor.add(responseLight);

    const baseColor = new THREE.Color("#f7f7ff");
    const errorColor = new THREE.Color("#ffd8dc");
    const clock = new THREE.Clock();
    let frameId = 0;
    let readySent = false;

    const resize = () => {
      const width = Math.max(1, canvas.clientWidth);
      const height = Math.max(1, canvas.clientHeight);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.65));
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    const render = () => {
      const delta = Math.min(clock.getDelta(), 0.05);
      const elapsed = clock.elapsedTime;
      const state = stateRef.current;
      const stateAge = Math.max(0, (performance.now() - stateStartedAt.current) / 1000);
      const recentInput = clamp01(1 - (performance.now() - signals.lastInputAt.current) / 620);
      const typing = state === "typing" ? 1 : 0;
      const errorEnvelope = state === "error" ? Math.exp(-stateAge * 2.9) : 0;
      const errorJolt = Math.sin(stateAge * 52) * errorEnvelope;
      const success = state === "success" ? smoother(clamp01(stateAge / 0.86)) : 0;
      const pointerX = signals.pointer.current.x;
      const pointerY = signals.pointer.current.y;

      const targetRotationX = Math.sin(elapsed * 0.46) * 0.028 - pointerY * 0.13 + errorJolt * 0.05 + success * 0.32;
      const targetRotationY = Math.cos(elapsed * 0.34) * 0.038 + pointerX * 0.19 + errorJolt * 0.15 + success * 0.58;
      const targetRotationZ = pointerX * -0.032 + errorJolt * 0.065 - success * 0.14;
      actor.rotation.x = THREE.MathUtils.damp(actor.rotation.x, targetRotationX, 5.4, delta);
      actor.rotation.y = THREE.MathUtils.damp(actor.rotation.y, targetRotationY, 5.4, delta);
      actor.rotation.z = THREE.MathUtils.damp(actor.rotation.z, targetRotationZ, 6.2, delta);

      const targetX = 0.2 + pointerX * 0.2 - success * 1.05;
      const targetY = 0.42 + pointerY * 0.1 + Math.sin(elapsed * 0.6) * 0.035 + success * 1.18;
      actor.position.x = THREE.MathUtils.damp(actor.position.x, targetX, 4.6, delta);
      actor.position.y = THREE.MathUtils.damp(actor.position.y, targetY, 4.6, delta);
      actor.position.z = THREE.MathUtils.damp(actor.position.z, -success * 1.3, 4.6, delta);

      const targetScale = 0.58 + recentInput * 0.016 + errorEnvelope * 0.012 + success * 0.27;
      const nextScale = THREE.MathUtils.damp(actor.scale.x, targetScale, 5.2, delta);
      actor.scale.setScalar(nextScale);

      material.color.copy(baseColor).lerp(errorColor, errorEnvelope);
      material.emissiveIntensity = 0.1 + typing * 0.025 + recentInput * 0.09 + errorEnvelope * 0.12;
      material.opacity = 1 - smoother(clamp01((success - 0.36) / 0.64));
      responseLight.intensity = Math.max(0, 4 + recentInput * 3 + errorEnvelope * 9 - success * 4);
      responseLight.color.set(state === "error" ? "#ff3147" : "#aaa8ff");

      renderer.render(scene, camera);
      if (!readySent) {
        readySent = true;
        onReadyRef.current();
      }
      frameId = requestAnimationFrame(render);
    };
    frameId = requestAnimationFrame(render);

    return () => {
      cancelAnimationFrame(frameId);
      observer.disconnect();
      geometries.arch.dispose();
      geometries.head.dispose();
      material.dispose();
      renderer.dispose();
    };
  }, [signals]);

  return <canvas ref={canvasRef} aria-hidden style={{ width: "100%", height: "100%", display: "block" }} />;
}
