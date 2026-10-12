import json
from pathlib import Path
import pytest
from war_game.services.map_loader import load_map
from webapp.app import app
from webapp.rooms import DATA_DIR, rooms
from test_socket_flow import events, game, last, only_error, start_and_place_all  # noqa: F401 (game é fixture)

STATIC_DIR = Path(app.static_folder)

def own_pair(state, player_id):
    """Dois territórios vizinhos do mesmo jogador."""
    for name in state["players"][player_id]["territories"]:
        for n in state["territories"][name]["neighbors"]:
            if state["territories"][n]["ownerId"] == player_id:
                return name, n
    raise AssertionError("jogador sem territórios vizinhos entre si")

# --- dados de exibição ---

def test_layout_covers_every_territory_and_continent():
    layout = json.loads((STATIC_DIR / "map_layout.json").read_text(encoding="utf-8"))
    territories = load_map(DATA_DIR)
    assert set(layout["territories"]) == set(territories)
    assert set(layout["continents"]) == {t.continent for t in territories.values()}
    for x, y in layout["territories"].values():
        assert 0 < x < layout["width"] and 0 < y < layout["height"]
    positions = [tuple(p) for p in layout["territories"].values()]
    assert len(set(positions)) == len(positions)

def test_layout_file_is_served():
    resp = app.test_client().get("/static/map_layout.json")
    assert resp.status_code == 200
    assert len(resp.get_json()["territories"]) == 42

def test_every_territory_and_continent_has_a_portuguese_label():
    territories = load_map(DATA_DIR)
    labels = [t.label for t in territories.values()]
    assert all(labels) and len(set(labels)) == 42
    assert territories["Brazil"].label == "Brasil"
    continents = json.loads((DATA_DIR / "continents.json").read_text(encoding="utf-8"))
    assert all(c.get("label") for c in continents)

def test_state_carries_labels_and_continents(game):
    room, a, b, state = game
    assert state["territories"]["Japan"]["label"] == "Japão"
    assert {c["name"]: c["bonus"] for c in state["continents"]}["Asia"] == 7
    assert {c["label"] for c in state["continents"]} >= {"Ásia", "Oceania"}
    assert state["nextTradeValue"] == 4
    assert state["movable"] == {}

# --- cartas ---

def test_hands_are_private(game):
    room, a, b, state = game
    st = rooms.get(room).state
    st.players[0].cards = ["c1", "c2", "c3"]   # infantaria, cavalaria, artilharia
    st.players[1].cards = ["c10"]
    a.emit("start_turn", {"roomId": room})
    events(a), events(b)
    a.emit("trade", {"roomId": room, "cards": ["c1", "c2"]})  # força um erro só para não mudar nada
    assert only_error(a)
    # o estado público só tem a contagem
    public = rooms.get(room)
    from webapp.state_adapter import state_to_dict
    players = state_to_dict(public.state, public.tm)["players"]
    assert [p["cardCount"] for p in players] == [3, 1, 0]
    assert all("cards" not in p for p in players)

def test_join_sends_own_hand_with_labels_and_combos(game):
    from test_socket_flow import token_for
    room, a, b, state = game
    rooms.get(room).state.players[0].cards = ["c4", "c5", "c6", "c10"]
    a.emit("join", {"roomId": room, "token": token_for(room, "a")})
    hand = last(a, "hand")
    assert hand["cards"][0] == {"id": "c4", "icon": "infantry", "territory": "Brasil"}
    assert hand["cards"][3] == {"id": "c10", "icon": "wild", "territory": None}
    assert ["c4", "c5", "c6"] in hand["combos"]

def test_trade_adds_reinforcements_and_updates_only_the_owner_hand(game):
    room, a, b, state = game
    st = rooms.get(room).state
    st.players[0].cards = ["c1", "c2", "c3", "c7"]
    a.emit("start_turn", {"roomId": room})
    events(a), events(b)
    a.emit("trade", {"roomId": room, "cards": ["c1", "c2", "c3"]})
    ev_a, ev_b = events(a), events(b)
    new_state = [d for n, d in ev_a if n == "state"][-1]
    assert new_state["reinforcementsLeft"] >= 4 + 4   # 4 do turno + 4 da primeira troca
    assert new_state["nextTradeValue"] == 6
    assert new_state["players"][0]["cardCount"] == 1
    assert [d for n, d in ev_a if n == "hand"][-1]["cards"] == [{"id": "c7", "icon": "infantry", "territory": "China"}]
    assert [d for n, d in ev_b if n == "hand"][-1]["cards"] == []
    assert any(n == "message" and "trocou cartas" in d["text"] for n, d in ev_b)

@pytest.mark.parametrize("cards", [None, "c1", ["c1", "c2"], ["c1", "c2", 3], ["c1", "c1", "c1"], ["c1", "c2", "c9"], ["c1", "c4", "c2"]])
def test_invalid_trade_reports_error(game, cards):
    room, a, b, state = game
    st = rooms.get(room).state
    st.players[0].cards = ["c1", "c2", "c3", "c4"]
    a.emit("start_turn", {"roomId": room})
    events(a), events(b)
    a.emit("trade", {"roomId": room, "cards": cards})
    assert only_error(a)
    assert events(b) == []
    assert len(st.players[0].cards) == 4

def test_trade_only_during_own_placement(game):
    room, a, b, state = game
    st = rooms.get(room).state
    st.players[0].cards = ["c1", "c2", "c3"]
    st.players[1].cards = ["c4", "c5", "c6"]
    a.emit("trade", {"roomId": room, "cards": ["c1", "c2", "c3"]})  # turno não iniciado
    assert only_error(a)
    b.emit("trade", {"roomId": room, "cards": ["c4", "c5", "c6"]})  # não é a vez dele
    assert only_error(b)
    start_and_place_all(room, a, state["players"][0]["territories"][0])
    events(a), events(b)
    a.emit("trade", {"roomId": room, "cards": ["c1", "c2", "c3"]})  # já na fase de ataque
    assert only_error(a)
    assert len(st.players[0].cards) == 3

def test_card_drawn_at_end_of_turn_reaches_only_its_owner(game):
    room, a, b, state = game
    st = rooms.get(room).state
    start_and_place_all(room, a, state["players"][0]["territories"][0])
    st.conquered_this_turn = True
    events(a), events(b)
    a.emit("end_turn", {"roomId": room})
    assert len(last(a, "hand")["cards"]) == 1
    ev_b = events(b)
    assert [d for n, d in ev_b if n == "hand"][-1]["cards"] == []
    assert [d for n, d in ev_b if n == "state"][-1]["players"][0]["cardCount"] == 1

# --- remanejamento ---

def test_fortify_flow(game):
    room, a, b, state = game
    src, dst = own_pair(state, 0)
    start_and_place_all(room, a, src)   # src fica com 1 + 4 tropas
    events(a), events(b)

    a.emit("fortify", {"roomId": room, "from": src, "to": dst, "count": 1})  # ainda na fase de ataque
    assert only_error(a)

    a.emit("begin_fortify", {"roomId": room})
    s = last(a, "state")
    assert s["phase"] == "fortifying"
    assert s["movable"][src] == 4 and s["movable"][dst] == 0
    assert last(b, "state")["phase"] == "fortifying"

    a.emit("fortify", {"roomId": room, "from": src, "to": dst, "count": 3})
    s = last(a, "state")
    assert s["territories"][src]["armies"] == 2 and s["territories"][dst]["armies"] == 4
    # das 4 tropas em dst, só a que já estava lá ainda pode se mover
    assert s["movable"][src] == 1 and s["movable"][dst] == 1
    assert last(b, "state")["territories"][dst]["armies"] == 4

    a.emit("attack", {"roomId": room, "from": dst, "to": "x", "dice": 1})  # ataques encerrados
    assert only_error(a)

    a.emit("end_turn", {"roomId": room})
    s = last(a, "state")
    assert s["currentPlayerIndex"] == 1 and s["phase"] == "waiting" and s["movable"] == {}

@pytest.mark.parametrize("payload", [
    {"count": 9},                 # mais do que pode sair
    {"count": 0},
    {"count": "2"},
    {"to": "Atlantis"},
    {"to": None},
    {"from": ["x"]},
])
def test_invalid_fortify_reports_error(game, payload):
    room, a, b, state = game
    src, dst = own_pair(state, 0)
    start_and_place_all(room, a, src)
    a.emit("begin_fortify", {"roomId": room})
    events(a), events(b)
    a.emit("fortify", {"roomId": room, **{"from": src, "to": dst, "count": 1}, **payload})
    assert only_error(a)
    assert events(b) == []

def test_only_current_player_can_fortify(game):
    room, a, b, state = game
    start_and_place_all(room, a, state["players"][0]["territories"][0])
    events(a), events(b)
    src, dst = own_pair(state, 1)
    b.emit("begin_fortify", {"roomId": room})
    assert only_error(b)
    b.emit("fortify", {"roomId": room, "from": src, "to": dst, "count": 1})
    assert only_error(b)
    assert events(a) == []
