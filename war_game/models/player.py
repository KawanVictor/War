from dataclasses import dataclass, field
from typing import List, Optional, Set

@dataclass
class Player:
    id: int
    name: str
    color: str
    alive: bool = True
    eliminated_by: Optional[int] = None  # id de quem conquistou o último território
    territories: Set[str] = field(default_factory=set)
    cards: List[str] = field(default_factory=list)
