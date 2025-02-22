from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from datetime import datetime
import httpx
import asyncio
from cron_monitor import CronMonitor, CronJobConfig
import json
import random
import threading

# Constants
WEBHOOK_URL = "https://ping.telex.im/v1/webhooks/01952c5a-d68b-7c5f-bd0e-6e691c8a7f35"

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
    description="Automated cron job monitoring with simulated jobs and interval-based checks",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://telex.im",
        "https://staging.telex.im",
        "https://telextest.im",
        "https://staging.telax.im"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
        "Access-Control-Allow-Origin"
    ],
    expose_headers=["Content-Type", "Authorization"],
    max_age=3600  # Cache preflight requests for 1 hour
)

# Global monitor instance
monitor = CronMonitor(log_path="logs/cron_monitor.log")

@app.get("/")
async def root():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/integration.json")
async def get_integration_json(request: Request):
    """Provide integration configuration for Telex"""
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse({
        "data": {
            "date": {
                "created_at": "2025-02-21",  
                "updated_at": "2025-02-20"   
            },
            "descriptions": {
                "app_name": "Cron Monitor",
                "app_description": "Monitor cron jobs and their execution status with simulated job support",
                "app_logo": "https://example.com/cron-monitor-logo.png",
                "app_url": base_url,  # Use base_url here
                "background_color": "#fff"  # Changed to #fff
            },
            "is_active": True,
            "integration_type": "interval",
            "integration_category": "Monitoring & Logging",
            "key_features": [
                "Real-time cron job monitoring",  # Removed extra quotes
                "Simulated job execution for testing",
                "Alerting via webhooks",
                "Customizable check intervals",
                "Detailed logging and reporting"
            ],
            "author": "bruce oyufi",
            "settings": [
                {
                    "label": "Check Interval",
                    "type": "dropdown",
                    "required": True,
                    "default": "*/1 * * * *",
                    "options": [
                        "*/1 * * * *",
                        "*/5 * * * *",
                        "*/15 * * * *",
                        "0 * * * *"
                    ]
                }
            ],
            "target_url": WEBHOOK_URL,
            "tick_url": f"{base_url}/tick"
        }
    })
async def run_monitoring_task(payload: MonitorPayload):
    """Background task to run cron monitoring checks with improved formatting"""
    try:
        # Get cron jobs from monitoring config or settings
        if payload.monitoring_config and payload.monitoring_config.cron_jobs:
            cron_jobs = [CronJobConfig(**job.dict()) for job in payload.monitoring_config.cron_jobs]
        else:
            jobs_config = payload.settings.get("Cron Jobs", [])
            if isinstance(jobs_config, str):
                jobs_config = json.loads(jobs_config)
            cron_jobs = [CronJobConfig(**job) for job in jobs_config]

        # Setup simulated jobs if enabled
        if payload.settings.get("Simulation Mode", True):
            monitor.setup_simulated_jobs(cron_jobs)
            if random.random() < 0.3:
                monitor.start_random_job()

        # Run monitoring checks
        results = monitor.monitor_jobs(cron_jobs)

        # Format results
        formatted_results = []
        for result in results:
            formatted_result = {
                "name": str(result["name"]),
                "status": str(result["status"]),
                "message": str(result["message"]),
                "running": bool(result["running"]),
                "last_run": result.get("last_run", "Unknown"),
                "next_run": result.get("next_run", "Unknown")
            }
            formatted_results.append(formatted_result)

        # Generate detailed report
        status = all(r["status"] == "ok" for r in formatted_results)
        message = "**Cron Monitoring Report**\n\n"
        message += "🔍 Job Status Summary:\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for result in formatted_results:
            status_emoji = {
                "ok": "✅",
                "warning": "⚠️",
                "error": "🚨",
                "running": "⚙️"
            }.get(result["status"], "❓")
            
            # Job header with status
            message += f"**{result['name']}** {status_emoji}\n"
            
            # Status details with proper indentation
            message += f"├─ Status: `{result['status'].upper()}`\n"
            message += f"├─ Details: {result['message']}\n"
            
            # Add timing information
            if result["last_run"] != "Unknown":
                message += f"├─ Last Run: {result['last_run']}\n"
            if result["next_run"] != "Unknown":
                message += f"├─ Next Run: {result['next_run']}\n"
            
            # Running status
            if result["running"]:
                message += f"└─ 🔄 Currently Running\n"
            else:
                message += "└─────────────\n"
            message += "\n"

        # Add summary statistics
        if len(formatted_results) > 1:
            total_ok = sum(1 for r in formatted_results if r["status"] == "ok")
            total_running = sum(1 for r in formatted_results if r["running"])
            message += f"\n📊 Summary:\n"
            message += f"• {total_ok}/{len(formatted_results)} jobs healthy\n"
            if total_running > 0:
                message += f"• {total_running} jobs currently running\n"

        webhook_payload = {
            "username": "Cron Monitor",
            "event_name": "Cron Check",
            "status": "success" if status else "warning",
            "message": message
        }

        # Send webhook
        async with httpx.AsyncClient() as client:
            await client.post(
                payload.return_url,
                json=webhook_payload
            )

    except Exception as e:
        error_msg = (
            "**Cron Monitor Error**\n\n"
            f"🚨 Monitoring task failed:\n"
            f"```\n{str(e)}\n```"
        )
        webhook_error_payload = {
            "username": "Cron Monitor",
            "event_name": "Monitoring Error",
            "status": "error",
            "message": error_msg
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(
                payload.return_url,
                json=webhook_error_payload
            )

@app.post("/tick")
async def handle_tick(payload: MonitorPayload, background_tasks: BackgroundTasks):
    """Handle automated monitoring tick events from Telex"""
    try:
        if not payload.channel_id:
            raise HTTPException(status_code=400, detail="Missing channel_id")
            
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
        # Ensure proper job configuration structure
        if not request.monitoring_config:
            request.monitoring_config = MonitoringConfig(
                cron_jobs=[
                    CronJob(**job) for job in request.settings.get("Cron Jobs", [])
                ],
                monitoring_types=["cron"]
            )
        
        background_tasks.add_task(run_monitoring_task, request)
        return {
            "status": "accepted",
            "message": "Monitoring task scheduled",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Updated monitoring task function
async def run_monitoring_task(payload: MonitorPayload):
    """Background task to run cron monitoring checks"""
    try:
        # Get cron jobs from monitoring config or settings
        if payload.monitoring_config and payload.monitoring_config.cron_jobs:
            cron_jobs = [CronJobConfig(**job.dict()) for job in payload.monitoring_config.cron_jobs]
        else:
            # Parse cron jobs from settings
            jobs_config = payload.settings.get("Cron Jobs", [])
            if isinstance(jobs_config, str):
                jobs_config = json.loads(jobs_config)
            cron_jobs = [CronJobConfig(**job) for job in jobs_config]

        # Setup simulated jobs if enabled
        if payload.settings.get("Simulation Mode", True):
            monitor.setup_simulated_jobs(cron_jobs)
            
            # Randomly start jobs (30% chance)
            if random.random() < 0.3:
                monitor.start_random_job()

        # Run monitoring checks
        results = monitor.monitor_jobs(cron_jobs)

        # Format and send results as before...
        formatted_results = []
        for result in results:
            formatted_result = {
                "name": str(result["name"]),
                "status": str(result["status"]),
                "message": str(result["message"]),
                "running": bool(result["running"])
            }
            formatted_results.append(formatted_result)

        status = all(r["status"] == "ok" for r in formatted_results)
        message = "🔍 Cron Job Status Report:\n\n"
        
        for result in formatted_results:
            status_emoji = {
                "ok": "✅",
                "warning": "⚠️",
                "error": "🚨",
                "running": "⚙️"
            }.get(result["status"], "❓")
            
            message += f"{status_emoji} {result['name']}\n"
            message += f"   Status: {result['status'].upper()}\n"
            message += f"   Details: {result['message']}\n"
            if result["running"]:
                message += f"   🔄 Currently running\n"
            message += "\n"

        webhook_payload = {
            "username": "Cron Monitor",
            "event_name": "Cron Check",
            "status": "success" if status else "error",
            "message": message
        }

        async with httpx.AsyncClient() as client:
            await client.post(
                payload.return_url,
                json=webhook_payload
            )

    except Exception as e:
        error_msg = f"🚨 Monitoring task failed: {str(e)}"
        webhook_error_payload = {
            "username": "Cron Monitor",
            "event_name": "Monitoring Error",
            "status": "error",
            "message": error_msg
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(
                payload.return_url,
                json=webhook_error_payload
            )
@app.get("/status")
async def get_status():
    """Get current status of all monitored jobs"""
    try:
        return {
            "status": "success",
            "data": monitor.last_check_results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/simulate/start")
async def start_job(job_name: str):
    """Manually start a simulated job"""
    try:
        if job_name in monitor.simulated_jobs:
            job = monitor.simulated_jobs[job_name]
            if not job.is_running:
                threading.Thread(target=job.run).start()
                return {
                    "status": "success",
                    "message": f"Started job: {job_name}",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "warning",
                    "message": f"Job {job_name} is already running",
                    "timestamp": datetime.now().isoformat()
                }
        else:
            raise HTTPException(status_code=404, detail=f"Job {job_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs")
async def list_jobs():
    """List all configured jobs and their current status"""
    try:
        jobs = []
        for name, job in monitor.simulated_jobs.items():
            jobs.append({
                "name": name,
                "running": job.is_running,
                "log_file": job.log_file,
                "last_status": monitor.last_check_results.get(name, {})
            })
        
        return {
            "status": "success",
            "data": jobs,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)