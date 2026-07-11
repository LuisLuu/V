# v-core/domains/memory/compaction.py
from typing import List, Dict

class CompactionEngine:
    """
    Prevents context rot by structurally moving resolved data from RAM to ROM.
    """
    def __init__(self, rom_connection):
        self.rom = rom_connection

    def compact_context(self, active_ram: List[Dict]) -> List[Dict]:
        """
        Sweeps the active RAM. 
        Saves verbose intermediate steps to ROM and returns a condensed state.
        """
        condensed_ram = []
        for message in active_ram:
            if message.get("status") == "completed":
                # Move to permanent SQLite/Vector storage
                self.rom.save_payload(message)
            else:
                # Keep open decisions and active constraints in RAM
                condensed_ram.append(message)
                
        return condensed_ram