import pytest
from war_game.models.mission import Mission
from war_game.rules.missions import FALLBACK_TERRITORIES, check_victory_by_mission, is_mission_complete

@pytest.fixture
def world(make_state):
    # Jogador 0 domina X e Y; jogadores 1 e 2 dividem Z
    return make_state({
        "X1": ("X", 0, 2, []), "X2": ("X", 0, 2, []),
        "Y1": ("Y", 0, 1, []),
        "Z1": ("Z", 1, 1, []), "Z2": ("Z", 2, 1, []),
    }, num_players=3)

def test_no_missions_means_no_victory(world):
    assert check_victory_by_mission(world, 0) is False

def test_player_without_mission(world):
    world.missions = {1: Mission("Conquistar X", continents=["X"])}
    assert check_victory_by_mission(world, 0) is False

def test_continent_mission_complete(world):
    world.missions = {0: Mission("Conquistar X e Y", continents=["X", "Y"])}
    assert check_victory_by_mission(world, 0) is True

def test_continent_mission_incomplete(world):
    world.missions = {0: Mission("Conquistar X e Z", continents=["X", "Z"])}
    assert check_victory_by_mission(world, 0) is False

def test_extra_continent_of_choice(world):
    assert is_mission_complete(world, 0, Mission("X e mais um", continents=["X"], extra_continents=1))
    assert not is_mission_complete(world, 0, Mission("X e mais dois", continents=["X"], extra_continents=2))

def test_territory_count_mission(world):
    assert is_mission_complete(world, 0, Mission("3 territórios", territories_required=3))
    assert not is_mission_complete(world, 0, Mission("4 territórios", territories_required=4))

def test_territory_count_with_min_armies(world):
    assert is_mission_complete(world, 0, Mission("2 com 2 tropas", territories_required=2, min_armies=2))
    assert not is_mission_complete(world, 0, Mission("3 com 2 tropas", territories_required=3, min_armies=2))

def test_destroy_mission(world):
    mission = Mission("Destruir o azul", target_color="blue")
    assert not is_mission_complete(world, 0, mission)
    world.territories["Z1"].owner_id = 2
    world.players[1].territories.clear()
    world.players[2].territories.add("Z1")
    assert is_mission_complete(world, 0, mission)

def test_destroy_own_color_falls_back_to_territory_count(make_state):
    spec = {f"T{i}": ("X", 0, 1, []) for i in range(FALLBACK_TERRITORIES - 1)}
    spec["E"] = ("X", 1, 1, [])
    state = make_state(spec)
    mission = Mission("Destruir o vermelho", target_color="red")
    assert not is_mission_complete(state, 0, mission)
    state.territories["E"].owner_id = 0
    state.players[1].territories.clear()
    state.players[0].territories.add("E")
    assert is_mission_complete(state, 0, mission)

def test_destroy_color_not_in_game_falls_back(world):
    assert not is_mission_complete(world, 0, Mission("Destruir o preto", target_color="black"))
