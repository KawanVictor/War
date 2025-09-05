from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")  # Permite conexões de qualquer origem para teste

@app.route("/")
def index():
    return render_template("index.html")

# Dicionário para mapear sala para sid->player_index
room_players = {}

@socketio.on("join")
def on_join(data):
    room_id = data.get("roomId", "default")
    num_players = int(data.get("numPlayers", 3))

    if room_id not in room_players:
        room_players[room_id] = {}

    if request.sid in room_players[room_id]:
        player_index = room_players[room_id][request.sid]
    else:
        assigned = set(room_players[room_id].values())
        available = set(range(num_players)) - assigned
        player_index = min(available) if available else 0
        room_players[room_id][request.sid] = player_index

    join_room(room_id)
    emit("joined", {"playerIndex": player_index}, room=request.sid)
    emit("message", {"text": f"Entrou na sala {room_id} como Jogador {player_index + 1}."}, room=room_id)

@socketio.on("start_turn")
def on_start_turn(data):
    room_id = data.get("roomId")
    player_index = room_players.get(room_id, {}).get(request.sid)
    if player_index is None:
        emit("message", {"text": "Jogador não autorizado."}, room=request.sid)
        return
    # Simulação de turno iniciado
    emit("turn_started", {"reinforcements": 5, "state": {}}, room=room_id)

@socketio.on("place")
def on_place(data):
    room_id = data.get("roomId")
    # Atualize estado conforme sua lógica real aqui
    emit("state", {}, room=room_id)

@socketio.on("attack")
def on_attack(data):
    room_id = data.get("roomId")
    # Atualize estado conforme sua lógica real aqui
    emit("attack_result", {"result": {"status": "ok"}, "state": {}}, room=room_id)

@socketio.on("end_turn")
def on_end_turn(data):
    room_id = data.get("roomId")
    emit("message", {"text": "Turno finalizado."}, room=room_id)

@socketio.on("disconnect")
def on_disconnect():
    for room_id, players in room_players.items():
        if request.sid in players:
            del players[request.sid]
            emit("message", {"text": f"Jogador saiu da sala {room_id}."}, room=room_id)
            break

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=50001)