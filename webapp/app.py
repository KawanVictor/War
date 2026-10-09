from flask import Flask, render_template
from flask_socketio import SocketIO
from webapp.socket_handlers import register_socket_handlers

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")  # Permite conexões de qualquer origem para teste

@app.route("/")
def index():
    return render_template("index.html")

register_socket_handlers(socketio)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=50001)
