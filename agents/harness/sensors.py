# v_core/domains/harness/sensors.py
import os
import socket
from pathlib import Path

def os_is_supported() -> bool:
    """Sensor: Verifies OS compatibility for bare-metal execution."""
    return os.name in ['nt', 'posix']

def has_internet_connection(host: str = "1.1.1.1", port: int = 53, timeout: float = 0.5) -> bool:
    """
    Sensor: Ultra-fast TCP socket check for internet connectivity.
    Eliminates blocking OS subprocess/ping overhead entirely.
    """
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
        return True
    except Exception:
        return False

def workspace_is_intact(workspace_path: str = "./v_workspace") -> bool:
    """
    Sensor: Replaces Docker isolation with Directory isolation.
    Ensures V only reads/writes within this transparent folder.
    """
    try:
        path = Path(workspace_path).resolve()
        current_root = Path.cwd().resolve()
        
        # Build the glass room if it doesn't exist
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            
        # Path Traversal Defense: Catch V if she tries to escape root isolation
        if current_root not in path.parents and path != current_root / "v_workspace":
            print(f"[SECURITY ALERT] Workspace escaped root isolation: {path}")
            return False 

        # Verify read/write access
        if not os.access(path, os.R_OK | os.W_OK):
            return False
            
        return True
    except Exception as e:
        print(f"[SENSOR FAILURE] Workspace verification crashed: {e}")
        return False