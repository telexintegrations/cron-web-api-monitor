# test_cron_monitor.py
import pytest
from datetime import datetime, timedelta
from pathlib import Path
import json
from cron_monitor import CronMonitor, CronJobConfig, SimulatedJob
import time

@pytest.fixture
def test_log_dir(tmp_path):
    """Create a temporary directory for test logs"""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir

@pytest.fixture
def monitor(test_log_dir):
    """Create a CronMonitor instance with test configuration"""
    monitor_log = test_log_dir / "cron_monitor.log"
    return CronMonitor(log_path=str(monitor_log))

@pytest.fixture
def sample_job_configs(test_log_dir):
    """Create sample job configurations for testing"""
    return [
        CronJobConfig(
            name="test_job_1",
            pattern="test1.sh",
            max_duration=5,
            log_file=str(test_log_dir / "test1.log"),
            expected_output="Test 1 completed"
        ),
        CronJobConfig(
            name="test_job_2",
            pattern="test2.sh",
            max_duration=3,
            log_file=str(test_log_dir / "test2.log")
        )
    ]

def create_test_log(log_file, entries):
    """Helper function to create test log files with specified entries"""
    with open(log_file, 'w') as f:
        for timestamp, message in entries:
            f.write(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

def test_monitor_initialization(monitor):
    """Test monitor initialization"""
    assert monitor.last_check_results == {}
    assert monitor.simulated_jobs == {}

def test_setup_simulated_jobs(monitor, sample_job_configs):
    """Test setting up simulated jobs"""
    monitor.setup_simulated_jobs(sample_job_configs)
    assert len(monitor.simulated_jobs) == 2
    assert "test_job_1" in monitor.simulated_jobs
    assert "test_job_2" in monitor.simulated_jobs

def test_check_job_logs_running(monitor, test_log_dir, sample_job_configs):
    """Test checking job logs with currently running job"""
    job_config = sample_job_configs[0]
    now = datetime.now()
    
    entries = [
        (now - timedelta(minutes=2), f"{job_config.pattern} started")
    ]
    create_test_log(job_config.log_file, entries)
    
    result = monitor.check_job_logs(job_config)
    assert result["status"] == "running"
    assert "progress" in result["message"]

def test_check_job_logs_stuck(monitor, test_log_dir, sample_job_configs):
    """Test checking job logs with stuck job"""
    job_config = sample_job_configs[0]
    now = datetime.now()
    
    entries = [
        (now - timedelta(minutes=10), f"{job_config.pattern} started")
    ]
    create_test_log(job_config.log_file, entries)
    
    result = monitor.check_job_logs(job_config)
    assert result["status"] == "error"
    assert "stuck" in result["message"]

def test_monitor_jobs(monitor, sample_job_configs):
    """Test monitoring multiple jobs"""
    monitor.setup_simulated_jobs(sample_job_configs)
    results = monitor.monitor_jobs(sample_job_configs)
    
    assert len(results) == 2
    assert all(isinstance(result, dict) for result in results)
    assert all("name" in result for result in results)
    assert all("status" in result for result in results)
    assert all("message" in result for result in results)

def test_get_active_jobs(monitor, sample_job_configs):
    """Test getting active jobs"""
    monitor.setup_simulated_jobs(sample_job_configs)
    
    # Start a job
    job = monitor.simulated_jobs["test_job_1"]
    job.is_running = True
    job.start_time = datetime.now()
    
    active_jobs = monitor.get_active_jobs()
    assert len(active_jobs) == 1
    assert active_jobs[0]["name"] == "test_job_1"
    assert isinstance(active_jobs[0]["runtime"], float)
def test_simulated_job_run(test_log_dir):
    """Test simulated job execution"""
    job = SimulatedJob(
        name="test_job",
        log_file=str(test_log_dir / "test.log"),
        duration_range=(0.1, 0.2)
    )
    
    job.run()
    
    with open(job.log_file, 'r') as f:
        log_content = f.read()
    
    assert "started" in log_content.lower()
    assert any(["completed" in line.lower() or "failed" in line.lower() 
                for line in log_content.splitlines()])