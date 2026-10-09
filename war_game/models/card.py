from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class Card:
    id: str
    territory: Optional[str]  # None para curingas
    icon: str  # 'infantry' | 'cavalry' | 'artillery' | 'wild'
