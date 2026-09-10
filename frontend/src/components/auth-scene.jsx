import { AdaptiveDpr, ContactShadows, Environment, Lightformer } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer, Noise, Vignette } from "@react-three/postprocessing";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

const clamp01 = (value) => Math.min(1, Math.max(0, value));
const smoother = (value) => value * value * value * (value * (value * 6 - 15) + 10);

// The public landing and auth page deliberately share this exact Talento actor geometry.
function createLogoGeometries() {
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
  const settings = { depth, bevelEnabled: true, bevelSegments: 6, steps: 1, bevelSize: 0.11, bevelThickness: 0.12, curveSegments: 64 };
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

function LogoLayer({ geometries, material }) {
  return <><mesh geometry={geometries.arch} material={material} castShadow receiveShadow /><mesh geometry={geometries.head} material={material} castShadow receiveShadow /></>;
}

function TalentoAuthActor({ visualState, signals }) {
  const actor = useRef(null);
  const rearLayer = useRef(null);
  const midLayer = useRef(null);
  const glow = useRef(null);
  const stateStartedAt = useRef(performance.now());
  const previousState = useRef(visualState);
  const { camera } = useThree();
  const geometries = useMemo(createLogoGeometries, []);
  const roughnessTexture = useMemo(createRoughnessTexture, []);
  const errorColors = useMemo(() => ({ front: new THREE.Color("#8f1f4e"), mid: new THREE.Color("#651838"), rear: new THREE.Color("#3d0d23") }), []);
  const materials = useMemo(() => ({
    front: new THREE.MeshPhysicalMaterial({ color: "#2f2bff", emissive: "#1712ff", emissiveIntensity: 1.45, metalness: 0.8, roughness: 0.2, roughnessMap: roughnessTexture, clearcoat: 1, clearcoatRoughness: 0.1, envMapIntensity: 2 }),
    mid: new THREE.MeshPhysicalMaterial({ color: "#2420e8", emissive: "#100dcc", emissiveIntensity: 0.92, metalness: 0.84, roughness: 0.25, roughnessMap: roughnessTexture, clearcoat: 0.92, clearcoatRoughness: 0.16, envMapIntensity: 1.7 }),
    rear: new THREE.MeshPhysicalMaterial({ color: "#100d8f", emissive: "#0b0870", emissiveIntensity: 0.58, metalness: 0.88, roughness: 0.32, roughnessMap: roughnessTexture, clearcoat: 0.78, clearcoatRoughness: 0.2, envMapIntensity: 1.45 }),
  }), [roughnessTexture]);

  useEffect(() => () => {
    geometries.arch.dispose();
    geometries.head.dispose();
    roughnessTexture.dispose();
    materials.front.dispose();
    materials.mid.dispose();
    materials.rear.dispose();
  }, [geometries, materials, roughnessTexture]);

  useFrame((state, delta) => {
    if (previousState.current !== visualState) {
      previousState.current = visualState;
      stateStartedAt.current = performance.now();
    }
    const time = state.clock.elapsedTime;
    const stateAge = Math.max(0, (performance.now() - stateStartedAt.current) / 1000);
    const recentInput = clamp01(1 - (performance.now() - signals.lastInputAt.current) / 620);
    const typing = visualState === "typing" ? 1 : 0;
    const errorEnvelope = visualState === "error" ? Math.exp(-stateAge * 2.55) : 0;
    const success = visualState === "success" ? smoother(clamp01(stateAge / 0.86)) : 0;
    const pointerX = signals.pointer.current.x;
    const pointerY = signals.pointer.current.y;
    const separation = typing * 0.1 + recentInput * 0.06 + errorEnvelope * 0.18;

    if (actor.current) {
      const rotationX = 0.08 + Math.sin(time * 0.23) * 0.065 - pointerY * 0.1 + errorEnvelope * Math.sin(stateAge * 27) * 0.018 + success * 0.22;
      const rotationY = -0.18 + Math.cos(time * 0.19) * 0.085 + pointerX * 0.15 + errorEnvelope * Math.sin(stateAge * 23) * 0.03 + success * 0.46;
      const rotationZ = -0.05 + Math.sin(time * 0.16) * 0.028 - pointerX * 0.026 - success * 0.1;
      actor.current.rotation.x = THREE.MathUtils.damp(actor.current.rotation.x, rotationX, 4.9, delta);
      actor.current.rotation.y = THREE.MathUtils.damp(actor.current.rotation.y, rotationY, 4.9, delta);
      actor.current.rotation.z = THREE.MathUtils.damp(actor.current.rotation.z, rotationZ, 5.7, delta);
      actor.current.position.x = THREE.MathUtils.damp(actor.current.position.x, pointerX * 0.17 - success * 0.86, 4.4, delta);
      actor.current.position.y = THREE.MathUtils.damp(actor.current.position.y, 0.08 + pointerY * 0.09 + Math.sin(time * 0.38) * 0.012 + success * 1.05, 4.4, delta);
      actor.current.position.z = THREE.MathUtils.damp(actor.current.position.z, -0.2 - success * 0.9, 4.4, delta);
      actor.current.scale.setScalar(THREE.MathUtils.damp(actor.current.scale.x, 0.62 + recentInput * 0.014 + success * 0.2, 5, delta));
    }
    if (rearLayer.current) rearLayer.current.position.z = THREE.MathUtils.damp(rearLayer.current.position.z, -0.34 - separation * 0.7, 5, delta);
    if (midLayer.current) midLayer.current.position.z = THREE.MathUtils.damp(midLayer.current.position.z, -0.17 - separation * 0.36, 5, delta);
    materials.front.color.set("#2f2bff").lerp(errorColors.front, errorEnvelope);
    materials.mid.color.set("#2420e8").lerp(errorColors.mid, errorEnvelope);
    materials.rear.color.set("#100d8f").lerp(errorColors.rear, errorEnvelope);
    materials.front.emissiveIntensity = 1.45 + typing * 0.08 + recentInput * 0.16 + errorEnvelope * 0.25;
    materials.mid.emissiveIntensity = 0.92 + recentInput * 0.08 + errorEnvelope * 0.15;
    materials.rear.emissiveIntensity = 0.58 + errorEnvelope * 0.08;
    if (glow.current) {
      glow.current.intensity = 18 + Math.sin(time * 0.7) * 1.2 + recentInput * 2 + errorEnvelope * 5;
      glow.current.color.set(visualState === "error" ? "#ff3153" : "#2f2bff");
    }
    camera.position.set(0, 0, 9.35);
    camera.lookAt(0, 0, 0);
  });

  return <group ref={actor} position={[0, 0.08, -0.2]} rotation={[0.08, -0.18, -0.05]} scale={0.62}>
    <group ref={rearLayer} scale={1.09} position-z={-0.34}><LogoLayer geometries={geometries} material={materials.rear} /></group>
    <group ref={midLayer} scale={1.045} position-z={-0.17}><LogoLayer geometries={geometries} material={materials.mid} /></group>
    <LogoLayer geometries={geometries} material={materials.front} />
    <pointLight ref={glow} position={[0, 0.2, -0.35]} color="#2f2bff" intensity={18} distance={9} decay={2} />
  </group>;
}

function AuthSceneContent({ visualState, signals }) {
  return <>
    <Environment resolution={256}>
      <Lightformer intensity={4.2} color="#ffffff" position={[4, 5, 4]} scale={[4, 1, 1]} />
      <Lightformer intensity={3.4} color="#2f2bff" position={[-4, 1, 2]} scale={[2, 3, 1]} />
      <Lightformer intensity={1.4} color="#6d6d7a" position={[0, -4, 2]} scale={[5, 1, 1]} />
    </Environment>
    <spotLight position={[4.5, 6.2, 5]} angle={0.46} penumbra={0.9} intensity={72} color="#eef0ff" castShadow shadow-mapSize={[1024, 1024]} />
    <TalentoAuthActor visualState={visualState} signals={signals} />
    <ContactShadows position={[0, -2.25, 0]} opacity={0.48} blur={2.8} scale={14} far={6} />
    <EffectComposer multisampling={2}><Bloom intensity={0.72} luminanceThreshold={0.84} luminanceSmoothing={0.2} mipmapBlur /><Vignette offset={0.25} darkness={0.66} /><Noise opacity={0.035} premultiply /></EffectComposer>
    <AdaptiveDpr pixelated />
  </>;
}

export default function AuthScene({ visualState, signals, onReady }) {
  return <Canvas shadows dpr={[1, 1.75]} gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }} camera={{ position: [0, 0, 9.35], fov: 38, near: 0.1, far: 40 }} onCreated={({ gl }) => {
    gl.toneMapping = THREE.ACESFilmicToneMapping;
    gl.toneMappingExposure = 0.92;
    requestAnimationFrame(onReady);
  }}><AuthSceneContent visualState={visualState} signals={signals} /></Canvas>;
}
