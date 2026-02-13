import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER')
    DATABASE_URL =os.getenv('DATABASE_URL') 
    DATABASE_URL_DIRECT = os.getenv('DATABASE_URL_DIRECT')
    MCP_SERVER_PATH = os.getenv('MCP_SERVER_PATH')