"""
AutoSRE Demo Scenarios

This module contains JSON scenario files for the demo command.
Each scenario provides realistic data for simulated incident investigations.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def load_scenario(scenario_id: str) -> dict[str, Any]:
    """
    Load a scenario from its JSON file.
    
    Args:
        scenario_id: The scenario ID (e.g., 'redis-connection', 'memory-leak')
        
    Returns:
        The scenario data with dynamic timestamps applied
        
    Raises:
        FileNotFoundError: If the scenario file doesn't exist
    """
    scenarios_dir = Path(__file__).parent
    scenario_path = scenarios_dir / f"{scenario_id}.json"
    
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario '{scenario_id}' not found at {scenario_path}")
    
    with open(scenario_path, "r") as f:
        scenario = json.load(f)
    
    # Apply dynamic timestamps
    scenario = _apply_dynamic_timestamps(scenario)
    
    return scenario


def _apply_dynamic_timestamps(scenario: dict[str, Any]) -> dict[str, Any]:
    """
    Replace relative timestamp markers with actual timestamps.
    
    Timestamp markers:
    - {now}: Current time
    - {now-Xm}: X minutes ago
    - {now-Xh}: X hours ago
    - {now-Xs}: X seconds ago
    """
    import re
    now = datetime.now()
    
    def replace_timestamp(value: str) -> str:
        if not isinstance(value, str):
            return value
        
        # Pattern for {now} or {now-Xm/h/s}
        pattern = r'\{now(?:-(\d+)([smh]))?\}'
        
        def replacer(match):
            if match.group(1) is None:
                # Just {now}
                return now.strftime("%H:%M:%S")
            else:
                # {now-Xm/h/s}
                amount = int(match.group(1))
                unit = match.group(2)
                
                if unit == "s":
                    offset = timedelta(seconds=amount)
                elif unit == "m":
                    offset = timedelta(minutes=amount)
                elif unit == "h":
                    offset = timedelta(hours=amount)
                else:
                    offset = timedelta()
                
                return (now - offset).strftime("%H:%M:%S")
        
        return re.sub(pattern, replacer, value)
    
    def process_value(value: Any) -> Any:
        if isinstance(value, str):
            return replace_timestamp(value)
        elif isinstance(value, dict):
            return {k: process_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [process_value(item) for item in value]
        return value
    
    return process_value(scenario)


def list_available_scenarios() -> list[str]:
    """Return a list of available scenario IDs."""
    scenarios_dir = Path(__file__).parent
    return [
        f.stem for f in scenarios_dir.glob("*.json")
        if f.is_file()
    ]
