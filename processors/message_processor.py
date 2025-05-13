import re
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

def preprocess_message(message: str, user_id: str,user_info: Dict, role: str = "employee", 
                      context: Optional[Dict] = None) -> str:
    """
    Preprocess the user message before sending to LLM

    Args:
        message: Original user message
        user_info: Dictionary with user details
        role: User role (employee or hr)
        context: Previous conversation context

    Returns:
        Processed message with role and context
    """
    user_id = user_id
    user_name = user_info.get("name", "Unknown")

    logger.info(f"Preprocessing message for user {user_id} with role {role}")

    role_context = f"[USER ROLE: {role.upper()}]"
    user_name_context = f"[USER: {user_name}]"

    context_summary = ""
    if context and context.get("summary"):
        context_summary = f"[PREVIOUS CONTEXT: {context['summary']}]"

    task_flags = ""
    if role.lower() == "hr" and is_hr_task(message):
        task_flags = "[HR TASK REQUEST]"

    enhanced_message = f"{role_context} {task_flags} {context_summary} {message} {user_name_context}"

    logger.debug(f"Enhanced message: {enhanced_message}")
    return enhanced_message

def postprocess_response(response: str) -> str:
    response = re.sub(r'\[SYSTEM.*?\]', '', response)
    response = re.sub(r'\[USER ROLE:.*?\]', '', response)
    response = re.sub(r'\[HR TASK REQUEST\]', '', response)
    response = re.sub(r'\s+', ' ', response).strip()

    if len(response) > 300:
        response = insert_line_breaks(response)

    return response

def is_hr_task(message: str) -> bool:
    hr_task_keywords = [
        "leave approval", "approve leave", 
        "attendance update", "update attendance",
        "performance review", "employee record", 
        "update employee", "payroll",
        "onboarding", "termination"
    ]
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in hr_task_keywords)

def insert_line_breaks(text: str) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    paragraphs = [' '.join(sentences[i:i+2]) for i in range(0, len(sentences), 2)]
    return '\n\n'.join(paragraphs)

def extract_task_details(message: str) -> Dict:
    task_details = {
        "task_type": None,
        "employee_id": None,
        "date_range": None,
        "details": None
    }

    if "leave" in message.lower() and ("approve" in message.lower() or "approval" in message.lower()):
        task_details["task_type"] = "leave_approval"

        employee_match = re.search(r'for\s+([A-Za-z0-9\s]+)', message)
        if employee_match:
            task_details["employee_id"] = employee_match.group(1).strip()

        date_match = re.search(r'from\s+([A-Za-z0-9\s,]+)\s+to\s+([A-Za-z0-9\s,]+)', message)
        if date_match:
            task_details["date_range"] = {
                "start": date_match.group(1).strip(),
                "end": date_match.group(2).strip()
            }

    return task_details
