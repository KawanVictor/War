import functools
import os
import time
from collections import deque
from typing import Deque, Dict, Tuple
from flask import request
from flask_socketio import join_room, leave_room, emit
from war_game.rules.errors import RuleError
from war_game.services import bot
from webapp.rooms import MAX_ROOM_ID_LENGTH, rooms
from webapp.state_adapter import hand_to_dict, state_to_dict

# Limite de eventos por conexão: no máximo RATE_LIMIT_EVENTS a cada RATE_LIMIT_WINDOW segundos
RATE_LIMIT_EVENTS = 80
RATE_LIMIT_WINDOW = 10.0
# Tempo que uma pessoa precisa estar fora para os outros poderem passar o lugar dela ao computador
ABANDON_SECONDS = float(os.environ.get("WAR_ABANDON_SECONDS", "30"))
MAX_BOT_TURNS_IN_A_ROW = 500

# sid -> (id da sala, token do jogador)
connections: Dict[str, Tuple[str, str]] = {}
# (id da sala, assento) -> instante em que a pessoa ficou sem nenhuma conexão
away_since: Dict[Tuple[str, int], float] = {}
# Quem ainda não apareceu desde que o servidor subiu conta como ausente desde então
STARTED_AT = time.monotonic()
# sid -> instantes dos últimos eventos recebidos
recent_events: Dict[str, Deque[float]] = {}

def current_sid() -> str:
    """Id da conexão que enviou o evento em tratamento (o Flask-SocketIO o coloca no request)."""
    return request.sid  # type: ignore[attr-defined]

def valid_token(token) -> bool:
    return isinstance(token, str) and 8 <= len(token) <= 64 and token.isascii() and token.isprintable()

def register_socket_handlers(socketio):
    def reply(text):
        emit("message", {"text": text}, room=current_sid())

    def guarded(handler):
        """Descarta eventos de quem manda rápido demais e garante que o payload é um dicionário."""
        @functools.wraps(handler)
        def wrapper(data=None):
            now = time.monotonic()
            events = recent_events.setdefault(current_sid(), deque())
            while events and now - events[0] > RATE_LIMIT_WINDOW:
                events.popleft()
            if len(events) >= RATE_LIMIT_EVENTS:
                reply("Muitas ações em pouco tempo. Aguarde um instante.")
                return
            events.append(now)
            handler(data if isinstance(data, dict) else {})
        return wrapper

    def sids_in(room_id):
        return [(sid, token) for sid, (rid, token) in connections.items() if rid == room_id]

    def my_room():
        """Devolve (sala, token) de quem enviou o evento, ou (None, None) se ainda não entrou em uma sala."""
        room_id, token = connections.get(current_sid(), (None, None))
        return (rooms.get(room_id) if room_id else None), token

    def current_room(action):
        """Devolve a sala se quem enviou o evento é o jogador da vez; senão avisa e devolve None."""
        room, token = my_room()
        if room is None:
            reply("Sala inexistente. Entre em uma sala primeiro.")
            return None
        if not room.started:
            reply("A partida ainda não começou.")
            return None
        seat = room.seat_of(token)
        if seat is None or seat != room.state.current_player_index:
            reply(f"Não é seu turno para {action}.")
            return None
        return room

    def connected_seats(room):
        return {room.seat_of(token) for _, token in sids_in(room.id)} - {None}

    def public_state(room):
        return state_to_dict(room.state, room.tm, room.bots, connected_seats(room), room.substituted)

    def send_lobby(room):
        # Cada pessoa recebe a sala de espera com a própria posição
        for sid, token in sids_in(room.id):
            emit("lobby", {
                "roomId": room.id,
                "numPlayers": room.num_players,
                "members": len(room.members),
                "you": room.seat_of(token),
                "isHost": token == room.host(),
            }, room=sid)

    def send_private(room, sid, token):
        """Manda a quem está em `sid` o seu assento e, se for jogador, a missão e as cartas."""
        seat = room.seat_of(token)
        emit("joined", {"playerIndex": seat, "started": room.started}, room=sid)
        if room.started and seat is not None:
            emit("mission", {"description": room.state.missions[seat].description}, room=sid)
            emit("hand", hand_to_dict(room.state, room.tm, seat), room=sid)

    def send_hands(room):
        # Cada jogador recebe só as próprias cartas
        for sid, token in sids_in(room.id):
            seat = room.seat_of(token)
            if seat is not None:
                emit("hand", hand_to_dict(room.state, room.tm, seat), room=sid)

    def broadcast_state(room):
        emit("state", public_state(room), room=room.id)
        send_hands(room)

    def run_bots(room):
        """Joga os turnos do computador até chegar a vez de uma pessoa ou a partida acabar."""
        state = room.state
        for _ in range(MAX_BOT_TURNS_IN_A_ROW):
            if state.winner_id is not None or state.current_player_index not in room.bots:
                break
            player = state.current_player()
            attacks = bot.play_turn(room.tm)
            conquered = [state.territories[a["to"]].label for a in attacks if a["conquered"]]
            summary = f"{player.name} (computador) jogou"
            if conquered:
                summary += " e conquistou " + ", ".join(conquered)
            emit("message", {"text": summary + "."}, room=room.id)
            for a in attacks:
                if a["eliminated"] is not None:
                    emit("message", {"text": f"{state.players[a['eliminated']].name} foi eliminado."}, room=room.id)
        broadcast_state(room)

    def finish(room, hands=False):
        """Depois de uma jogada válida: grava a partida e avisa a sala."""
        rooms.save(room)
        if state_needs_bots(room):
            run_bots(room)
            rooms.save(room)
        elif hands:
            broadcast_state(room)
        else:
            emit("state", public_state(room), room=room.id)

    def state_needs_bots(room):
        return room.state.winner_id is None and room.state.current_player_index in room.bots

    @socketio.on("join")
    @guarded
    def on_join(data):
        room_id = data.get("roomId", "default")
        if not isinstance(room_id, str) or not 1 <= len(room_id) <= MAX_ROOM_ID_LENGTH or not room_id.isprintable():
            reply(f"Nome de sala inválido (use até {MAX_ROOM_ID_LENGTH} caracteres).")
            return
        # Sem token (ou com um inválido) a conexão vale como identidade, e o assento não sobrevive a um recarregamento
        token = data.get("token") if valid_token(data.get("token")) else current_sid()
        if connections.get(current_sid()) != (room_id, token):
            leave_current_room()
        rooms.purge_stale()
        try:
            room = rooms.get_or_create(room_id)
        except RuleError as e:
            reply(str(e))
            return

        connections[current_sid()] = (room_id, token)
        join_room(room_id)
        room.touch()

        if room.started:
            seat = room.seat_of(token)
            send_private(room, current_sid(), token)
            if seat is None:
                emit("state", public_state(room), room=current_sid())
                reply(f"A partida na sala {room_id} já começou; você entrou como espectador.")
                return
            away_since.pop((room_id, seat), None)
            if room.restore(seat):
                rooms.save(room)
                emit("message", {"text": f"Jogador {seat + 1} voltou e reassumiu o lugar."}, room=room_id)
            else:
                emit("message", {"text": f"Jogador {seat + 1} entrou na sala {room_id}."}, room=room_id)
            # Todos veem que o jogador está presente de novo
            emit("state", public_state(room), room=room_id)
            return

        if not room.add_member(token):
            reply(f"A sala {room_id} está cheia; você entrou como espectador.")
        send_private(room, current_sid(), token)
        send_lobby(room)

    @socketio.on("configure")
    @guarded
    def on_configure(data):
        room, token = my_room()
        if room is None or token != room.host():
            reply("Só quem criou a sala pode configurar a partida.")
            return
        try:
            room.configure(data.get("numPlayers"))
        except RuleError as e:
            reply(str(e))
            return
        send_lobby(room)

    @socketio.on("start_game")
    @guarded
    def on_start_game(data):
        room, token = my_room()
        if room is None or token != room.host():
            reply("Só quem criou a sala pode iniciar a partida.")
            return
        try:
            room.start()
        except RuleError as e:
            reply(str(e))
            return
        rooms.save(room)
        humans = len(room.seats)
        text = f"Partida iniciada com {room.num_players} jogadores"
        if room.bots:
            text += f" ({humans} pessoa(s) e {len(room.bots)} controlado(s) pelo computador)"
        emit("message", {"text": text + "."}, room=room.id)
        for sid, member_token in sids_in(room.id):
            send_private(room, sid, member_token)
        emit("state", public_state(room), room=room.id)

    @socketio.on("substitute")
    @guarded
    def on_substitute(data):
        room, token = my_room()
        if room is None or not room.started:
            reply("A partida ainda não começou.")
            return
        if room.seat_of(token) is None:
            reply("Só quem está jogando pode passar um lugar para o computador.")
            return
        seat = data.get("seat")
        state = room.state
        try:
            if state.winner_id is not None:
                raise RuleError("A partida já terminou.")
            if type(seat) is not int or not 0 <= seat < len(state.players):
                raise RuleError("Jogador inexistente.")
            if seat in connected_seats(room):
                raise RuleError(f"O Jogador {seat + 1} está na sala.")
            waited = time.monotonic() - away_since.get((room.id, seat), STARTED_AT)
            if waited < ABANDON_SECONDS and seat not in room.bots:
                raise RuleError(f"Aguarde mais {int(ABANDON_SECONDS - waited) + 1} segundo(s): "
                                f"o Jogador {seat + 1} acabou de sair e pode estar voltando.")
            room.substitute(seat)
        except RuleError as e:
            reply(str(e))
            return
        emit("message", {"text": f"O computador assumiu o lugar do Jogador {seat + 1} até ele voltar."}, room=room.id)
        rooms.save(room)
        if state_needs_bots(room):
            run_bots(room)
            rooms.save(room)
        else:
            emit("state", public_state(room), room=room.id)

    @socketio.on("start_turn")
    @guarded
    def on_start_turn(data):
        room = current_room("iniciar")
        if not room:
            return
        try:
            reinf = room.tm.start_turn()
        except RuleError as e:
            reply(str(e))
            return
        rooms.save(room)
        emit("turn_started", {"reinforcements": reinf, "state": public_state(room)}, room=room.id)

    @socketio.on("trade")
    @guarded
    def on_trade(data):
        room = current_room("trocar cartas")
        if not room:
            return
        cards = data.get("cards")
        try:
            if not isinstance(cards, list) or not all(isinstance(c, str) for c in cards):
                raise RuleError("Escolha 3 cartas da sua mão.")
            gained = room.tm.trade_cards_if_any(cards)
            if not gained:
                raise RuleError("Escolha 3 cartas da sua mão.")
        except RuleError as e:
            reply(str(e))
            return
        player = room.state.current_player()
        emit("message", {"text": f"{player.name} trocou cartas por {gained} tropas."}, room=room.id)
        finish(room, hands=True)

    @socketio.on("place")
    @guarded
    def on_place(data):
        room = current_room("colocar tropas")
        if not room:
            return
        placements = data.get("placements", {})
        try:
            if not isinstance(placements, dict):
                raise RuleError("Posicionamento inválido.")
            room.tm.place_reinforcements(placements)
        except RuleError as e:
            reply(str(e))
            return
        finish(room)

    @socketio.on("attack")
    @guarded
    def on_attack(data):
        room = current_room("atacar")
        if not room:
            return
        from_t = data.get("from")
        to_t = data.get("to")
        try:
            dice = data.get("dice", 3)
            if type(dice) is not int or not isinstance(from_t, str) or not isinstance(to_t, str):
                raise RuleError("Ataque inválido.")
            res = room.tm.do_attack(from_t, to_t, dice)
        except RuleError as e:
            reply(str(e))
            return
        rooms.save(room)
        emit("attack_result", {"result": res, "from": from_t, "to": to_t, "state": public_state(room)}, room=room.id)
        if res["eliminated"] is not None:
            # As cartas do eliminado mudaram de mão
            send_hands(room)

    @socketio.on("occupy")
    @guarded
    def on_occupy(data):
        room = current_room("ocupar o território")
        if not room:
            return
        try:
            room.tm.occupy(data.get("count"))
        except RuleError as e:
            reply(str(e))
            return
        finish(room)

    @socketio.on("begin_fortify")
    @guarded
    def on_begin_fortify(data):
        room = current_room("remanejar")
        if not room:
            return
        try:
            room.tm.begin_fortify()
        except RuleError as e:
            reply(str(e))
            return
        finish(room)

    @socketio.on("fortify")
    @guarded
    def on_fortify(data):
        room = current_room("remanejar")
        if not room:
            return
        from_t = data.get("from")
        to_t = data.get("to")
        try:
            if not isinstance(from_t, str) or not isinstance(to_t, str):
                raise RuleError("Remanejamento inválido.")
            room.tm.fortify(from_t, to_t, data.get("count", 1))
        except RuleError as e:
            reply(str(e))
            return
        finish(room)

    @socketio.on("end_turn")
    @guarded
    def on_end_turn(data):
        room = current_room("encerrar")
        if not room:
            return
        try:
            room.tm.end_turn()
        except RuleError as e:
            reply(str(e))
            return
        # Quem conquistou um território pode ter recebido uma carta
        finish(room, hands=True)

    def leave_current_room():
        """Tira a conexão da sala em que está. Na sala de espera o lugar é liberado; na partida, o assento fica guardado."""
        entry = connections.pop(current_sid(), None)
        if entry is None:
            return
        room_id, token = entry
        room = rooms.get(room_id)
        if room is None:
            return
        leave_room(room_id)
        still_here = any(t == token for _, t in sids_in(room_id))
        if room.started:
            seat = room.seat_of(token)
            if seat is not None and not still_here:
                away_since[(room_id, seat)] = time.monotonic()
                emit("message", {"text": f"Jogador {seat + 1} saiu da sala; o lugar dele fica guardado."}, room=room_id)
                # Quem ficou vê o jogador como ausente e pode passar o lugar ao computador
                emit("state", public_state(room), room=room_id)
            return
        if not still_here:
            room.remove_member(token)
        if not room.members and not sids_in(room_id):
            rooms.remove(room_id)  # sala de espera vazia não precisa continuar existindo
        else:
            send_lobby(room)

    @socketio.on("disconnect")
    def on_disconnect(*args):
        leave_current_room()
        recent_events.pop(current_sid(), None)
