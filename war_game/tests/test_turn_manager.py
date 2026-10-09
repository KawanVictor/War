import pytest
from war_game.models.mission import Mission
from war_game.rules import combat
from war_game.rules.errors import RuleError
from war_game.services.turn_manager import TurnManager

def attacker_always_wins(monkeypatch):
    monkeypatch.setattr(combat, "roll_dice", lambda num: [6] * num if num != 1 else [1])

@pytest.fixture
def tm(duel, data_dir):
    return TurnManager(duel, data_dir)

@pytest.fixture
def three_players(make_state, data_dir):
    """Jogador 0 forte em A, vizinho de B (jogador 1) e C (jogador 2), com um território de 1 tropa cada."""
    state = make_state({
        "A": ("X", 0, 10, ["B", "C"]),
        "B": ("X", 1, 1, ["A"]),
        "C": ("X", 2, 1, ["A"]),
    }, num_players=3)
    return TurnManager(state, data_dir)

def ready_to_attack(tm):
    reinf = tm.start_turn()
    tm.place_reinforcements({next(iter(sorted(tm.state.current_player().territories))): reinf})

# --- fases do turno ---

def test_start_turn_sets_phase_and_reinforcements(tm):
    tm.state.conquered_this_turn = True
    assert tm.start_turn() == 3
    assert tm.state.conquered_this_turn is False
    assert tm.state.phase == "placing"
    assert tm.state.reinforcements_left == 3

def test_cannot_start_turn_twice(tm):
    tm.start_turn()
    with pytest.raises(RuleError):
        tm.start_turn()
    assert tm.state.reinforcements_left == 3

def test_cannot_place_before_starting_turn(tm):
    with pytest.raises(RuleError):
        tm.place_reinforcements({"A": 1})
    assert tm.state.territories["A"].armies == 5

def test_place_reinforcements_in_steps(tm):
    tm.start_turn()
    tm.place_reinforcements({"A": 2})
    assert tm.state.territories["A"].armies == 7
    assert tm.state.reinforcements_left == 1
    assert tm.state.phase == "placing"
    tm.place_reinforcements({"A": 1})
    assert tm.state.reinforcements_left == 0
    assert tm.state.phase == "attacking"

def test_cannot_place_more_than_available(tm):
    tm.start_turn()
    with pytest.raises(RuleError):
        tm.place_reinforcements({"A": 4})
    assert tm.state.territories["A"].armies == 5
    assert tm.state.reinforcements_left == 3

def test_cannot_place_after_all_reinforcements_used(tm):
    ready_to_attack(tm)
    with pytest.raises(RuleError):
        tm.place_reinforcements({"A": 1})

def test_place_on_enemy_territory(tm):
    tm.start_turn()
    with pytest.raises(RuleError):
        tm.place_reinforcements({"B": 1})

@pytest.mark.parametrize("count", [0, -5, "2", 1.5, True, None])
def test_place_invalid_count(tm, count):
    tm.start_turn()
    with pytest.raises(RuleError):
        tm.place_reinforcements({"A": count})
    assert tm.state.territories["A"].armies == 5

def test_invalid_placement_is_all_or_nothing(make_state, data_dir):
    state = make_state({"A": ("X", 0, 1, []), "B": ("X", 0, 1, []), "C": ("X", 1, 1, [])})
    tm = TurnManager(state, data_dir)
    tm.start_turn()
    with pytest.raises(RuleError):
        tm.place_reinforcements({"A": 2, "C": 1})
    assert state.territories["A"].armies == 1
    assert state.reinforcements_left == 3

def test_cannot_attack_before_placing_everything(tm):
    with pytest.raises(RuleError):
        tm.do_attack("A", "B", 1)
    tm.start_turn()
    tm.place_reinforcements({"A": 1})
    with pytest.raises(RuleError):
        tm.do_attack("A", "B", 1)

def test_cannot_end_turn_before_placing_everything(tm):
    with pytest.raises(RuleError):
        tm.end_turn()
    tm.start_turn()
    with pytest.raises(RuleError):
        tm.end_turn()
    assert tm.state.current_player_index == 0

def test_do_attack_unknown_target(tm):
    ready_to_attack(tm)
    with pytest.raises(RuleError):
        tm.do_attack("A", "Atlantis", 1)

def test_end_turn_passes_to_next_player_and_wraps(tm):
    ready_to_attack(tm)
    tm.end_turn()
    assert tm.state.current_player_index == 1
    assert tm.state.phase == "waiting"
    ready_to_attack(tm)
    tm.end_turn()
    assert tm.state.current_player_index == 0

# --- cartas ---

def test_card_only_after_conquest(tm):
    tm.state.deck = ["c1", "c2"]
    ready_to_attack(tm)
    tm.end_turn()
    assert tm.state.players[0].cards == []
    ready_to_attack(tm)
    tm.state.conquered_this_turn = True
    tm.end_turn()
    assert tm.state.players[1].cards == ["c2"]
    assert tm.state.deck == ["c1"]

def test_no_card_when_deck_and_discard_are_empty(tm):
    ready_to_attack(tm)
    tm.state.conquered_this_turn = True
    tm.end_turn()
    assert tm.state.players[0].cards == []

def test_discard_is_reshuffled_into_empty_deck(tm):
    tm.state.discard = ["c1", "c2", "c3"]
    ready_to_attack(tm)
    tm.state.conquered_this_turn = True
    tm.end_turn()
    assert len(tm.state.players[0].cards) == 1
    assert tm.state.discard == []
    assert sorted(tm.state.deck + tm.state.players[0].cards) == ["c1", "c2", "c3"]

@pytest.fixture
def trader(make_state, data_dir):
    state = make_state({"Peru": ("South America", 0, 1, []), "Venezuela": ("South America", 1, 1, [])})
    state.players[0].cards = ["c1", "c2", "c3", "c4", "c5", "c6"]
    return TurnManager(state, data_dir)

def test_trade_adds_reinforcements_and_increments_progression(trader):
    trader.start_turn()
    assert trader.trade_cards_if_any() == 0
    assert trader.trade_cards_if_any(("c1", "c2", "c3")) == 4
    assert trader.state.reinforcements_left == 3 + 4
    assert trader.trade_cards_if_any(("c4", "c5", "c6")) == 6
    assert trader.state.reinforcements_left == 3 + 4 + 6
    assert trader.state.players[0].cards == []

def test_trade_only_during_placement(trader):
    with pytest.raises(RuleError):
        trader.trade_cards_if_any(("c1", "c2", "c3"))
    assert len(trader.state.players[0].cards) == 6

@pytest.mark.parametrize("chosen", [
    ("c1", "c2"),          # menos de 3 cartas
    ("c1", "c1", "c1"),    # a mesma carta repetida
    ("c1", "c2", "c9"),    # carta que não está na mão
    ("c1", "c4", "c2"),    # dois iguais e um diferente
])
def test_invalid_trade(trader, chosen):
    trader.start_turn()
    with pytest.raises(RuleError):
        trader.trade_cards_if_any(chosen)
    assert len(trader.state.players[0].cards) == 6
    assert trader.state.reinforcements_left == 3
    assert trader.trades_done == 0

# --- eliminação e vitória ---

def test_elimination_marks_player_and_transfers_cards(three_players, monkeypatch):
    tm = three_players
    tm.state.players[1].cards = ["c1", "c2"]
    attacker_always_wins(monkeypatch)
    ready_to_attack(tm)
    result = tm.do_attack("A", "B", 3)
    assert result["eliminated"] == 1
    assert tm.state.players[1].alive is False
    assert tm.state.players[1].eliminated_by == 0
    assert tm.state.players[1].cards == []
    assert tm.state.players[0].cards == ["c1", "c2"]
    assert tm.state.winner_id is None

def test_eliminated_player_is_skipped(three_players, monkeypatch):
    tm = three_players
    attacker_always_wins(monkeypatch)
    ready_to_attack(tm)
    tm.do_attack("A", "B", 3)
    tm.end_turn()
    assert tm.state.current_player_index == 2

def test_conquest_without_elimination(make_state, data_dir, monkeypatch):
    state = make_state({"A": ("X", 0, 5, ["B"]), "B": ("X", 1, 1, ["A"]), "C": ("X", 1, 1, [])})
    tm = TurnManager(state, data_dir)
    attacker_always_wins(monkeypatch)
    ready_to_attack(tm)
    result = tm.do_attack("A", "B", 3)
    assert result["conquered"] is True
    assert result["eliminated"] is None
    assert state.players[1].alive is True
    assert state.winner_id is None

def test_last_player_standing_wins(tm, monkeypatch):
    attacker_always_wins(monkeypatch)
    ready_to_attack(tm)
    tm.do_attack("A", "B", 3)
    assert tm.state.winner_id == 0

def test_no_actions_after_game_over(tm, monkeypatch):
    attacker_always_wins(monkeypatch)
    ready_to_attack(tm)
    tm.do_attack("A", "B", 3)
    for action in (tm.start_turn, tm.end_turn, lambda: tm.do_attack("B", "A", 1), lambda: tm.place_reinforcements({"A": 1})):
        with pytest.raises(RuleError):
            action()

def test_mission_completed_by_conquest_wins(three_players, monkeypatch):
    tm = three_players
    tm.state.missions = {0: Mission("2 territórios", territories_required=2)}
    attacker_always_wins(monkeypatch)
    ready_to_attack(tm)
    assert tm.state.winner_id is None
    tm.do_attack("A", "B", 3)
    assert tm.state.winner_id == 0

def test_mission_completed_by_placement_wins(tm):
    tm.state.missions = {0: Mission("1 território com 8 tropas", territories_required=1, min_armies=8)}
    tm.start_turn()
    tm.place_reinforcements({"A": 2})
    assert tm.state.winner_id is None
    tm.place_reinforcements({"A": 1})
    assert tm.state.winner_id == 0

def test_destroy_mission_wins_on_elimination(three_players, monkeypatch):
    tm = three_players
    tm.state.missions = {0: Mission("Destruir o azul", target_color="blue")}
    attacker_always_wins(monkeypatch)
    ready_to_attack(tm)
    tm.do_attack("A", "B", 3)
    assert tm.state.winner_id == 0
