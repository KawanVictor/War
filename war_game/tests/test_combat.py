import pytest
from war_game.rules import combat
from war_game.rules.combat import attack_once, max_attack_dice, max_defend_dice, resolve_battle, roll_dice
from war_game.rules.errors import RuleError

def fixed_rolls(monkeypatch, *rolls):
    it = iter(rolls)
    monkeypatch.setattr(combat, "roll_dice", lambda num: next(it))

def test_defender_wins_ties():
    la, ld = resolve_battle([5, 2], [5, 2])
    assert la == 2 and ld == 0

def test_attacker_wins_higher_rolls():
    assert resolve_battle([6, 4, 1], [5, 3]) == (0, 2)

def test_split_result():
    assert resolve_battle([6, 2], [5, 4]) == (1, 1)

def test_only_paired_dice_are_compared():
    assert resolve_battle([6, 6, 6], [1]) == (0, 1)

@pytest.mark.parametrize("armies,expected", [(1, 0), (2, 1), (3, 2), (4, 3), (10, 3)])
def test_max_attack_dice(armies, expected):
    assert max_attack_dice(armies) == expected

@pytest.mark.parametrize("armies,expected", [(1, 1), (2, 2), (7, 2)])
def test_max_defend_dice(armies, expected):
    assert max_defend_dice(armies) == expected

def test_roll_dice_sorted_and_in_range():
    for _ in range(50):
        rolls = roll_dice(3)
        assert len(rolls) == 3
        assert rolls == sorted(rolls, reverse=True)
        assert all(1 <= r <= 6 for r in rolls)

def test_attack_conquers_and_moves_armies(duel, monkeypatch):
    fixed_rolls(monkeypatch, [6, 5, 4], [1])
    result = attack_once(duel, "A", "B", 3, 1)
    assert result["conquered"] is True
    assert duel.territories["B"].owner_id == 0
    assert duel.territories["B"].armies == 3
    assert duel.territories["A"].armies == 2
    assert duel.players[0].territories == {"A", "B"}
    assert duel.players[1].territories == set()
    assert duel.conquered_this_turn is True

def test_failed_attack_costs_attacker(duel, monkeypatch):
    fixed_rolls(monkeypatch, [3, 2], [6])
    result = attack_once(duel, "A", "B", 2, 1)
    assert result["conquered"] is False
    assert result["losses_attacker"] == 1
    assert duel.territories["A"].armies == 4
    assert duel.territories["B"].owner_id == 1
    assert duel.conquered_this_turn is False

def test_conquest_always_leaves_one_army_behind(make_state, monkeypatch):
    state = make_state({"A": ("X", 0, 2, ["B"]), "B": ("X", 1, 1, ["A"])})
    fixed_rolls(monkeypatch, [6], [1])
    attack_once(state, "A", "B", 1, 1)
    assert state.territories["A"].armies == 1
    assert state.territories["B"].armies == 1

def test_cannot_attack_from_enemy_territory(duel):
    with pytest.raises(RuleError):
        attack_once(duel, "B", "A", 1, 2)

def test_cannot_attack_own_territory(make_state):
    state = make_state({"A": ("X", 0, 5, ["B"]), "B": ("X", 0, 1, ["A"]), "C": ("X", 1, 1, [])})
    with pytest.raises(RuleError):
        attack_once(state, "A", "B", 1, 1)

def test_cannot_attack_non_neighbor(make_state):
    state = make_state({"A": ("X", 0, 5, []), "B": ("X", 1, 1, [])})
    with pytest.raises(RuleError):
        attack_once(state, "A", "B", 1, 1)

def test_unknown_territory(duel):
    with pytest.raises(RuleError):
        attack_once(duel, "A", "Atlantis", 1, 1)

@pytest.mark.parametrize("dice", [0, -1, 4])
def test_invalid_attack_dice(duel, dice):
    with pytest.raises(RuleError):
        attack_once(duel, "A", "B", dice, 1)

def test_too_many_dice_for_armies(make_state):
    state = make_state({"A": ("X", 0, 2, ["B"]), "B": ("X", 1, 1, ["A"])})
    with pytest.raises(RuleError):
        attack_once(state, "A", "B", 2, 1)

def test_invalid_defend_dice(duel):
    with pytest.raises(RuleError):
        attack_once(duel, "A", "B", 1, 2)

def test_invalid_attack_does_not_change_state(duel):
    with pytest.raises(RuleError):
        attack_once(duel, "A", "B", 4, 1)
    assert duel.territories["A"].armies == 5
    assert duel.territories["B"].armies == 1
