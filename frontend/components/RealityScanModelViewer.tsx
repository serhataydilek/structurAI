"use client";

import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { MTLLoader } from "three/examples/jsm/loaders/MTLLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { Box3, Group, Vector3 } from "three";
import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";
import type { ModelArtifact } from "@/lib/types";

function artifactRelativePath(artifact: ModelArtifact, source: string | null | undefined) {
  if (!source) return null;
  const normalized = source.replaceAll("\\", "/");
  const root = artifact.bundle?.bundleRootPath?.replaceAll("\\", "/").replace(/\/$/, "");
  return root && normalized.startsWith(`${root}/`) ? normalized.slice(root.length + 1) : normalized.split("/").pop() ?? null;
}

function Model({ artifact, projectId, onError }: { artifact: ModelArtifact; projectId: string; onError: (message: string) => void }) {
  const [object, setObject] = useState<Group | null>(null);
  const { camera } = useThree();
  useEffect(() => {
    let active = true;
    const objPath = artifactRelativePath(artifact, artifact.bundle?.mainObjPath) ?? artifact.fileName;
    const mtlPath = artifactRelativePath(artifact, artifact.bundle?.mtlPath);
    const base = `${API_BASE}/projects/${encodeURIComponent(projectId)}/model-artifacts/${encodeURIComponent(artifact.artifactId)}/viewer-files/`;
    const loadObj = (materials?: any) => {
      const loader = new OBJLoader();
      if (materials) loader.setMaterials(materials);
      loader.load(`${base}${objPath.split("/").map(encodeURIComponent).join("/")}`, (loaded) => {
        if (!active) return;
        const bounds = new Box3().setFromObject(loaded);
        const center = bounds.getCenter(new Vector3());
        const size = bounds.getSize(new Vector3()).length() || 1;
        loaded.position.sub(center);
        camera.position.set(size * 0.8, size * 0.55, size * 0.8);
        camera.near = Math.max(0.001, size / 10000); camera.far = size * 100; camera.updateProjectionMatrix();
        setObject(loaded);
      }, undefined, () => active && onError("The OBJ file could not be loaded from this artifact bundle."));
    };
    if (!mtlPath) { loadObj(); return () => { active = false; }; }
    const materials = new MTLLoader();
    materials.setResourcePath(base + mtlPath.split("/").slice(0, -1).map(encodeURIComponent).join("/") + "/");
    materials.load(`${base}${mtlPath.split("/").map(encodeURIComponent).join("/")}`, (loaded) => { loaded.preload(); loadObj(loaded); }, undefined, () => loadObj());
    return () => { active = false; };
  }, [artifact, camera, onError, projectId]);
  return object ? <primitive object={object} /> : null;
}

export function RealityScanModelViewer({ artifact, projectId }: { artifact: ModelArtifact; projectId: string }) {
  const [error, setError] = useState("");
  const renderable = (artifact.format ?? artifact.bundle?.mainObjPath?.split(".").pop() ?? artifact.fileName.split(".").pop())?.toLowerCase() === "obj";
  if (!renderable) return <p className="text-sm text-slate-400">Preview is being prepared for this artifact.</p>;
  return <div className="h-[540px] overflow-hidden rounded-lg border border-white/10 bg-slate-950">{error ? <div className="flex h-full items-center justify-center p-8 text-center text-sm text-amber-100">{error} Download the artifact to inspect its files.</div> : <Canvas camera={{ position: [3, 2, 3], fov: 42 }}><color attach="background" args={["#020617"]} /><ambientLight intensity={0.7} /><directionalLight position={[5, 8, 5]} intensity={2} /><directionalLight position={[-4, 2, -3]} intensity={0.7} /><Model artifact={artifact} projectId={projectId} onError={setError} /><OrbitControls enableDamping makeDefault /></Canvas>}</div>;
}
