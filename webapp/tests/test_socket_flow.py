import itertools
import pytest
from war_game.rules import combat
from webapp.app import app, socketio
from webapp.rooms import rooms

_room_ids = (f"sala-teste-{i}" for i in itertools.count())

def events(client):
    out = []
    for e in client.get_received():
        args = e["args"]
        out.append((e["name"], args[0] if isinstance(args, list) else args))
    return out

def last(client, name):
    found = [data for n, data in events(client) if n == name]
    assert found, f"evento {name} não recebido"
    return found[-1]

def only_error(client):
    """O cliente recebeu só uma mensagem de erro, sem mudança de estado."""
    return [n for n, _ in events(client)] == ["message"]

@pytest.fixture
def game():
    room = next(_room_ids)
    a, b = socketio.test_client(app), socketio.test_client(app)
    a.emit("join", {"roomId": room, "numPlayers": 3})
    state = last(a, "state")
    b.emit("join", {"roomId": room, "numPlayers": 3})
    events(a), events(b)
    yield room, a, b, state
    a.disconnect()
    b.disconnect()

def own_and_enemy_neighbor(state, player_id):
    for name in state["players"][player_id]["territories"]:
        for n in state["territories"][name]["neighbors"]:
            if state["territories"][n]["ownerId"] != player_id:
                return name, n
    raise AssertionError("jogador sem fronteira inimiga")

def start_and_place_all(room, client, territory):
    client.emit("start_turn", {"roomId": room})
    reinf = last(client, "turn_started")["reinforcements"]
    client.emit("place", {"roomId": room, "placements": {territory: reinf}})
    return last(client, "state")

def test_index_page_loads():
    resp = app.test_client().get("/")
    assert resp.status_code == 200
    assert b"socket.io" in resp.data

def test_join_assigns_seats_and_sends_state():
    room = next(_room_ids)
    a, b = socketio.test_client(app), socketio.test_client(app)
    a.emit("join", {"roomId": room, "numPlayers": 3})
    ev = events(a)
    assert ("joined", {"playerIndex": 0}) in ev
    state = [d for n, d in ev if n == "state"][0]
    assert len(state["territories"]) == 42
    assert [len(p["territories"]) for p in state["players"]] == [14, 14, 14]
    assert state["currentPlayerIndex"] == 0
    assert state["phase"] == "waiting" and state["winnerId"] is None
    b.emit("join", {"roomId": room, "numPlayers": 3})
    assert last(b, "joined") == {"playerIndex": 1}

def test_mission_is_sent_only_to_its_owner():
    room = next(_room_ids)
    a, b = socketio.test_client(app), socketio.test_client(app)
    a.emit("join", {"roomId": room, "numPlayers": 3})
    ev_a = events(a)
    b.emit("join", {"roomId": room, "numPlayers": 3})
    missions = rooms.get(room).state.missions
    assert [d for n, d in ev_a if n == "mission"] == [{"description": missions[0].description}]
    assert last(b, "mission") == {"description": missions[1].description}
    assert "mission" not in [n for n, _ in events(a)]
    assert "missions" not in [d for n, d in ev_a if n == "state"][0]

def test_extra_players_join_as_spectators():
    room = next(_room_ids)
    clients = [socketio.test_client(app) for _ in range(4)]
    seats = []
    for c in clients:
        c.emit("join", {"roomId": room, "numPlayers": 3})
        ev = events(c)
        seats.append([d for n, d in ev if n == "joined"][0]["playerIndex"])
        spectator_events = ev
    assert seats == [0, 1, 2, None]
    assert "mission" not in [n for n, _ in spectator_events]
    assert "state" in [n for n, _ in spectator_events]
    # o espectador não consegue jogar no lugar do Jogador 1
    for c in clients:
        events(c)
    clients[3].emit("start_turn", {"roomId": room})
    assert only_error(clients[3])
    assert events(clients[0]) == []

@pytest.mark.parametrize("num_players", [1, 7, "3", None])
def test_invalid_number_of_players_does_not_create_room(num_players):
    room = next(_room_ids)
    c = socketio.test_client(app)
    c.emit("join", {"roomId": room, "numPlayers": num_players})
    assert only_error(c)
    assert rooms.get(room) is None

def test_events_for_unknown_room_do_not_create_it():
    room = next(_room_ids)
    c = socketio.test_client(app)
    for event in ["start_turn", "place", "attack", "end_turn"]:
        c.emit(event, {"roomId": room})
        assert only_error(c)
    c.emit("start_turn", {})
    assert only_error(c)
    assert rooms.get(room) is None

def test_only_current_player_can_act(game):
    room, a, b, state = game
    for event, payload in [
        ("start_turn", {}),
        ("place", {"placements": {state["players"][1]["territories"][0]: 1}}),
        ("attack", {"from": "x", "to": "y", "dice": 1}),
        ("end_turn", {}),
    ]:
        b.emit(event, {"roomId": room, **payload})
        assert only_error(b)
        assert events(a) == []

def test_full_turn(game):
    room, a, b, state = game
    a.emit("start_turn", {"roomId": room})
    started = last(a, "turn_started")
    assert started["reinforcements"] == 4  # 14 territórios // 3
    assert started["state"]["phase"] == "placing"
    assert started["state"]["reinforcementsLeft"] == 4
    assert last(b, "turn_started")["state"]["currentPlayerIndex"] == 0

    src, target = own_and_enemy_neighbor(state, 0)
    a.emit("place", {"roomId": room, "placements": {src: 3}})
    placed = last(a, "state")
    assert placed["territories"][src]["armies"] == 4
    assert placed["reinforcementsLeft"] == 1 and placed["phase"] == "placing"
    a.emit("place", {"roomId": room, "placements": {src: 1}})
    assert last(a, "state")["phase"] == "attacking"
    assert last(b, "state")["territories"][src]["armies"] == 5

    a.emit("attack", {"roomId": room, "from": src, "to": target, "dice": 3})
    result = last(a, "attack_result")
    assert len(result["result"]["attacker_rolls"]) == 3
    assert len(result["state"]["territories"]) == 42

    a.emit("end_turn", {"roomId": room})
    ended = last(a, "state")
    assert ended["currentPlayerIndex"] == 1 and ended["phase"] == "waiting"
    assert last(b, "state")["currentPlayerIndex"] == 1

def test_turn_cannot_be_started_twice(game):
    room, a, b, state = game
    a.emit("start_turn", {"roomId": room})
    events(a), events(b)
    a.emit("start_turn", {"roomId": room})
    assert only_error(a)
    assert events(b) == []

def test_cannot_place_more_than_reinforcements(game):
    room, a, b, state = game
    own = state["players"][0]["territories"][0]
    a.emit("place", {"roomId": room, "placements": {own: 1}})  # turno ainda não iniciado
    assert only_error(a)
    a.emit("start_turn", {"roomId": room})
    events(a), events(b)
    a.emit("place", {"roomId": room, "placements": {own: 5}})
    assert only_error(a)
    assert events(b) == []
    assert rooms.get(room).state.territories[own].armies == 1

def test_cannot_attack_or_end_turn_before_placing(game):
    room, a, b, state = game
    src, target = own_and_enemy_neighbor(state, 0)
    a.emit("start_turn", {"roomId": room})
    events(a), events(b)
    a.emit("attack", {"roomId": room, "from": src, "to": target, "dice": 1})
    assert only_error(a)
    a.emit("end_turn", {"roomId": room})
    assert only_error(a)
    assert events(b) == []
    assert rooms.get(room).state.current_player_index == 0

@pytest.mark.parametrize("placements", [None, [], "abc", {"Atlantis": 1}])
def test_invalid_placement_reports_error(game, placements):
    room, a, b, state = game
    a.emit("start_turn", {"roomId": room})
    events(a), events(b)
    a.emit("place", {"roomId": room, "placements": placements})
    assert only_error(a)
    assert events(b) == []

@pytest.mark.parametrize("count", [0, -3, "2", 1.5])
def test_invalid_placement_count_reports_error(game, count):
    room, a, b, state = game
    own = state["players"][0]["territories"][0]
    a.emit("start_turn", {"roomId": room})
    events(a), events(b)
    a.emit("place", {"roomId": room, "placements": {own: count}})
    assert only_error(a)
    assert events(b) == []

def test_invalid_attacks_report_error_without_broadcast(game):
    room, a, b, state = game
    src, target = own_and_enemy_neighbor(state, 0)
    other = next(t for t in state["players"][0]["territories"] if t != src)
    enemy = state["players"][1]["territories"][0]
    enemy_target = state["territories"][enemy]["neighbors"][0]
    start_and_place_all(room, a, src)
    events(a), events(b)
    for payload in [
        {"from": other, "to": target, "dice": 1},        # só 1 tropa (ou nem é vizinho)
        {"from": enemy, "to": enemy_target, "dice": 1},  # território de outro jogador
        {"from": "Atlantis", "to": target, "dice": 1},
        {"from": src, "to": "Atlantis", "dice": 1},
        {"from": src, "to": target, "dice": "muitos"},
        {"from": src, "to": target, "dice": 9},
        {"from": src, "to": ["x"], "dice": 1},
        {"to": target},
    ]:
        a.emit("attack", {"roomId": room, **payload})
        assert only_error(a), payload
        assert events(b) == []

def test_game_over_is_broadcast_and_blocks_further_actions(game, monkeypatch):
    room, a, b, state = game
    # Deixa o Jogador 1 a uma conquista da vitória: os outros ficam só com o território alvo
    src, target = own_and_enemy_neighbor(state, 0)
    st = rooms.get(room).state
    for t in st.territories.values():
        if t.name != target and t.owner_id != 0:
            st.players[t.owner_id].territories.discard(t.name)
            t.owner_id = 0
            st.players[0].territories.add(t.name)
    for p in st.players:
        p.alive = bool(p.territories)
    st.missions = {}
    monkeypatch.setattr(combat, "roll_dice", lambda num: [6] * num if num != 1 else [1])

    start_and_place_all(room, a, src)
    events(a), events(b)
    a.emit("attack", {"roomId": room, "from": src, "to": target, "dice": 3})
    result = last(b, "attack_result")
    assert result["result"]["eliminated"] is not None
    assert result["state"]["winnerId"] == 0
    events(a)
    a.emit("end_turn", {"roomId": room})
    assert only_error(a)
