"use client";

import { Canvas } from "@react-three/fiber";
import { Environment, Grid, OrbitControls, useGLTF } from "@react-three/drei";
import { Suspense, useState } from "react";

function SampleModel({ url }: { url: string }) {
  const gltf = useGLTF(url);
  return <primitive object={gltf.scene} scale={1.15} position={[0, -0.8, 0]} />;
}

function InteriorPlaceholder() {
  return (
    <group>
      <mesh position={[0, -0.05, 0]} receiveShadow>
        <boxGeometry args={[6, 0.1, 4.4]} />
        <meshStandardMaterial color="#1f2937" roughness={0.8} />
      </mesh>
      <mesh position={[0, 1.5, -2.2]}>
        <boxGeometry args={[6, 3.1, 0.12]} />
        <meshStandardMaterial color="#334155" roughness={0.7} />
      </mesh>
      <mesh position={[-3, 1.5, 0]}>
        <boxGeometry args={[0.12, 3.1, 4.4]} />
        <meshStandardMaterial color="#263244" roughness={0.7} />
      </mesh>
      <mesh position={[3, 1.5, 0]}>
        <boxGeometry args={[0.12, 3.1, 4.4]} />
        <meshStandardMaterial color="#263244" roughness={0.7} />
      </mesh>
      <mesh position={[-1.2, 1.65, -2.28]}>
        <boxGeometry args={[1.25, 1.05, 0.08]} />
        <meshStandardMaterial color="#67e8f9" emissive="#164e63" emissiveIntensity={0.25} />
      </mesh>
      <mesh position={[1.55, 0.45, -1.25]}>
        <boxGeometry args={[1.2, 0.8, 0.75]} />
        <meshStandardMaterial color="#475569" roughness={0.65} />
      </mesh>
      <mesh position={[-1.7, 0.35, 1.1]}>
        <boxGeometry args={[1.5, 0.7, 0.75]} />
        <meshStandardMaterial color="#64748b" roughness={0.72} />
      </mesh>
      <mesh position={[2.35, 0.85, 1.55]}>
        <boxGeometry args={[0.55, 1.7, 0.55]} />
        <meshStandardMaterial color="#94a3b8" roughness={0.7} />
      </mesh>
    </group>
  );
}

function SceneContent({ modelUrl }: { modelUrl?: string }) {
  const [modelFailed, setModelFailed] = useState(false);

  return (
    <>
      <ambientLight intensity={0.65} />
      <directionalLight position={[4, 5, 3]} intensity={1.5} castShadow />
      <pointLight position={[-3, 2, 2]} intensity={1} color="#67e8f9" />
      <Suspense fallback={<InteriorPlaceholder />}>
        {modelUrl && !modelFailed ? (
          <ErrorBoundary onError={() => setModelFailed(true)}>
            <SampleModel url={modelUrl} />
          </ErrorBoundary>
        ) : (
          <InteriorPlaceholder />
        )}
      </Suspense>
      <Grid infiniteGrid fadeDistance={18} fadeStrength={1.5} cellColor="#334155" sectionColor="#67e8f9" />
      <Environment preset="city" />
      <OrbitControls enableDamping makeDefault />
    </>
  );
}

function ErrorBoundary({ children, onError }: { children: React.ReactNode; onError: () => void }) {
  try {
    return <>{children}</>;
  } catch {
    onError();
    return <InteriorPlaceholder />;
  }
}

export function ViewerScene({ modelUrl }: { modelUrl?: string }) {
  return (
    <div className="relative h-[540px] overflow-hidden rounded-lg border border-white/10 bg-slate-950 shadow-glow">
      {!modelUrl && (
        <div className="pointer-events-none absolute left-4 top-4 z-10 rounded-md border border-brand/25 bg-slate-950/80 px-3 py-2 text-xs font-medium text-cyan-100 backdrop-blur">
          Prototype digital twin preview
        </div>
      )}
      <Canvas camera={{ position: [5, 4, 6], fov: 45 }} shadows>
        <SceneContent modelUrl={modelUrl} />
      </Canvas>
    </div>
  );
}
