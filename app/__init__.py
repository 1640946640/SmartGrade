from flask import Flask
from app.config import Config
from app.utils.logger import setup_logging

def create_app():
    # Setup logging
    setup_logging()
    
    app = Flask(__name__, 
                static_folder='../static',
                template_folder='../templates')
    
    app.config.from_object(Config)
    Config.init_app(app)
    
    # Register blueprints
    from app.routes import main, api
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp)
    
    return app
