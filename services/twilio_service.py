import logging
from typing import Optional
import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Twilio client
def get_twilio_client() -> Optional[Client]:
    """
    Get Twilio client instance
    
    Returns:
        Twilio Client instance or None if initialization fails
    """
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        if not account_sid or not auth_token:
            logger.error("Twilio credentials not configured")
            return None
            
        return Client(account_sid, auth_token)
        
    except Exception as e:
        logger.error(f"Error initializing Twilio client: {str(e)}")
        return None

def send_whatsapp_message(to_number: str, message: str) -> bool:
    """
    Send WhatsApp message via Twilio
    
    Args:
        to_number: Recipient phone number (with country code)
        message: Message content
        
    Returns:
        Boolean indicating success
    """
    try:
        client = get_twilio_client()
        if not client:
            return False
            
        # Get WhatsApp from number from environment
        from_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
        if not from_number:
            logger.error("WhatsApp 'from' number not configured")
            return False
            
        # Format numbers for WhatsApp if needed
        to_whatsapp = f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number
        from_whatsapp = f"whatsapp:{from_number}" if not from_number.startswith("whatsapp:") else from_number
        
        # Split long messages if needed (WhatsApp limit is around 1600 characters)
        if len(message) > 1500:
            chunks = [message[i:i+1500] for i in range(0, len(message), 1500)]
            
            for chunk in chunks:
                client.messages.create(
                    body=chunk,
                    from_=from_whatsapp,
                    to=to_whatsapp
                )
        else:
            client.messages.create(
                body=message,
                from_=from_whatsapp,
                to=to_whatsapp
            )
            
        logger.info(f"WhatsApp message sent to {to_number}")
        return True
        
    except TwilioRestException as e:
        logger.error(f"Twilio API error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        return False

def validate_whatsapp_webhook(request_data) -> bool:
    """
    Validate Twilio WhatsApp webhook request
    
    Args:
        request_data: Request data from webhook
        
    Returns:
        Boolean indicating if webhook is valid
    """
    # Basic validation - in production you'd implement 
    # request signature validation using Twilio's security features
    
    required_fields = ["From", "Body"]
    
    for field in required_fields:
        if field not in request_data:
            logger.warning(f"Invalid webhook - missing {field}")
            return False
            
    return True