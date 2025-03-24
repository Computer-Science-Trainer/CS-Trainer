from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config
import os

db = SQLAlchemy()


def create_app(config_class=Config):
    template_path = os.path.join(os.path.dirname(__file__), 'templates')
    app = Flask(__name__, template_folder=template_path)

    app.config.from_object(config_class)
    db.init_app(app)

    from src import routes
    routes.init_app(app)

    return app
