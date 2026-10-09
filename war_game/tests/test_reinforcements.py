from war_game.models.game_state import GameState
from war_game.models.player import Player
from war_game.models.territory import Territory
from war_game.rules.reinforcements import calc_total_reinforcements
from pathlib import Path

def test_min_three():
    terrs = {
        "A": Territory("A", "X", set(), 0, 1),
        "B": Territory("B", "X", set(), 0, 1)
    }
    p = [Player(0, "P", "red", territories={"A", "B"})]
    st = GameState(territories=terrs, players=p, deck=[])
    assert calc_total_reinforcements(st, Path("war_game/data")) >= 3
