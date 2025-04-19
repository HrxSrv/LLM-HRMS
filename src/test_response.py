# Dictionary mapping keywords to responses
HR_RESPONSES = {
    "leave": """
    *Leave Management*
    
    To apply for leave, send a message in this format:
    "Apply leave from DD-MM-YYYY to DD-MM-YYYY, reason"
    
    To check your leave balance, send:
    "Leave balance"
    """,
    
    "attendance": """
    *Attendance Management*
    
    To mark attendance:
    - Check-in: Send "Check in"
    - Check-out: Send "Check out"
    
    To view your attendance report, send:
    "Attendance report"
    """,
    
    "payroll": """
    *Payroll Information*
    
    To view your latest salary slip, send:
    "Salary slip"
    
    For tax declaration, send:
    "Tax declaration"
    """,
    
    "policy": """
    *HR Policies*
    
    Available policy documents:
    1. Leave Policy
    2. Work From Home Policy
    3. Travel Policy
    4. Code of Conduct
    
    Send the name of the policy to view details.
    """,
    
    "hello": """
    Hello! I'm your HR Assistant. I can help you with:
    
    1. Leave management
    2. Attendance tracking
    3. Payroll information
    4. HR policies
    
    What would you like assistance with?
    """,
    
    "help": """
    *HR Bot Help*
    
    You can ask me about:
    - Leave (balance, application)
    - Attendance (check-in, check-out, reports)
    - Payroll (salary slips, tax)
    - Policies (company rules and guidelines)
    
    Just send a message with your query!
    """
}

# Default response for unrecognized queries
DEFAULT_RESPONSE = """
I'm not sure how to help with that. You can ask about:

- Leave management
- Attendance tracking
- Payroll information
- HR policies

Type "help" for more information.
"""

def get_response(message):
    """
    Returns a predefined response based on keywords in the message
    """
    message_lower = message.lower()
    
    # Check for keywords in the message
    for keyword, response in HR_RESPONSES.items():
        if keyword in message_lower:
            return response
    
    return DEFAULT_RESPONSE