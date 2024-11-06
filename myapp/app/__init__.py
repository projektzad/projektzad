# /app/__init__.py

from flask import Flask
from .routes import main_routes  # Import routes from routes.py

def create_app():
    # Initialize the Flask app
    app = Flask(__name__)

    # Set the secret key (for session management, CSRF protection, etc.)
    app.config['SECRET_KEY'] = '_5#y2L"F4Q8z\n\xec]/'

    # Register the routes (blueprint or directly)
    app.register_blueprint(main_routes)

    return app
