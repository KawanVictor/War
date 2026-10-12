import pytest
from webapp import socket_handlers
from webapp.rooms import Room, RoomManager, rooms
from test_socket_flow import (  # noqa: F401 (game é fixture)
    _room_ids, events, game, join, last, only_error, own_and_enemy_neighbor, start_and_place_all, start_game,
)

@pytest.fixture
def no_wait(monkeypatch):
    """Dispensa o tempo de espera antes de poder substituir quem saiu."""
    monkeypatch.setattr(socket_handlers, "ABANDON_SECONDS", 0)

def players(client):
    return last(client, "state")["players"]

def test_state_shows_who_is_connected(game):
    room, a, b, state = game
    a.emit("join", {"roomId": room, "token": f"token-{room}-a"})
    assert [p["connected"] for p in players(a)] == [True, True, True]
    events(b)
    b.disconnect()
    after = players(a)
    assert [p["connected"] for p in after] == [True, False, True]
    assert not any(p["bot"] or p["substituted"] for p in after)

def test_absent_player_blocks_the_game_until_substituted(game, no_wait):
    room, a, b, state = game
    b.disconnect()
    start_and_place_all(room, a, state["players"][0]["territories"][0])
    a.emit("end_turn", {})
    st = rooms.get(room).state
    assert st.current_player_index == 1 and st.phase == "waiting"  # parado na vez de quem saiu
    events(a)

    a.emit("substitute", {"seat": 1})
    ev = events(a)
    texts = [d["text"] for n, d in ev if n == "message"]
    assert any("O computador assumiu o lugar do Jogador 2" in t for t in texts)
    assert any("Jogador 2 (computador) jogou" in t for t in texts)
    after = [d for n, d in ev if n == "state"][-1]
    assert after["currentPlayerIndex"] == 2  # o computador jogou e a vez passou para a próxima pessoa
    assert after["players"][1]["bot"] and after["players"][1]["substituted"] and after["players"][1]["connected"]
    assert rooms.get(room).substituted == {1}

def test_substituted_player_takes_the_seat_back_on_return(game, no_wait):
    room, a, b, state = game
    st = rooms.get(room).state
    st.players[1].cards = ["c1"]
    b.disconnect()
    a.emit("substitute", {"seat": 1})
    events(a)

    b2 = join(room, "b")
    ev = events(b2)
    assert [d for n, d in ev if n == "joined"] == [{"playerIndex": 1, "started": True}]
    assert [d for n, d in ev if n == "hand"][-1]["cards"][0]["id"] == "c1"
    r = rooms.get(room)
    assert r.bots == set() and r.substituted == set()
    ev_a = events(a)
    assert any("voltou e reassumiu" in d["text"] for n, d in ev_a if n == "message")
    back = [d for n, d in ev_a if n == "state"][-1]["players"][1]
    assert back == {**back, "bot": False, "substituted": False, "connected": True}

    # e a partida volta a esperar por ele na vez dele
    start_and_place_all(room, a, state["players"][0]["territories"][0])
    a.emit("end_turn", {})
    assert st.current_player_index == 1 and st.phase == "waiting"
    b2.emit("start_turn", {})
    assert last(b2, "turn_started")["state"]["currentPlayerIndex"] == 1

def test_computer_finishes_a_turn_left_halfway(game, no_wait):
    room, a, b, state = game
    st = rooms.get(room).state
    start_and_place_all(room, a, state["players"][0]["territories"][0])
    a.emit("end_turn", {})
    # o Jogador 2 começa o turno, coloca parte das tropas e some
    own = state["players"][1]["territories"][0]
    b.emit("start_turn", {})
    b.emit("place", {"placements": {own: 1}})
    assert st.phase == "placing" and st.reinforcements_left == 3
    armies_before = sum(t.armies for t in st.territories.values() if t.owner_id == 1)
    b.disconnect()
    events(a)

    a.emit("substitute", {"seat": 1})
    after = last(a, "state")
    assert after["currentPlayerIndex"] == 2 and after["phase"] == "waiting"
    # as 3 tropas que faltavam foram posicionadas pelo computador (ataques podem ter mudado o total depois)
    assert st.reinforcements_left == 0
    assert sum(t.armies for t in st.territories.values()) >= armies_before

def test_must_wait_before_substituting(game, monkeypatch):
    room, a, b, state = game
    monkeypatch.setattr(socket_handlers, "ABANDON_SECONDS", 3600)
    b.disconnect()
    events(a)
    a.emit("substitute", {"seat": 1})
    ev = events(a)
    assert [n for n, _ in ev] == ["message"] and "Aguarde mais" in ev[0][1]["text"]
    assert rooms.get(room).bots == set()
    # passado o tempo, a troca é aceita
    key = (room, 1)
    socket_handlers.away_since[key] -= 3601
    a.emit("substitute", {"seat": 1})
    assert rooms.get(room).bots == {1}

def test_cannot_substitute_someone_who_is_present(game, no_wait):
    room, a, b, state = game
    a.emit("substitute", {"seat": 1})
    ev = events(a)
    assert [n for n, _ in ev] == ["message"] and "está na sala" in ev[0][1]["text"]
    a.emit("substitute", {"seat": 0})  # nem a si mesmo
    assert only_error(a)
    assert rooms.get(room).bots == set()

@pytest.mark.parametrize("seat", [None, "1", 1.0, True, -1, 3, 99])
def test_invalid_seat(game, no_wait, seat):
    room, a, b, state = game
    b.disconnect()
    events(a)
    a.emit("substitute", {"seat": seat})
    assert only_error(a)
    assert rooms.get(room).bots == set()

def test_spectators_cannot_substitute(game, no_wait):
    room, a, b, state = game
    b.disconnect()
    watcher = join(room, "espectador")
    events(watcher)
    watcher.emit("substitute", {"seat": 1})
    assert only_error(watcher)
    assert rooms.get(room).bots == set()

def test_cannot_substitute_twice_or_a_regular_computer_player(no_wait):
    room = next(_room_ids)
    a, b = start_game(room, names="ab", num_players=3)
    b.disconnect()
    events(a)
    a.emit("substitute", {"seat": 2})  # já é do computador desde o início
    assert only_error(a)
    a.emit("substitute", {"seat": 1})
    events(a)
    a.emit("substitute", {"seat": 1})
    assert only_error(a)
    r = rooms.get(room)
    assert r.bots == {1, 2} and r.substituted == {1}

def test_substitute_before_the_game_or_after_it_ends(game, no_wait):
    room, a, b, state = game
    lobby = next(_room_ids)
    c = join(lobby, "c")
    events(c)
    c.emit("substitute", {"seat": 0})
    assert only_error(c)

    b.disconnect()
    events(a)
    rooms.get(room).state.winner_id = 0
    a.emit("substitute", {"seat": 1})
    assert only_error(a)

def test_everyone_else_leaving_lets_one_person_finish_against_computers(no_wait):
    room = next(_room_ids)
    a, b, c = start_game(room)
    b.disconnect()
    c.disconnect()
    events(a)
    a.emit("substitute", {"seat": 1})
    a.emit("substitute", {"seat": 2})
    st = rooms.get(room).state
    own = last(a, "state")["players"][0]["territories"][0]
    start_and_place_all(room, a, own)
    a.emit("end_turn", {})
    ev = events(a)
    assert sum("(computador) jogou" in d["text"] for n, d in ev if n == "message") == 2
    assert st.current_player_index == 0 or st.winner_id is not None

def test_substitution_survives_a_server_restart(game, no_wait):
    room, a, b, state = game
    b.disconnect()
    a.emit("substitute", {"seat": 1})
    restored = RoomManager(rooms.storage_dir).get(room)
    assert restored.substituted == {1} and restored.bots == {1}
    assert restored.restore(1) and restored.bots == set()

def test_saves_from_before_this_feature_still_load():
    room = Room("antiga")
    room.add_member("token-aaaa")
    room.start()
    data = room.to_dict()
    del data["substituted"]
    assert Room.from_dict(data).substituted == set()
