import pytest
from war_game.rules.reinforcements import (
    calc_base_reinforcements, calc_total_reinforcements, continent_bonus_map, has_full_continent,
)
from war_game.services.map_loader import load_map

@pytest.fixture
def south_america_vs_rest(make_state, data_dir):
    """Mapa real: jogador 0 com a América do Sul inteira, jogador 1 com o resto."""
    territories = load_map(data_dir)
    return make_state({
        name: (t.continent, 0 if t.continent == "South America" else 1, 1, t.neighbors)
        for name, t in territories.items()
    })

@pytest.mark.parametrize("territories,expected", [(0, 3), (2, 3), (9, 3), (11, 3), (12, 4), (14, 4), (42, 14)])
def test_base_reinforcements(territories, expected):
    assert calc_base_reinforcements(territories) == expected

def test_min_three(make_state, data_dir):
    state = make_state({"A": ("X", 0, 1, []), "B": ("X", 0, 1, []), "C": ("X", 1, 1, [])})
    assert calc_total_reinforcements(state, data_dir) == 3

def test_has_full_continent(make_state):
    state = make_state({"A": ("X", 0, 1, []), "B": ("X", 0, 1, []), "C": ("Y", 0, 1, []), "D": ("Y", 1, 1, [])})
    assert has_full_continent(state, 0, "X")
    assert not has_full_continent(state, 0, "Y")
    assert not has_full_continent(state, 1, "Y")
    assert not has_full_continent(state, 0, "Continente inexistente")

def test_continent_bonus_values(data_dir):
    assert continent_bonus_map(data_dir) == {
        "North America": 5, "Europe": 5, "Asia": 7, "South America": 2, "Africa": 3, "Australia": 2,
    }

def test_continent_bonus_added(south_america_vs_rest, data_dir):
    # 4 territórios -> base 3, mais 2 pela América do Sul
    assert calc_total_reinforcements(south_america_vs_rest, data_dir) == 5

def test_uses_current_player(south_america_vs_rest, data_dir):
    south_america_vs_rest.current_player_index = 1
    # 38 territórios -> base 12, mais 5 + 5 + 7 + 3 + 2 dos outros continentes
    assert calc_total_reinforcements(south_america_vs_rest, data_dir) == 34
