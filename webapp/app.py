import os
from flask import Flask, render_template
from flask_socketio import SocketIO
from webapp.socket_handlers import register_socket_handlers

def _cors_origins():
    # Sem configuração, só a própria origem pode abrir conexões.
    # WAR_CORS_ORIGINS aceita uma lista separada por vírgulas, para quando a página é servida de outro endereço.
    origins = [o.strip() for o in os.environ.get("WAR_CORS_ORIGINS", "").split(",") if o.strip()]
    return origins or None

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins=_cors_origins(), max_http_buffer_size=64 * 1024)

@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self' ws: wss:",
    )
    return response

@app.route("/")
def index():
    return render_template("index.html")

register_socket_handlers(socketio)

def main():
    # Por padrão o servidor só atende a própria máquina; use WAR_HOST=0.0.0.0 para jogar na rede local
    host = os.environ.get("WAR_HOST", "127.0.0.1")
    port = int(os.environ.get("WAR_PORT", "50001"))
    socketio.run(app, host=host, port=port)

if __name__ == "__main__":
    main()
