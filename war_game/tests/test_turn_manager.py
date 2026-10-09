import pytest
from war_game.rules.errors import RuleError
from war_game.services.turn_manager import TurnManager

@pytest.fixture
def tm(duel, data_dir):
    return TurnManager(duel, data_dir)

def test_start_turn_returns_reinforcements_and_resets_flag(tm):
    tm.state.conquered_this_turn = True
    assert tm.start_turn() == 3
    assert tm.state.conquered_this_turn is False

def test_place_reinforcements(tm):
    tm.place_reinforcements({"A": 3})
    assert tm.state.territories["A"].armies == 8

def test_place_on_enemy_territory(tm):
    with pytest.raises(RuleError):
        tm.place_reinforcements({"B": 1})

@pytest.mark.parametrize("count", [0, -5, "2", 1.5, True, None])
def test_place_invalid_count(tm, count):
    with pytest.raises(RuleError):
        tm.place_reinforcements({"A": count})
    assert tm.state.territories["A"].armies == 5

def test_invalid_placement_is_all_or_nothing(make_state, data_dir):
    state = make_state({"A": ("X", 0, 1, []), "B": ("X", 0, 1, []), "C": ("X", 1, 1, [])})
    tm = TurnManager(state, data_dir)
    with pytest.raises(RuleError):
        tm.place_reinforcements({"A": 2, "C": 1})
    assert state.territories["A"].armies == 1

def test_do_attack_unknown_target(tm):
    with pytest.raises(RuleError):
        tm.do_attack("A", "Atlantis", 1)

def test_end_turn_passes_to_next_player_and_wraps(tm):
    tm.end_turn()
    assert tm.state.current_player_index == 1
    tm.end_turn()
    assert tm.state.current_player_index == 0

def test_card_only_after_conquest(tm):
    tm.state.deck = ["c1", "c2"]
    tm.end_turn()
    assert tm.state.players[0].cards == []
    tm.state.conquered_this_turn = True
    tm.end_turn()
    assert tm.state.players[1].cards == ["c2"]
    assert tm.state.deck == ["c1"]

def test_no_card_when_deck_is_empty(tm):
    tm.state.conquered_this_turn = True
    tm.end_turn()
    assert tm.state.players[0].cards == []

def test_trade_cards_increments_progression(make_state, data_dir):
    state = make_state({"Peru": ("South America", 0, 1, []), "Egypt": ("Africa", 1, 1, [])})
    state.players[0].cards = ["c1", "c2", "c3", "c4", "c5", "c6"]
    tm = TurnManager(state, data_dir)
    assert tm.trade_cards_if_any() == 0
    assert tm.trade_cards_if_any(("c1", "c2", "c3")) == 4
    assert tm.trade_cards_if_any(("c4", "c5", "c6")) == 6
