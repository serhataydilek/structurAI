from datetime import datetime, timezone
import json
from uuid import uuid4
from app.database import get_connection

def _now(): return datetime.now(timezone.utc).isoformat()
def _job(row):
    item=dict(row); item["errors"]=json.loads(item.pop("errors_json") or "[]")
    return {"jobId":item.pop("job_id"),"projectId":item.pop("project_id"),"engine":item.pop("engine"),"status":item.pop("status"),"inputImageFolder":item.pop("input_image_folder"),"outputFolder":item.pop("output_folder"),"commandFilePath":item.pop("command_file_path"),"commandUsed":item.pop("command_used"),"logPath":item.pop("log_path"),"logTail":item.pop("log_tail"),"startedAt":item.pop("started_at"),"finishedAt":item.pop("finished_at"),"durationSeconds":item.pop("duration_seconds"),"producedArtifactId":item.pop("produced_artifact_id"),"notes":item.pop("notes"),"errors":item.pop("errors"),"createdAt":item.pop("created_at"),"updatedAt":item.pop("updated_at")}
def create(project_id, engine, status, input_folder, output_folder, command_file_path, log_path, notes, errors):
    job_id, now=str(uuid4()),_now()
    with get_connection() as conn:
        conn.execute("""INSERT INTO photogrammetry_jobs (job_id,project_id,engine,status,input_image_folder,output_folder,command_file_path,log_path,notes,errors_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",(job_id,project_id,engine,status,input_folder,output_folder,command_file_path,log_path,notes,json.dumps(errors),now,now))
        return _job(conn.execute("SELECT * FROM photogrammetry_jobs WHERE job_id=?",(job_id,)).fetchone())
def list_jobs(project_id):
    with get_connection() as conn: rows=conn.execute("SELECT * FROM photogrammetry_jobs WHERE project_id=? ORDER BY created_at DESC",(project_id,)).fetchall()
    return [_job(row) for row in rows]
