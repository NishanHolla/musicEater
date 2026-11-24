from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4


_jobs = {}
_lock = Lock()


def create_job(tenant, source):
    job_id = str(uuid4())
    with _lock:
        _jobs[job_id] = {
            "id": job_id,
            "tenant": tenant,
            "source": source,
            "state": "queued",
            "message": "Waiting to start",
            "total": 0,
            "completed": 0,
            "skipped": 0,
            "failed": 0,
            "cancel_requested": False,
            "process": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    return job_id


def update_job(job_id, **changes):
    with _lock:
        job = _jobs.get(job_id)
        if job:
            job.update(changes)


def increment_job(job_id, field):
    with _lock:
        job = _jobs.get(job_id)
        if job:
            job[field] += 1


def attach_process(job_id, process):
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return False
        job["process"] = process
        cancel_requested = job["cancel_requested"]
    if cancel_requested and process.poll() is None:
        process.terminate()
    return True


def is_cancel_requested(job_id):
    with _lock:
        job = _jobs.get(job_id)
        return bool(job and job["cancel_requested"])


def cancel_job(job_id, tenant):
    with _lock:
        job = _jobs.get(job_id)
        if not job or job["tenant"] != tenant or job["state"] not in {"queued", "running"}:
            return False
        job["cancel_requested"] = True
        job["state"] = "canceled"
        job["message"] = "Import canceled"
        process = job["process"]
    if process and process.poll() is None:
        process.terminate()
    return True


def get_jobs(tenant):
    with _lock:
        jobs = [
            {key: value for key, value in job.items() if key not in {"tenant", "process", "cancel_requested"}}
            for job in _jobs.values()
            if job["tenant"] == tenant
        ]
    return sorted(jobs, key=lambda job: job["created_at"], reverse=True)[:20]
