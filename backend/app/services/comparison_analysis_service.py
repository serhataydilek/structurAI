def metadata_analysis(reference: dict, current: dict, externally_aligned: bool = False) -> dict:
    ref, cur = reference.get("stats") or {}, current.get("stats") or {}
    warnings=[]; ref_bounds=ref.get("boundingBox"); cur_bounds=cur.get("boundingBox")
    if not ref_bounds or not cur_bounds: warnings.append("Bounding box metadata is missing for one or both artifacts.")
    if not ref.get("vertexCount") or not cur.get("vertexCount"): warnings.append("Vertex count metadata is missing for one or both artifacts.")
    delta=None; scale_warning=None
    if ref_bounds and cur_bounds:
        size=lambda b:[b["max"][axis]-b["min"][axis] for axis in ("x","y","z")]
        rs,cs=size(ref_bounds),size(cur_bounds)
        ratios=[c/r for r,c in zip(rs,cs) if abs(r)>1e-9]
        delta={"referenceSize":dict(zip(("x","y","z"),rs)),"currentSize":dict(zip(("x","y","z"),cs)),"scaleRatios":ratios}
        if ratios and (max(ratios)>1.5 or min(ratios)<0.67): scale_warning="Rough bounding-box scale mismatch detected; align and confirm units externally."
    ready=bool(externally_aligned and ref_bounds and cur_bounds and ref.get("vertexCount") and cur.get("vertexCount"))
    return {"analysisStatus":"ready_for_distance_analysis" if ready else "requires_alignment", "analysisReady":False, "analysisSummary":{"referenceVertexCount":ref.get("vertexCount"),"currentVertexCount":cur.get("vertexCount"),"referenceFaceCount":ref.get("faceCount"),"currentFaceCount":cur.get("faceCount")}, "warnings":warnings, "referenceBounds":ref_bounds,"currentBounds":cur_bounds,"roughBoundsDelta":delta,"scaleMismatchWarning":scale_warning,"noProgressPercentageReason":"Progress percentage requires aligned reference/current models and distance/zone analysis."}
