import json
from pathlib import Path
from typing import Dict
from war_game.models.territory import Territory

def load_map(data_dir: Path) -> Dict[str, Territory]:
    data = json.loads((data_dir / "map.json").read_text(encoding="utf-8"))
    territories: Dict[str, Territory] = {}
    for t in data:
        territories[t["name"]] = Territory(
            name=t["name"],
            continent=t["continent"],
            neighbors=set(t["neighbors"])
        )
    return territories
