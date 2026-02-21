import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'supersecretkey')
    
    # Base directory is the parent of the 'app' directory
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    GRADING_FOLDER = os.path.join(BASE_DIR, 'static', 'grading')
    ANSWERS_FOLDER = os.path.join(BASE_DIR, 'answers')
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    ALLOWED_ANSWER_EXTENSIONS = {'doc', 'docx'}
    
    # Ensure directories exist
    @staticmethod
    def init_app(app):
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.GRADING_FOLDER, exist_ok=True)
        os.makedirs(Config.ANSWERS_FOLDER, exist_ok=True)
