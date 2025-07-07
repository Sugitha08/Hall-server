from flask import Flask , Blueprint
from app.config import Config
from app.routes import auth, booking, accounts, notes, personal
from app.extension import jwt , db , migrate , cors ,mail, scheduler,limiter
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app)
    mail.init_app(app)
    scheduler.init_app(app)
    limiter.init_app(app)
    scheduler.start()
    CORS(app, supports_credentials=True)

    app.register_blueprint(auth , url_prefix='/auth')
    app.register_blueprint(booking, url_prefix='/event')
    app.register_blueprint(accounts, url_prefix='/account')
    app.register_blueprint(notes, url_prefix='/notes')
    app.register_blueprint(personal, url_prefix='/personal')

    return app