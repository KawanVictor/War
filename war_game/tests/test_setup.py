import pytest
from war_game.rules.errors import RuleError
from war_game.services.setup import new_game

@pytest.mark.parametrize("num_players", [2, 3, 4, 5, 6])
def test_new_game_distributes_everything(data_dir, num_players):
    state = new_game(data_dir, num_players)
    assert len(state.players) == num_players
    assert len({p.color for p in state.players}) == num_players
    owned = [t for p in state.players for t in p.territories]
    assert sorted(owned) == sorted(state.territories)
    sizes = [len(p.territories) for p in state.players]
    assert max(sizes) - min(sizes) <= 1
    for p in state.players:
        assert all(state.territories[t].owner_id == p.id for t in p.territories)
    assert all(t.armies == 1 for t in state.territories.values())
    assert state.phase == "waiting" and state.winner_id is None

def test_each_player_gets_a_different_mission(data_dir):
    state = new_game(data_dir, 6)
    assert set(state.missions) == {0, 1, 2, 3, 4, 5}
    assert len({m.description for m in state.missions.values()}) == 6

@pytest.mark.parametrize("num_players", [0, 1, 7, -1, "3", 2.5, None])
def test_invalid_number_of_players(data_dir, num_players):
    with pytest.raises(RuleError):
        new_game(data_dir, num_players)
