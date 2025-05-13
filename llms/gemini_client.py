import os
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, List, Optional

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Configure the Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# System prompts for different roles
SYSTEM_PROMPTS = {
    "employee": """
    You are an AI assistant for an HR Management System. You're currently talking to an EMPLOYEE.
    
    As an assistant to employees, you can:
    - Provide information about company policies
    - Help with checking leave balances and leave application status
    - Assist with submitting HR requests
    - Answer general HR-related questions
    
    You CANNOT:
    - Approve or reject leave requests (only HR can do this)
    - Access confidential employee information
    - Make changes to HR records
    
    Be helpful, concise, and professional.
    """,
    
    "hr": """
    You are an AI assistant for an HR Management System. You're currently talking to an HR STAFF MEMBER.
    
    As an assistant to HR staff, you can:
    - Process leave approval requests
    - Update employee records
    - Access HR dashboards and reports
    - Schedule interviews and meetings
    - Help manage HR communications
    
    You have elevated permissions to handle employee data and make HR decisions.
    You should confirm critical actions before executing them.
    
    Be efficient, detail-oriented, and maintain confidentiality.
    """
}

async def get_gemini_response(message: str, user_id: str, role: str = "employee", 
                             conversation_history: Optional[List[Dict]] = None) -> str:
    """
    Get response from Gemini API based on user role and conversation history
    
    Args:
        message: User's message
        user_id: Unique identifier for user
        role: User role (employee or hr)
        conversation_history: Previous messages for context
        
    Returns:
        Response text from Gemini
    """
    try:
        # Set up the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Create chat session
        chat = model.start_chat(history=[])
        
        # Add system prompt based on role
        system_prompt = SYSTEM_PROMPTS.get(role.lower(), SYSTEM_PROMPTS["employee"])
        chat.send_message(f"[SYSTEM INSTRUCTION] {system_prompt}")
        
        # Add conversation history for context
        if conversation_history:
            for entry in conversation_history:
                role_type = "user" if entry.get("role") == "user" else "model"
                content = entry.get("content", "")
                if role_type == "user":
                    chat.send_message(content)
                else:
                    # For model messages, we're just setting up context, 
                    # not expecting a response
                    chat._history.append({"role": "model", "parts": [content]})
        
        # Send the current message and get response
        response = chat.send_message(message)
        
        logger.info(f"Gemini API response received for user {user_id}")
        return response.text
        
    except Exception as e:
        logger.error(f"Error in Gemini API call: {str(e)}")
        return "I'm sorry, I encountered an error processing your request. Please try again later."