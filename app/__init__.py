import os
from flask import Flask, g
from dotenv import load_dotenv

def create_app(test_config=None):
    # Load environment variables
    load_dotenv()
    
    app = Flask(__name__, instance_relative_config=True)
    
    # Configure App
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY', 'dev-secret-key-12345'),
        DATABASE_URL=os.getenv('DATABASE_URL'),
    )
    
    if test_config is not None:
        app.config.from_mapping(test_config)
        
    # Ensure DATABASE_URL is present
    if not app.config.get('DATABASE_URL'):
        raise ValueError("DATABASE_URL is not set. Please configure it in your environment or .env file.")
        
    # Initialize Database connection pool
    from app.db import init_pool
    init_pool(app)
    
    # Register context processors to make current_user available in templates
    @app.context_processor
    def inject_user():
        return dict(current_user=g.user if hasattr(g, 'user') else None)
        
    # Register Blueprints
    from app.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.tickets import tickets_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tickets_bp)
    
    return app
