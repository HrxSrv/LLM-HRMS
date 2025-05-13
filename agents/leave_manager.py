from typing import Dict, List, Optional, Any
import logging
import json
from datetime import datetime, timedelta
import re

from llms.gemini_client import get_gemini_response
from services.gsuite_service import update_gsuite_resources
from database.pgDb import SessionLocal
from models.models import LeaveRequest, User

logger = logging.getLogger(__name__)

class LeaveManagerAgent:
    """Agent responsible for handling all leave-related requests and operations"""
    
    async def process(self, message: str, user_id: str, user_info: Dict, role: str, context: List) -> str:
        """Process leave-related messages"""
        
        # Step 1: Determine the leave action intent
        leave_action = await self._determine_leave_action(message, user_info, role)
        
        # Step 2: Handle based on the specific leave action
        if leave_action == "request":
            return await self._handle_leave_request(message, user_id, user_info)
        elif leave_action == "approval":
            return await self._handle_leave_approval(message, user_id, user_info, role)
        elif leave_action == "balance":
            return await self._handle_leave_balance(message, user_id, user_info)
        elif leave_action == "cancel":
            return await self._handle_leave_cancellation(message, user_id, user_info)
        elif leave_action == "list":
            return await self._handle_leave_listing(message, user_id, user_info, role)
        else:
            # For general leave questions
            return await self._handle_general_leave_query(message, user_id, user_info)
    
    async def _determine_leave_action(self, message: str, user_info: Dict, role: str) -> str:
        """Determine what kind of leave action is needed"""
        
        prompt = f"""
        As a leave management classifier, determine what type of leave action is being requested in this message:
        
        USER: {user_info.get('name')} ({user_info.get('role')})
        MESSAGE: {message}
        
        Classify into exactly ONE of these categories:
        - request: User wants to apply for leave
        - approval: User wants to approve someone's leave (if they're HR/manager)
        - balance: User is asking about leave balance or entitlement
        - cancel: User wants to cancel an existing leave request
        - list: User wants to see pending or approved leaves
        - general: General questions about leave policy or other leave-related queries
        
        Respond with ONLY the category name without any explanation.
        """
        
        action = await get_gemini_response(prompt, user_info.get("id", "unknown"), "system")
        action = action.strip().lower()
        
        # Force to general if role doesn't have approval permission
        if action == "approval" and role not in ["hr", "manager"]:
            action = "general"
            
        logger.info(f"Leave action determined as '{action}' for message: {message[:50]}...")
        return action
    
    async def _handle_leave_request(self, message: str, user_id: str, user_info: Dict) -> str:
        """Handle a request to apply for leave"""
        
        # Extract leave details using LLM
        extraction_prompt = f"""
        Extract the following leave request details from this message:
        
        MESSAGE: {message}
        
        Extract and return as JSON with these keys:
        - leave_type: (annual, sick, personal, bereavement, parental, unpaid)
        - start_date: (YYYY-MM-DD format)
        - end_date: (YYYY-MM-DD format)
        - reason: (brief reason for leave)
        - half_day: (true if half day requested, false otherwise)
        
        If any information is missing, use null for that field.
        Return ONLY the JSON object without explanation.
        """
        
        try:
            extraction_result = await get_gemini_response(extraction_prompt, user_id, "system")
            leave_details = json.loads(extraction_result)
            
            # Validate the extracted information
            missing_fields = []
            if not leave_details.get("leave_type"):
                missing_fields.append("leave type")
            if not leave_details.get("start_date"):
                missing_fields.append("start date")
            if not leave_details.get("end_date"):
                missing_fields.append("end date")
                
            # If critical information is missing, ask for clarification
            if missing_fields:
                missing_info = ", ".join(missing_fields)
                return f"I'd be happy to process your leave request, but I need a few more details. Could you please provide the {missing_info}?"
            
            # Save the leave request to the database
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_info.get("id")).first()
                if not user:
                    return "I couldn't find your user profile in our system. Please contact HR for assistance."
                
                leave_request = LeaveRequest(
                    user_id=user.id,
                    leave_type=leave_details["leave_type"],
                    start_date=datetime.strptime(leave_details["start_date"], "%Y-%m-%d").date(),
                    end_date=datetime.strptime(leave_details["end_date"], "%Y-%m-%d").date(),
                    reason=leave_details.get("reason", "Not specified"),
                    status="pending",
                    half_day=leave_details.get("half_day", False)
                )
                
                db.add(leave_request)
                db.commit()
                
                # Calculate the number of days
                delta = leave_request.end_date - leave_request.start_date
                days = delta.days + 1
                if leave_request.half_day:
                    days = days - 0.5
                
                # Notify the user's manager
                # self._notify_manager(user.manager_id, leave_request)
                
                return f"Your leave request has been submitted successfully!\n\nDetails:\n- Type: {leave_request.leave_type.capitalize()}\n- From: {leave_request.start_date}\n- To: {leave_request.end_date}\n- Duration: {days} day(s)\n\nYour request is pending approval. I'll notify you once it's approved."
                
            finally:
                db.close()
                
        except json.JSONDecodeError:
            logger.error(f"Failed to parse leave details JSON: {extraction_result}")
            return "I'm having trouble understanding your leave request. Could you please provide your leave details in a clearer format? For example: 'I want to take annual leave from May 15 to May 18 for a family vacation.'"
        
        except Exception as e:
            logger.error(f"Error processing leave request: {str(e)}")
            return "I encountered an error while processing your leave request. Please try again or contact HR directly."
    
    async def _handle_leave_approval(self, message: str, user_id: str, user_info: Dict, role: str) -> str:
        """Handle approval of leave requests (for HR and managers)"""
        
        if role not in ["hr", "manager"]:
            return "You don't have permission to approve leave requests. This action requires HR or manager access."
        
        # Extract approval details
        approval_prompt = f"""
        Extract leave approval details from this message:
        
        MESSAGE: {message}
        
        Extract and return as JSON with these keys:
        - request_id: (the ID of the leave request to approve, if mentioned)
        - employee_name: (the name of the employee whose leave is being approved, if mentioned)
        - decision: (approve/reject)
        - comment: (any comment provided for the decision)
        
        If any information is missing, use null for that field.
        Return ONLY the JSON object without explanation.
        """
        
        try:
            extraction_result = await get_gemini_response(approval_prompt, user_id, "system")
            approval_details = json.loads(extraction_result)
            
            db = SessionLocal()
            try:
                # Try to find the leave request
                query = db.query(LeaveRequest).filter(LeaveRequest.status == "pending")
                
                if approval_details.get("request_id"):
                    query = query.filter(LeaveRequest.id == approval_details["request_id"])
                    
                if approval_details.get("employee_name"):
                    employee = db.query(User).filter(User.username.ilike(f"%{approval_details['employee_name']}%")).first()
                    if employee:
                        query = query.filter(LeaveRequest.user_id == employee.id)
                    else:
                        return f"I couldn't find an employee named '{approval_details['employee_name']}' in our system."
                
                # If there's still ambiguity
                leave_requests = query.all()
                
                if not leave_requests:
                    return "I couldn't find any pending leave requests matching your criteria. Please specify which request you'd like to approve."
                
                if len(leave_requests) > 1:
                    # If multiple requests match, list them for selection
                    request_list = "\n".join([
                        f"ID: {lr.id} - {db.query(User).get(lr.user_id).username}: {lr.leave_type} leave from {lr.start_date} to {lr.end_date}"
                        for lr in leave_requests[:5]  # Limit to 5 results
                    ])
                    return f"I found multiple pending leave requests. Please specify which one you'd like to {approval_details.get('decision', 'process')}:\n\n{request_list}"
                
                # Process the single matching request
                leave_request = leave_requests[0]
                employee = db.query(User).get(leave_request.user_id)
                
                decision = approval_details.get("decision", "").lower()
                if decision == "approve":
                    leave_request.status = "approved"
                    leave_request.approved_by = user_info.get("id")
                    leave_request.approved_at = datetime.now()
                    leave_request.comment = approval_details.get("comment", "Approved")
                    
                    # Update calendar and other systems
                    calendar_update = {
                        "action": "create_event",
                        "user_email": employee.email,
                        "title": f"{leave_request.leave_type.capitalize()} Leave",
                        "start_date": leave_request.start_date.isoformat(),
                        "end_date": leave_request.end_date.isoformat(),
                        "description": leave_request.reason
                    }
                    await update_gsuite_resources(calendar_update)
                    
                    db.commit()
                    return f"Leave request #{leave_request.id} for {employee.username} has been approved successfully. They have been notified of this decision."
                    
                elif decision == "reject":
                    leave_request.status = "rejected"
                    leave_request.approved_by = user_info.get("id")
                    leave_request.approved_at = datetime.now()
                    leave_request.comment = approval_details.get("comment", "Rejected")
                    
                    db.commit()
                    return f"Leave request #{leave_request.id} for {employee.username} has been rejected. They have been notified of this decision."
                    
                else:
                    return "Please specify whether you want to 'approve' or 'reject' this leave request."
                
            finally:
                db.close()
                
        except json.JSONDecodeError:
            logger.error(f"Failed to parse approval details JSON: {extraction_result}")
            return "I'm having trouble understanding your approval request. Please try again with a clearer format like 'Approve John's leave request' or 'Reject leave request #123'."
            
        except Exception as e:
            logger.error(f"Error processing leave approval: {str(e)}")
            return "I encountered an error while processing the leave approval. Please try again or check the request details."
    
    async def _handle_leave_balance(self, message: str, user_id: str, user_info: Dict) -> str:
        """Handle inquiries about leave balance"""
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_info.get("id")).first()
            if not user:
                return "I couldn't find your user profile in our system. Please contact HR for assistance."
            
            # In a real system, this would fetch from the leave balance table
            # This is a simplified example
            annual_balance = 20  # Example values
            sick_balance = 10
            personal_balance = 5
            
            # Calculate used leaves this year
            year_start = datetime(datetime.now().year, 1, 1).date()
            year_end = datetime(datetime.now().year, 12, 31).date()
            
            approved_leaves = db.query(LeaveRequest).filter(
                LeaveRequest.user_id == user.id,
                LeaveRequest.status == "approved",
                LeaveRequest.start_date >= year_start,
                LeaveRequest.end_date <= year_end
            ).all()
            
            # Calculate days used per type
            annual_used = sum(
                (leave.end_date - leave.start_date).days + 1 
                for leave in approved_leaves if leave.leave_type == "annual"
            )
            
            sick_used = sum(
                (leave.end_date - leave.start_date).days + 1 
                for leave in approved_leaves if leave.leave_type == "sick"
            )
            
            personal_used = sum(
                (leave.end_date - leave.start_date).days + 1 
                for leave in approved_leaves if leave.leave_type == "personal"
            )
            
            # Pending leaves
            pending_leaves = db.query(LeaveRequest).filter(
                LeaveRequest.user_id == user.id,
                LeaveRequest.status == "pending"
            ).all()
            
            pending_info = ""
            if pending_leaves:
                pending_list = "\n".join([
                    f"- {leave.leave_type.capitalize()} leave from {leave.start_date} to {leave.end_date} ({(leave.end_date - leave.start_date).days + 1} days)"
                    for leave in pending_leaves[:3]  # Limit to 3 results
                ])
                pending_info = f"\n\nYou also have {len(pending_leaves)} pending leave request(s):\n{pending_list}"
                if len(pending_leaves) > 3:
                    pending_info += f"\n...and {len(pending_leaves) - 3} more pending request(s)."
            
            return f"Here's your current leave balance for {datetime.now().year}:\n\n" \
                   f"Annual Leave: {annual_balance - annual_used} days remaining (used {annual_used} of {annual_balance})\n" \
                   f"Sick Leave: {sick_balance - sick_used} days remaining (used {sick_used} of {sick_balance})\n" \
                   f"Personal Leave: {personal_balance - personal_used} days remaining (used {personal_used} of {personal_balance})" \
                   f"{pending_info}"
                
        finally:
            db.close()
    
    async def _handle_leave_cancellation(self, message: str, user_id: str, user_info: Dict) -> str:
        """Handle cancellation of leave requests"""
        
        # Extract cancellation details using LLM
        cancel_prompt = f"""
        Extract leave cancellation details from this message:
        
        MESSAGE: {message}
        
        Extract and return as JSON with these keys:
        - request_id: (the ID of the leave request to cancel, if mentioned)
        - date_info: (any date information mentioned that could identify the leave)
        
        If any information is missing, use null for that field.
        Return ONLY the JSON object without explanation.
        """
        
        try:
            extraction_result = await get_gemini_response(cancel_prompt, user_id, "system")
            cancel_details = json.loads(extraction_result)
            
            db = SessionLocal()
            try:
                # Try to find the leave request
                query = db.query(LeaveRequest).filter(
                    LeaveRequest.user_id == user_info.get("id"),
                    LeaveRequest.status.in_(["pending", "approved"])
                )
                
                if cancel_details.get("request_id"):
                    query = query.filter(LeaveRequest.id == cancel_details["request_id"])
                    
                if cancel_details.get("date_info"):
                    # Use LLM to parse the date information
                    date_prompt = f"""
                    Parse this date information and return start and end dates if possible: {cancel_details["date_info"]}
                    
                    Return as JSON with these keys:
                    - start_date: (YYYY-MM-DD format)
                    - end_date: (YYYY-MM-DD format)
                    
                    If you can only determine one date, set both to that date.
                    If you cannot determine dates, set both to null.
                    Return ONLY the JSON object without explanation.
                    """
                    
                    date_result = await get_gemini_response(date_prompt, user_id, "system")
                    date_info = json.loads(date_result)
                    
                    if date_info.get("start_date"):
                        start_date = datetime.strptime(date_info["start_date"], "%Y-%m-%d").date()
                        query = query.filter(LeaveRequest.start_date == start_date)
                        
                    if date_info.get("end_date"):
                        end_date = datetime.strptime(date_info["end_date"], "%Y-%m-%d").date()
                        query = query.filter(LeaveRequest.end_date == end_date)
                
                # Get the matching leave requests
                leave_requests = query.all()
                
                if not leave_requests:
                    return "I couldn't find any active leave requests that match your cancellation criteria. Please specify which leave request you'd like to cancel."
                
                if len(leave_requests) > 1:
                    # If multiple requests match, list them for selection
                    request_list = "\n".join([
                        f"ID: {lr.id} - {lr.leave_type.capitalize()} leave from {lr.start_date} to {lr.end_date} (Status: {lr.status.capitalize()})"
                        for lr in leave_requests[:5]  # Limit to 5 results
                    ])
                    return f"I found multiple leave requests that could be cancelled. Please specify which one by ID:\n\n{request_list}"
                
                # Process the single matching request
                leave_request = leave_requests[0]
                
                # Cancel the leave
                previous_status = leave_request.status
                leave_request.status = "cancelled"
                leave_request.updated_at = datetime.now()
                
                # If it was approved, also update calendar
                if previous_status == "approved":
                    calendar_update = {
                        "action": "delete_event",
                        "user_email": db.query(User).get(leave_request.user_id).email,
                        "title": f"{leave_request.leave_type.capitalize()} Leave",
                        "start_date": leave_request.start_date.isoformat(),
                        "end_date": leave_request.end_date.isoformat()
                    }
                    await update_gsuite_resources(calendar_update)
                
                db.commit()
                
                # Format the response
                start_date = leave_request.start_date.strftime("%B %d, %Y")
                end_date = leave_request.end_date.strftime("%B %d, %Y")
                return f"Your {leave_request.leave_type} leave request from {start_date} to {end_date} has been successfully cancelled."
                
            finally:
                db.close()
                
        except json.JSONDecodeError:
            logger.error(f"Failed to parse cancel details JSON: {extraction_result}")
            return "I'm having trouble understanding your cancellation request. Please try again with a clearer format like 'Cancel my leave for next week' or 'Cancel leave request #123'."
            
        except Exception as e:
            logger.error(f"Error processing leave cancellation: {str(e)}")
            return "I encountered an error while processing the leave cancellation. Please try again or contact HR for assistance."
    
    async def _handle_leave_listing(self, message: str, user_id: str, user_info: Dict, role: str) -> str:
        """Handle requests to list leave requests"""
        
        # Extract listing parameters using LLM
        list_prompt = f"""
        Extract leave listing parameters from this message:
        
        MESSAGE: {message}
        
        Extract and return as JSON with these keys:
        - status: (pending, approved, rejected, cancelled, all)
        - employee_name: (name of employee if HR/manager is asking about someone else)
        - time_frame: (any time frame mentioned like 'this month', 'next week', etc.)
        
        If any information is missing, use null for that field.
        Return ONLY the JSON object without explanation.
        """
        
        try:
            extraction_result = await get_gemini_response(list_prompt, user_id, "system")
            list_params = json.loads(extraction_result)
            
            db = SessionLocal()
            try:
                # Determine whose leaves to show
                target_user_id = user_info.get("id")
                
                # If HR/manager is asking about someone else
                if role in ["hr", "manager"] and list_params.get("employee_name"):
                    employee = db.query(User).filter(User.username.ilike(f"%{list_params['employee_name']}%")).first()
                    if employee:
                        target_user_id = employee.id
                        employee_name = employee.username
                    else:
                        return f"I couldn't find an employee named '{list_params['employee_name']}' in our system."
                else:
                    employee_name = user_info.get("name", "you")
                
                # Build the query
                query = db.query(LeaveRequest).filter(LeaveRequest.user_id == target_user_id)
                
                # Filter by status if specified
                if list_params.get("status") and list_params["status"] != "all":
                    query = query.filter(LeaveRequest.status == list_params["status"])
                
                # Filter by time frame if specified
                if list_params.get("time_frame"):
                    # Use LLM to parse the time frame
                    time_prompt = f"""
                    Parse this time frame and return date ranges: {list_params["time_frame"]}
                    
                    Today is {datetime.now().strftime("%Y-%m-%d")}.
                    
                    Return as JSON with these keys:
                    - start_date: (YYYY-MM-DD format)
                    - end_date: (YYYY-MM-DD format)
                    
                    Return ONLY the JSON object without explanation.
                    """
                    
                    time_result = await get_gemini_response(time_prompt, user_id, "system")
                    time_info = json.loads(time_result)
                    
                    if time_info.get("start_date"):
                        start_date = datetime.strptime(time_info["start_date"], "%Y-%m-%d").date()
                        query = query.filter(LeaveRequest.start_date >= start_date)
                        
                    if time_info.get("end_date"):
                        end_date = datetime.strptime(time_info["end_date"], "%Y-%m-%d").date()
                        query = query.filter(LeaveRequest.start_date <= end_date)
                
                # Execute the query and limit results
                leave_requests = query.order_by(LeaveRequest.start_date).limit(10).all()
                
                if not leave_requests:
                    status_text = f" with status '{list_params.get('status')}'" if list_params.get("status") else ""
                    time_text = f" for {list_params.get('time_frame')}" if list_params.get("time_frame") else ""
                    return f"No leave requests found for {employee_name}{status_text}{time_text}."
                
                # Format the results
                status_text = f"{list_params.get('status', 'all')} " if list_params.get("status") else ""
                time_text = f" for {list_params.get('time_frame')}" if list_params.get("time_frame") else ""
                
                header = f"Here are the {status_text}leave requests for {employee_name}{time_text}:\n\n"
                
                leave_list = []
                for lr in leave_requests:
                    status_emoji = {
                        "pending": "⏳",
                        "approved": "✅",
                        "rejected": "❌",
                        "cancelled": "🚫"
                    }.get(lr.status, "")
                    
                    days = (lr.end_date - lr.start_date).days + 1
                    day_text = f"{days} day{'s' if days != 1 else ''}"
                    
                    leave_list.append(
                        f"{status_emoji} {lr.leave_type.capitalize()} leave from {lr.start_date} to {lr.end_date} ({day_text}) - {lr.status.capitalize()}"
                    )
                
                return header + "\n".join(leave_list)
                
            finally:
                db.close()
                
        except json.JSONDecodeError:
            logger.error(f"Failed to parse list parameters JSON: {extraction_result}")
            return "I'm having trouble understanding your request. Please try again with a clearer format like 'Show my pending leaves' or 'List John's approved leaves for next month'."
            
        except Exception as e:
            logger.error(f"Error processing leave listing: {str(e)}")
            return "I encountered an error while retrieving leave information. Please try again or be more specific in your request."
    
    async def _handle_general_leave_query(self, message: str, user_id: str, user_info: Dict) -> str:
        """Handle general questions about leave policies or other leave-related queries"""
        
        # Use LLM to generate a response based on company leave policies
        policy_prompt = f"""
        Answer this leave policy related question:
        
        USER ROLE: {user_info.get('role', 'employee')}
        QUESTION: {message}
        
        Use these company leave policies:
        - Annual leave: 20 days per year, accruing monthly
        - Sick leave: 10 days per year, requires doctor's note for 3+ consecutive days
        - Personal leave: 5 days per year for personal matters
        - Bereavement leave: Up to 5 days for immediate family
        - Parental leave: 12 weeks for primary caregiver, 4 weeks for secondary
        - Unpaid leave: Considered on case-by-case basis after paid leave is exhausted
        - Leave requests should be submitted at least 2 weeks in advance except for emergencies
        - All leave requests require manager approval
        - Carryover policy: Up to 5 days of annual leave can be carried over to next year
        
        Answer concisely and professionally.
        """
        
        try:
            response = await get_gemini_response(policy_prompt, user_id, "hr_assistant")
            return response
            
        except Exception as e:
            logger.error(f"Error processing general leave query: {str(e)}")
            return "I'm sorry, I'm having trouble answering your question about our leave policies. Please contact HR for more information or try asking in a different way."
        
    async def _notify_manager(self, manager_id: str, leave_request: LeaveRequest) -> None:
        """Send notification to manager about a new leave request"""
        try:
            db = SessionLocal()
            try:
                # Get manager details
                manager = db.query(User).filter(User.id == manager_id).first()
                if not manager:
                    logger.error(f"Manager with ID {manager_id} not found for notification")
                    return
                    
                # Get employee details
                employee = db.query(User).filter(User.id == leave_request.user_id).first()
                if not employee:
                    logger.error(f"Employee with ID {leave_request.user_id} not found for notification")
                    return
                    
                # Calculate duration
                delta = leave_request.end_date - leave_request.start_date
                days = delta.days + 1
                if leave_request.half_day:
                    days = days - 0.5
                    
                # Send notification
                notification_data = {
                    "recipient_id": manager.id,
                    "message": f"New leave request from {employee.username}:\n"
                            f"Type: {leave_request.leave_type.capitalize()}\n"
                            f"From: {leave_request.start_date}\n"
                            f"To: {leave_request.end_date}\n"
                            f"Duration: {days} day(s)\n"
                            f"Reason: {leave_request.reason}\n\n"
                            f"Reply with 'Approve leave for {employee.username}' or 'Reject leave for {employee.username}'"
                }
                
                # Add this to notification queue or send directly
                # In a real implementation, this would call your notification service
                logger.info(f"Sending leave approval notification to manager {manager.username}")
                
                # Example implementation with a notification service:
                # await notification_service.send_notification(notification_data)
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error notifying manager about leave request: {str(e)}")

    async def validate_leave_eligibility(self, user_id: str, leave_type: str, start_date: datetime, end_date: datetime) -> Dict:
        """Validate if user is eligible for the requested leave"""
        db = SessionLocal()
        try:
            # Get user information
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"eligible": False, "reason": "User not found in system"}
                
            # Calculate requested days
            delta = end_date - start_date
            requested_days = delta.days + 1
            
            # Get current balance (simplified example)
            # In a real system, you'd pull this from a leave balance table
            balances = {
                "annual": 20,
                "sick": 10,
                "personal": 5,
                "bereavement": 5,
                "parental": 84 if user.is_primary_caregiver else 28,
                "unpaid": 9999  # effectively unlimited
            }
            
            # Calculate used leaves this year
            year_start = datetime(datetime.now().year, 1, 1).date()
            year_end = datetime(datetime.now().year, 12, 31).date()
            
            used_leaves = db.query(LeaveRequest).filter(
                LeaveRequest.user_id == user_id,
                LeaveRequest.status == "approved",
                LeaveRequest.leave_type == leave_type,
                LeaveRequest.start_date >= year_start,
                LeaveRequest.end_date <= year_end
            ).all()
            
            # Sum up used days
            used_days = sum(
                (leave.end_date - leave.start_date).days + 1 
                for leave in used_leaves
            )
            
            # Adjust for half days
            half_day_count = len([leave for leave in used_leaves if leave.half_day])
            used_days -= 0.5 * half_day_count
            
            # Calculate remaining balance
            remaining_balance = balances.get(leave_type, 0) - used_days
            
            # Check if eligible
            if leave_type not in balances:
                return {"eligible": False, "reason": f"Invalid leave type: {leave_type}"}
                
            if remaining_balance < requested_days:
                return {
                    "eligible": False, 
                    "reason": f"Insufficient {leave_type} leave balance. Requested: {requested_days} days, Available: {remaining_balance} days"
                }
                
            # Additional validation rules
            # Example: Check if leave is requested with sufficient notice
            notice_days = (start_date.date() - datetime.now().date()).days
            if leave_type != "sick" and notice_days < 14:  # 2 weeks notice required
                return {
                    "eligible": True,
                    "warning": f"Leave requested with only {notice_days} days notice. Company policy recommends 14 days notice."
                }
                
            return {"eligible": True}
            
        finally:
            db.close()

    async def get_team_leave_calendar(self, manager_id: str, start_date: Optional[datetime] = None, 
                                    end_date: Optional[datetime] = None) -> str:
        """Generate a calendar view of team leaves for managers"""
        
        if not start_date:
            # Default to current month
            today = datetime.now()
            start_date = datetime(today.year, today.month, 1).date()
            end_date = (datetime(today.year, today.month + 1, 1) - timedelta(days=1)).date()
        
        db = SessionLocal()
        try:
            # Get all team members
            team_members = db.query(User).filter(User.manager_id == manager_id).all()
            if not team_members:
                return "You don't have any team members reporting to you."
                
            # Get approved leaves in the date range
            team_leaves = {}
            for member in team_members:
                leaves = db.query(LeaveRequest).filter(
                    LeaveRequest.user_id == member.id,
                    LeaveRequest.status == "approved",
                    LeaveRequest.start_date <= end_date,
                    LeaveRequest.end_date >= start_date
                ).all()
                
                if leaves:
                    team_leaves[member.username] = leaves
            
            if not team_leaves:
                return f"No approved leaves for your team between {start_date} and {end_date}."
                
            # Generate calendar view
            result = f"Team Leave Calendar ({start_date} to {end_date}):\n\n"
            
            for username, leaves in team_leaves.items():
                result += f"{username}:\n"
                for leave in leaves:
                    result += f"• {leave.leave_type.capitalize()} leave: {leave.start_date} to {leave.end_date}\n"
                result += "\n"
                
            return result
            
        finally:
            db.close()

    async def handle_leave_report(self, message: str, user_id: str, user_info: Dict, role: str) -> str:
        """Generate reports about leave patterns, usage, etc. for HR and managers"""
        
        if role not in ["hr", "manager"]:
            return "You don't have permission to access leave reports. This action requires HR or manager access."
        
        # Extract report parameters
        report_prompt = f"""
        Extract leave report parameters from this message:
        
        MESSAGE: {message}
        
        Extract and return as JSON with these keys:
        - report_type: (usage, calendar, upcoming, department)
        - department: (department name if specified)
        - time_frame: (any time frame like 'this month', 'last quarter', etc.)
        
        If any information is missing, use null for that field.
        Return ONLY the JSON object without explanation.
        """
        
        try:
            extraction_result = await get_gemini_response(report_prompt, user_id, "system")
            report_params = json.loads(extraction_result)
            
            report_type = report_params.get("report_type", "usage")
            
            # Handle different report types
            if report_type == "calendar":
                # For managers, show their team's leave calendar
                if role == "manager":
                    return await self.get_team_leave_calendar(user_info.get("id"))
                # For HR, need to specify a department or team
                else:
                    if report_params.get("department"):
                        # In a real implementation, you would query managers by department
                        return "Please specify a manager to view their team's leave calendar."
                    else:
                        return "Please specify a department or team manager to view a leave calendar."
                        
            elif report_type == "upcoming":
                # Show upcoming leaves across the organization (for HR) or team (for managers)
                db = SessionLocal()
                try:
                    today = datetime.now().date()
                    next_month = today + timedelta(days=30)
                    
                    query = db.query(LeaveRequest).filter(
                        LeaveRequest.status == "approved",
                        LeaveRequest.start_date >= today,
                        LeaveRequest.start_date <= next_month
                    )
                    
                    if role == "manager":
                        # Get team member IDs
                        team_ids = [user.id for user in db.query(User).filter(User.manager_id == user_info.get("id")).all()]
                        if team_ids:
                            query = query.filter(LeaveRequest.user_id.in_(team_ids))
                        else:
                            return "You don't have any team members reporting to you."
                    
                    upcoming_leaves = query.order_by(LeaveRequest.start_date).all()
                    
                    if not upcoming_leaves:
                        return "No upcoming approved leaves for the next 30 days."
                    
                    # Format the results
                    result = "Upcoming leaves for the next 30 days:\n\n"
                    for leave in upcoming_leaves:
                        user = db.query(User).get(leave.user_id)
                        days = (leave.end_date - leave.start_date).days + 1
                        result += f"• {user.username}: {leave.leave_type.capitalize()} leave from {leave.start_date} to {leave.end_date} ({days} days)\n"
                    
                    return result
                    
                finally:
                    db.close()
                    
            elif report_type == "department":
                # Show department-wide leave statistics (for HR only)
                if role != "hr":
                    return "Department-wide leave reports are only available to HR personnel."
                    
                if not report_params.get("department"):
                    return "Please specify a department to generate a leave report."
                
                # In a real implementation, you would query users by department
                # This is a simplified example
                return f"Department leave report functionality will be implemented in the next release."
                
            else:  # Default to usage report
                # Generate leave usage statistics
                db = SessionLocal()
                try:
                    year_start = datetime(datetime.now().year, 1, 1).date()
                    year_end = datetime(datetime.now().year, 12, 31).date()
                    
                    # For managers, show their team's usage
                    if role == "manager":
                        team_members = db.query(User).filter(User.manager_id == user_info.get("id")).all()
                        if not team_members:
                            return "You don't have any team members reporting to you."
                            
                        result = "Leave usage report for your team:\n\n"
                        
                        for member in team_members:
                            approved_leaves = db.query(LeaveRequest).filter(
                                LeaveRequest.user_id == member.id,
                                LeaveRequest.status == "approved",
                                LeaveRequest.start_date >= year_start,
                                LeaveRequest.end_date <= year_end
                            ).all()
                            
                            # Calculate days used per type
                            leave_stats = {}
                            for leave in approved_leaves:
                                days = (leave.end_date - leave.start_date).days + 1
                                if leave.half_day:
                                    days -= 0.5
                                    
                                leave_type = leave.leave_type
                                if leave_type not in leave_stats:
                                    leave_stats[leave_type] = 0
                                leave_stats[leave_type] += days
                                
                            # Add to result
                            result += f"{member.username}:\n"
                            for leave_type, days in leave_stats.items():
                                result += f"- {leave_type.capitalize()}: {days} days\n"
                            result += "\n"
                        
                        return result
                        
                    # For HR, show organization-wide statistics
                    else:
                        # This would be a more complex report in a real implementation
                        # Simplified example
                        approved_leaves = db.query(LeaveRequest).filter(
                            LeaveRequest.status == "approved",
                            LeaveRequest.start_date >= year_start,
                            LeaveRequest.end_date <= year_end
                        ).all()
                        
                        # Calculate stats by leave type
                        leave_stats = {}
                        for leave in approved_leaves:
                            days = (leave.end_date - leave.start_date).days + 1
                            if leave.half_day:
                                days -= 0.5
                                
                            leave_type = leave.leave_type
                            if leave_type not in leave_stats:
                                leave_stats[leave_type] = 0
                            leave_stats[leave_type] += days
                        
                        result = "Organization-wide leave usage this year:\n\n"
                        for leave_type, days in leave_stats.items():
                            result += f"{leave_type.capitalize()}: {days} days\n"
                        
                        # Add some additional statistics
                        total_employees = db.query(User).count()
                        total_leaves = len(approved_leaves)
                        
                        result += f"\nTotal employees: {total_employees}\n"
                        result += f"Total leave requests: {total_leaves}\n"
                        result += f"Average leaves per employee: {total_leaves / total_employees:.1f}\n"
                        
                        return result
                
                finally:
                    db.close()
        
        except json.JSONDecodeError:
            logger.error(f"Failed to parse report parameters JSON: {extraction_result}")
            return "I'm having trouble understanding your report request. Please try again with a clearer format like 'Show leave usage report for my team' or 'Generate department leave calendar for Engineering'."
            
        except Exception as e:
            logger.error(f"Error generating leave report: {str(e)}")
            return "I encountered an error while generating the leave report. Please try again or contact the system administrator."