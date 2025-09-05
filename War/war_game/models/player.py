from dataclasses import dataclass, field
from typing import List, Set

@dataclass
class Player:
    id: int
    name: str
    color: str
    alive: bool = True
    territories: Set[str] = field(default_factory=set)
    cards: List[str] = field(default_factory=list)
