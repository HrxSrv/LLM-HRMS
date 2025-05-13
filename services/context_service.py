import logging
from typing import Dict, List, Optional
import uuid
from sqlalchemy.orm import Session
import google.generativeai as genai
import os

from database.db import SessionLocal
from models.models import User, ChatSession, ChatMessage

# Configure logging
logger = logging.getLogger(__name__)

# Configure the Gemini API for summarization
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
summarization_model = genai.GenerativeModel('gemini-pro')

def get_or_create_chat_session(db: Session, user_id: str) -> ChatSession:
    """
    Get existing chat session or create a new one
    
    Args:
        db: Database session
        user_id: User identifier (phone number or user ID)
        
    Returns:
        ChatSession object
    """
    # Find user by phone number or create one if not exists
    user = db.query(User).filter(User.phone_number == user_id).first()
    
    if not user:
        # Create placeholder user if not found
        user = User(
            username=f"user_{uuid.uuid4().hex[:8]}",
            phone_number=user_id,
            email=f"user_{uuid.uuid4().hex[:8]}@placeholder.com",
            role="employee"  # Default role
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Get most recent active session or create new one
    session = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .first()
    )
    
    if not session:
        # Create new session
        session = ChatSession(
            user_id=user.id,
            session_id=f"session_{uuid.uuid4().hex}",
            summary="New conversation"
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    
    return session

def store_chat_context(user_id: str, user_message: str, assistant_response: str) -> None:
    """
    Store chat messages and update context summary
    
    Args:
        user_id: User identifier
        user_message: Message from user
        assistant_response: Response from assistant
    """
    db = SessionLocal()
    try:
        # Get or create chat session
        session = get_or_create_chat_session(db, user_id)
        
        # Store user message
        user_msg = ChatMessage(
            session_id=session.id,
            role="user",
            content=user_message
        )
        db.add(user_msg)
        
        # Store assistant response
        assistant_msg = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=assistant_response
        )
        db.add(assistant_msg)
        
        # Commit to save messages
        db.commit()
        db.refresh(user_msg)
        db.refresh(assistant_msg)
        
        # Update conversation summary if enough messages have accumulated
        message_count = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).count()
        
        # Generate new summary every 5 messages
        if message_count % 5 == 0:
            update_session_summary(db, session.id)
            
    except Exception as e:
        logger.error(f"Error storing chat context: {str(e)}")
        db.rollback()
    finally:
        db.close()

def update_session_summary(db: Session, session_id: int) -> None:
    """
    Generate and update summary of conversation
    
    Args:
        db: Database session
        session_id: Chat session ID
    """
    try:
        # Get last 10 messages from the session
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.timestamp.desc())
            .limit(10)
            .all()
        )
        
        if not messages:
            return
            
        # Prepare conversation for summarization
        conversation_text = "\n".join([
            f"{'User' if msg.role == 'user' else 'Assistant'}: {msg.content}"
            for msg in reversed(messages)
        ])
        
        # Generate summary using Gemini
        prompt = f"""
        Summarize the following conversation in 1-2 sentences. Focus on key topics, requests, 
        and information exchanged. This summary will be used as context for future conversation.
        
        Conversation:
        {conversation_text}
        
        Summary:
        """
        
        summary_response = summarization_model.generate_content(prompt)
        summary = summary_response.text.strip()
        
        # Update session summary
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.summary = summary
            db.commit()
            
    except Exception as e:
        logger.error(f"Error updating session summary: {str(e)}")
        db.rollback()

def retrieve_chat_context(user_id: str) -> Optional[Dict]:
    """
    Retrieve conversation context for a user
    
    Args:
        user_id: User identifier
        
    Returns:
        Dictionary with conversation context
    """
    db = SessionLocal()
    try:
        # Get or create chat session
        session = get_or_create_chat_session(db, user_id)
        
        # Get recent messages (last 5)
        recent_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.timestamp.desc())
            .limit(5)
            .all()
        )
        
        # Format messages for context
        formatted_messages = [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
            }
            for msg in reversed(recent_messages)
        ]
        
        return {
            "summary": session.summary,
            "recent_messages": formatted_messages
        }
        
    except Exception as e:
        logger.error(f"Error retrieving chat context: {str(e)}")
        return {"summary": "Error retrieving context", "recent_messages": []}
    finally:
        db.close()