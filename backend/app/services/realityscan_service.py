from pathlib import Path
import os, shutil, subprocess
from app.database import PROCESSED_DIR
from app.repositories import photogrammetry_job_repository
from app.services import job_progress_service

COMMON_PATHS = [Path(r"C:\Program Files\Epic Games\RealityScan_2.1\RealityScan.exe"), Path(r"C:\Program Files\Epic Games\RealityScan\RealityScan.exe"), Path(r"C:\Program Files\Capturing Reality\RealityCapture\RealityCapture.exe"), Path(r"C:\Program Files\RealityScan\RealityScan.exe")]
JOB_KEY = "realityscan_prepare"
def diagnostics() -> dict:
    errors=[]; exe=None; source="not found"
    configured=os.getenv("REALITYSCAN_EXE")
    if configured and Path(configured).is_file(): exe,source=Path(configured),"env var"
    elif shutil.which("RealityScan.exe") or shutil.which("RealityCapture.exe"): exe,source=Path(shutil.which("RealityScan.exe") or shutil.which("RealityCapture.exe")),"PATH"
    else:
        exe=next((path for path in COMMON_PATHS if path.is_file()),None); source="common install path" if exe else "not found"
    version=None
    if exe:
        try: version=subprocess.run([str(exe),"--help"],capture_output=True,text=True,timeout=8).stdout[-2000:] or None
        except Exception as exc: errors.append(f"Unable to inspect CLI help: {exc}")
    return {"realityScanAvailable":bool(exe),"resolvedRealityScanExe":str(exe) if exe else None,"source":source,"versionHelpOutput":version,"supportsHeadless":"unknown","supportsCommandFile":"unknown","outputWriteable":os.access(PROCESSED_DIR,os.W_OK),"errors":errors}
def prepare(project_id: str) -> dict:
    frames=PROCESSED_DIR/project_id/"frames"; images=[p for p in frames.glob("*") if p.suffix.lower() in {".jpg",".jpeg",".png",".tif",".tiff"}] if frames.is_dir() else []
    if len(images)<3: raise ValueError("At least three prepared images are required for a RealityScan job")
    job_progress_service.start(project_id, JOB_KEY, "copying_images", f"Copying RealityScan image set: 0/{len(images)}", total_items=len(images), progress_percent=5)
    job_root=PROCESSED_DIR/project_id/"realityscan_jobs"; temp_id=__import__("uuid").uuid4().hex
    root=job_root/temp_id; input_dir=root/"input"; output=root/"output"; logs=root/"logs"
    for directory in (input_dir,output,logs): directory.mkdir(parents=True,exist_ok=True)
    try:
        for index,image in enumerate(images, start=1):
            shutil.copy2(image, input_dir / image.name)
            job_progress_service.update(project_id, JOB_KEY, label=f"Copied image {index}/{len(images)}", progress_percent=5 + index / max(len(images),1) * 75, processed_items=index, total_items=len(images))
        job_progress_service.update(project_id, JOB_KEY, stage="writing_command_draft", label="Writing RealityScan manual workflow draft", progress_percent=90, processed_items=None, total_items=None)
        command=root/"realityscan_command_draft.txt"; diag=diagnostics()
        command.write_text("RealityScan automation draft\nInput folder: %s\nOutput folder: %s\nTODO: verify this RealityScan version's command-file/headless syntax before executing.\nManual bridge: import images, align, build model, texture, export OBJ + MTL + textures as ZIP.\n"%(input_dir,output),encoding="utf-8")
        status="pending" if diag["realityScanAvailable"] else "waiting_for_manual_steps"
        job=photogrammetry_job_repository.create(project_id,"realityscan",status,str(input_dir),str(output),str(command),str(logs/"realityscan.log"),"Manual RealityScan workflow: open app, import prepared frames, align, build model, texture, export OBJ bundle ZIP, import into Model Artifacts.",diag["errors"])
        job_progress_service.complete(project_id, JOB_KEY, f"RealityScan job prepared with {len(images)} images", warnings=diag["errors"])
        return {**job,"imageCount":len(images),"diagnostics":diag,"ready":diag["realityScanAvailable"],"manualRequired":not diag["realityScanAvailable"],"progress":job_progress_service.get(project_id, JOB_KEY)}
    except Exception as exc:
        job_progress_service.fail(project_id, JOB_KEY, str(exc))
        raise
