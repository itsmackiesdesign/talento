import { AdaptiveDpr, ContactShadows, Environment, Lightformer } from "@react-three/drei";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer, Noise, Vignette } from "@react-three/postprocessing";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { SVGLoader } from "three/examples/jsm/loaders/SVGLoader.js";

import type { LandingTimeline } from "./landing-types";

type Pose = {
  position: [number, number, number];
  rotation: [number, number, number];
  scale: number;
  camera: [number, number, number];
};

const POSES: Pose[] = [
  { position: [0, 0.1, 0], rotation: [0.04, -0.12, -0.08], scale: 1.28, camera: [0, 0, 9] },
  { position: [2.75, 0.05, 0], rotation: [-0.06, -0.42, 0.1], scale: 1.62, camera: [0, 0, 9.4] },
  { position: [-2.65, 0.12, -0.2], rotation: [0.06, 0.36, -0.12], scale: 1.18, camera: [0.2, 0, 9.2] },
  { position: [2.55, -0.05, -0.35], rotation: [-0.04, -0.3, 0.08], scale: 1.34, camera: [-0.15, 0, 9.1] },
  { position: [0, 0, 1.1], rotation: [0, 0, 0], scale: 2.45, camera: [0, 0, 8.2] },
  { position: [3.4, 0.18, -0.7], rotation: [0.08, -0.52, 0.08], scale: 1.05, camera: [0.1, 0.05, 9.5] },
  { position: [2.75, 0.05, -0.2], rotation: [0, -0.25, 0.08], scale: 1.44, camera: [0, 0, 9.2] },
  { position: [0, 0.1, 0], rotation: [0, 0, 0], scale: 1.24, camera: [0, 0, 9] },
];

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const smooth = (value: number) => value * value * (3 - 2 * value);

function PortalGeometry() {
  const svg = useLoader(SVGLoader, "/assets/brand/talento-symbol-blue.svg");
  const geometries = useMemo(() => {
    const list: THREE.ExtrudeGeometry[] = [];
    svg.paths.forEach((path) => {
      SVGLoader.createShapes(path).forEach((shape) => {
        const geometry = new THREE.ExtrudeGeometry(shape, {
          depth: 18,
          bevelEnabled: true,
          bevelSegments: 6,
          steps: 1,
          bevelSize: 2.8,
          bevelThickness: 3.2,
          curveSegments: 28,
        });
        geometry.translate(-128, -128, -9);
        geometry.computeVertexNormals();
        list.push(geometry);
      });
    });
    return list;
  }, [svg]);

  useEffect(
    () => () => {
      geometries.forEach((geometry) => geometry.dispose());
    },
    [geometries],
  );

  return (
    <group scale={[0.018, -0.018, 0.018]}>
      {geometries.map((geometry, index) => (
        <mesh key={index} geometry={geometry} castShadow receiveShadow>
          <meshPhysicalMaterial
            color="#2f2bff"
            emissive="#1712ff"
            emissiveIntensity={1.3}
            metalness={0.82}
            roughness={0.18}
            clearcoat={1}
            clearcoatRoughness={0.12}
            envMapIntensity={1.8}
          />
        </mesh>
      ))}
    </group>
  );
}

function PortalActor({ timeline, reducedMotion }: { timeline: LandingTimeline; reducedMotion: boolean }) {
  const actor = useRef<THREE.Group>(null);
  const rearLayer = useRef<THREE.Group>(null);
  const midLayer = useRef<THREE.Group>(null);
  const glow = useRef<THREE.PointLight>(null);
  const { camera } = useThree();
  const target = useMemo(() => new THREE.Vector3(), []);

  useFrame((state) => {
    const sample = timeline.current;
    const current = POSES[sample.index] ?? POSES[0];
    const next = POSES[Math.min(POSES.length - 1, sample.index + 1)];
    const transition = reducedMotion ? 0 : smooth(clamp01((sample.local - 0.7) / 0.3));
    const time = state.clock.elapsedTime;

    if (actor.current) {
      actor.current.position.set(
        THREE.MathUtils.lerp(current.position[0], next.position[0], transition),
        THREE.MathUtils.lerp(current.position[1], next.position[1], transition),
        THREE.MathUtils.lerp(current.position[2], next.position[2], transition),
      );
      actor.current.rotation.set(
        THREE.MathUtils.lerp(current.rotation[0], next.rotation[0], transition),
        THREE.MathUtils.lerp(current.rotation[1], next.rotation[1], transition),
        THREE.MathUtils.lerp(current.rotation[2], next.rotation[2], transition),
      );
      const idle = reducedMotion ? 0 : Math.sin(time * 0.38) * 0.012;
      const scale = THREE.MathUtils.lerp(current.scale, next.scale, transition) + idle;
      actor.current.scale.setScalar(scale);
    }

    const systemOpen = sample.index === 6 ? smooth(clamp01((sample.local - 0.44) / 0.28)) : 0;
    if (rearLayer.current) rearLayer.current.position.z = -0.34 - systemOpen * 1.2;
    if (midLayer.current) midLayer.current.position.z = -0.17 - systemOpen * 0.55;
    if (glow.current) glow.current.intensity = 18 + Math.sin(time * 0.7) * (reducedMotion ? 0 : 1.2);

    camera.position.set(
      THREE.MathUtils.lerp(current.camera[0], next.camera[0], transition),
      THREE.MathUtils.lerp(current.camera[1], next.camera[1], transition),
      THREE.MathUtils.lerp(current.camera[2], next.camera[2], transition),
    );
    target.set(0, 0, 0);
    camera.lookAt(target);
  });

  return (
    <group ref={actor}>
      <group ref={rearLayer} scale={1.09}>
        <PortalGeometry />
      </group>
      <group ref={midLayer} scale={1.045}>
        <PortalGeometry />
      </group>
      <PortalGeometry />
      <mesh position={[0, 0, -0.48]} scale={[2.15, 2.15, 0.08]}>
        <circleGeometry args={[1, 96]} />
        <meshPhysicalMaterial
          color="#050507"
          roughness={0.18}
          metalness={0.35}
          transmission={0.16}
          thickness={0.8}
          transparent
          opacity={0.9}
        />
      </mesh>
      <pointLight ref={glow} color="#2f2bff" intensity={18} distance={9} decay={2} />
    </group>
  );
}

function SceneContent({ timeline, reducedMotion }: { timeline: LandingTimeline; reducedMotion: boolean }) {
  return (
    <>
      <color attach="background" args={["#050507"]} />
      <fog attach="fog" args={["#050507", 8, 18]} />

      <Environment resolution={256}>
        <Lightformer intensity={4.2} color="#ffffff" position={[4, 5, 4]} scale={[4, 1, 1]} />
        <Lightformer intensity={3.4} color="#2f2bff" position={[-4, 1, 2]} scale={[2, 3, 1]} />
        <Lightformer intensity={1.4} color="#6d6d7a" position={[0, -4, 2]} scale={[5, 1, 1]} />
      </Environment>
      <spotLight
        position={[4.5, 6.2, 5]}
        angle={0.46}
        penumbra={0.9}
        intensity={72}
        color="#eef0ff"
        castShadow
        shadow-mapSize={[1024, 1024]}
      />
      <PortalActor timeline={timeline} reducedMotion={reducedMotion} />
      <ContactShadows position={[0, -2.25, 0]} opacity={0.48} blur={2.8} scale={14} far={6} />

      <EffectComposer multisampling={2}>
        <Bloom intensity={0.72} luminanceThreshold={0.84} luminanceSmoothing={0.2} mipmapBlur />
        <Vignette offset={0.25} darkness={0.66} />
        <Noise opacity={0.035} premultiply />
      </EffectComposer>
      <AdaptiveDpr pixelated />
    </>
  );
}

export default function LandingScene({
  timeline,
  reducedMotion,
  onReady,
}: {
  timeline: LandingTimeline;
  reducedMotion: boolean;
  onReady: () => void;
}) {
  return (
    <Canvas
      shadows
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
      camera={{ position: [0, 0, 9], fov: 38, near: 0.1, far: 40 }}
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 0.92;
        requestAnimationFrame(onReady);
      }}
    >
      <SceneContent timeline={timeline} reducedMotion={reducedMotion} />
    </Canvas>
  );
}

