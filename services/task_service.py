import logging
from typing import Dict, Optional, List
from datetime import datetime
import re
from sqlalchemy.orm import Session
import json

from database.db import SessionLocal
from models.models import User, LeaveRequest, TaskRecord
from processors.message_processor import extract_task_details

# Configure logging
logger = logging.getLogger(__name__)

def process_task_request(message: str, user_id: str) -> Optional[Dict]:
    """
    Process HR-specific task requests
    
    Args:
        message: User message
        user_id: User identifier
        
    Returns:
        Dictionary with task processing result or None if not a valid task
    """
    # Extract structured details from the message
    task_details = extract_task_details(message)
    
    # If no valid task identified, return None
    if not task_details["task_type"]:
        return None
        
    db = SessionLocal()
    try:
        # Get user
        hr_user = db.query(User).filter(User.phone_number == user_id).first()
        
        # Process based on task type
        if task_details["task_type"] == "leave_approval":
            result = process_leave_approval(db, task_details, hr_user)
            return result
            
        # Add other task types as needed
        
        return None
        
    except Exception as e:
        logger.error(f"Error processing task request: {str(e)}")
        return None
    finally:
        db.close()

def process_leave_approval(db: Session, task_details: Dict, hr_user: User) -> Dict:
    """
    Process leave approval request
    
    Args:
        db: Database session
        task_details: Structured task details
        hr_user: HR user processing the request
        
    Returns:
        Dictionary with task processing result
    """
    result = {
        "success": False,
        "summary": "",
        "details": {},
        "task_type": "leave_approval"
    }
    
    try:
        # Find the employee
        employee_identifier = task_details.get("employee_id")
        if not employee_identifier:
            result["summary"] = "Employee not specified in request"
            return result
            
        # Try to find employee by name, username, or ID
        employee = (
            db.query(User)
            .filter(
                (User.username == employee_identifier) | 
                (User.email.like(f"%{employee_identifier}%")) |
                (User.id == employee_identifier if employee_identifier.isdigit() else False)
            )
            .first()
        )
        
        if not employee:
            result["summary"] = f"Employee '{employee_identifier}' not found"
            return result
            
        # Find pending leave request
        date_range = task_details.get("date_range", {})
        
        query = db.query(LeaveRequest).filter(
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.status == "pending"
        )
        
        # Add date filtering if available
        if date_range and date_range.get("start"):
            # Parse dates (simplified here - would need proper date parsing in production)
            query = query.filter(LeaveRequest.start_date.like(f"%{date_range['start']}%"))
            
        if date_range and date_range.get("end"):
            query = query.filter(LeaveRequest.end_date.like(f"%{date_range['end']}%"))
            
        leave_request = query.first()
        
        if not leave_request:
            result["summary"] = f"No pending leave request found for {employee.username}"
            return result
            
        # Process approval
        leave_request.status = "approved"
        leave_request.approved_by = hr_user.id
        leave_request.approved_at = datetime.now()
        
        # Create task record
        task_record = TaskRecord(
            task_type="leave_approval",
            user_id=hr_user.id,
            details={
                "leave_id": leave_request.id,
                "employee_id": employee.id,
                "action": "approved"
            },
            status="completed",
            completed_at=datetime.now()
        )
        
        db.add(task_record)
        db.commit()
        
        # Prepare response
        result["success"] = True
        result["summary"] = f"Leave request approved for {employee.username} from {leave_request.start_date} to {leave_request.end_date}"
        result["details"] = {
            "leave_id": leave_request.id,
            "employee_id": employee.id,
            "employee_name": employee.username,
            "start_date": str(leave_request.start_date),
            "end_date": str(leave_request.end_date),
            "leave_type": leave_request.leave_type,
            "calendar_update_required": True
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error in leave approval process: {str(e)}")
        result["summary"] = f"Error processing leave approval: {str(e)}"
        return result

def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse date string to datetime object
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        Datetime object or None if parsing fails
    """
    date_formats = [
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", 
        "%d-%m-%Y", "%d %B %Y", "%B %d, %Y"
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
            
    return None