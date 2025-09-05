from dataclasses import dataclass
from typing import Optional, Dict

@dataclass
class Mission:
    description: str
    target_color: Optional[str] = None
    continents: Optional[Dict[str, int]] = None
    territories_required: Optional[int] = None
