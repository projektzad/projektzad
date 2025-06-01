# myapp/app/__init__.py
from flask import Flask
from .routes import main_routes  # Assuming routes.py is in the same directory
import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '_5#y2L"F4Q8z\n\xec]/')  # Use env var for secret key

    # Configure logging
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')

        file_handler = RotatingFileHandler('logs/ldap_admin.log', maxBytes=102400, backupCount=10)  # Increased maxBytes
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        # Set the level for the handler and the app.logger
        # For debugging issues in models, you might want DEBUG here during development
        log_level = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
        file_handler.setLevel(log_level)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(log_level)

        # Also configure the root logger if you want other libraries (like ldap3) to log to this file
        # logging.getLogger().addHandler(file_handler) # Be careful with this, can make logs very verbose
        # logging.getLogger().setLevel(log_level)

        app.logger.info('LDAP Admin startup')

    # Register blueprints
    app.register_blueprint(main_routes)

    # Custom Jinja2 filter
    def bitwise_and(value, other):
        try:
            return int(value) & int(other)
        except Exception:
            return 0

    app.jinja_env.filters['bitwise_and'] = bitwise_and

    @app.context_processor
    def inject_now():
        return {'current_year': datetime.utcnow().year}

    return app