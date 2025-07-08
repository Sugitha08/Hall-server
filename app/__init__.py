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

    app.register_blueprint(auth , url_prefix='/api/auth')
    app.register_blueprint(booking, url_prefix='/api/event')
    app.register_blueprint(accounts, url_prefix='/api/account')
    app.register_blueprint(notes, url_prefix='/api/notes')
    app.register_blueprint(personal, url_prefix='/api/personal')

    return app