# v_core/domains/harness/sensors.py
import os
import subprocess

def os_is_supported() -> bool:
    """Sensor: Verifies OS compatibility for local execution."""
    return os.name in ['nt', 'posix']

def docker_is_running() -> bool:
    """Sensor: Fast ping to check if the Docker daemon is responsive."""
    try:
        # A 1-second timeout prevents the agent from hanging if Docker is frozen
        res = subprocess.run(["docker", "info"], capture_output=True, timeout=1)
        return res.returncode == 0
    except Exception:
        return False

def has_internet_connection() -> bool:
    """Sensor: Fast ping to a reliable DNS to check external connectivity."""
    try:
        # Ping Cloudflare DNS (1.1.1.1) exactly once
        ping_cmd = ["ping", "-c", "1", "-W", "1", "1.1.1.1"] if os.name == 'posix' else ["ping", "-n", "1", "-w", "1000", "1.1.1.1"]
        res = subprocess.run(ping_cmd, capture_output=True)
        return res.returncode == 0
    except Exception:
        return False