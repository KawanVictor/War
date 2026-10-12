from dataclasses import dataclass, field
from typing import Set, Optional

@dataclass
class Territory:
    name: str
    continent: str
    neighbors: Set[str] = field(default_factory=set)
    owner_id: Optional[int] = None
    armies: int = 0
    label: str = ""  # nome de exibição; `name` é o identificador

    def __post_init__(self):
        if not self.label:
            self.label = self.name
