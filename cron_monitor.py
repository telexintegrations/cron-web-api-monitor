import logging
from pathlib import Path
import subprocess
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import schedule
import time

class CronJobConfig(BaseModel):
    name: str
    pattern: str
    max_duration: int
    log_file: str
    expected_output: Optional[str] = None

class CronMonitor:
    def __init__(self, log_path: str = "logs/cron_monitor.log"):
        self.setup_logging(log_path)

    def setup_logging(self, log_path: str):
        """Setup logging configuration"""
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

    def get_active_cron_jobs(self) -> List[Dict[str, Any]]:
        """Get list of currently running cron jobs"""
        try:
            cmd = ["ps", "-eo", "pid,etime,cmd", "--no-headers"]
            output = subprocess.check_output(cmd, text=True)
            
            cron_jobs = []
            for line in output.split('\n'):
                if not line.strip():
                    continue
                    
                if 'cron' in line.lower() or 'CRON' in line:
                    parts = line.split(None, 2)
                    if len(parts) >= 3:
                        pid, etime, command = parts
                        cron_jobs.append({
                            'pid': int(pid),
                            'runtime': etime.strip(),
                            'command': command.strip()
                        })
            
            return cron_jobs
        except Exception as e:
            self.logger.error(f"Failed to get active cron jobs: {e}")
            return []

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
            
            for line in reversed(lines):
                if job_config.pattern in line:
                    timestamp = self.parse_log_timestamp(line)
                    if timestamp and current_time - timestamp <= timedelta(hours=24):
                        if "started" in line.lower() or "beginning" in line.lower():
                            job_start = timestamp
                        elif "completed" in line.lower() or "finished" in line.lower():
                            job_end = timestamp
                        if job_start and job_end:
                            break

            if not job_start:
                return {
                    "status": "warning",
                    "message": "No executions found in the last 24 hours"
                }

            if job_end:
                duration = (job_end - job_start).total_seconds() / 60
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

    def parse_log_timestamp(self, line: str) -> Optional[datetime]:
        """Parse timestamp from log line with multiple format support"""
        timestamp_formats = [
            (r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', '%Y-%m-%d %H:%M:%S'),
            (r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}', '%b %d %H:%M:%S'),
            (r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}', '%m/%d/%Y %H:%M:%S')
        ]
        
        for pattern, date_format in timestamp_formats:
            match = re.search(pattern, line)
            if match:
                try:
                    timestamp_str = match.group()
                    timestamp = datetime.strptime(timestamp_str, date_format)
                    if timestamp.year == 1900:
                        timestamp = timestamp.replace(year=datetime.now().year)
                    return timestamp
                except ValueError:
                    continue
        return None

    def monitor_jobs(self, job_configs: List[CronJobConfig]):
        """Monitor all configured cron jobs"""
        for job_config in job_configs:
            result = self.check_job_logs(job_config)
            self.logger.info(f"Job: {job_config.name} - {result['status']}: {result['message']}")

def main():
    # Example job configurations
    job_configs = [
        CronJobConfig(
            name="Backup Job",
            pattern="backup",
            max_duration=30,
            log_file="/var/log/backup.log"
        ),
        CronJobConfig(
            name="Cleanup Job",
            pattern="cleanup",
            max_duration=10,
            log_file="/var/log/cleanup.log"
        )
    ]

    monitor = CronMonitor()

    # Schedule the monitoring task to run every 2 minutes
    schedule.every(2).minutes.do(monitor.monitor_jobs, job_configs=job_configs)

    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()