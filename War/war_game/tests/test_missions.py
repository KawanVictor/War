from war_game.rules.missions import check_victory_by_mission

def test_mission_stub():
    assert check_victory_by_mission(None, 0) == False
