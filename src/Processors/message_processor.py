import re
from datetime import datetime

def preprocess_message(message, user_id):
    """
    Preprocess messages before sending to Gemini
    """
    # Check for specific commands or formats
    if message.lower() == "check in":
        return f"I want to record my attendance check-in for today {datetime.now().strftime('%d-%m-%Y')} at {datetime.now().strftime('%H:%M')}"
    
    if message.lower() == "check out":
        return f"I want to record my attendance check-out for today {datetime.now().strftime('%d-%m-%Y')} at {datetime.now().strftime('%H:%M')}"
    
    # Handle leave application format
    leave_match = re.search(r"apply leave from (\d{2}-\d{2}-\d{4}) to (\d{2}-\d{2}-\d{4})(.*)", message.lower())
    if leave_match:
        start_date = leave_match.group(1)
        end_date = leave_match.group(2)
        reason = leave_match.group(3).strip(", ")
        return f"I want to formally apply for leave starting {start_date} until {end_date}. Reason: {reason}"
    
    return message

def postprocess_response(response):
    """
    Clean up or format the Gemini response before sending to user
    """
    # Remove any system prompts that might leak through
    response = re.sub(r"As an AI assistant|As an HR assistant", "", response)
    
    # Format the response for WhatsApp (add emoji, formatting)
    response = response.replace("**", "*")  # Convert markdown bold to WhatsApp bold
    
    # Add helpful formatting for readability
    if "leave balance" in response.lower():
        response = "📊 *Leave Balance*\n\n" + response
    elif "attendance" in response.lower():
        response = "⏰ *Attendance*\n\n" + response
    elif "payroll" in response.lower():
        response = "💰 *Payroll Information*\n\n" + response
    
    return response.strip()