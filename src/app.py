from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import os
import logging
import asyncio
from LLMS.gemini_client import get_gemini_response
from Processors.message_processor import preprocess_message, postprocess_response
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
    
    # Extract the phone number from sender (format: 'whatsapp:+1234567890')
    user_id = sender.split(':')[1] if ':' in sender else sender
    
    # Log incoming message
    logger.info(f"Received message from {sender}: {incoming_msg}")
    
    # Get response from Gemini (run async function in sync context)
    processed_message = preprocess_message(incoming_msg, user_id)
    raw_response = asyncio.run(get_gemini_response(processed_message, user_id))
    response_text = postprocess_response(raw_response)
    
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