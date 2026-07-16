# v_core/domains/tools/iots/bambu_controller.py
import json
import ssl
import time
from v_core.domains.tools.preconditions import BaseTool, SecurityTier

class BambuController(BaseTool):
    """
    Directly connects to a Bambu Lab printer (A1, P1, X1) via local MQTT,
    sends a command, and returns the immediate status telemetry.
    """
    def __init__(self):
        self.name = "bambu_controller"
        self.description = "Controls and reads telemetry from a Bambu Lab 3D printer locally via MQTT."
        # This is a WRITE operation. V can run it, but the Orchestrator will log it.
        self.security_tier = SecurityTier.WRITE
        self.preconditions = [self._check_mqtt]

    def _check_mqtt(self) -> bool:
        """
        Computational Sensor: Verifies the MQTT library is installed before attempting execution.
        """
        try:
            import paho.mqtt.client as mqtt
            return True
        except ImportError:
            return False

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ip": {"type": "string", "description": "Printer IP address."},
                        "access_code": {"type": "string", "description": "8-digit LAN access code from the printer screen."},
                        "serial": {"type": "string", "description": "15-character serial number."},
                        "command": {
                            "type": "string", 
                            "enum": ["status", "pause", "resume", "stop", "light_on", "light_off"],
                            "description": "The physical command to execute."
                        }
                    },
                    "required": ["ip", "access_code", "serial", "command"]
                }
            }
        }

    def execute(self, ip: str, access_code: str, serial: str, command: str) -> str:
        """
        The physical network action: Connects via TLS, fires the payload, grabs the report, and disconnects.
        """
        import paho.mqtt.client as mqtt
        
        # Map simple commands to the precise JSON schema the Bambu motherboard expects
        payloads = {
            "status": {"pushing": {"sequence_id": "1", "command": "pushall"}},
            "pause": {"print": {"sequence_id": "1", "command": "pause"}},
            "resume": {"print": {"sequence_id": "1", "command": "resume"}},
            "stop": {"print": {"sequence_id": "1", "command": "stop"}},
            "light_on": {"system": {"sequence_id": "1", "command": "ledctrl", "led_node": "chamber_light", "led_mode": "on"}},
            "light_off": {"system": {"sequence_id": "1", "command": "ledctrl", "led_node": "chamber_light", "led_mode": "off"}}
        }
        
        target_payload = payloads.get(command)
        if not target_payload:
            return json.dumps({"status": "error", "message": "Invalid command."})

        response_data = {"status": "timeout", "data": None}
        
        # Network Callbacks
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                # Subscribe to the printer's telemetry channel
                client.subscribe(f"device/{serial}/report")
                # Fire the command payload
                client.publish(f"device/{serial}/request", json.dumps(target_payload))
                
        def on_message(client, userdata, msg):
            try:
                data = json.loads(msg.payload.decode("utf-8"))
                # Filter for the massive print telemetry block
                if "print" in data:
                    response_data["status"] = "success"
                    telemetry = data["print"]
                    # Extract only the critical signals to keep V's context window sharp
                    response_data["data"] = {
                        "nozzle_temp": telemetry.get("nozzle_temper"),
                        "bed_temp": telemetry.get("bed_temper"),
                        "progress": telemetry.get("mc_percent"),
                        "state": telemetry.get("gcode_state")
                    }
                    client.disconnect()
            except:
                pass

        # Bambu Lab requires specific TLS configurations and the 'bblp' username
        client = mqtt.Client()
        client.username_pw_set("bblp", access_code)
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)
        
        client.on_connect = on_connect
        client.on_message = on_message
        
        try:
            client.connect(ip, 8883, 10)
            client.loop_start()
            # Wait exactly 2.5 seconds for the physical machine to respond
            time.sleep(2.5) 
            client.loop_stop()
            return json.dumps(response_data)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})