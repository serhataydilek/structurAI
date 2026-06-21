"""Deterministic post-processing boundary for RealityScan meshes.

Raw RealityScan exports are never modified. Future jobs must write a separate
derived artifact with artifactRole `cleaned_mesh` or `viewer_ready` and link its
sourceArtifactId. Planned operations are: isolated-component removal, largest
component preservation, optional bounds cleanup/repair/decimation, and OBJ→GLB.
AI geometry completion is intentionally out of scope; any future inferred
geometry must be labelled AI-inferred rather than factual reconstruction.
"""

from app.repositories import model_artifact_repository

PLANNED_OPERATIONS = ("remove_small_components", "preserve_largest_components", "bounding_box_cleanup", "mesh_repair", "decimation", "obj_to_glb")


def plan(source_artifact: dict) -> dict:
    """Return an explicit, non-mutating plan until deterministic tooling is configured."""
    return {"sourceArtifactId": source_artifact["artifactId"], "mutatesRaw": False, "operations": PLANNED_OPERATIONS,
            "outputRoles": ("cleaned_mesh", "viewer_ready"), "status": "tooling_not_configured"}


def register_derived_artifact(project_id: str, source_artifact: dict, **kwargs) -> dict:
    """Register a separately-written output; callers must never reuse raw storage paths."""
    if kwargs.get("storage_path") == source_artifact["storagePath"]:
        raise ValueError("Derived artifact must not overwrite the raw artifact path")
    metadata = {**kwargs.pop("metadata", {}), "sourceArtifactId": source_artifact["artifactId"]}
    return model_artifact_repository.add_artifact(project_id, metadata=metadata, **kwargs)
