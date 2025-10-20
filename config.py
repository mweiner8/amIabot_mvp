"""
Configuration settings for AmIABot.com MVP
Handles environment variables and game settings
"""

import os


class Config:
    """Application configuration from environment variables"""

    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24).hex())
    DEBUG = False  # Always False for production

    # External services
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

    # Game timing settings (in seconds)
    QUEUE_WAIT_TIME = int(os.environ.get('QUEUE_WAIT_TIME', 30))
    CONVERSATION_TIME = int(os.environ.get('CONVERSATION_TIME', 180))
    DECISION_TIME = int(os.environ.get('DECISION_TIME', 30))

    # Bot behavior settings
    BOT_RESPONSE_DELAY = (1, 4)

    # Performance settings
    MAX_MESSAGE_LENGTH = 500
    MAX_CONVERSATION_HISTORY = 50

    # Server settings
    HOST = '0.0.0.0'
    PORT = int(os.environ.get('PORT', 10000))