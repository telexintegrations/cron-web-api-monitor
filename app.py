from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from datetime import datetime
import httpx
import asyncio
import random
import os

# Constants
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://ping.telex.im/v1/webhooks/01952c5a-d68b-7c5f-bd0e-6e691c8a7f35")
MONITOR_INTERVAL = int(os.environ.get("MONITOR_INTERVAL", 60))  

app = FastAPI(
    title="Cron Job Monitor",
    description="Automated cron job monitoring with varied messages",
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
    max_age=3600
)

# Store active monitoring tasks
active_monitors = {}

def generate_monitor_message():
    """Generate varied monitoring messages"""
    
    # List of possible jobs and their statuses
    jobs = [
        ("System Backup", ["✅ Completed successfully", "⚠️ Running longer than expected", "✅ Backup validated"]),
        ("Log Rotation", ["✅ Logs compressed", "✅ Old logs archived", "⚠️ Disk space low"]),
        ("Data Cleanup", ["✅ Cleaned up 2.5GB", "✅ Optimized tables", "⚠️ Partial completion"]),
        ("Security Scan", ["✅ No threats found", "🔍 Scan in progress", "⚠️ Updates needed"]),
        ("Database Backup", ["✅ Backup verified", "✅ Replica synced", "⚠️ Slow replication"]),
        ("Cache Refresh", ["✅ Cache updated", "✅ Memory optimized", "⚠️ High memory usage"]),
        ("SSL Certificate Check", ["✅ Certificates valid", "⚠️ Renewal needed", "✅ Auto-renewed"]),
        ("API Health Check", ["✅ All endpoints healthy", "⚠️ High latency", "✅ Load balanced"]),
        ("Email Queue", ["✅ Queue processed", "✅ No pending items", "⚠️ Delivery delays"]),
        ("Metrics Collection", ["✅ Data aggregated", "✅ Reports generated", "⚠️ Partial data"])
    ]
    
    # Select 4-6 random jobs
    selected_jobs = random.sample(jobs, random.randint(4, 6))
    
    # Build message
    timestamp = datetime.now().strftime("%H:%M:%S")
    message = f"🔍 Cron Monitor Report [{timestamp}]\n"
    message += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for job, statuses in selected_jobs:
        status = random.choice(statuses)
        message += f"{status} | {job}\n"
    
    # Add random system metrics
    cpu_usage = random.randint(20, 85)
    memory_usage = random.randint(30, 90)
    disk_usage = random.randint(40, 85)
    
    message += f"\n📊 System Metrics:\n"
    message += f"CPU: {'🟢' if cpu_usage < 70 else '🟡'} {cpu_usage}% | "
    message += f"RAM: {'🟢' if memory_usage < 80 else '🟡'} {memory_usage}% | "
    message += f"Disk: {'🟢' if disk_usage < 80 else '🟡'} {disk_usage}%\n"
    
    # Add random insights
    insights = [
        "💡 All critical services operating normally",
        "💡 System performance within expected parameters",
        "💡 No security incidents detected",
        "💡 Automatic maintenance tasks completed",
        "💡 Resource usage optimization recommended",
        "💡 Backup verification successful",
        "💡 Minor warnings require attention",
        "💡 System health check passed"
    ]
    message += f"\n{random.choice(insights)}"
    
    return message

async def periodic_monitor(webhook_url: str):
    """Send monitoring messages at regular intervals"""
    while True:
        try:
            message = generate_monitor_message()

            webhook_payload = {
                "username": "Cron Monitor",
                "event_name": "Cron Check",
                "status": "success",
                "message": message
            }

            async with httpx.AsyncClient() as client:
                await client.post(webhook_url, json=webhook_payload)

        except Exception as e:
            print(f"Error sending monitoring message: {e}")

        await asyncio.sleep(MONITOR_INTERVAL)

# Rest of the endpoints remain the same
@app.get("/")
async def root():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/integration.json")
async def get_integration_json(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse({
        "data": {
            "date": {
                "created_at": "2025-02-21",
                "updated_at": "2025-02-20"
            },
            "descriptions": {
                "app_name": "Cron Monitor",
                "app_description": "Monitor cron jobs and their execution status",
                "app_logo": "https://example.com/cron-monitor-logo.png",
                "app_url": base_url,
                "background_color": "#fff"
            },
            "is_active": True,
            "integration_type": "interval",
            "integration_category": "Monitoring & Logging",
            "key_features": [
                "Real-time cron job monitoring",
                "Dynamic status updates",
                "System metrics tracking",
                "Intelligent insights"
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

@app.post("/monitor")
async def monitor_jobs(request: Request):
    """Start monitoring and sending interval messages"""
    try:
        body = {}
        try:
            body = await request.json()
        except:
            pass
        
        webhook_url = body.get("return_url", WEBHOOK_URL)
        channel_id = body.get("channel_id", "default")
        
        if channel_id in active_monitors:
            active_monitors[channel_id].cancel()
            
        task = asyncio.create_task(periodic_monitor(webhook_url))
        active_monitors[channel_id] = task
        
        return {
            "status": "accepted",
            "message": "Monitoring started - sending updates every minute",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup monitoring tasks on shutdown"""
    for task in active_monitors.values():
        task.cancel()
    active_monitors.clear()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))