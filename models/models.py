from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class RoleType(str, enum.Enum):
    EMPLOYEE = "employee"
    HR = "hr"
    ADMIN = "admin"

class LeaveStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# class User(Base):
#     __tablename__ = "users"
    
#     id = Column(Integer, primary_key=True, index=True)
#     username = Column(String(50), unique=True, index=True)
#     email = Column(String(100), unique=True, index=True)
#     phone_number = Column(String(20), unique=True, index=True)
#     hashed_password = Column(String(255))
#     role = Column(String(20), default="employee")
#     is_active = Column(Boolean, default=True)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
#     # Relationships
#     chat_sessions = relationship("ChatSession", back_populates="user")
# leaves = relationship(
#     "LeaveRequest",
#     back_populates="employee",
#     foreign_keys="LeaveRequest.employee_id"
# )

    
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String(100), unique=True, index=True)
    summary = Column(Text, nullable=True)
    context_vector = Column(String, nullable=True)  # Store embeddings or reference to vector DB
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    role = Column(String(20))  # 'user' or 'assistant'
    content = Column(Text)
    summary = Column(Text, nullable=True)  # Summarized content for context
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    phone_number = Column(String(20), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(String(20), default="employee")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    chat_sessions = relationship("ChatSession", back_populates="user")
    leaves = relationship(
        "LeaveRequest",
        back_populates="employee",
        foreign_keys="LeaveRequest.employee_id"
    )
    approved_leaves = relationship(
        "LeaveRequest",
        back_populates="approver",
        foreign_keys="LeaveRequest.approved_by"
    )


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("users.id"))
    leave_type = Column(String(50))
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))
    reason = Column(Text)
    status = Column(String(20), default="pending")
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    calendar_event_id = Column(String(255), nullable=True)

    # Relationships
    employee = relationship(
        "User",
        foreign_keys=[employee_id],
        back_populates="leaves"
    )
    approver = relationship(
        "User",
        foreign_keys=[approved_by],
        back_populates="approved_leaves"
    )


class TaskRecord(Base):
    __tablename__ = "task_records"
    
    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String(50))  # e.g., leave_approval, attendance_update
    user_id = Column(Integer, ForeignKey("users.id"))
    details = Column(JSON)  # Store task-specific details
    status = Column(String(20), default="pending")
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")