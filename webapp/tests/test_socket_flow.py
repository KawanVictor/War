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

def token_for(room, who):
    return f"token-{room}-{who}"

def join(room, who):
    client = socketio.test_client(app)
    client.emit("join", {"roomId": room, "token": token_for(room, who)})
    return client

def start_game(room, names="abc", num_players=3, skip_setup_round=True):
    """Cria a sala com uma pessoa por letra de `names`, inicia a partida e devolve os clientes."""
    clients = [join(room, who) for who in names]
    if num_players != 3:
        clients[0].emit("configure", {"numPlayers": num_players})
    clients[0].emit("start_game", {})
    if skip_setup_round:
        rooms.get(room).state.setup_turns_left = 0
    return clients

@pytest.fixture
def game():
    """Partida de 3 pessoas já fora da primeira rodada. Devolve a sala, dois dos jogadores e o estado inicial."""
    room = next(_room_ids)
    a, b, c = start_game(room)
    state = last(a, "state")
    for client in (a, b, c):
        events(client)
    yield room, a, b, state
    for client in (a, b, c):
        if client.is_connected():
            client.disconnect()

def own_and_enemy_neighbor(state, player_id):
    for name in state["players"][player_id]["territories"]:
        for n in state["territories"][name]["neighbors"]:
            if state["territories"][n]["ownerId"] != player_id:
                return name, n
    raise AssertionError("jogador sem fronteira inimiga")

def start_and_place_all(room, client, territory):
    client.emit("start_turn", {})
    reinf = last(client, "turn_started")["reinforcements"]
    client.emit("place", {"placements": {territory: reinf}})
    return last(client, "state")

def test_index_page_loads():
    resp = app.test_client().get("/")
    assert resp.status_code == 200
    assert b"socket.io" in resp.data

def test_game_starts_with_seats_in_join_order():
    room = next(_room_ids)
    a, b, c = start_game(room, skip_setup_round=False)
    seats = [[d for n, d in events(x) if n == "joined"][-1] for x in (a, b, c)]
    assert seats == [{"playerIndex": i, "started": True} for i in range(3)]
    state = rooms.get(room).state
    assert len(state.territories) == 42
    assert [len(p.territories) for p in state.players] == [14, 14, 14]
    assert state.current_player_index == 0 and state.phase == "waiting" and state.winner_id is None

def test_mission_is_sent_only_to_its_owner():
    room = next(_room_ids)
    a, b, c = start_game(room)
    missions = rooms.get(room).state.missions
    ev_a, ev_b = events(a), events(b)
    assert [d for n, d in ev_a if n == "mission"] == [{"description": missions[0].description}]
    assert [d for n, d in ev_b if n == "mission"] == [{"description": missions[1].description}]
    assert "missions" not in [d for n, d in ev_a if n == "state"][-1]

def test_events_before_joining_a_room_report_error():
    c = socketio.test_client(app)
    for event in ["start_turn", "place", "attack", "occupy", "begin_fortify", "fortify", "trade", "end_turn",
                  "configure", "start_game"]:
        c.emit(event, {"roomId": "nao-existe"})
        assert only_error(c), event
    assert rooms.get("nao-existe") is None

def test_game_events_in_the_lobby_report_error():
    room = next(_room_ids)
    a = join(room, "a")
    events(a)
    for event in ["start_turn", "place", "attack", "end_turn"]:
        a.emit(event, {})
        assert only_error(a), event

@pytest.mark.parametrize("payload", [None, "texto", 42, ["lista"]])
def test_non_dict_payloads_are_tolerated(game, payload):
    room, a, b, state = game
    for event in ["place", "attack", "fortify", "trade", "occupy"]:
        a.emit(event, payload)
        assert only_error(a), event

def test_only_current_player_can_act(game):
    room, a, b, state = game
    for event, payload in [
        ("start_turn", {}),
        ("place", {"placements": {state["players"][1]["territories"][0]: 1}}),
        ("attack", {"from": "x", "to": "y", "dice": 1}),
        ("end_turn", {}),
    ]:
        b.emit(event, payload)
        assert only_error(b)
        assert events(a) == []

def test_full_turn(game):
    room, a, b, state = game
    a.emit("start_turn", {})
    started = last(a, "turn_started")
    assert started["reinforcements"] == 4  # 14 territórios // 3
    assert started["state"]["phase"] == "placing"
    assert started["state"]["reinforcementsLeft"] == 4
    assert last(b, "turn_started")["state"]["currentPlayerIndex"] == 0

    src, target = own_and_enemy_neighbor(state, 0)
    a.emit("place", {"placements": {src: 3}})
    placed = last(a, "state")
    assert placed["territories"][src]["armies"] == 4
    assert placed["reinforcementsLeft"] == 1 and placed["phase"] == "placing"
    a.emit("place", {"placements": {src: 1}})
    assert last(a, "state")["phase"] == "attacking"
    assert last(b, "state")["territories"][src]["armies"] == 5

    a.emit("attack", {"from": src, "to": target, "dice": 3})
    result = last(a, "attack_result")
    assert len(result["result"]["attacker_rolls"]) == 3
    assert result["from"] == src and result["to"] == target
    assert len(result["state"]["territories"]) == 42

    a.emit("end_turn", {})
    ended = last(a, "state")
    assert ended["currentPlayerIndex"] == 1 and ended["phase"] == "waiting"
    assert last(b, "state")["currentPlayerIndex"] == 1

def test_turn_cannot_be_started_twice(game):
    room, a, b, state = game
    a.emit("start_turn", {})
    events(a), events(b)
    a.emit("start_turn", {})
    assert only_error(a)
    assert events(b) == []

def test_cannot_place_more_than_reinforcements(game):
    room, a, b, state = game
    own = state["players"][0]["territories"][0]
    a.emit("place", {"placements": {own: 1}})  # turno ainda não iniciado
    assert only_error(a)
    a.emit("start_turn", {})
    events(a), events(b)
    a.emit("place", {"placements": {own: 5}})
    assert only_error(a)
    assert events(b) == []
    assert rooms.get(room).state.territories[own].armies == 1

def test_cannot_attack_or_end_turn_before_placing(game):
    room, a, b, state = game
    src, target = own_and_enemy_neighbor(state, 0)
    a.emit("start_turn", {})
    events(a), events(b)
    a.emit("attack", {"from": src, "to": target, "dice": 1})
    assert only_error(a)
    a.emit("end_turn", {})
    assert only_error(a)
    assert events(b) == []
    assert rooms.get(room).state.current_player_index == 0

@pytest.mark.parametrize("placements", [None, [], "abc", {"Atlantis": 1}])
def test_invalid_placement_reports_error(game, placements):
    room, a, b, state = game
    a.emit("start_turn", {})
    events(a), events(b)
    a.emit("place", {"placements": placements})
    assert only_error(a)
    assert events(b) == []

@pytest.mark.parametrize("count", [0, -3, "2", 1.5])
def test_invalid_placement_count_reports_error(game, count):
    room, a, b, state = game
    own = state["players"][0]["territories"][0]
    a.emit("start_turn", {})
    events(a), events(b)
    a.emit("place", {"placements": {own: count}})
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
        a.emit("attack", payload)
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
    a.emit("attack", {"from": src, "to": target, "dice": 3})
    result = last(b, "attack_result")
    assert result["result"]["eliminated"] is not None
    assert result["state"]["winnerId"] == 0
    events(a)
    a.emit("end_turn", {})
    assert only_error(a)
