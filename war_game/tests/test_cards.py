import pytest
from war_game.rules.cards import can_redeem_set, next_trade_value, redeem_cards

DEFS = {
    "i1": {"icon": "infantry"}, "i2": {"icon": "infantry"}, "i3": {"icon": "infantry"},
    "c1": {"icon": "cavalry"}, "c2": {"icon": "cavalry"},
    "a1": {"icon": "artillery"},
    "w1": {"icon": "wild"},
}

@pytest.mark.parametrize("trades,expected", [(0, 4), (1, 6), (2, 8), (3, 10), (4, 12), (5, 15), (6, 20), (7, 25)])
def test_trade_value_progression(trades, expected):
    assert next_trade_value(trades) == expected

def test_three_of_a_kind():
    assert can_redeem_set(["i1", "i2", "i3"], DEFS) == [("i1", "i2", "i3")]

def test_one_of_each():
    assert can_redeem_set(["i1", "c1", "a1"], DEFS) == [("i1", "c1", "a1")]

def test_two_plus_one_is_not_a_set():
    assert can_redeem_set(["i1", "i2", "c1"], DEFS) == []

def test_wild_completes_any_set():
    assert can_redeem_set(["i1", "i2", "w1"], DEFS) == [("i1", "i2", "w1")]
    assert can_redeem_set(["i1", "c1", "w1"], DEFS) == [("i1", "c1", "w1")]

def test_fewer_than_three_cards():
    assert can_redeem_set(["i1", "i2"], DEFS) == []

def test_all_combos_listed():
    assert can_redeem_set(["i1", "i2", "i3", "c1"], DEFS) == [("i1", "i2", "i3")]
    combos = can_redeem_set(["i1", "c1", "c2", "a1"], DEFS)
    assert set(combos) == {("i1", "c1", "a1"), ("i1", "c2", "a1")}

def test_redeem_moves_cards_to_discard(make_state, data_dir):
    state = make_state({"Peru": ("South America", 0, 1, []), "Egypt": ("Africa", 1, 1, [])})
    state.players[0].cards = ["c1", "c2", "c3", "c4"]  # Alaska, Alberta, Ontario, Brazil
    value = redeem_cards(state, data_dir, ("c1", "c2", "c3"), trades_done=0)
    assert value == 4
    assert state.players[0].cards == ["c4"]
    assert state.discard == ["c1", "c2", "c3"]
    assert state.territories["Peru"].armies == 1

def test_redeem_bonus_for_owned_territory_applies_once(make_state, data_dir):
    state = make_state({
        "Alaska": ("North America", 0, 1, []),
        "Alberta": ("North America", 0, 1, []),
        "Egypt": ("Africa", 1, 1, []),
    })
    state.players[0].cards = ["c1", "c2", "c3"]
    value = redeem_cards(state, data_dir, ("c1", "c2", "c3"), trades_done=2)
    assert value == 8
    assert state.territories["Alaska"].armies == 3
    assert state.territories["Alberta"].armies == 1

def test_redeem_card_not_in_hand(make_state, data_dir):
    state = make_state({"Peru": ("South America", 0, 1, []), "Egypt": ("Africa", 1, 1, [])})
    state.players[0].cards = ["c1", "c2"]
    with pytest.raises(ValueError):
        redeem_cards(state, data_dir, ("c1", "c2", "c3"), trades_done=0)
