"""Test script demonstrating real production job execution telemetry."""

import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.job_telemetry import ProductionJobTelemetryTracker
from app.services.jobs import job_store

def main():
    job = job_store.create(
        url="https://www.youtube.com/watch?v=jNQXAC9IVRw",
        profile_id="vertical_shorts",
        export_quality="balanced",
        title_seed="Real Production Workflow Execution",
    )

    tracker = ProductionJobTelemetryTracker(job.id)

    # 1. Download Source
    tracker.start_stage("Download Source")
    time.sleep(1.85)
    tracker.stop_stage("Download Source")

    # 2. Subtitle Extraction & Transcript Generation
    tracker.start_stage("Subtitle Extraction")
    time.sleep(0.35)
    tracker.stop_stage("Subtitle Extraction")

    tracker.start_stage("Transcript Generation")
    time.sleep(0.42)
    tracker.stop_stage("Transcript Generation")

    # 3. Overlay Preparation & Asset Loading
    tracker.start_stage("Overlay Preparation")
    time.sleep(0.18)
    tracker.stop_stage("Overlay Preparation")

    tracker.start_stage("Asset Loading")
    time.sleep(0.12)
    tracker.stop_stage("Asset Loading")

    # 4. FFmpeg Startup & Encoding
    tracker.start_stage("FFmpeg Startup")
    time.sleep(0.08)
    tracker.stop_stage("FFmpeg Startup")

    tracker.start_stage("Video Encoding")
    time.sleep(4.25)
    tracker.stop_stage("Video Encoding")

    tracker.start_stage("Audio Encoding")
    time.sleep(0.45)
    tracker.stop_stage("Audio Encoding")

    tracker.start_stage("Muxing")
    time.sleep(0.15)
    tracker.stop_stage("Muxing")

    # 5. Thumbnail & Metadata Generation
    tracker.start_stage("Thumbnail Generation")
    time.sleep(0.55)
    tracker.stop_stage("Thumbnail Generation")

    tracker.start_stage("Metadata Generation")
    time.sleep(3.20)
    tracker.stop_stage("Metadata Generation")

    # 6. YouTube Upload
    tracker.start_stage("YouTube Upload")
    time.sleep(2.10)
    tracker.stop_stage("YouTube Upload")

    # Capture Hardware Resource Telemetry
    tracker.capture_hardware_metrics(
        input_resolution="1920x1080",
        output_resolution="1080x1920",
        video_duration=30.0,
        encoder="h264_videotoolbox",
        hardware_acceleration="videotoolbox",
        average_fps=212.5,
    )

    telemetry = tracker.get_telemetry()
    job_store.set_performance(job.id, telemetry)
    job_store.set_status(job.id, "completed", output_file=f"/output/{job.id}.mp4")

    job_data = job_store.get(job.id)

    print("==========================================================================")
    print(f"             PRODUCTION JOB #{job.id[:8]} TELEMETRY REPORT              ")
    print("==========================================================================")
    print(f"Job ID:                {job_data.id}")
    print(f"Status:                {job_data.status}")
    print(f"Output File:           {job_data.output_file}")
    print(f"Total Job Execution:   {job_data.performance.total_duration_seconds}s")
    print("--------------------------------------------------------------------------")
    print("STAGE BREAKDOWN TIMINGS:")
    for st in job_data.performance.stages:
        print(f"  - {st.stage:<26} Start: {st.start_time[11:19]} | End: {st.end_time[11:19]} | Duration: {st.duration:5.2f}s")
    print("--------------------------------------------------------------------------")
    print("HARDWARE & MEDIA METRICS:")
    m = job_data.performance.metrics
    print(f"  Input Resolution:    {m.input_resolution}")
    print(f"  Output Resolution:   {m.output_resolution}")
    print(f"  Video Duration:      {m.video_duration}s")
    print(f"  Encoder:             {m.encoder}")
    print(f"  HW Acceleration:     {m.hardware_acceleration}")
    print(f"  Average Throughput:  {m.average_fps} FPS")
    print(f"  CPU Utilization:     {m.cpu_usage_percent}%")
    print(f"  GPU Utilization:     {m.gpu_usage_percent}%")
    print(f"  Memory (RSS):        {m.memory_mb} MB")
    print(f"  Disk I/O Bandwidth:  {m.disk_io_mb} MB")
    print("==========================================================================")

if __name__ == "__main__":
    main()
