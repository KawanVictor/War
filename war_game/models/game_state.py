from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .territory import Territory
from .player import Player
from .mission import Mission

@dataclass
class GameState:
    territories: Dict[str, Territory]
    players: List[Player]
    deck: List[str]
    discard: List[str] = field(default_factory=list)
    missions: Optional[Dict[int, Mission]] = None
    current_player_index: int = 0
    conquered_this_turn: bool = False
    phase: str = "waiting"  # 'waiting' | 'placing' | 'attacking' | 'fortifying'
    reinforcements_left: int = 0
    winner_id: Optional[int] = None
    trades_done: int = 0  # trocas de cartas já feitas na partida; define o valor da próxima
    movable: Dict[str, int] = field(default_factory=dict)  # tropas que ainda podem ser remanejadas no turno
    conquest: Optional[Dict[str, str]] = None  # {'from', 'to'} do território recém-conquistado
    setup_turns_left: int = 0  # turnos que faltam da primeira rodada, só de posicionamento

    def current_player(self) -> Player:
        return self.players[self.current_player_index]
