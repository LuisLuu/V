import sys
import os

# Dynamically append the project root to the system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import subprocess
from agents.tools.preconditions import SecurityTier
from agents.harness.blast_gates import BlastGate
import agents.harness.sensors as sensors

def run_harness_tests():
    print("--- Starting Harness Validation Matrix ---")
    gate = BlastGate()
    
    # ---------------------------------------------------------
    # PHASE 1: SENSOR TELEMETRY TESTS
    # ---------------------------------------------------------
    print("\n🟢 Phase 1: Testing Environmental Sensors...")
    
    os_check = sensors.os_is_supported()
    print(f"OS Supported: {os_check}")
    assert os_check is True, "FAIL: OS sensor failed to recognize a valid environment."

    docker_check = sensors.docker_is_running()
    print(f"Docker Running: {docker_check}")
    # We don't fail the assert here because Docker might legitimately be off on your test machine,
    # but we need to ensure the sensor returns a clean boolean and doesn't crash.
    assert isinstance(docker_check, bool), "FAIL: Docker sensor did not return a boolean."

    # ---------------------------------------------------------
    # PHASE 2: BLAST GATE ROUTING TESTS
    # ---------------------------------------------------------
    print("\n🟢 Phase 2: Testing READ (Autonomous) Gate...")
    read_payload = gate.evaluate_execution("file_reader", SecurityTier.READ, {"file": "log.txt"})
    print(f"Payload: {read_payload}")
    assert read_payload["approved"] is True, "FAIL: READ operation was blocked."
    assert read_payload["status"] == "AUTO_APPROVED", "FAIL: Incorrect status string."

    print("\n🟡 Phase 3: Testing WRITE (Logged/HITL) Gate...")
    # Default behavior should block and request HITL
    write_payload = gate.evaluate_execution("task_manager", SecurityTier.WRITE, {"task_id": "123"})
    print(f"Payload: {write_payload}")
    assert write_payload["approved"] is False, "FAIL: WRITE operation auto-approved unsafely."
    assert write_payload["status"] == "HITL_REQUIRED", "FAIL: Did not emit HITL state."
    assert "tool_payload" in write_payload, "FAIL: Missing tool payload for frontend rendering."

    print("\n🔴 Phase 4: Testing DESTRUCTIVE (Hard Stop) Gate...")
    destruct_payload = gate.evaluate_execution("command_executor", SecurityTier.DESTRUCTIVE, {"command": "rm -rf /"})
    print(f"Payload: {destruct_payload}")
    assert destruct_payload["approved"] is False, "FAIL: DESTRUCTIVE operation slipped through!"
    assert destruct_payload["status"] == "HITL_REQUIRED", "FAIL: Did not emit HITL state."
    assert "rm -rf" in destruct_payload["ui_prompt"], "FAIL: UI prompt missing context."

    # ---------------------------------------------------------
    # PHASE 5: OVERRIDE VULNERABILITY TEST
    # ---------------------------------------------------------
    print("\n🔴 Phase 5: Testing DESTRUCTIVE Override Vulnerability...")
    # Even if we set auto_approve_writes to True, DESTRUCTIVE must still block.
    gate.auto_approve_writes = True
    vuln_payload = gate.evaluate_execution("command_executor", SecurityTier.DESTRUCTIVE, {"command": "fdisk"})
    assert vuln_payload["approved"] is False, "CRITICAL FAIL: DESTRUCTIVE tier was bypassed by auto-write settings!"

    print("\n🎉 ALL TESTS PASSED: The Security Harness is locked down.")

if __name__ == "__main__":
    run_harness_tests()