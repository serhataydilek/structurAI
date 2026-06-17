"use client";

import { Canvas } from "@react-three/fiber";
import { Environment, Grid, OrbitControls, useGLTF } from "@react-three/drei";
import { Suspense, useMemo, useState } from "react";
import type { PointCloudPoint, PointCloudResponse, SceneAnalysis, SceneVector } from "@/lib/types";

export type PointCloudPointSize = "Small" | "Medium" | "Large";

const pointSizes: Record<PointCloudPointSize, number> = {
  Small: 0.025,
  Medium: 0.04,
  Large: 0.065
};

function sceneTransform(analysis?: SceneAnalysis | null) {
  const center = analysis?.center ?? { x: 0, y: 0, z: 0 };
  const scale = analysis?.available ? analysis.scale : 1;
  return (point: SceneVector | PointCloudPoint): [number, number, number] => [
    (point.x - center.x) * scale,
    (point.y - center.y) * scale,
    (point.z - center.z) * scale
  ];
}

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

function SparsePointCloud({
  pointCloud,
  pointSize,
  analysis
}: {
  pointCloud: PointCloudResponse;
  pointSize: PointCloudPointSize;
  analysis?: SceneAnalysis | null;
}) {
  const { positions, colors } = useMemo(() => {
    const points = pointCloud.points;
    if (points.length === 0) {
      return { positions: new Float32Array(), colors: new Float32Array() };
    }

    let transform = sceneTransform(analysis);
    if (!analysis?.available) {
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
      transform = (point) => [(point.x - center.x) * scale, (point.y - center.y) * scale, (point.z - center.z) * scale];
    }

    const positionArray = new Float32Array(points.length * 3);
    const colorArray = new Float32Array(points.length * 3);

    points.forEach((point, index) => {
      const offset = index * 3;
      const [x, y, z] = transform(point);
      positionArray[offset] = x;
      positionArray[offset + 1] = y;
      positionArray[offset + 2] = z;
      colorArray[offset] = point.r / 255;
      colorArray[offset + 1] = point.g / 255;
      colorArray[offset + 2] = point.b / 255;
    });

    return { positions: positionArray, colors: colorArray };
  }, [analysis, pointCloud]);

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

function EstimatedFloor({ analysis }: { analysis?: SceneAnalysis | null }) {
  if (!analysis?.available || !analysis.floorEstimate || !analysis.roomScaffold) return null;
  const transform = sceneTransform(analysis);
  const scaffold = analysis.roomScaffold;
  const [centerX, floorY, centerZ] = transform({
    x: (scaffold.minX + scaffold.maxX) / 2,
    y: analysis.floorEstimate.level,
    z: (scaffold.minZ + scaffold.maxZ) / 2
  });
  const width = Math.max(0.2, scaffold.width * analysis.scale);
  const depth = Math.max(0.2, scaffold.depth * analysis.scale);

  return (
    <mesh position={[centerX, floorY - 0.015, centerZ]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[width, depth]} />
      <meshStandardMaterial color="#0f766e" transparent opacity={0.16} roughness={0.9} />
    </mesh>
  );
}

function RoomScaffold({ analysis }: { analysis?: SceneAnalysis | null }) {
  const scaffold = analysis?.roomScaffold;
  if (!analysis?.available || !scaffold) return null;
  const transform = sceneTransform(analysis);
  const corners = [
    transform({ x: scaffold.minX, y: scaffold.minY, z: scaffold.minZ }),
    transform({ x: scaffold.maxX, y: scaffold.minY, z: scaffold.minZ }),
    transform({ x: scaffold.maxX, y: scaffold.minY, z: scaffold.maxZ }),
    transform({ x: scaffold.minX, y: scaffold.minY, z: scaffold.maxZ }),
    transform({ x: scaffold.minX, y: scaffold.maxY, z: scaffold.minZ }),
    transform({ x: scaffold.maxX, y: scaffold.maxY, z: scaffold.minZ }),
    transform({ x: scaffold.maxX, y: scaffold.maxY, z: scaffold.maxZ }),
    transform({ x: scaffold.minX, y: scaffold.maxY, z: scaffold.maxZ })
  ];
  const edgePairs = [
    [0, 1], [1, 2], [2, 3], [3, 0],
    [4, 5], [5, 6], [6, 7], [7, 4],
    [0, 4], [1, 5], [2, 6], [3, 7]
  ];
  const positions = new Float32Array(edgePairs.flatMap(([a, b]) => [...corners[a], ...corners[b]]));

  return (
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <lineBasicMaterial color="#67e8f9" transparent opacity={0.9} />
    </lineSegments>
  );
}

function CameraPath({ analysis }: { analysis?: SceneAnalysis | null }) {
  const cameras = analysis?.cameraPath.positions ?? [];
  if (!analysis?.available || !analysis.cameraPath.available || cameras.length === 0) return null;
  const transform = sceneTransform(analysis);
  const pathPositions = new Float32Array(cameras.flatMap((camera) => transform(camera)));

  return (
    <group>
      {cameras.map((camera) => {
        const position = transform(camera);
        return (
          <mesh key={`${camera.imageId}-${camera.imageName}`} position={position}>
            <sphereGeometry args={[0.055, 12, 12]} />
            <meshStandardMaterial color="#fbbf24" emissive="#78350f" emissiveIntensity={0.25} />
          </mesh>
        );
      })}
      {cameras.length > 1 && (
        <line>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[pathPositions, 3]} />
          </bufferGeometry>
          <lineBasicMaterial color="#fbbf24" transparent opacity={0.85} />
        </line>
      )}
    </group>
  );
}

function SceneContent({
  modelUrl,
  pointCloud,
  sceneAnalysis,
  pointSize,
  showSparsePoints,
  showRoomBounds,
  showEstimatedFloor,
  showCameraPath,
  showReference
}: {
  modelUrl?: string;
  pointCloud?: PointCloudResponse | null;
  sceneAnalysis?: SceneAnalysis | null;
  pointSize: PointCloudPointSize;
  showSparsePoints: boolean;
  showRoomBounds: boolean;
  showEstimatedFloor: boolean;
  showCameraPath: boolean;
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
        <>
          {showSparsePoints && <SparsePointCloud pointCloud={pointCloud as PointCloudResponse} pointSize={pointSize} analysis={sceneAnalysis} />}
          {showEstimatedFloor && <EstimatedFloor analysis={sceneAnalysis} />}
          {showRoomBounds && <RoomScaffold analysis={sceneAnalysis} />}
          {showCameraPath && <CameraPath analysis={sceneAnalysis} />}
        </>
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
  sceneAnalysis,
  pointSize = "Medium",
  showSparsePoints = true,
  showRoomBounds = true,
  showEstimatedFloor = true,
  showCameraPath = true,
  showReference = true,
  resetKey = 0
}: {
  modelUrl?: string;
  pointCloud?: PointCloudResponse | null;
  sceneAnalysis?: SceneAnalysis | null;
  pointSize?: PointCloudPointSize;
  showSparsePoints?: boolean;
  showRoomBounds?: boolean;
  showEstimatedFloor?: boolean;
  showCameraPath?: boolean;
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
            : sceneAnalysis?.available
              ? "Sparse scene preview"
              : "Sparse point cloud preview"
          : "Prototype digital twin preview"}
      </div>
      <Canvas key={resetKey} camera={{ position: hasPointCloud ? [3.5, 2.6, 4.2] : [5, 4, 6], fov: hasPointCloud ? 38 : 45 }} shadows>
        <SceneContent
          modelUrl={modelUrl}
          pointCloud={pointCloud}
          sceneAnalysis={sceneAnalysis}
          pointSize={pointSize}
          showSparsePoints={showSparsePoints}
          showRoomBounds={showRoomBounds}
          showEstimatedFloor={showEstimatedFloor}
          showCameraPath={showCameraPath}
          showReference={showReference}
        />
      </Canvas>
    </div>
  );
}
