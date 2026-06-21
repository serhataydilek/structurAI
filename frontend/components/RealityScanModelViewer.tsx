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

function Model({ artifact, projectId, onState, onFit }: { artifact: ModelArtifact; projectId: string; onState: (state: "ready" | "error") => void; onFit: (position: Vector3) => void }) {
  const [object, setObject] = useState<Object3D | null>(null);
  const objectRef = useRef<Object3D | null>(null);
  const { camera } = useThree();
  useEffect(() => {
    let active = true;
    const format = (artifact.format ?? artifact.fileName.split(".").pop())?.toLowerCase();
    const objPath = artifactRelativePath(artifact, artifact.bundle?.mainObjPath) ?? artifact.fileName;
    const glbPath = artifactRelativePath(artifact, (artifact.bundle as { mainGlbPath?: string } | undefined)?.mainGlbPath) ?? artifact.fileName;
    const mtlPath = artifactRelativePath(artifact, artifact.bundle?.mtlPath);
    const base = `${API_BASE}/projects/${encodeURIComponent(projectId)}/model-artifacts/${encodeURIComponent(artifact.artifactId)}/viewer-files/`;
    const finish = (loaded: Object3D) => {
      if (!active) { disposeObject(loaded); return; }
      const bounds = new Box3().setFromObject(loaded);
      const center = bounds.getCenter(new Vector3());
      const size = bounds.getSize(new Vector3()).length() || 1;
      loaded.position.sub(center);
      camera.position.set(size * 0.8, size * 0.55, size * 0.8);
      camera.near = Math.max(0.001, size / 10000); camera.far = size * 100; camera.updateProjectionMatrix();
      onFit(camera.position.clone());
      objectRef.current = loaded; setObject(loaded); onState("ready");
    };
    const loadObj = (materials?: any) => {
      const loader = new OBJLoader();
      if (materials) loader.setMaterials(materials);
      loader.load(`${base}${objPath.split("/").map(encodeURIComponent).join("/")}`, finish, undefined, () => active && onState("error"));
    };
    if (format === "glb" || format === "gltf") new GLTFLoader().load(`${base}${glbPath.split("/").map(encodeURIComponent).join("/")}`, (gltf) => finish(gltf.scene), undefined, () => active && onState("error"));
    else if (!mtlPath) loadObj();
    else {
      const materials = new MTLLoader();
      materials.setResourcePath(base + mtlPath.split("/").slice(0, -1).map(encodeURIComponent).join("/") + "/");
      materials.load(`${base}${mtlPath.split("/").map(encodeURIComponent).join("/")}`, (loaded) => { loaded.preload(); loadObj(loaded); }, undefined, () => loadObj());
    }
    return () => { active = false; if (objectRef.current) disposeObject(objectRef.current); objectRef.current = null; };
  }, [artifact, camera, onFit, onState, projectId]);
  return object ? <primitive object={object} dispose={null} /> : null;
}

function ViewerScene({ artifact, projectId, onState, onControls }: { artifact: ModelArtifact; projectId: string; onState: (state: "ready" | "error") => void; onControls: (controls: ViewerControls) => void }) {
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
  const handleFit = useCallback((position: Vector3) => {
    initialPosition.current = position.clone();
    controlsRef.current?.target?.copy?.(target.current);
    controlsRef.current?.update?.();
  }, []);
  return <><color attach="background" args={["#020617"]} /><ambientLight intensity={1.05} /><hemisphereLight args={["#e0f2fe", "#1e293b", 0.9]} /><directionalLight position={[4, 5, 7]} intensity={2.2} /><directionalLight position={[-5, 3, -4]} intensity={1.1} /><Model artifact={artifact} projectId={projectId} onState={onState} onFit={handleFit} /><OrbitControls ref={controlsRef} enableDamping makeDefault /></>;
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

export function RealityScanModelViewer({ artifact, projectId }: { artifact: ModelArtifact; projectId: string }) {
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const controls = useRef<ViewerControls | null>(null);
  const warning = previewEligibility(artifact);
  const handleModelState = useCallback((next: "ready" | "error") => setState(next === "ready" ? "ready" : "error"), []);
  const handleControls = useCallback((next: ViewerControls) => { controls.current = next; }, []);
  const failed = state === "error";
  if (warning) return <div className="rounded-lg border border-amber-300/20 bg-amber-300/10 p-5 text-sm text-amber-100">{warning}</div>;
  if (failed) return <div className="rounded-lg border border-amber-300/20 bg-amber-300/10 p-5 text-sm text-amber-100">Preview unavailable for this artifact.</div>;
  return <div className="relative h-[540px] overflow-hidden rounded-lg border border-white/10 bg-slate-950">{state === "loading" && <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/80 text-sm text-slate-200">Loading preview...</div>}<div className="absolute left-4 top-4 z-20 flex flex-wrap items-center gap-2 rounded-lg border border-white/10 bg-slate-950/85 p-2 shadow-lg backdrop-blur"><button type="button" onClick={() => controls.current?.zoomIn()} className="h-8 w-8 rounded bg-white/10 text-sm font-semibold text-white hover:bg-white/20" aria-label="Zoom in">+</button><button type="button" onClick={() => controls.current?.zoomOut()} className="h-8 w-8 rounded bg-white/10 text-sm font-semibold text-white hover:bg-white/20" aria-label="Zoom out">-</button><button type="button" onClick={() => controls.current?.front()} className="rounded bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20">Front</button><button type="button" onClick={() => controls.current?.side()} className="rounded bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20">Side</button><button type="button" onClick={() => controls.current?.top()} className="rounded bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20">Top</button><button type="button" onClick={() => controls.current?.reset()} className="rounded bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20">Reset</button><span className="hidden text-xs text-slate-300 lg:inline">Drag to rotate - Scroll or use +/- to zoom</span></div><PreviewErrorBoundary onError={() => setState("error")}><Canvas camera={{ position: [2.2, 1.4, 3.4], fov: 38 }} onCreated={({ gl }) => gl.domElement.addEventListener("webglcontextlost", () => setState("error"), { once: true })}><ViewerScene artifact={artifact} projectId={projectId} onState={handleModelState} onControls={handleControls} /></Canvas></PreviewErrorBoundary></div>;
}
