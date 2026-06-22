"use client";

import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { MTLLoader } from "three/examples/jsm/loaders/MTLLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Box3, Group, Object3D, Vector3 } from "three";
import { Component, type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import type { ModelArtifact } from "@/lib/types";

export const MAX_DIRECT_OBJ_BYTES = 75 * 1024 * 1024;
export const MAX_DIRECT_TEXTURE_COUNT = 24;
export const MAX_DIRECT_GLB_BYTES = 250 * 1024 * 1024;

export type ViewerModelLayer = {
  id: string;
  url: string;
  label: string;
  role: "current" | "target";
  visible: boolean;
  opacity: number;
  transform?: {
    position: { x: number; y: number; z: number };
    rotation?: { x?: number; y: number; z?: number };
    scale: number;
  };
  artifact: ModelArtifact;
};
export type ViewerLayerCenter = { x: number; y: number; z: number };

function artifactRelativePath(artifact: ModelArtifact, source: string | null | undefined) {
  if (!source) return null;
  const normalized = source.replaceAll("\\", "/");
  const root = artifact.bundle?.bundleRootPath?.replaceAll("\\", "/").replace(/\/$/, "");
  return root && normalized.startsWith(`${root}/`) ? normalized.slice(root.length + 1) : normalized.split("/").pop() ?? null;
}

function disposeObject(object: Object3D) {
  object.traverse((node) => {
    const mesh = node as Group & { geometry?: { dispose: () => void }; material?: unknown };
    mesh.geometry?.dispose();
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    materials.forEach((material: any) => {
      if (!material) return;
      Object.values(material).forEach((value: any) => value?.isTexture && value.dispose?.());
      material.dispose?.();
    });
  });
}

class PreviewErrorBoundary extends Component<{ children: ReactNode; onError: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onError(); }
  render() { return this.state.failed ? null : this.props.children; }
}

type ViewerControls = { zoomIn: () => void; zoomOut: () => void; reset: () => void; front: () => void; side: () => void; top: () => void };

function applyOpacity(object: Object3D, opacity: number) {
  object.traverse((node) => {
    const mesh = node as Group & { material?: unknown };
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    materials.forEach((material: any) => {
      if (!material) return;
      const baseOpacity = material.userData.__structuraBaseOpacity ?? material.opacity ?? 1;
      material.userData.__structuraBaseOpacity = baseOpacity;
      material.opacity = baseOpacity * opacity;
      material.transparent = material.opacity < 1 || material.transparent;
      material.depthWrite = material.opacity >= 1;
      material.needsUpdate = true;
    });
  });
}

function cloneMaterials(object: Object3D) {
  object.traverse((node) => {
    const mesh = node as Group & { material?: unknown };
    if (!mesh.material) return;
    mesh.material = Array.isArray(mesh.material) ? mesh.material.map((material: any) => material?.clone?.() ?? material) : (mesh.material as any).clone?.() ?? mesh.material;
  });
}

function applyTransform(object: Object3D, layer: ViewerModelLayer) {
  const transform = layer.transform;
  object.position.set(transform?.position.x ?? 0, transform?.position.y ?? 0, transform?.position.z ?? 0);
  object.rotation.set(transform?.rotation?.x ?? 0, transform?.rotation?.y ?? 0, transform?.rotation?.z ?? 0);
  object.scale.setScalar(transform?.scale ?? 1);
  object.updateMatrixWorld(true);
}

function Model({ layer, projectId, onState, onFit, onObject, onLayerCenter }: { layer: ViewerModelLayer; projectId: string; onState: (state: "ready" | "error") => void; onFit: (bounds: Box3) => void; onObject: (id: string, object: Object3D | null) => void; onLayerCenter?: (id: string, center: ViewerLayerCenter) => void }) {
  const [object, setObject] = useState<Object3D | null>(null);
  const objectRef = useRef<Object3D | null>(null);
  useEffect(() => {
    let active = true;
    const artifact = layer.artifact;
    const format = (artifact.format ?? artifact.fileName.split(".").pop())?.toLowerCase();
    const objPath = artifactRelativePath(artifact, artifact.bundle?.mainObjPath) ?? artifact.fileName;
    const glbPath = artifactRelativePath(artifact, (artifact.bundle as { mainGlbPath?: string } | undefined)?.mainGlbPath) ?? artifact.fileName;
    const mtlPath = artifactRelativePath(artifact, artifact.bundle?.mtlPath);
    const base = `${API_BASE}/projects/${encodeURIComponent(projectId)}/model-artifacts/${encodeURIComponent(artifact.artifactId)}/viewer-files/`;
    const finish = (loaded: Object3D) => {
      if (!active) { disposeObject(loaded); return; }
      cloneMaterials(loaded);
      applyOpacity(loaded, layer.opacity);
      applyTransform(loaded, layer);
      const bounds = new Box3().setFromObject(loaded);
      onFit(bounds);
      onLayerCenter?.(layer.id, bounds.getCenter(new Vector3()));
      objectRef.current = loaded; onObject(layer.id, loaded); setObject(loaded); onState("ready");
    };
    const loadObj = (materials?: any) => {
      const loader = new OBJLoader();
      if (materials) loader.setMaterials(materials);
      loader.load(`${base}${objPath.split("/").map(encodeURIComponent).join("/")}`, finish, undefined, () => active && onState("error"));
    };
    const directUrl = layer.url.startsWith("http") ? layer.url : `${API_BASE}${layer.url}`;
    if (format === "glb" || format === "gltf") new GLTFLoader().load(layer.url ? directUrl : `${base}${glbPath.split("/").map(encodeURIComponent).join("/")}`, (gltf) => finish(gltf.scene), undefined, () => active && onState("error"));
    else if (!mtlPath) loadObj();
    else {
      const materials = new MTLLoader();
      materials.setResourcePath(base + mtlPath.split("/").slice(0, -1).map(encodeURIComponent).join("/") + "/");
      materials.load(`${base}${mtlPath.split("/").map(encodeURIComponent).join("/")}`, (loaded) => { loaded.preload(); loadObj(loaded); }, undefined, () => loadObj());
    }
    return () => { active = false; onObject(layer.id, null); if (objectRef.current) disposeObject(objectRef.current); objectRef.current = null; };
  }, [layer.artifact, layer.id, layer.url, onFit, onObject, onState, onLayerCenter, projectId]);
  useEffect(() => { if (object) applyOpacity(object, layer.opacity); }, [layer.opacity, object]);
  useEffect(() => { if (!object) return; applyTransform(object, layer); onLayerCenter?.(layer.id, new Box3().setFromObject(object).getCenter(new Vector3())); }, [layer.id, layer.transform, object, onLayerCenter]);
  return object ? <primitive object={object} dispose={null} /> : null;
}

function ViewerScene({ layers, projectId, onState, onControls, fitRequest, onLayerCenter }: { layers: ViewerModelLayer[]; projectId: string; onState: (state: "ready" | "error") => void; onControls: (controls: ViewerControls) => void; fitRequest?: number; onLayerCenter?: (id: string, center: ViewerLayerCenter) => void }) {
  const { camera } = useThree();
  const controlsRef = useRef<any>(null);
  const initialPosition = useRef<Vector3 | null>(null);
  const target = useRef(new Vector3(0, 0, 0));
  const applyZoom = useCallback((scale: number) => {
    const next = camera.position.clone().sub(target.current).multiplyScalar(scale);
    const minDistance = Math.max(camera.near * 20, 0.01);
    const maxDistance = Math.max(camera.near * 25, camera.far * 0.35);
    const length = Math.max(minDistance, Math.min(maxDistance, next.length()));
    next.setLength(length).add(target.current);
    camera.position.copy(next);
    camera.updateProjectionMatrix();
    controlsRef.current?.update?.();
  }, [camera]);
  const setView = useCallback((axis: "front" | "side" | "top") => {
    const currentDistance = Math.max(camera.position.clone().sub(target.current).length(), initialPosition.current?.length() ?? 1);
    const distance = currentDistance || 1;
    const position = axis === "front"
      ? new Vector3(0, distance * 0.18, distance)
      : axis === "side"
        ? new Vector3(distance, distance * 0.18, 0)
        : new Vector3(0, distance, 0.001);
    camera.position.copy(position.add(target.current));
    controlsRef.current?.target?.copy?.(target.current);
    camera.updateProjectionMatrix();
    controlsRef.current?.update?.();
  }, [camera]);
  const reset = useCallback(() => {
    if (!initialPosition.current) return;
    camera.position.copy(initialPosition.current);
    controlsRef.current?.target?.copy?.(target.current);
    camera.updateProjectionMatrix();
    controlsRef.current?.update?.();
  }, [camera]);
  useEffect(() => {
    onControls({ zoomIn: () => applyZoom(0.82), zoomOut: () => applyZoom(1.22), reset, front: () => setView("front"), side: () => setView("side"), top: () => setView("top") });
  }, [applyZoom, onControls, reset, setView]);
  const combinedBounds = useRef<Box3 | null>(null);
  const objects = useRef(new Map<string, Object3D>());
  const onObject = useCallback((id: string, object: Object3D | null) => { if (object) objects.current.set(id, object); else objects.current.delete(id); }, []);
  const handleFit = useCallback((bounds: Box3) => {
    combinedBounds.current = combinedBounds.current ? combinedBounds.current.union(bounds) : bounds.clone();
    const center = combinedBounds.current.getCenter(new Vector3());
    const size = combinedBounds.current.getSize(new Vector3()).length() || 1;
    target.current.copy(center);
    camera.position.set(center.x + size * 0.8, center.y + size * 0.55, center.z + size * 0.8);
    camera.near = Math.max(0.001, size / 10000); camera.far = size * 100; camera.updateProjectionMatrix();
    initialPosition.current = camera.position.clone();
    controlsRef.current?.target?.copy?.(center);
    controlsRef.current?.update?.();
  }, [camera]);
  useEffect(() => {
    if (!fitRequest) return;
    const visibleObjects = layers.filter((layer) => layer.visible).map((layer) => objects.current.get(layer.id)).filter(Boolean) as Object3D[];
    if (!visibleObjects.length) return;
    const bounds = visibleObjects.reduce((combined, object) => combined.union(new Box3().setFromObject(object)), new Box3());
    combinedBounds.current = null;
    handleFit(bounds);
  }, [fitRequest, handleFit]);
  return <><color attach="background" args={["#020617"]} /><ambientLight intensity={1.05} /><hemisphereLight args={["#e0f2fe", "#1e293b", 0.9]} /><directionalLight position={[4, 5, 7]} intensity={2.2} /><directionalLight position={[-5, 3, -4]} intensity={1.1} />{layers.filter((layer) => layer.visible).map((layer) => <Model key={layer.id} layer={layer} projectId={projectId} onState={onState} onFit={handleFit} onObject={onObject} onLayerCenter={onLayerCenter} />)}<OrbitControls ref={controlsRef} enableDamping makeDefault /></>;
}

function previewEligibility(artifact: ModelArtifact) {
  const format = (artifact.format ?? artifact.bundle?.mainObjPath?.split(".").pop() ?? artifact.fileName.split(".").pop())?.toLowerCase();
  if ((format === "glb" || format === "gltf") && artifact.fileSize <= MAX_DIRECT_GLB_BYTES) return null;
  if (format === "glb" || format === "gltf") return "Preview requires a smaller viewer-ready optimized model.";
  if (format !== "obj") return "Preview requires a viewer-ready optimized model.";
  if (!artifact.fileSize || artifact.fileSize > MAX_DIRECT_OBJ_BYTES) return "Preview requires a viewer-ready optimized model.";
  if ((artifact.bundle?.textureCount ?? 0) > MAX_DIRECT_TEXTURE_COUNT) return "Preview requires a viewer-ready optimized model.";
  return null;
}

export function RealityScanModelViewer({ artifact, projectId, layers, fitRequest, onLayerCenter }: { artifact?: ModelArtifact; projectId: string; layers?: ViewerModelLayer[]; fitRequest?: number; onLayerCenter?: (id: string, center: ViewerLayerCenter) => void }) {
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const controls = useRef<ViewerControls | null>(null);
  const effectiveLayers = layers ?? (artifact ? [{ id: artifact.artifactId, url: "", label: artifact.fileName, role: "current" as const, visible: true, opacity: 1, artifact }] : []);
  const warning = effectiveLayers.map((layer) => previewEligibility(layer.artifact)).find(Boolean);
  const handleModelState = useCallback((next: "ready" | "error") => setState(next === "ready" ? "ready" : "error"), []);
  const handleControls = useCallback((next: ViewerControls) => { controls.current = next; }, []);
  const failed = state === "error";
  if (!effectiveLayers.some((layer) => layer.visible)) return <div className="rounded-lg border border-white/10 bg-slate-950 p-5 text-sm text-slate-300">Both compare layers are hidden. Enable Current Model or Target Model to continue.</div>;
  if (warning) return <div className="rounded-lg border border-amber-300/20 bg-amber-300/10 p-5 text-sm text-amber-100">{warning}</div>;
  if (failed) return <div className="rounded-lg border border-amber-300/20 bg-amber-300/10 p-5 text-sm text-amber-100">Preview unavailable for this artifact.</div>;
  return <div className="relative h-[540px] overflow-hidden rounded-lg border border-white/10 bg-slate-950">{state === "loading" && <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/80 text-sm text-slate-200">Loading preview...</div>}<div className="absolute left-4 top-4 z-20 flex flex-wrap items-center gap-2 rounded-lg border border-white/10 bg-slate-950/85 p-2 shadow-lg backdrop-blur"><button type="button" onClick={() => controls.current?.zoomIn()} className="h-8 w-8 rounded bg-white/10 text-sm font-semibold text-white hover:bg-white/20" aria-label="Zoom in">+</button><button type="button" onClick={() => controls.current?.zoomOut()} className="h-8 w-8 rounded bg-white/10 text-sm font-semibold text-white hover:bg-white/20" aria-label="Zoom out">-</button><button type="button" onClick={() => controls.current?.front()} className="rounded bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20">Front</button><button type="button" onClick={() => controls.current?.side()} className="rounded bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20">Side</button><button type="button" onClick={() => controls.current?.top()} className="rounded bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20">Top</button><button type="button" onClick={() => controls.current?.reset()} className="rounded bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20">Reset</button><span className="hidden text-xs text-slate-300 lg:inline">Drag to rotate - Scroll or use +/- to zoom</span></div><PreviewErrorBoundary onError={() => setState("error")}><Canvas camera={{ position: [2.2, 1.4, 3.4], fov: 38 }} onCreated={({ gl }) => gl.domElement.addEventListener("webglcontextlost", () => setState("error"), { once: true })}><ViewerScene layers={effectiveLayers} projectId={projectId} onState={handleModelState} onControls={handleControls} fitRequest={fitRequest} onLayerCenter={onLayerCenter} /></Canvas></PreviewErrorBoundary></div>;
}
