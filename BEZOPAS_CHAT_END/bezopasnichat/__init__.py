from flask import Flask, render_template
from flask_socketio import SocketIO
from config import Config

socketio = SocketIO(async_mode='threading')

def create_app():
    app = Flask(__name__, static_folder='../static', template_folder='../templates')
    app.config.from_object(Config)

    # Главная страница
    @app.route('/')
    def index():
        return render_template('index.html')

    socketio.init_app(app, cors_allowed_origins="*")

    # Импорт событий (чтобы зарегистрировать обработчики Socket.IO)
    from . import events

    return app