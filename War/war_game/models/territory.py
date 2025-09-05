from dataclasses import dataclass, field
from typing import Set, Optional

@dataclass
class Territory:
    name: str
    continent: str
    neighbors: Set[str] = field(default_factory=set)
    owner_id: Optional[int] = None
    armies: int = 0
