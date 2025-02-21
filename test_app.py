# test_app.py
import pytest
from fastapi.testclient import TestClient
from app import app, monitor
import json
from cron_monitor import SimulatedJob
from datetime import datetime

client = TestClient(app)

@pytest.fixture
def sample_payload():
    """Create a sample monitoring payload"""
    return {
        "channel_id": "test-channel",
        "return_url": "https://example.com/webhook",
        "settings": {
            "Simulation Mode": True,
            "Cron Jobs": [
                {
                    "name": "Test Job",
                    "pattern": "test.sh",
                    "max_duration": 5,
                    "log_file": "logs/test.log",
                    "expected_output": "Test completed successfully"
                }
            ]
        }
    }

def test_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "status" in response.json()
    assert "timestamp" in response.json()

def test_integration_json():
    """Test integration.json endpoint"""
    response = client.get("/integration.json")
    assert response.status_code == 200
    data = response.json()
    
    assert "descriptions" in data
    assert "integration_type" in data
    assert "settings" in data
    assert "tick_url" in data

def test_monitor_endpoint_invalid_payload():
    """Test monitor endpoint with invalid payload"""
    invalid_payload = {"channel_id": "test"}  # Missing required fields
    response = client.post("/monitor", json=invalid_payload)
    assert response.status_code == 422  # Validation error

def test_status_endpoint():
    """Test status endpoint"""
    response = client.get("/status")
    assert response.status_code == 200
    assert "status" in response.json()
    assert "data" in response.json()
    assert "timestamp" in response.json()

def test_jobs_endpoint():
    """Test jobs endpoint"""
    response = client.get("/jobs")
    assert response.status_code == 200
    assert "status" in response.json()
    assert "data" in response.json()
    assert isinstance(response.json()["data"], list)

def test_tick_endpoint(sample_payload):
    """Test tick endpoint"""
    response = client.post("/tick", json=sample_payload)
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

def test_tick_endpoint_invalid_payload():
    """Test tick endpoint with invalid payload"""
    invalid_payload = {"settings": {}}  # Missing required channel_id
    response = client.post("/tick", json=invalid_payload)
    assert response.status_code == 422  # Validation error

def test_simulate_start_endpoint():
    """Test simulate/start endpoint"""
    # First set up a job
    monitor.simulated_jobs = {
        "Test Job": SimulatedJob(
            name="Test Job",
            log_file="logs/test.log",
            duration_range=(0.1, 0.2)
        )
    }
    
    response = client.post("/simulate/start?job_name=Test%20Job")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


