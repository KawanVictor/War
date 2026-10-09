import itertools
import pytest
from webapp.app import app, socketio

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
    b.emit("join", {"roomId": room, "numPlayers": 3})
    assert last(b, "joined") == {"playerIndex": 1}

def test_only_current_player_can_act(game):
    room, a, b, state = game
    for event, payload in [
        ("start_turn", {}),
        ("place", {"placements": {state["players"][1]["territories"][0]: 1}}),
        ("attack", {"from": "x", "to": "y", "dice": 1}),
        ("end_turn", {}),
    ]:
        b.emit(event, {"roomId": room, **payload})
        assert [n for n, _ in events(b)] == ["message"]
        assert events(a) == []

def test_full_turn(game):
    room, a, b, state = game
    a.emit("start_turn", {"roomId": room})
    started = last(a, "turn_started")
    assert started["reinforcements"] == 4  # 14 territórios // 3
    assert last(b, "turn_started")["state"]["currentPlayerIndex"] == 0

    src, target = own_and_enemy_neighbor(state, 0)
    a.emit("place", {"roomId": room, "placements": {src: 4}})
    assert last(a, "state")["territories"][src]["armies"] == 5
    assert last(b, "state")["territories"][src]["armies"] == 5

    a.emit("attack", {"roomId": room, "from": src, "to": target, "dice": 3})
    result = last(a, "attack_result")
    assert len(result["result"]["attacker_rolls"]) == 3
    assert len(result["state"]["territories"]) == 42

    a.emit("end_turn", {"roomId": room})
    assert last(a, "state")["currentPlayerIndex"] == 1
    assert last(b, "state")["currentPlayerIndex"] == 1

@pytest.mark.parametrize("placements", [None, [], "abc", {"Atlantis": 1}])
def test_invalid_placement_reports_error(game, placements):
    room, a, b, state = game
    a.emit("place", {"roomId": room, "placements": placements})
    assert [n for n, _ in events(a)] == ["message"]
    assert events(b) == []

@pytest.mark.parametrize("count", [0, -3, "2", 1.5])
def test_invalid_placement_count_reports_error(game, count):
    room, a, b, state = game
    own = state["players"][0]["territories"][0]
    a.emit("place", {"roomId": room, "placements": {own: count}})
    assert [n for n, _ in events(a)] == ["message"]
    assert events(b) == []

def test_invalid_attacks_report_error_without_broadcast(game):
    room, a, b, state = game
    src, target = own_and_enemy_neighbor(state, 0)
    enemy = state["players"][1]["territories"][0]
    enemy_target = state["territories"][enemy]["neighbors"][0]
    for payload in [
        {"from": src, "to": target, "dice": 1},          # só 1 tropa, não pode atacar
        {"from": enemy, "to": enemy_target, "dice": 1},  # território de outro jogador
        {"from": "Atlantis", "to": target, "dice": 1},
        {"from": src, "to": "Atlantis", "dice": 1},
        {"from": src, "to": target, "dice": "muitos"},
        {"to": target},
    ]:
        a.emit("attack", {"roomId": room, **payload})
        assert [n for n, _ in events(a)] == ["message"], payload
        assert events(b) == []
