from pathlib import Path
import pytest
from war_game.models.game_state import GameState
from war_game.models.player import Player
from war_game.models.territory import Territory

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

@pytest.fixture
def data_dir():
    return DATA_DIR

@pytest.fixture
def make_state():
    """Monta um estado a partir de {territorio: (continente, dono, tropas, vizinhos)}."""
    def _make(spec, num_players=2, deck=None):
        colors = ["red", "blue", "green"]
        players = [Player(id=i, name=f"P{i}", color=colors[i]) for i in range(num_players)]
        territories = {}
        for name, (continent, owner, armies, neighbors) in spec.items():
            territories[name] = Territory(name, continent, set(neighbors), owner, armies)
            players[owner].territories.add(name)
        return GameState(territories=territories, players=players, deck=list(deck or []))
    return _make

@pytest.fixture
def duel(make_state):
    """Dois territórios vizinhos: A (jogador 0, 5 tropas) e B (jogador 1, 1 tropa)."""
    return make_state({
        "A": ("X", 0, 5, ["B"]),
        "B": ("X", 1, 1, ["A"]),
    })
