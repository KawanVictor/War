import json
import random
import pytest
from war_game.rules import combat
from war_game.rules.errors import RuleError
from war_game.services import bot
from war_game.services.serialization import state_from_json, state_to_json
from war_game.services.setup import new_game
from war_game.services.turn_manager import TurnManager

def attacker_always_wins(monkeypatch):
    monkeypatch.setattr(combat, "roll_dice", lambda num: [6] * num if num != 1 else [1])

def ready_to_attack(tm, territory):
    reinf = tm.start_turn()
    tm.place_reinforcements({territory: reinf})

# --- primeira rodada ---

def test_new_game_starts_with_a_placement_only_round(data_dir):
    state = new_game(data_dir, 4)
    assert state.setup_turns_left == 4
    tm = TurnManager(state, data_dir)
    assert tm.in_setup_round()

def test_no_attack_or_fortify_in_the_setup_round(make_state, data_dir):
    state = make_state({"A": ("X", 0, 5, ["B"]), "B": ("X", 1, 3, ["A"])})
    state.setup_turns_left = 2
    tm = TurnManager(state, data_dir)
    ready_to_attack(tm, "A")
    with pytest.raises(RuleError):
        tm.do_attack("A", "B", 3)
    with pytest.raises(RuleError):
        tm.begin_fortify()
    tm.end_turn()
    assert state.setup_turns_left == 1 and state.current_player_index == 1
    ready_to_attack(tm, "B")
    tm.end_turn()
    assert state.setup_turns_left == 0 and not tm.in_setup_round()
    ready_to_attack(tm, "A")
    tm.do_attack("A", "B", 3)  # a partir da segunda rodada o ataque é permitido

# --- baralho e troca obrigatória ---

def test_deck_has_one_card_per_territory_plus_two_wilds(data_dir):
    cards = json.loads((data_dir / "cards.json").read_text(encoding="utf-8"))
    state = new_game(data_dir, 3)
    assert len(cards) == 44 and len(state.deck) == 44
    assert sorted(c["territory"] for c in cards if c["territory"]) == sorted(state.territories)
    icons = [c["icon"] for c in cards]
    assert {i: icons.count(i) for i in set(icons)} == {"infantry": 14, "cavalry": 14, "artillery": 14, "wild": 2}

@pytest.fixture
def holder(make_state, data_dir):
    state = make_state({"Peru": ("South America", 0, 1, []), "Venezuela": ("South America", 1, 1, [])})
    return TurnManager(state, data_dir)

def test_four_cards_do_not_force_a_trade(holder):
    holder.state.players[0].cards = ["c1", "c2", "c3", "c4"]
    holder.start_turn()
    assert not holder.must_trade()
    holder.place_reinforcements({"Peru": 3})

def test_five_cards_force_a_trade_before_placing(holder):
    holder.state.players[0].cards = ["c1", "c2", "c3", "c4", "c7"]
    holder.start_turn()
    assert holder.must_trade()
    with pytest.raises(RuleError):
        holder.place_reinforcements({"Peru": 1})
    assert holder.state.territories["Peru"].armies == 1
    holder.trade_cards_if_any(("c1", "c2", "c3"))
    assert not holder.must_trade()
    holder.place_reinforcements({"Peru": holder.state.reinforcements_left})
    assert holder.state.phase == "attacking"

# --- ocupação depois da conquista ---

@pytest.fixture
def conqueror(make_state, data_dir, monkeypatch):
    """A (jogador 0, 9 tropas após os reforços) conquista B com 2 dados; C mantém o jogador 1 vivo."""
    state = make_state({
        "A": ("X", 0, 6, ["B"]),
        "B": ("X", 1, 1, ["A", "C"]),
        "C": ("X", 1, 2, ["B"]),
    })
    tm = TurnManager(state, data_dir)
    attacker_always_wins(monkeypatch)
    ready_to_attack(tm, "A")
    return tm

def test_no_conquest_nothing_to_occupy(conqueror):
    assert conqueror.max_occupy() == 0
    with pytest.raises(RuleError):
        conqueror.occupy(1)

def test_occupy_moves_extra_armies(conqueror):
    tm = conqueror
    tm.do_attack("A", "B", 2)
    assert tm.state.conquest == {"from": "A", "to": "B"}
    assert (tm.state.territories["A"].armies, tm.state.territories["B"].armies) == (7, 2)
    assert tm.max_occupy() == 6
    tm.occupy(4)
    assert (tm.state.territories["A"].armies, tm.state.territories["B"].armies) == (3, 6)
    assert tm.max_occupy() == 2
    tm.occupy(2)
    assert tm.state.territories["A"].armies == 1
    with pytest.raises(RuleError):
        tm.occupy(1)

@pytest.mark.parametrize("count", [0, -1, 7, "2", 1.5, True, None])
def test_invalid_occupy(conqueror, count):
    conqueror.do_attack("A", "B", 2)
    with pytest.raises(RuleError):
        conqueror.occupy(count)
    assert conqueror.state.territories["A"].armies == 7

def test_occupy_window_closes_on_the_next_action(conqueror, monkeypatch):
    tm = conqueror
    tm.do_attack("A", "B", 2)
    monkeypatch.setattr(combat, "roll_dice", lambda num: [1] * num if num != 2 else [6, 6])
    tm.do_attack("B", "C", 1)  # ataque que não conquista
    assert tm.state.conquest is None
    with pytest.raises(RuleError):
        tm.occupy(1)

def test_occupy_window_closes_when_fortify_or_turn_ends(conqueror):
    tm = conqueror
    tm.do_attack("A", "B", 2)
    tm.begin_fortify()
    assert tm.state.conquest is None
    with pytest.raises(RuleError):
        tm.occupy(1)
    tm.end_turn()
    assert tm.state.conquest is None

# --- salvar e carregar ---

def test_state_survives_a_json_roundtrip_mid_turn(data_dir, monkeypatch):
    random.seed(3)
    state = new_game(data_dir, 4)
    state.setup_turns_left = 0
    tm = TurnManager(state, data_dir)
    state.players[0].cards = ["c1", "c2", "c3"]
    tm.start_turn()
    tm.trade_cards_if_any(("c1", "c2", "c3"))
    src = next(t for t in sorted(state.players[0].territories)
               if any(state.territories[n].owner_id != 0 for n in state.territories[t].neighbors))
    dst = next(n for n in sorted(state.territories[src].neighbors) if state.territories[n].owner_id != 0)
    tm.place_reinforcements({src: state.reinforcements_left})
    attacker_always_wins(monkeypatch)
    tm.do_attack(src, dst, 3)

    data = json.loads(json.dumps(state_to_json(state)))
    copy = state_from_json(data)
    assert state_to_json(copy) == state_to_json(state)
    assert copy.conquest == {"from": src, "to": dst} and copy.trades_done == 1
    assert copy.territories[dst].owner_id == 0 and dst in copy.players[0].territories
    assert copy.missions[2].description == state.missions[2].description
    assert copy.territories[src].label == state.territories[src].label

    # a cópia continua a partida de onde parou
    tm2 = TurnManager(copy, data_dir)
    tm2.occupy(tm2.max_occupy())
    tm2.begin_fortify()
    assert copy.movable
    tm2.end_turn()
    assert copy.current_player_index == 1 and len(copy.players[0].cards) == 1

def test_unknown_save_version_is_rejected(data_dir):
    data = state_to_json(new_game(data_dir, 2))
    data["version"] = 999
    with pytest.raises(ValueError):
        state_from_json(data)

# --- computador ---

def test_bot_turn_in_setup_round_only_places(data_dir):
    random.seed(1)
    state = new_game(data_dir, 3)
    tm = TurnManager(state, data_dir)
    before = sum(t.armies for t in state.territories.values())
    log = bot.play_turn(tm)
    assert log == []
    assert sum(t.armies for t in state.territories.values()) == before + 4
    assert state.current_player_index == 1 and state.phase == "waiting"
    assert [len(p.territories) for p in state.players] == [14, 14, 14]

def test_bot_trades_when_it_can(make_state, data_dir):
    state = make_state({"Peru": ("South America", 0, 1, ["Venezuela"]), "Venezuela": ("South America", 1, 9, ["Peru"])})
    state.players[0].cards = ["c1", "c2", "c3", "c4", "c7"]
    tm = TurnManager(state, data_dir)
    bot.play_turn(tm)
    assert state.players[0].cards == ["c4", "c7"]
    assert state.territories["Peru"].armies == 1 + 3 + 4
    assert state.current_player_index == 1

def test_bot_attacks_with_advantage_and_fortifies(make_state, data_dir, monkeypatch):
    # Interior (I) cercado só por aliados, fronteira (F) ao lado de um inimigo fraco (E); Z mantém o inimigo vivo
    state = make_state({
        "I": ("X", 0, 6, ["F"]),
        "F": ("X", 0, 4, ["I", "E"]),
        "E": ("X", 1, 1, ["F", "Z"]),
        "Z": ("X", 1, 30, ["E"]),
    })
    tm = TurnManager(state, data_dir)
    attacker_always_wins(monkeypatch)
    log = bot.play_turn(tm)
    assert [(a["from"], a["to"], a["conquered"]) for a in log] == [("F", "E", True)]
    assert state.territories["E"].owner_id == 0
    assert state.territories["I"].armies == 1  # as tropas do interior foram para a fronteira
    assert state.current_player_index == 1 and state.winner_id is None

@pytest.mark.parametrize("seed", range(8))
def test_bots_finish_a_whole_game(data_dir, seed):
    random.seed(seed)
    state = new_game(data_dir, 2 + seed % 5)
    tm = TurnManager(state, data_dir)
    for _ in range(1500):
        if state.winner_id is not None:
            break
        player = state.current_player()
        assert player.alive and player.territories
        bot.play_turn(tm)
        assert all(t.armies >= 1 for t in state.territories.values())
        assert len(state.deck) + len(state.discard) + sum(len(p.cards) for p in state.players) == 44
    assert state.winner_id is not None

# --- computador assumindo um turno em andamento ---

@pytest.fixture
def midgame(make_state, data_dir):
    state = make_state({
        "A": ("X", 0, 3, ["B"]),
        "B": ("X", 1, 9, ["A", "C"]),
        "C": ("X", 1, 9, ["B"]),
    })
    return TurnManager(state, data_dir)

def test_bot_continues_from_the_placement_phase(midgame):
    tm = midgame
    tm.start_turn()
    tm.place_reinforcements({"A": 1})
    left = tm.state.reinforcements_left
    bot.play_turn(tm)
    assert tm.state.territories["A"].armies == 3 + 1 + left
    assert tm.state.current_player_index == 1 and tm.state.phase == "waiting"

def test_bot_continues_from_the_attack_phase(midgame):
    tm = midgame
    ready_to_attack(tm, "A")
    armies = tm.state.territories["A"].armies
    assert bot.play_turn(tm) == []  # sem vantagem, não ataca
    assert tm.state.territories["A"].armies == armies
    assert tm.state.current_player_index == 1

def test_bot_continues_from_the_fortify_phase(midgame):
    tm = midgame
    ready_to_attack(tm, "A")
    tm.begin_fortify()
    assert bot.play_turn(tm) == []
    assert tm.state.current_player_index == 1 and tm.state.phase == "waiting"
