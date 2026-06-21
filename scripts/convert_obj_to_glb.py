"""Run under Blender: import a managed OBJ and export a viewer-ready GLB.

The script is deterministic and conservative:
- raw OBJ/MTL/textures are never modified
- missing geometry is never generated
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector


def _mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def _polygon_count(objects: list[bpy.types.Object]) -> int:
    return sum(len(obj.data.polygons) for obj in objects if obj.type == "MESH")


def _texture_count(objects: list[bpy.types.Object]) -> int:
    texture_paths: set[str] = set()
    for obj in objects:
        for slot in obj.material_slots:
            material = slot.material
            if not material or not material.use_nodes or not material.node_tree:
                continue
            for node in material.node_tree.nodes:
                image = getattr(node, "image", None)
                if image:
                    texture_paths.add(image.filepath or image.name)
    return len(texture_paths)


def _int(value: Any, default: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _load_options(raw: str | None) -> dict[str, int]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        parsed = {}
    return {"target_faces": _int(parsed.get("target_faces"), 300_000)}


def _scene_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector, float]:
    corners = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    if not corners:
        return Vector(), Vector(), 1.0
    low = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
    high = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
    return low, high, (high - low).length or 1.0


def _recalculate_normals(objects: list[bpy.types.Object]) -> None:
    for obj in objects:
        if obj.type != "MESH" or not obj.data.polygons:
            continue
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")


def _center_scene(objects: list[bpy.types.Object]) -> None:
    low, high, _diag = _scene_bounds(objects)
    center = (low + high) / 2
    for obj in objects:
        obj.location -= center


def _decimate(objects: list[bpy.types.Object], target_faces: int, warnings: list[str]) -> bool:
    polygons_before = _polygon_count(objects)
    if target_faces <= 0 or polygons_before <= target_faces:
        return False
    ratio = max(0.001, min(1.0, target_faces / max(polygons_before, 1)))
    for obj in objects:
        if obj.type != "MESH" or not obj.data.polygons:
            continue
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        modifier = obj.modifiers.new("StructuraViewerDecimate", "DECIMATE")
        modifier.ratio = ratio
        modifier.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    warnings.append(f"Decimated mesh from {polygons_before} polygons toward {target_faces} polygons.")
    return True


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:]
    source, output, report = map(Path, args[:3])
    options = _load_options(args[3] if len(args) > 3 else None)
    warnings: list[str] = []

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.wm.obj_import(filepath=str(source))
    objects = _mesh_objects()
    polygons_before = _polygon_count(objects)
    texture_count = _texture_count(objects)
    if texture_count == 0:
        warnings.append("No image textures detected in imported materials.")

    _recalculate_normals(objects)
    _center_scene(objects)
    decimation_applied = _decimate(objects, options["target_faces"], warnings)
    objects = _mesh_objects()
    _recalculate_normals(objects)
    objects = _mesh_objects()
    polygon_count = _polygon_count(objects)

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB", export_materials="EXPORT", export_apply=True)
    output_size = output.stat().st_size if output.is_file() else None
    report.write_text(json.dumps({
        "input_obj": str(source),
        "output_glb": str(output),
        "object_count": len(objects),
        "polygon_count": polygon_count,
        "polygon_count_before": polygons_before,
        "polygons_before": polygons_before,
        "polygons_after_decimation": polygon_count,
        "decimation_applied": decimation_applied,
        "target_faces": options["target_faces"],
        "output_glb_size_bytes": output_size,
        "texture_count": texture_count,
        "warnings": warnings,
    }, indent=2))


if __name__ == "__main__":
    main()
