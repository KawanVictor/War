from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Mission:
    description: str
    target_color: Optional[str] = None  # destruir os exércitos dessa cor
    continents: List[str] = field(default_factory=list)  # continentes a conquistar por inteiro
    extra_continents: int = 0  # continentes adicionais à escolha do jogador
    territories_required: Optional[int] = None
    min_armies: int = 1  # exércitos mínimos em cada território contado
