import google.generativeai as genai
from dotenv import load_dotenv
import os
import sys
# Get the directory of the current script (gemini_client.py)
current_dir = os.path.dirname(__file__)
# Construct the path to the parent directory (LLMS)
llms_dir = os.path.abspath(current_dir)
# Construct the path to the grandparent directory (your_project_root)
project_root = os.path.abspath(os.path.join(llms_dir, ".."))

# Add the project root to sys.path
sys.path.append(project_root)
from contexts.hr_contexts import HR_CONTEXT

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key='AIzaSyAoTrxXVJbeTdDejsMRT1rF0Y7ORVSWnGA')

# Setup the model
model = genai.GenerativeModel('gemini-2.0-flash-lite')

# Store conversation history with users
user_conversations = {}

async def get_gemini_response(message, user_id):
    """
    Get a response from Gemini API with HR context
    """
    # Initialize conversation for new users
    if user_id not in user_conversations:
        user_conversations[user_id] = model.start_chat(history=[
            {
                "role": "user",
                "parts": ["Here is context about our company's HR policies. Use this to answer employee questions."]
            },
            {
                "role": "model",
                "parts": ["I understand. I'll use this HR policy information to help answer employee questions accurately and professionally."]
            },
            {
                "role": "user", 
                "parts": [HR_CONTEXT]
            },
            {
                "role": "model",
                "parts": ["I've recorded all the HR policies and information. I'm ready to assist employees with their HR-related queries in a professional and helpful manner."]
            }
        ])
    
    try:
        # Get response from Gemini
        response = user_conversations[user_id].send_message(message)
        
        # Format and return the response
        return response.text
        
    except Exception as e:
        print(f"Error with Gemini API: {e}")
        return "I'm having trouble connecting right now. Please try again shortly or contact HR directly at hr@company.com."