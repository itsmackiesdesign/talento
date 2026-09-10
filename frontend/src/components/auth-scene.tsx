import { useEffect, useRef } from "react";
import type { MutableRefObject } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

export type AuthVisualState = "idle" | "typing" | "error" | "success";

export type AuthSceneSignals = {
  pointer: MutableRefObject<{ x: number; y: number }>;
  lastInputAt: MutableRefObject<number>;
};

type LogoGeometries = {
  arch: THREE.ExtrudeGeometry;
  head: THREE.ExtrudeGeometry;
};

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const smoother = (value: number) => value * value * value * (value * (value * 6 - 15) + 10);

// This is the same Talento Actor construction used by the public landing scene.
// Keeping it here in raw Three.js lets the auth route stay a lazy, isolated bundle.
function createLogoGeometries(): LogoGeometries {
  const outer = 2.7;
  const inner = 1.5;
  const verticalOffset = -2.52;
  const depth = 0.54;
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
    bevelSegments: 6,
    steps: 1,
    bevelSize: 0.11,
    bevelThickness: 0.12,
    curveSegments: 64,
  };
  const arch = new THREE.ExtrudeGeometry(archShape, settings);
  const head = new THREE.ExtrudeGeometry(headShape, settings);
  arch.translate(0, verticalOffset, -depth / 2);
  head.translate(0, 1.95, -depth / 2);
  arch.computeVertexNormals();
  head.computeVertexNormals();
  return { arch, head };
}

function createRoughnessTexture() {
  const size = 64;
  const data = new Uint8Array(size * size);
  for (let index = 0; index < data.length; index += 1) {
    const wave = Math.sin(index * 12.9898) * 43758.5453;
    data[index] = 112 + Math.floor((wave - Math.floor(wave)) * 44);
  }
  const texture = new THREE.DataTexture(data, size, size, THREE.RedFormat);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(3, 3);
  texture.needsUpdate = true;
  return texture;
}

function addLogoLayer(actor: THREE.Group, geometries: LogoGeometries, material: THREE.Material, scale: number, depth: number) {
  const layer = new THREE.Group();
  layer.scale.setScalar(scale);
  layer.position.z = depth;
  layer.add(new THREE.Mesh(geometries.arch, material), new THREE.Mesh(geometries.head, material));
  actor.add(layer);
  return layer;
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
    renderer.toneMappingExposure = 0.92;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 30);
    camera.position.set(0, 0, 9.35);

    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    const environment = pmremGenerator.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = environment;
    pmremGenerator.dispose();

    const actor = new THREE.Group();
    actor.position.set(0.18, 0.3, 0);
    actor.scale.setScalar(0.63);
    scene.add(actor);

    const geometries = createLogoGeometries();
    const roughnessTexture = createRoughnessTexture();
    const materials = {
      front: new THREE.MeshPhysicalMaterial({
        color: "#2f2bff",
        emissive: "#1712ff",
        emissiveIntensity: 1.45,
        metalness: 0.8,
        roughness: 0.2,
        roughnessMap: roughnessTexture,
        clearcoat: 1,
        clearcoatRoughness: 0.1,
        envMapIntensity: 2,
      }),
      mid: new THREE.MeshPhysicalMaterial({
        color: "#2420e8",
        emissive: "#100dcc",
        emissiveIntensity: 0.92,
        metalness: 0.84,
        roughness: 0.25,
        roughnessMap: roughnessTexture,
        clearcoat: 0.92,
        clearcoatRoughness: 0.16,
        envMapIntensity: 1.7,
      }),
      rear: new THREE.MeshPhysicalMaterial({
        color: "#100d8f",
        emissive: "#0b0870",
        emissiveIntensity: 0.58,
        metalness: 0.88,
        roughness: 0.32,
        roughnessMap: roughnessTexture,
        clearcoat: 0.78,
        clearcoatRoughness: 0.2,
        envMapIntensity: 1.45,
      }),
    };
    const rearLayer = addLogoLayer(actor, geometries, materials.rear, 1.09, -0.34);
    const midLayer = addLogoLayer(actor, geometries, materials.mid, 1.045, -0.17);
    addLogoLayer(actor, geometries, materials.front, 1, 0);

    scene.add(new THREE.HemisphereLight("#eef0ff", "#0b0870", 1.4));
    const keyLight = new THREE.SpotLight("#eef0ff", 72, 18, 0.46, 0.9, 1.5);
    keyLight.position.set(4.5, 6.2, 5);
    scene.add(keyLight);
    const blueLight = new THREE.PointLight("#2f2bff", 18, 9, 2);
    blueLight.position.set(0, 0.2, -0.35);
    actor.add(blueLight);
    const fillLight = new THREE.PointLight("#8d8aff", 9, 10, 2);
    fillLight.position.set(-3.5, 0.8, 4.2);
    scene.add(fillLight);

    const errorFront = new THREE.Color("#8f1f4e");
    const errorMid = new THREE.Color("#651838");
    const errorRear = new THREE.Color("#3d0d23");
    const clock = new THREE.Clock();
    let frameId = 0;
    let readySent = false;

    const resize = () => {
      const width = Math.max(1, canvas.clientWidth);
      const height = Math.max(1, canvas.clientHeight);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
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
      const errorEnvelope = state === "error" ? Math.exp(-stateAge * 2.55) : 0;
      const success = state === "success" ? smoother(clamp01(stateAge / 0.86)) : 0;
      const pointerX = signals.pointer.current.x;
      const pointerY = signals.pointer.current.y;
      const separation = typing * 0.1 + recentInput * 0.06 + errorEnvelope * 0.18;

      // The movement is restrained so the precise bevel silhouette stays crisp.
      const targetRotationX = Math.sin(elapsed * 0.23) * 0.065 - pointerY * 0.1 + errorEnvelope * Math.sin(stateAge * 27) * 0.018 + success * 0.22;
      const targetRotationY = Math.cos(elapsed * 0.19) * 0.085 + pointerX * 0.15 + errorEnvelope * Math.sin(stateAge * 23) * 0.03 + success * 0.46;
      const targetRotationZ = Math.sin(elapsed * 0.16) * 0.028 - pointerX * 0.026 - success * 0.1;
      actor.rotation.x = THREE.MathUtils.damp(actor.rotation.x, targetRotationX, 4.9, delta);
      actor.rotation.y = THREE.MathUtils.damp(actor.rotation.y, targetRotationY, 4.9, delta);
      actor.rotation.z = THREE.MathUtils.damp(actor.rotation.z, targetRotationZ, 5.7, delta);

      const targetX = 0.18 + pointerX * 0.17 - success * 0.86;
      const targetY = 0.3 + pointerY * 0.09 + Math.sin(elapsed * 0.38) * 0.012 + success * 1.05;
      actor.position.x = THREE.MathUtils.damp(actor.position.x, targetX, 4.4, delta);
      actor.position.y = THREE.MathUtils.damp(actor.position.y, targetY, 4.4, delta);
      actor.position.z = THREE.MathUtils.damp(actor.position.z, -success * 0.9, 4.4, delta);
      const targetScale = 0.63 + recentInput * 0.014 + success * 0.2;
      actor.scale.setScalar(THREE.MathUtils.damp(actor.scale.x, targetScale, 5, delta));

      rearLayer.position.z = THREE.MathUtils.damp(rearLayer.position.z, -0.34 - separation * 0.7, 5, delta);
      midLayer.position.z = THREE.MathUtils.damp(midLayer.position.z, -0.17 - separation * 0.36, 5, delta);
      materials.front.color.set("#2f2bff").lerp(errorFront, errorEnvelope);
      materials.mid.color.set("#2420e8").lerp(errorMid, errorEnvelope);
      materials.rear.color.set("#100d8f").lerp(errorRear, errorEnvelope);
      materials.front.emissiveIntensity = 1.45 + typing * 0.08 + recentInput * 0.16 + errorEnvelope * 0.25;
      materials.mid.emissiveIntensity = 0.92 + recentInput * 0.08 + errorEnvelope * 0.15;
      materials.rear.emissiveIntensity = 0.58 + errorEnvelope * 0.08;
      blueLight.intensity = 18 + Math.sin(elapsed * 0.7) * 1.2 + recentInput * 2 + errorEnvelope * 5;
      blueLight.color.set(state === "error" ? "#ff3153" : "#2f2bff");

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
      roughnessTexture.dispose();
      materials.front.dispose();
      materials.mid.dispose();
      materials.rear.dispose();
      environment.dispose();
      renderer.dispose();
    };
  }, [signals]);

  return <canvas ref={canvasRef} aria-hidden style={{ width: "100%", height: "100%", display: "block" }} />;
}
