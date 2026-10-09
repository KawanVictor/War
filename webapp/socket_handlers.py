from flask import request
from flask_socketio import join_room, emit
from war_game.rules.errors import RuleError
from webapp.rooms import rooms
from webapp.state_adapter import state_to_dict

# Dicionário global para mapear sala para dicionário sid->player_index
room_players = {}

def register_socket_handlers(socketio):
    def reply(text):
        emit("message", {"text": text}, room=request.sid)

    def current_room(data, action):
        """Devolve (room_id, room) se quem enviou o evento é o jogador da vez; senão avisa e devolve None."""
        room_id = data.get("roomId") if isinstance(data, dict) else None
        room = rooms.get(room_id) if isinstance(room_id, str) else None
        if room is None:
            reply("Sala inexistente. Entre em uma sala primeiro.")
            return None
        player_index = room_players.get(room_id, {}).get(request.sid)
        if player_index is None or player_index != room.state.current_player_index:
            reply(f"Não é seu turno para {action}.")
            return None
        return room_id, room

    @socketio.on("join")
    def on_join(data):
        if not isinstance(data, dict):
            data = {}
        room_id = data.get("roomId", "default")
        if not isinstance(room_id, str) or not room_id:
            reply("Nome de sala inválido.")
            return
        try:
            room = rooms.get_or_create(room_id, data.get("numPlayers", 3))
        except RuleError as e:
            reply(str(e))
            return
        join_room(room_id)

        seats = room_players.setdefault(room_id, {})
        # Se o sid já está no mapa, retorna o índice
        if request.sid in seats:
            player_index = seats[request.sid]
        else:
            # Atribui o primeiro assento livre; com a sala cheia, entra como espectador
            available = set(range(len(room.state.players))) - set(seats.values())
            player_index = min(available) if available else None
            if player_index is not None:
                seats[request.sid] = player_index

        emit("joined", {"playerIndex": player_index}, room=request.sid)
        emit("state", state_to_dict(room.state), room=request.sid)
        if player_index is None:
            reply(f"A sala {room_id} está cheia; você entrou como espectador.")
            return
        emit("mission", {"description": room.state.missions[player_index].description}, room=request.sid)
        emit("message", {"text": f"Entrou na sala {room_id} como Jogador {player_index + 1}."}, to=room_id)

    @socketio.on("start_turn")
    def on_start_turn(data):
        found = current_room(data, "iniciar")
        if not found:
            return
        room_id, room = found
        try:
            reinf = room.tm.start_turn()
        except RuleError as e:
            reply(str(e))
            return
        emit("turn_started", {"reinforcements": reinf, "state": state_to_dict(room.state)}, room=room_id)

    @socketio.on("place")
    def on_place(data):
        found = current_room(data, "colocar tropas")
        if not found:
            return
        room_id, room = found
        placements = data.get("placements", {})
        try:
            if not isinstance(placements, dict):
                raise RuleError("Posicionamento inválido.")
            room.tm.place_reinforcements(placements)
        except RuleError as e:
            reply(str(e))
            return
        emit("state", state_to_dict(room.state), room=room_id)

    @socketio.on("attack")
    def on_attack(data):
        found = current_room(data, "atacar")
        if not found:
            return
        room_id, room = found
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
        emit("attack_result", {"result": res, "state": state_to_dict(room.state)}, room=room_id)

    @socketio.on("end_turn")
    def on_end_turn(data):
        found = current_room(data, "encerrar")
        if not found:
            return
        room_id, room = found
        try:
            room.tm.end_turn()
        except RuleError as e:
            reply(str(e))
            return
        emit("state", state_to_dict(room.state), room=room_id)

    @socketio.on("disconnect")
    def on_disconnect():
        # Remove jogador do mapa quando desconectar
        for room_id, players_map in room_players.items():
            if request.sid in players_map:
                del players_map[request.sid]
                # Opcional: emitir mensagem que jogador saiu
                emit("message", {"text": f"Jogador saiu da sala {room_id}."}, room=room_id)
                break
