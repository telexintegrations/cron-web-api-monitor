import logging
from pathlib import Path
import subprocess
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import time
import random
import threading
import json

class CronJobConfig(BaseModel):
    name: str
    pattern: str
    max_duration: int
    log_file: str
    expected_output: Optional[str] = None

class SimulatedJob:
    def __init__(self, name: str, log_file: str, duration_range: tuple, expected_output: Optional[str] = None):
        self.name = name
        self.log_file = log_file
        self.duration_range = duration_range
        self.expected_output = expected_output
        self.is_running = False
        self.start_time = None
        
    def write_log(self, message: str):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_file, 'a') as f:
            f.write(f"{timestamp} - {self.name}: {message}\n")
            if self.expected_output and "completed" in message.lower():
                f.write(f"{timestamp} - {self.name}: {self.expected_output}\n")
            
    def run(self):
        if not self.is_running:
            self.is_running = True
            self.start_time = datetime.now()
            self.write_log("started")
            
            # Simulate job running
            duration = random.uniform(*self.duration_range)
            time.sleep(duration)
            
            # Randomly simulate failures (10% chance)
            if random.random() < 0.1:
                self.write_log("failed: Error during execution")
            else:
                self.write_log("completed")
            
            self.is_running = False
            self.start_time = None

class CronMonitor:
    def __init__(self, log_path: str = "logs/cron_monitor.log"):
        self.setup_logging(log_path)
        self.simulated_jobs = {}
        self.last_check_results = {}

    def setup_logging(self, log_path: str):
        try:
            log_dir = Path(log_path).parent
            log_dir.mkdir(exist_ok=True)
            
            logging.basicConfig(
                filename=log_path,
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s'
            )
            self.logger = logging.getLogger(__name__)
        except Exception as e:
            print(f"Failed to initialize logging: {e}")
            self.logger = logging.getLogger(__name__)
            self.logger.addHandler(logging.StreamHandler())

    def setup_simulated_jobs(self, job_configs: List[CronJobConfig]):
        """Set up simulated jobs based on configurations"""
        for config in job_configs:
            # Create log file directory if it doesn't exist
            Path(config.log_file).parent.mkdir(parents=True, exist_ok=True)
            
            # Create empty log file if it doesn't exist
            Path(config.log_file).touch()
            
            # Create simulated job
            self.simulated_jobs[config.name] = SimulatedJob(
                name=config.name,
                log_file=config.log_file,
                duration_range=(1, config.max_duration),
                expected_output=config.expected_output
            )

    def start_random_job(self):
        """Start a random job simulation"""
        if self.simulated_jobs:
            job = random.choice(list(self.simulated_jobs.values()))
            if not job.is_running:
                threading.Thread(target=job.run).start()

    def check_job_logs(self, job_config: CronJobConfig) -> Dict[str, str]:
        """Check cron job logs for status and completion"""
        try:
            if not Path(job_config.log_file).exists():
                return {
                    "status": "error",
                    "message": f"Log file not found: {job_config.log_file}"
                }

            with open(job_config.log_file, 'r') as f:
                lines = f.readlines()[-100:]
                
            current_time = datetime.now()
            job_start = None
            job_end = None
            last_output = None
            
            for line in reversed(lines):
                if job_config.pattern in line:
                    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
                    if timestamp_match:
                        timestamp = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
                        if current_time - timestamp <= timedelta(hours=24):
                            if "started" in line.lower():
                                job_start = timestamp
                            elif "completed" in line.lower() or "failed" in line.lower():
                                job_end = timestamp
                                if job_config.expected_output and job_config.expected_output in line:
                                    last_output = True
                            if job_start and job_end:
                                break

            if not job_start:
                return {
                    "status": "warning",
                    "message": "No executions found in the last 24 hours"
                }

            if job_end:
                duration = (job_end - job_start).total_seconds() / 60
                
                if "failed" in line.lower():
                    return {
                        "status": "error",
                        "message": f"Job failed after {duration:.1f} minutes"
                    }
                
                if job_config.expected_output and not last_output:
                    return {
                        "status": "warning",
                        "message": f"Expected output not found in logs"
                    }
                
                if duration > job_config.max_duration:
                    return {
                        "status": "warning",
                        "message": f"Last job took {duration:.1f} minutes (max: {job_config.max_duration})"
                    }
                
                return {
                    "status": "ok",
                    "message": f"Last run completed in {duration:.1f} minutes"
                }
            else:
                duration = (current_time - job_start).total_seconds() / 60
                if duration > job_config.max_duration:
                    return {
                        "status": "error",
                        "message": f"Job possibly stuck - running for {duration:.1f} minutes"
                    }
                return {
                    "status": "running",
                    "message": f"In progress for {duration:.1f} minutes"
                }

        except Exception as e:
            self.logger.error(f"Failed to check job logs for {job_config.name}: {e}")
            return {
                "status": "error",
                "message": f"Log check failed: {str(e)}"
            }

    

    def monitor_jobs(self, job_configs: List[CronJobConfig]) -> List[Dict[str, Any]]:
        """Monitor all configured cron jobs and return results"""
        results = []
        for job_config in job_configs:
            status = self.check_job_logs(job_config)
            is_running = any(job.name == job_config.name for job in self.get_active_jobs())
            
            # Ensure all values are basic Python types
            result = {
                "name": str(job_config.name),
                "status": str(status["status"]),
                "message": str(status["message"]),
                "running": bool(is_running)
            }
            results.append(result)
            self.last_check_results[job_config.name] = result
            
            self.logger.info(f"Job: {job_config.name} - {status['status']}: {status['message']}")
            
        return results

    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """Get list of currently running simulated jobs"""
        active_jobs = []
        for name, job in self.simulated_jobs.items():
            if job.is_running:
                active_jobs.append({
                    "name": str(name),
                    "runtime": float((datetime.now() - job.start_time).total_seconds() / 60)
                    if job.start_time else 0.0
                })
        return active_jobs