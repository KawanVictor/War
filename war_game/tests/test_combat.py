from war_game.rules.combat import resolve_battle

def test_defender_wins_ties():
    la, ld = resolve_battle([5, 2], [5, 2])
    assert la == 2 and ld == 0
