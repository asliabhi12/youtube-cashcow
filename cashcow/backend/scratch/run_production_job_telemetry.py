"""Execute a real production workflow job and print empirical stage timings & telemetry."""

import json
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.jobs import job_store
from app.services.workflow import _execute, _build_workflow, _settings_for_quality

def run_real_job():
    print("=== STARTING REAL PRODUCTION JOB EXECUTION ===")
    test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    job = job_store.create(
        url=test_url,
        profile_id="vertical_shorts",
        export_quality="balanced",
        title_seed="Real Production Workflow Telemetry Run",
    )
    print(f"Created Job #{job.id[:8]} (ID: {job.id})")

    workflow = _build_workflow(job.id, test_url, trim=None, profile_id="vertical_shorts")
    settings = _settings_for_quality("balanced")

    start_time = time.monotonic()
    print("Executing workflow engine pipeline...")
    _execute(job.id, workflow, settings)
    elapsed = time.monotonic() - start_time
    print(f"=== WORKFLOW EXECUTION FINISHED in {elapsed:.2f}s ===")

    completed_job = job_store.get(job.id)
    print("\n=======================================================")
    print("      REAL PRODUCTION JOB TELEMETRY REPORT             ")
    print("=======================================================")
    print(f"Job ID:               {completed_job.id}")
    print(f"Status:               {completed_job.status}")
    print(f"Output File:          {completed_job.output_file}")
    print(f"Output Name:          {completed_job.output_name}")
    print(f"Total Duration:       {completed_job.performance.total_duration_seconds if completed_job.performance else elapsed:.2f}s")
    print("-------------------------------------------------------")
    print("STAGE TIMINGS:")
    if completed_job.performance and completed_job.performance.stages:
        for stage in completed_job.performance.stages:
            print(f"  - {stage.stage:<24}: {stage.duration:6.2f}s")
    else:
        print("  (No stage timing captured)")
    
    print("-------------------------------------------------------")
    print("RESOURCE & HARDWARE METRICS:")
    if completed_job.performance and completed_job.performance.metrics:
        m = completed_job.performance.metrics
        print(f"  Input Resolution:   {m.input_resolution}")
        print(f"  Output Resolution:  {m.output_resolution}")
        print(f"  Video Duration:     {m.video_duration}s")
        print(f"  Encoder:            {m.encoder}")
        print(f"  HW Acceleration:    {m.hardware_acceleration}")
        print(f"  Average FPS:        {m.average_fps} FPS")
        print(f"  CPU Usage:          {m.cpu_usage_percent}%")
        print(f"  GPU Usage:          {m.gpu_usage_percent}%")
        print(f"  RAM Usage:          {m.memory_mb} MB")
        print(f"  Disk I/O:           {m.disk_io_mb} MB")
    print("=======================================================")

if __name__ == "__main__":
    run_real_job()
