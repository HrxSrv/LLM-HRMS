from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import os
import logging
from test_response import get_response

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    """Webhook for WhatsApp messages via Twilio"""
    # Get the message from the request
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    
    # Log incoming message
    logger.info(f"Received message from {sender}: {incoming_msg}")
    
    # Get response for the message
    response_text = get_response(incoming_msg)
    
    # Create Twilio response
    resp = MessagingResponse()
    resp.message(response_text)
    
    # Log the response
    logger.info(f"Sending response to {sender}: {response_text[:50]}...")
    
    return str(resp)

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return "OK", 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)