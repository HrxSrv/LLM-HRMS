from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Optional, List
import uvicorn
import logging
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import json
from datetime import datetime

# Import modules
from services.orchestrator import orchestrator
from database.pgDb import get_db, SessionLocal, engine
from models.models import Base, User, ChatSession, ChatMessage
from services.auth_service import get_current_user
from services.context_service import retrieve_chat_context
from services.twilio_service import send_whatsapp_message

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

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(title="LLM HRMS", description="Role-based HR Management System with LLM capabilities")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class MessageRequest(BaseModel):
    message: str
    user_id: str
    role: Optional[str] = "employee"

class MessageResponse(BaseModel):
    response: str
    requires_action: bool = False
    action_details: Optional[Dict] = None

# Utility to convert datetime for JSON
def json_serial(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError("Type not serializable")

# Route: Twilio Webhook
@app.post("/webhook", response_class=PlainTextResponse)
async def webhook(request: Request):
    form_data = await request.form()
    incoming_msg = form_data.get('Body', '').strip()
    sender = form_data.get('From', '')
    user_id = sender.split(':')[1] if ':' in sender else sender

    logger.info(f"Received message from {sender}: {incoming_msg}")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone_number == user_id).first()
        role = user.role if user else "employee"
        user_info = {
            "id": user.id if user else None,
            "name": user.username if user else "Unknown",
            "email": user.email if user else "",
            "phone": user.phone_number if user else user_id,
            "role": role
        }
    finally:
        db.close()

    context = retrieve_chat_context(user_id)
    response = await orchestrator.process_message(incoming_msg, user_id, user_info, role, context)

    # Just return the response — Twilio will send it back to the user
    return PlainTextResponse(content=response, status_code=200)


# Route: Web Chat (Authenticated)
@app.post("/chat", response_model=MessageResponse)
async def chat(message_request: MessageRequest, current_user=Depends(get_current_user)):
    if message_request.role == "hr" and current_user.role != "hr":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to use HR role"
        )

    user_info = {
        "id": current_user.id,
        "name": current_user.username,
        "email": current_user.email,
        "phone": current_user.phone_number,
        # "joined": current_user.created_at,
        "role": current_user.role
    }

    context = retrieve_chat_context(message_request.user_id)
    response = await orchestrator.process_message(
        message_request.message,
        message_request.user_id,
        user_info,
        message_request.role,
        context
    )

    return MessageResponse(response=response)

# Health Check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Main Entry
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)