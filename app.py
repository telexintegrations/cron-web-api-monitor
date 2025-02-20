from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from datetime import datetime
import httpx
import schedule
import time
import asyncio
from cron_monitor import CronMonitor, CronJobConfig

# Constants
WEBHOOK_URL = "https://ping.telex.im/v1/webhooks/019517d3-7a2e-7f80-8cfb-614494172063"  # Replace with your webhook ID

class CronJob(BaseModel):
    name: str
    pattern: str
    max_duration: int
    log_file: str
    expected_output: Optional[str] = None

class MonitoringConfig(BaseModel):
    cron_jobs: List[CronJob]
    monitoring_types: List[str] = ["cron"]

class MonitorPayload(BaseModel):
    channel_id: str
    return_url: str = WEBHOOK_URL
    settings: Dict[str, Any]
    monitoring_config: Optional[MonitoringConfig] = None

app = FastAPI(
    title="Cron Job Monitor",
    description="Automated cron job monitoring with interval-based checks",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variable to store monitoring configurations
monitoring_configs = []

@app.get("/")
async def root():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/integration.json")
async def get_integration_json(request: Request):
    """Provide integration configuration for Telex"""
    base_url = str(request.base_url).rstrip("/")
    return {
        "descriptions": {
            "app_name": "Cron Monitor",
            "app_description": "Monitor cron jobs and their execution status",
            "app_url": base_url,
            "app_logo": "https://example.com/cron-monitor-logo.png",
            "background_color": "#4A90E2"
        },
        "integration_type": "interval",
        "integration_category": "Monitoring & Logging",
        "webhook_url": WEBHOOK_URL,
        "settings": [
            {
                "label": "Check Interval",
                "type": "dropdown",
                "required": True,
                "default": "*/15 * * * *",
                "options": [
                    "*/5 * * * *",    # Every 5 minutes
                    "*/15 * * * *",   # Every 15 minutes
                    "0 * * * *",      # Hourly
                ]
            },
            {
                "label": "Cron Jobs",
                "type": "json",
                "required": True,
                "default": """[
                    {
                        "name": "Daily Backup",
                        "pattern": "backup.sh",
                        "max_duration": 120,
                        "log_file": "/var/log/cron/backup.log",
                        "expected_output": "Backup completed successfully"
                    }
                ]""",
                "placeholder": "Enter cron job configurations"
            }
        ],
        "tick_url": f"{base_url}/tick"
    }

async def run_monitoring_task(payload: MonitorPayload):
    """Background task to run cron monitoring checks"""
    try:
        monitor = CronMonitor(log_path="logs/cron_monitor.log")
        
        # Parse cron jobs from settings
        cron_jobs = []
        if "Cron Jobs" in payload.settings:
            import json
            jobs_config = json.loads(payload.settings["Cron Jobs"])
            cron_jobs = [CronJobConfig(**job) for job in jobs_config]

        results = []
        for job_config in cron_jobs:
            # Check job logs
            log_status = monitor.check_job_logs(job_config)
            
            # Get active job status
            active_jobs = monitor.get_active_cron_jobs()
            is_running = any(job_config.pattern in job['command'] for job in active_jobs)
            
            results.append({
                "name": job_config.name,
                "status": "ok" if log_status["status"] == "ok" and is_running else "error",
                "message": log_status["message"],
                "running": is_running
            })

        # Prepare message for webhook
        status = all(r["status"] == "ok" for r in results)
        message = "Cron Job Status Report:\n\n"
        for result in results:
            emoji = "✅" if result["status"] == "ok" else "🚨"
            message += f"{emoji} {result['name']}: {result['message']}\n"
            if not result["running"]:
                message += "   ⚠️ Job not currently running\n"

        # Send results to webhook
        async with httpx.AsyncClient() as client:
            await client.post(
                payload.return_url,
                json={
                    "username": "Cron Monitor",
                    "event_name": "Cron Check",
                    "status": "success" if status else "error",
                    "message": message
                }
            )

    except Exception as e:
        error_msg = f"🚨 Monitoring task failed: {str(e)}"
        async with httpx.AsyncClient() as client:
            await client.post(
                payload.return_url,
                json={
                    "username": "Cron Monitor",
                    "event_name": "Monitoring Error",
                    "status": "error",
                    "message": error_msg
                }
            )

@app.post("/tick")
async def handle_tick(payload: MonitorPayload, background_tasks: BackgroundTasks):
    """Handle automated monitoring tick events from Telex"""
    try:
        if not payload.channel_id:
            raise HTTPException(status_code=400, detail="Missing channel_id")
            
        # Schedule monitoring task
        background_tasks.add_task(run_monitoring_task, payload)
        
        return {
            "status": "accepted",
            "message": "Monitoring task scheduled",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/monitor")
async def monitor_jobs(request: MonitorPayload, background_tasks: BackgroundTasks):
    """Manual monitoring endpoint for testing"""
    try:
        background_tasks.add_task(run_monitoring_task, request)
        return {
            "status": "accepted",
            "message": "Monitoring task scheduled",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def schedule_monitoring():
    """Schedule monitoring tasks every 2 minutes"""
    for payload in monitoring_configs:
        schedule.every(2).minutes.do(asyncio.run, run_monitoring_task(payload))

async def start_scheduler():
    """Start the scheduler in the background"""
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    """Start the scheduler when the application starts"""
    asyncio.create_task(start_scheduler())

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)


