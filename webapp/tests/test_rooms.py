import json
import time
import pytest
from war_game.rules import combat
from war_game.rules.errors import RuleError
from webapp import socket_handlers
from webapp.app import app, socketio
from webapp.rooms import MAX_ROOMS, Room, RoomManager, rooms
from test_socket_flow import (  # noqa: F401 (game é fixture)
    _room_ids, events, game, join, last, only_error, own_and_enemy_neighbor, start_and_place_all, start_game, token_for,
)

# --- sala de espera ---

def test_lobby_shows_members_and_host():
    room = next(_room_ids)
    a = join(room, "a")
    assert last(a, "lobby") == {"roomId": room, "numPlayers": 3, "members": 1, "you": 0, "isHost": True}
    b = join(room, "b")
    assert last(b, "lobby") == {"roomId": room, "numPlayers": 3, "members": 2, "you": 1, "isHost": False}
    assert last(a, "lobby")["members"] == 2
    assert not rooms.get(room).started

def test_only_host_can_configure_and_start():
    room = next(_room_ids)
    a, b = join(room, "a"), join(room, "b")
    events(a), events(b)
    b.emit("configure", {"numPlayers": 4})
    assert only_error(b)
    b.emit("start_game", {})
    assert only_error(b)
    assert rooms.get(room).num_players == 3 and not rooms.get(room).started
    a.emit("configure", {"numPlayers": 5})
    assert last(b, "lobby")["numPlayers"] == 5

@pytest.mark.parametrize("num_players", [1, 7, "3", None, 2.5])
def test_invalid_number_of_players(num_players):
    room = next(_room_ids)
    a = join(room, "a")
    events(a)
    a.emit("configure", {"numPlayers": num_players})
    assert only_error(a)
    assert rooms.get(room).num_players == 3

def test_leaving_the_lobby_frees_the_place_and_empty_lobbies_are_removed():
    room = next(_room_ids)
    a, b = join(room, "a"), join(room, "b")
    events(a), events(b)
    a.disconnect()
    # quem sobrou vira o anfitrião
    assert last(b, "lobby") == {"roomId": room, "numPlayers": 3, "members": 1, "you": 0, "isHost": True}
    b.disconnect()
    assert rooms.get(room) is None

def test_lobby_holds_at_most_six_people():
    room = next(_room_ids)
    clients = [join(room, str(i)) for i in range(7)]
    assert [last(c, "joined")["playerIndex"] for c in clients] == [0, 1, 2, 3, 4, 5, None]

@pytest.mark.parametrize("room_id", ["", "x" * 41, None, 123, ["sala"], "quebra\nlinha"])
def test_invalid_room_name(room_id):
    c = socketio.test_client(app)
    before = len(rooms.rooms)
    c.emit("join", {"roomId": room_id})
    assert only_error(c)
    assert len(rooms.rooms) == before

def test_people_beyond_the_number_of_players_watch():
    room = next(_room_ids)
    a, b, c = start_game(room, num_players=2)
    assert [[d for n, d in events(x) if n == "joined"][-1]["playerIndex"] for x in (a, b, c)] == [0, 1, None]
    assert len(rooms.get(room).state.players) == 2
    c.emit("start_turn", {})
    assert only_error(c)

def test_joining_a_running_game_as_a_stranger_is_spectating(game):
    room, a, b, state = game
    d = join(room, "d")
    ev = events(d)
    assert [d_ for n, d_ in ev if n == "joined"] == [{"playerIndex": None, "started": True}]
    assert "state" in [n for n, _ in ev] and "mission" not in [n for n, _ in ev] and "hand" not in [n for n, _ in ev]

# --- reconexão ---

def test_reconnecting_with_the_same_token_keeps_the_seat(game):
    room, a, b, state = game
    st = rooms.get(room).state
    st.players[1].cards = ["c1"]
    b.disconnect()
    assert any("lugar dele fica guardado" in d["text"] for n, d in events(a) if n == "message")
    b2 = join(room, "b")
    ev = events(b2)
    assert [d for n, d in ev if n == "joined"] == [{"playerIndex": 1, "started": True}]
    assert [d for n, d in ev if n == "mission"] == [{"description": st.missions[1].description}]
    assert [d for n, d in ev if n == "hand"][-1]["cards"][0]["id"] == "c1"
    # e continua podendo jogar na vez dele
    start_and_place_all(room, a, state["players"][0]["territories"][0])
    a.emit("end_turn", {})
    events(b2)
    b2.emit("start_turn", {})
    assert last(b2, "turn_started")["state"]["currentPlayerIndex"] == 1

def test_seat_cannot_be_taken_by_another_token(game):
    room, a, b, state = game
    b.disconnect()
    intruder = join(room, "intruso")
    assert last(intruder, "joined") == {"playerIndex": None, "started": True}

def test_without_token_the_connection_is_the_identity():
    room = next(_room_ids)
    c = socketio.test_client(app)
    c.emit("join", {"roomId": room})
    assert last(c, "lobby")["you"] == 0
    c.emit("join", {"roomId": room, "token": "curto"})  # token inválido é ignorado
    assert last(c, "lobby") == {"roomId": room, "numPlayers": 3, "members": 1, "you": 0, "isHost": True}

def test_switching_rooms_leaves_the_previous_one():
    first, second = next(_room_ids), next(_room_ids)
    a = join(first, "a")
    a.emit("join", {"roomId": second, "token": token_for(first, "a")})
    assert last(a, "lobby")["roomId"] == second
    assert rooms.get(first) is None

# --- computador ---

def test_empty_seats_are_played_by_the_computer():
    room = next(_room_ids)
    (a,) = start_game(room, names="a", num_players=4, skip_setup_round=False)
    r = rooms.get(room)
    assert r.bots == {1, 2, 3}
    state = last(a, "state")
    assert [p["bot"] for p in state["players"]] == [False, True, True, True]
    assert state["setupRound"] is True

    # Primeira rodada: só posicionamento, e depois os três computadores jogam sozinhos
    own = state["players"][0]["territories"][0]
    start_and_place_all(room, a, own)
    a.emit("attack", {"from": own, "to": state["territories"][own]["neighbors"][0], "dice": 1})
    assert only_error(a)
    a.emit("begin_fortify", {})
    assert only_error(a)
    a.emit("end_turn", {})
    ev = events(a)
    assert sum("(computador) jogou" in d["text"] for n, d in ev if n == "message") == 3
    after = [d for n, d in ev if n == "state"][-1]
    assert after["currentPlayerIndex"] == 0 and after["phase"] == "waiting"
    assert after["setupRound"] is False
    # cada computador posicionou os próprios reforços
    assert sum(t["armies"] for t in after["territories"].values()) > sum(t["armies"] for t in state["territories"].values()) + 6

def test_game_against_computers_runs_to_the_end():
    room = next(_room_ids)
    (a,) = start_game(room, names="a", num_players=3, skip_setup_round=False)
    st = rooms.get(room).state
    for _ in range(400):
        if st.winner_id is not None:
            break
        assert st.current_player_index == 0  # depois de cada jogada a vez volta para a pessoa
        a.emit("start_turn", {})
        own = sorted(st.players[0].territories)[0]
        while st.phase == "placing" and st.winner_id is None:
            combos = last(a, "hand")["combos"] if st.players[0].cards else []
            if rooms.get(room).tm.must_trade():
                a.emit("trade", {"cards": combos[0]})
            else:
                a.emit("place", {"placements": {own: st.reinforcements_left}})
        if st.winner_id is None:
            a.emit("end_turn", {})
        events(a)
        socket_handlers.recent_events.clear()
    assert st.winner_id is not None

# --- persistência ---

def test_started_games_are_saved_and_restored(game):
    room, a, b, state = game
    src, _ = own_and_enemy_neighbor(state, 0)
    start_and_place_all(room, a, src)
    live = rooms.get(room)
    path = rooms._path(room)
    assert path.exists()

    restored = RoomManager(rooms.storage_dir).get(room)
    assert restored is not None and restored is not live
    assert restored.to_dict() == live.to_dict()
    assert restored.state.territories[src].armies == 5
    assert restored.state.phase == "attacking"
    assert restored.seat_of(token_for(room, "b")) == 1
    # a partida restaurada continua jogável
    restored.tm.end_turn()
    assert restored.state.current_player_index == 1

def test_lobbies_are_not_written_to_disk():
    room = next(_room_ids)
    join(room, "a")
    assert not rooms._path(room).exists()

def test_room_id_never_becomes_a_path(tmp_path):
    manager = RoomManager(tmp_path)
    room = manager.get_or_create("../../fora")
    room.add_member("token-aaaa")
    room.start()
    manager.save(room)
    files = list(tmp_path.iterdir())
    assert len(files) == 1 and files[0].parent == tmp_path and files[0].suffix == ".json"
    assert json.loads(files[0].read_text(encoding="utf-8"))["id"] == "../../fora"

def test_corrupted_files_are_ignored(tmp_path):
    (tmp_path / "ruim.json").write_text("{isto não é json", encoding="utf-8")
    (tmp_path / "velho.json").write_text(json.dumps({"id": "x", "state": {"version": 0}}), encoding="utf-8")
    assert RoomManager(tmp_path).rooms == {}

def test_manager_without_storage_keeps_rooms_in_memory_only():
    manager = RoomManager(None)
    room = manager.get_or_create("sala")
    room.add_member("token-aaaa")
    room.start()
    manager.save(room)
    manager.remove("sala")
    assert manager.get("sala") is None

# --- limpeza e limites ---

def test_stale_rooms_are_purged(tmp_path):
    manager = RoomManager(tmp_path, ttl_hours=1)
    old, fresh = manager.get_or_create("velha"), manager.get_or_create("nova")
    for room in (old, fresh):
        room.add_member("token-aaaa")
        room.start()
        manager.save(room)
    old.last_activity = time.time() - 2 * 3600
    assert manager.purge_stale() == ["velha"]
    assert manager.get("velha") is None and manager.get("nova") is fresh
    assert not manager._path("velha").exists() and manager._path("nova").exists()

def test_joining_purges_stale_rooms():
    stale = next(_room_ids)
    join(stale, "a")
    rooms.get(stale).last_activity = time.time() - rooms.ttl_seconds - 60
    join(next(_room_ids), "b")
    assert rooms.get(stale) is None

def test_room_limit(tmp_path):
    manager = RoomManager(None)
    for i in range(MAX_ROOMS):
        manager.get_or_create(f"sala-{i}")
    with pytest.raises(RuleError):
        manager.get_or_create("mais-uma")
    assert manager.get_or_create("sala-0") is manager.get("sala-0")

def test_rate_limit(game, monkeypatch):
    room, a, b, state = game
    monkeypatch.setattr(socket_handlers, "RATE_LIMIT_EVENTS", 5)
    socket_handlers.recent_events.clear()
    for _ in range(5):
        a.emit("start_turn", {})
    st = rooms.get(room).state
    assert st.phase == "placing"
    events(a)
    own = state["players"][0]["territories"][0]
    a.emit("place", {"placements": {own: 1}})
    ev = events(a)
    assert [n for n, _ in ev] == ["message"] and "Muitas ações" in ev[0][1]["text"]
    assert st.territories[own].armies == 1
    # o limite é por conexão
    events(b)
    b.emit("start_turn", {})
    assert "Não é seu turno" in events(b)[0][1]["text"]

def test_security_headers():
    resp = app.test_client().get("/")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    csp = resp.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp
    # a página não depende de nada fora do próprio servidor
    html = resp.get_data(as_text=True)
    assert "http://" not in html and "https://" not in html and "<script>" not in html

def test_static_assets_are_served():
    client = app.test_client()
    for path in ["/static/game.js", "/static/style.css", "/static/map_layout.json", "/static/vendor/socket.io.min.js"]:
        assert client.get(path).status_code == 200, path

# --- regras novas pela web ---

def test_setup_round_blocks_attacks_for_everyone_once():
    room = next(_room_ids)
    a, b, c = start_game(room, skip_setup_round=False)
    state = last(a, "state")
    st = rooms.get(room).state
    for i, client in enumerate((a, b, c)):
        assert st.setup_turns_left == 3 - i
        src, target = own_and_enemy_neighbor(state, i)
        start_and_place_all(room, client, src)
        events(client)
        client.emit("attack", {"from": src, "to": target, "dice": 3})
        assert only_error(client)
        client.emit("end_turn", {})
    assert st.setup_turns_left == 0 and st.current_player_index == 0
    src, target = own_and_enemy_neighbor(state, 0)
    start_and_place_all(room, a, src)
    a.emit("attack", {"from": src, "to": target, "dice": 3})
    assert last(a, "attack_result")["from"] == src

def test_must_trade_with_five_cards(game):
    room, a, b, state = game
    st = rooms.get(room).state
    st.players[0].cards = ["c1", "c2", "c3", "c4", "c7"]
    own = state["players"][0]["territories"][0]
    a.emit("start_turn", {})
    assert last(a, "turn_started")["state"]["mustTrade"] is True
    a.emit("place", {"placements": {own: 1}})
    ev = events(a)
    assert [n for n, _ in ev] == ["message"] and "obrigatório trocar" in ev[0][1]["text"]
    a.emit("trade", {"cards": ["c1", "c2", "c3"]})
    assert [d for n, d in events(a) if n == "state"][-1]["mustTrade"] is False
    before = st.territories[own].armies  # a troca pode ter dado 2 tropas de bônus a este território
    a.emit("place", {"placements": {own: 1}})
    assert last(a, "state")["territories"][own]["armies"] == before + 1

def test_occupy_after_conquest(game, monkeypatch):
    room, a, b, state = game
    monkeypatch.setattr(combat, "roll_dice", lambda num: [6] * num if num != 1 else [1])
    src, target = own_and_enemy_neighbor(state, 0)
    a.emit("occupy", {"count": 1})  # nada foi conquistado ainda
    assert only_error(a)
    start_and_place_all(room, a, src)   # src com 5 tropas
    a.emit("attack", {"from": src, "to": target, "dice": 2})
    result = last(a, "attack_result")
    assert result["result"]["conquered"] is True
    # 2 tropas seguiram com os dados; sobram 3 na origem, das quais 2 ainda podem ir
    assert result["state"]["conquest"] == {"from": src, "to": target, "max": 2}
    events(b)
    for count in [3, 0, "1", None]:
        a.emit("occupy", {"count": count})
        assert only_error(a), count
    a.emit("occupy", {"count": 2})
    after = last(a, "state")
    assert after["territories"][src]["armies"] == 1 and after["territories"][target]["armies"] == 4
    assert after["conquest"] == {"from": src, "to": target, "max": 0}
    assert last(b, "state")["territories"][target]["armies"] == 4
    a.emit("begin_fortify", {})
    assert last(a, "state")["conquest"] is None

def test_room_roundtrip_through_dict():
    room = Room("ida-e-volta")
    for token in ("token-aaaa", "token-bbbb"):
        room.add_member(token)
    room.configure(4)
    room.start()
    copy = Room.from_dict(json.loads(json.dumps(room.to_dict())))
    assert copy.to_dict() == room.to_dict()
    assert copy.bots == {2, 3} and copy.seat_of("token-bbbb") == 1 and copy.started
