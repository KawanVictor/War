import pytest
from war_game.models.mission import Mission
from war_game.rules.errors import RuleError
from war_game.services.turn_manager import TurnManager

@pytest.fixture
def tm(make_state, data_dir):
    """Jogador 0 tem A(5) - B(1) - C(3) em linha; D é do jogador 1 e vizinho de C."""
    state = make_state({
        "A": ("X", 0, 5, ["B"]),
        "B": ("X", 0, 1, ["A", "C"]),
        "C": ("X", 0, 3, ["B", "D"]),
        "D": ("X", 1, 2, ["C"]),
    })
    tm = TurnManager(state, data_dir)
    reinf = tm.start_turn()
    tm.place_reinforcements({"A": reinf})  # A fica com 5 + 4 pelo continente... conferido abaixo
    return tm

def armies(tm):
    return {n: t.armies for n, t in tm.state.territories.items()}

def test_fixture_starts_in_attack_phase(tm):
    assert tm.state.phase == "attacking"
    assert armies(tm) == {"A": 8, "B": 1, "C": 3, "D": 2}

def test_fortify_requires_begin(tm):
    with pytest.raises(RuleError):
        tm.fortify("A", "B", 1)
    assert armies(tm)["A"] == 8

def test_begin_fortify_only_from_attack_phase(make_state, data_dir):
    state = make_state({"A": ("X", 0, 5, ["B"]), "B": ("X", 1, 1, ["A"])})
    tm = TurnManager(state, data_dir)
    with pytest.raises(RuleError):
        tm.begin_fortify()
    tm.start_turn()
    with pytest.raises(RuleError):
        tm.begin_fortify()

def test_fortify_moves_armies(tm):
    tm.begin_fortify()
    assert tm.state.phase == "fortifying"
    tm.fortify("A", "B", 3)
    assert armies(tm) == {"A": 5, "B": 4, "C": 3, "D": 2}

def test_must_leave_one_army_behind(tm):
    tm.begin_fortify()
    assert tm.max_fortify("A") == 7
    with pytest.raises(RuleError):
        tm.fortify("A", "B", 8)
    tm.fortify("A", "B", 7)
    assert armies(tm)["A"] == 1
    assert tm.max_fortify("A") == 0
    with pytest.raises(RuleError):
        tm.fortify("A", "B", 1)

def test_territory_with_one_army_cannot_move(tm):
    tm.begin_fortify()
    assert tm.max_fortify("B") == 0
    with pytest.raises(RuleError):
        tm.fortify("B", "A", 1)

def test_each_army_moves_only_once(tm):
    tm.begin_fortify()
    tm.fortify("A", "B", 4)
    # B tinha 1 tropa no início: as 4 que chegaram não podem seguir para C
    assert tm.max_fortify("B") == 1
    tm.fortify("B", "C", 1)
    with pytest.raises(RuleError):
        tm.fortify("B", "C", 1)
    assert armies(tm) == {"A": 4, "B": 4, "C": 4, "D": 2}

def test_moved_out_armies_reduce_what_is_left_to_move(tm):
    tm.begin_fortify()
    tm.fortify("C", "B", 2)
    assert tm.max_fortify("C") == 0
    tm.fortify("A", "B", 2)
    assert tm.max_fortify("A") == 5

def test_cannot_fortify_to_non_neighbor(tm):
    tm.begin_fortify()
    with pytest.raises(RuleError):
        tm.fortify("A", "C", 1)

def test_cannot_fortify_to_or_from_enemy(tm):
    tm.begin_fortify()
    with pytest.raises(RuleError):
        tm.fortify("C", "D", 1)
    with pytest.raises(RuleError):
        tm.fortify("D", "C", 1)

def test_unknown_territory(tm):
    tm.begin_fortify()
    with pytest.raises(RuleError):
        tm.fortify("A", "Atlantis", 1)
    with pytest.raises(RuleError):
        tm.fortify("Atlantis", "A", 1)

@pytest.mark.parametrize("count", [0, -2, "1", 1.5, True, None])
def test_invalid_count(tm, count):
    tm.begin_fortify()
    with pytest.raises(RuleError):
        tm.fortify("A", "B", count)
    assert armies(tm)["A"] == 8

def test_no_attack_after_fortify_begins(tm):
    tm.begin_fortify()
    with pytest.raises(RuleError):
        tm.do_attack("C", "D", 1)

def test_end_turn_from_fortify_phase(tm):
    tm.begin_fortify()
    tm.fortify("A", "B", 1)
    tm.end_turn()
    assert tm.state.current_player_index == 1
    assert tm.state.phase == "waiting"
    assert tm.max_fortify("A") == 0

def test_movable_is_reset_each_turn(tm):
    tm.begin_fortify()
    tm.fortify("A", "B", 7)
    tm.end_turn()
    reinf = tm.start_turn()
    tm.place_reinforcements({"D": reinf})
    tm.end_turn()
    reinf = tm.start_turn()
    tm.place_reinforcements({"C": reinf})
    tm.begin_fortify()
    assert tm.max_fortify("B") == 7

def test_fortify_can_complete_a_mission(tm):
    tm.state.missions = {0: Mission("3 territórios com 2 tropas", territories_required=3, min_armies=2)}
    tm.begin_fortify()
    assert tm.state.winner_id is None
    tm.fortify("A", "B", 1)
    assert tm.state.winner_id == 0
