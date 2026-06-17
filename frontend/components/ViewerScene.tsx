"use client";

import { Canvas } from "@react-three/fiber";
import { Environment, Grid, OrbitControls } from "@react-three/drei";
import { useMemo } from "react";
import type { PointCloudPoint, PointCloudResponse, PreviewMode, SceneAnalysis, SceneVector, ViewerTransform } from "@/lib/types";

export type PointCloudPointSize = "Small" | "Medium" | "Large";
export type PointCloudColorMode = "rgb" | "height" | "depth" | "solid";

const pointSizes: Record<PointCloudPointSize, number> = {
  Small: 0.025,
  Medium: 0.04,
  Large: 0.065
};

const identityTransform: ViewerTransform = {
  rotationX: 0,
  rotationY: 0,
  rotationZ: 0,
  flipX: false,
  flipY: false,
  flipZ: false,
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  offsetZ: 0
};

function applyViewerTransform(position: [number, number, number], transform?: Partial<ViewerTransform>): [number, number, number] {
  const next = { ...identityTransform, ...transform };
  let [x, y, z] = position;
  x *= next.flipX ? -1 : 1;
  y *= next.flipY ? -1 : 1;
  z *= next.flipZ ? -1 : 1;
  const rotate = (axis: "x" | "y" | "z", degrees: number) => {
    const radians = (degrees * Math.PI) / 180;
    const cos = Math.cos(radians);
    const sin = Math.sin(radians);
    if (axis === "x") {
      const ny = y * cos - z * sin;
      const nz = y * sin + z * cos;
      y = ny;
      z = nz;
    } else if (axis === "y") {
      const nx = x * cos + z * sin;
      const nz = -x * sin + z * cos;
      x = nx;
      z = nz;
    } else {
      const nx = x * cos - y * sin;
      const ny = x * sin + y * cos;
      x = nx;
      y = ny;
    }
  };
  rotate("x", next.rotationX);
  rotate("y", next.rotationY);
  rotate("z", next.rotationZ);
  return [
    x * next.scale + next.offsetX,
    y * next.scale + next.offsetY,
    z * next.scale + next.offsetZ
  ];
}

function sceneTransform(analysis?: SceneAnalysis | null, viewerTransform?: Partial<ViewerTransform>) {
  const center = analysis?.center ?? { x: 0, y: 0, z: 0 };
  const scale = analysis?.available ? analysis.scale : 1;
  return (point: SceneVector | PointCloudPoint): [number, number, number] => applyViewerTransform([
    (point.x - center.x) * scale,
    (point.y - center.y) * scale,
    (point.z - center.z) * scale
  ], viewerTransform);
}

function colorForValue(value: number): [number, number, number] {
  const clamped = Math.max(0, Math.min(1, value));
  return [0.1 + clamped * 0.9, 0.85 - Math.abs(clamped - 0.5) * 0.8, 1 - clamped * 0.85];
}

function SparsePointCloud({
  pointCloud,
  pointSize,
  pointSizeValue,
  pointOpacity,
  colorMode,
  solidColor,
  analysis,
  viewerTransform
}: {
  pointCloud: PointCloudResponse;
  pointSize: PointCloudPointSize;
  pointSizeValue: number;
  pointOpacity: number;
  colorMode: PointCloudColorMode;
  solidColor: [number, number, number];
  analysis?: SceneAnalysis | null;
  viewerTransform?: Partial<ViewerTransform>;
}) {
  const { positions, colors } = useMemo(() => {
    const points = pointCloud.points;
    if (points.length === 0) {
      return { positions: new Float32Array(), colors: new Float32Array() };
    }

    let transform = sceneTransform(analysis, viewerTransform);
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
      transform = (point) => applyViewerTransform([(point.x - center.x) * scale, (point.y - center.y) * scale, (point.z - center.z) * scale], viewerTransform);
    }

    const positionArray = new Float32Array(points.length * 3);
    const colorArray = new Float32Array(points.length * 3);
    const bounds = { minY: Infinity, maxY: -Infinity, minZ: Infinity, maxZ: -Infinity };
    const transformed = points.map((point) => {
      const position = transform(point);
      bounds.minY = Math.min(bounds.minY, position[1]);
      bounds.maxY = Math.max(bounds.maxY, position[1]);
      bounds.minZ = Math.min(bounds.minZ, position[2]);
      bounds.maxZ = Math.max(bounds.maxZ, position[2]);
      return position;
    });

    points.forEach((point, index) => {
      const offset = index * 3;
      const [x, y, z] = transformed[index];
      positionArray[offset] = x;
      positionArray[offset + 1] = y;
      positionArray[offset + 2] = z;
      const heightSpan = Math.max(0.001, bounds.maxY - bounds.minY);
      const depthSpan = Math.max(0.001, bounds.maxZ - bounds.minZ);
      const color = colorMode === "height"
        ? colorForValue((y - bounds.minY) / heightSpan)
        : colorMode === "depth"
          ? colorForValue((z - bounds.minZ) / depthSpan)
          : colorMode === "solid"
            ? solidColor
            : [point.r / 255, point.g / 255, point.b / 255];
      colorArray[offset] = color[0];
      colorArray[offset + 1] = color[1];
      colorArray[offset + 2] = color[2];
    });

    return { positions: positionArray, colors: colorArray };
  }, [analysis, colorMode, pointCloud, solidColor, viewerTransform]);

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial size={pointSizeValue || pointSizes[pointSize]} vertexColors sizeAttenuation transparent opacity={pointOpacity} depthWrite={pointOpacity >= 0.98} />
    </points>
  );
}

function EstimatedFloor({ analysis, viewerTransform }: { analysis?: SceneAnalysis | null; viewerTransform?: Partial<ViewerTransform> }) {
  if (!analysis?.available || !analysis.floorEstimate || !analysis.roomScaffold) return null;
  const transform = sceneTransform(analysis, viewerTransform);
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

function RoomScaffold({ analysis, viewerTransform, exterior = false }: { analysis?: SceneAnalysis | null; viewerTransform?: Partial<ViewerTransform>; exterior?: boolean }) {
  const scaffold = analysis?.roomScaffold;
  if (!analysis?.available || !scaffold) return null;
  const transform = sceneTransform(analysis, viewerTransform);
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
      <lineBasicMaterial color={exterior ? "#94a3b8" : "#67e8f9"} transparent opacity={exterior ? 0.45 : 0.9} />
    </lineSegments>
  );
}

function CameraPath({ analysis, viewerTransform }: { analysis?: SceneAnalysis | null; viewerTransform?: Partial<ViewerTransform> }) {
  const cameras = analysis?.cameraPath.positions ?? [];
  if (!analysis?.available || !analysis.cameraPath.available || cameras.length === 0) return null;
  const transform = sceneTransform(analysis, viewerTransform);
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

function AxisGizmo() {
  const positions = new Float32Array([
    0, 0, 0, 1, 0, 0,
    0, 0, 0, 0, 1, 0,
    0, 0, 0, 0, 0, 1
  ]);
  const colors = new Float32Array([
    1, 0.2, 0.2, 1, 0.2, 0.2,
    0.2, 1, 0.3, 0.2, 1, 0.3,
    0.3, 0.55, 1, 0.3, 0.55, 1
  ]);
  return (
    <lineSegments position={[-2.4, -1.55, -2.2]}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <lineBasicMaterial vertexColors />
    </lineSegments>
  );
}

function SceneContent({
  pointCloud,
  sceneAnalysis,
  pointSize,
  pointSizeValue,
  pointOpacity,
  colorMode,
  solidColor,
  showSparsePoints,
  showRoomBounds,
  showEstimatedFloor,
  showCameraPath,
  showBoundingBox,
  showReference,
  viewerTransform,
  previewMode
}: {
  pointCloud?: PointCloudResponse | null;
  sceneAnalysis?: SceneAnalysis | null;
  pointSize: PointCloudPointSize;
  pointSizeValue: number;
  pointOpacity: number;
  colorMode: PointCloudColorMode;
  solidColor: [number, number, number];
  showSparsePoints: boolean;
  showRoomBounds: boolean;
  showEstimatedFloor: boolean;
  showCameraPath: boolean;
  showBoundingBox: boolean;
  showReference: boolean;
  viewerTransform?: Partial<ViewerTransform>;
  previewMode: PreviewMode;
}) {
  const hasPointCloud = Boolean(pointCloud?.available && pointCloud.points.length > 0);

  return (
    <>
      <ambientLight intensity={0.65} />
      <directionalLight position={[4, 5, 3]} intensity={1.5} castShadow />
      <pointLight position={[-3, 2, 2]} intensity={1} color="#67e8f9" />
      {hasPointCloud && (
        <>
          {showSparsePoints && <SparsePointCloud pointCloud={pointCloud as PointCloudResponse} pointSize={pointSize} pointSizeValue={pointSizeValue} pointOpacity={pointOpacity} colorMode={colorMode} solidColor={solidColor} analysis={sceneAnalysis} viewerTransform={viewerTransform} />}
          {showEstimatedFloor && <EstimatedFloor analysis={sceneAnalysis} viewerTransform={viewerTransform} />}
          {showRoomBounds && <RoomScaffold analysis={sceneAnalysis} viewerTransform={viewerTransform} />}
          {showBoundingBox && <RoomScaffold analysis={sceneAnalysis} viewerTransform={viewerTransform} exterior={previewMode === "exterior"} />}
          {showCameraPath && <CameraPath analysis={sceneAnalysis} viewerTransform={viewerTransform} />}
          {previewMode === "exterior" && <AxisGizmo />}
        </>
      )}
      {showReference && (
        <Grid infiniteGrid fadeDistance={18} fadeStrength={1.5} cellColor="#334155" sectionColor="#67e8f9" />
      )}
      <Environment preset="city" />
      <OrbitControls enableDamping makeDefault />
    </>
  );
}

export function ViewerScene({
  pointCloud,
  sceneAnalysis,
  pointSize = "Medium",
  pointSizeValue,
  pointOpacity = 1,
  colorMode = "rgb",
  solidColor = [0.4, 0.9, 1],
  showSparsePoints = true,
  showRoomBounds = true,
  showEstimatedFloor = true,
  showCameraPath = true,
  showBoundingBox = false,
  showReference = true,
  viewerTransform,
  previewMode = "auto",
  outputLabel,
  resetKey = 0
}: {
  pointCloud?: PointCloudResponse | null;
  sceneAnalysis?: SceneAnalysis | null;
  pointSize?: PointCloudPointSize;
  pointSizeValue?: number;
  pointOpacity?: number;
  colorMode?: PointCloudColorMode;
  solidColor?: [number, number, number];
  showSparsePoints?: boolean;
  showRoomBounds?: boolean;
  showEstimatedFloor?: boolean;
  showCameraPath?: boolean;
  showBoundingBox?: boolean;
  showReference?: boolean;
  viewerTransform?: Partial<ViewerTransform>;
  previewMode?: PreviewMode;
  outputLabel?: string;
  resetKey?: number;
}) {
  const hasPointCloud = Boolean(pointCloud?.available && pointCloud.points.length > 0);
  if (!hasPointCloud) {
    return (
      <div className="flex h-[540px] items-center justify-center rounded-lg border border-white/10 bg-slate-950 p-8 text-center shadow-glow">
        <div>
          <p className="text-xl font-semibold text-white">No reconstruction output yet</p>
          <p className="mt-2 max-w-md text-sm leading-6 text-slate-400">
            Upload media, process capture, then run sparse reconstruction to generate a real preview.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="relative h-[540px] overflow-hidden rounded-lg border border-white/10 bg-slate-950 shadow-glow">
      <div className="pointer-events-none absolute left-4 top-4 z-10 rounded-md border border-brand/25 bg-slate-950/80 px-3 py-2 text-xs font-medium text-cyan-100 backdrop-blur">
        {outputLabel ?? (hasPointCloud
          ? pointCloud?.source === "colmap_dense"
            ? "Dense point cloud preview"
            : previewMode === "exterior"
              ? "Sparse building preview"
              : sceneAnalysis?.available
                ? "Sparse scene preview"
                : "Sparse point cloud preview"
          : "No reconstruction output")}
      </div>
      <Canvas key={resetKey} camera={{ position: [3.5, 2.6, 4.2], fov: 38 }} shadows>
        <SceneContent
          pointCloud={pointCloud}
          sceneAnalysis={sceneAnalysis}
          pointSize={pointSize}
          pointSizeValue={pointSizeValue ?? pointSizes[pointSize]}
          pointOpacity={pointOpacity}
          colorMode={colorMode}
          solidColor={solidColor}
          showSparsePoints={showSparsePoints}
          showRoomBounds={showRoomBounds}
          showEstimatedFloor={showEstimatedFloor}
          showCameraPath={showCameraPath}
          showBoundingBox={showBoundingBox}
          showReference={showReference}
          viewerTransform={viewerTransform}
          previewMode={previewMode}
        />
      </Canvas>
    </div>
  );
}
