from flask import request
from flask_socketio import join_room, leave_room, emit
from war_game.rules.errors import RuleError
from webapp.rooms import rooms
from webapp.state_adapter import state_to_dict

# Dicionário global para mapear sala para dicionário sid->player_index
room_players = {}

def register_socket_handlers(socketio):
    @socketio.on("join")
    def on_join(data):
        room_id = data.get("roomId", "default")
        num_players = int(data.get("numPlayers", 3))

        room = rooms.get_or_create(room_id, num_players)
        join_room(room_id)

        if room_id not in room_players:
            room_players[room_id] = {}

        # Se o sid já está no mapa, retorna o índice
        if request.sid in room_players[room_id]:
            player_index = room_players[room_id][request.sid]
        else:
            # Atribui índice disponível (primeiro que não foi atribuído)
            assigned = set(room_players[room_id].values())
            available = set(range(num_players)) - assigned
            player_index = min(available) if available else 0
            room_players[room_id][request.sid] = player_index

        emit("joined", {"playerIndex": player_index}, room=request.sid)
        emit("state", state_to_dict(room.state), room=request.sid)
        emit("message", {"text": f"Entrou na sala {room_id} como Jogador {player_index + 1}."}, to=room_id)

    @socketio.on("start_turn")
    def on_start_turn(data):
        room_id = data.get("roomId")
        room = rooms.get_or_create(room_id)
        # Apenas o jogador da vez pode iniciar o turno
        player_index = room_players.get(room_id, {}).get(request.sid)
        if player_index != room.state.current_player_index:
            emit("message", {"text": "Não é seu turno para iniciar."}, room=request.sid)
            return

        reinf = room.tm.start_turn()
        emit("turn_started", {"reinforcements": reinf, "state": state_to_dict(room.state)}, room=room_id)

    @socketio.on("place")
    def on_place(data):
        room_id = data.get("roomId")
        room = rooms.get_or_create(room_id)
        player_index = room_players.get(room_id, {}).get(request.sid)
        if player_index != room.state.current_player_index:
            emit("message", {"text": "Não é seu turno para colocar tropas."}, room=request.sid)
            return

        placements = data.get("placements", {})
        try:
            if not isinstance(placements, dict):
                raise RuleError("Posicionamento inválido.")
            room.tm.place_reinforcements(placements)
        except RuleError as e:
            emit("message", {"text": str(e)}, room=request.sid)
            return
        emit("state", state_to_dict(room.state), room=room_id)

    @socketio.on("attack")
    def on_attack(data):
        room_id = data.get("roomId")
        room = rooms.get_or_create(room_id)
        player_index = room_players.get(room_id, {}).get(request.sid)
        if player_index != room.state.current_player_index:
            emit("message", {"text": "Não é seu turno para atacar."}, room=request.sid)
            return

        from_t = data.get("from")
        to_t = data.get("to")
        try:
            dice = data.get("dice", 3)
            if type(dice) is not int:
                raise RuleError("Quantidade de dados inválida.")
            res = room.tm.do_attack(from_t, to_t, dice)
        except RuleError as e:
            emit("message", {"text": str(e)}, room=request.sid)
            return
        emit("attack_result", {"result": res, "state": state_to_dict(room.state)}, room=room_id)

    @socketio.on("end_turn")
    def on_end_turn(data):
        room_id = data.get("roomId")
        room = rooms.get_or_create(room_id)
        player_index = room_players.get(room_id, {}).get(request.sid)
        if player_index != room.state.current_player_index:
            emit("message", {"text": "Não é seu turno para encerrar."}, room=request.sid)
            return

        room.tm.end_turn()
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
