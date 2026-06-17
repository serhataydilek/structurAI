"use client";

import { Canvas } from "@react-three/fiber";
import { Environment, Grid, OrbitControls, useGLTF } from "@react-three/drei";
import { Suspense, useMemo, useState } from "react";
import type { PointCloudResponse } from "@/lib/types";

export type PointCloudPointSize = "Small" | "Medium" | "Large";

const pointSizes: Record<PointCloudPointSize, number> = {
  Small: 0.025,
  Medium: 0.04,
  Large: 0.065
};

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

function SparsePointCloud({ pointCloud, pointSize }: { pointCloud: PointCloudResponse; pointSize: PointCloudPointSize }) {
  const { positions, colors } = useMemo(() => {
    const points = pointCloud.points;
    if (points.length === 0) {
      return { positions: new Float32Array(), colors: new Float32Array() };
    }

    const center = points.reduce(
      (acc, point) => {
        acc.x += point.x;
        acc.y += point.y;
        acc.z += point.z;
        return acc;
      },
      { x: 0, y: 0, z: 0 }
    );
    center.x /= points.length;
    center.y /= points.length;
    center.z /= points.length;

    let maxRadius = 0;
    for (const point of points) {
      const dx = point.x - center.x;
      const dy = point.y - center.y;
      const dz = point.z - center.z;
      maxRadius = Math.max(maxRadius, Math.sqrt(dx * dx + dy * dy + dz * dz));
    }
    const scale = maxRadius > 0 ? 4 / maxRadius : 1;

    const positionArray = new Float32Array(points.length * 3);
    const colorArray = new Float32Array(points.length * 3);

    points.forEach((point, index) => {
      const offset = index * 3;
      positionArray[offset] = (point.x - center.x) * scale;
      positionArray[offset + 1] = (point.y - center.y) * scale;
      positionArray[offset + 2] = (point.z - center.z) * scale;
      colorArray[offset] = point.r / 255;
      colorArray[offset + 1] = point.g / 255;
      colorArray[offset + 2] = point.b / 255;
    });

    return { positions: positionArray, colors: colorArray };
  }, [pointCloud]);

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial size={pointSizes[pointSize]} vertexColors sizeAttenuation />
    </points>
  );
}

function SceneContent({
  modelUrl,
  pointCloud,
  pointSize,
  showReference
}: {
  modelUrl?: string;
  pointCloud?: PointCloudResponse | null;
  pointSize: PointCloudPointSize;
  showReference: boolean;
}) {
  const [modelFailed, setModelFailed] = useState(false);
  const hasPointCloud = Boolean(pointCloud?.available && pointCloud.points.length > 0);

  return (
    <>
      <ambientLight intensity={0.65} />
      <directionalLight position={[4, 5, 3]} intensity={1.5} castShadow />
      <pointLight position={[-3, 2, 2]} intensity={1} color="#67e8f9" />
      {hasPointCloud ? (
        <SparsePointCloud pointCloud={pointCloud as PointCloudResponse} pointSize={pointSize} />
      ) : (
        <Suspense fallback={<InteriorPlaceholder />}>
          {modelUrl && !modelFailed ? (
          <ErrorBoundary onError={() => setModelFailed(true)}>
            <SampleModel url={modelUrl} />
          </ErrorBoundary>
          ) : (
            <InteriorPlaceholder />
          )}
        </Suspense>
      )}
      {(!hasPointCloud || showReference) && (
        <Grid infiniteGrid fadeDistance={18} fadeStrength={1.5} cellColor="#334155" sectionColor="#67e8f9" />
      )}
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

export function ViewerScene({
  modelUrl,
  pointCloud,
  pointSize = "Medium",
  showReference = true,
  resetKey = 0
}: {
  modelUrl?: string;
  pointCloud?: PointCloudResponse | null;
  pointSize?: PointCloudPointSize;
  showReference?: boolean;
  resetKey?: number;
}) {
  const hasPointCloud = Boolean(pointCloud?.available && pointCloud.points.length > 0);
  return (
    <div className="relative h-[540px] overflow-hidden rounded-lg border border-white/10 bg-slate-950 shadow-glow">
      <div className="pointer-events-none absolute left-4 top-4 z-10 rounded-md border border-brand/25 bg-slate-950/80 px-3 py-2 text-xs font-medium text-cyan-100 backdrop-blur">
        {hasPointCloud
          ? pointCloud?.source === "colmap_dense"
            ? "Dense point cloud preview"
            : "Sparse point cloud preview"
          : "Prototype digital twin preview"}
      </div>
      <Canvas key={resetKey} camera={{ position: hasPointCloud ? [3.5, 2.6, 4.2] : [5, 4, 6], fov: hasPointCloud ? 38 : 45 }} shadows>
        <SceneContent modelUrl={modelUrl} pointCloud={pointCloud} pointSize={pointSize} showReference={showReference} />
      </Canvas>
    </div>
  );
}
