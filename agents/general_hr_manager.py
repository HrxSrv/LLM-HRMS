from typing import Dict
import logging
import json

from llms.gemini_client import get_gemini_response

logger = logging.getLogger(__name__)

class GeneralHRAgent:
    def __init__(self):
        logger.info("General HR Agent initialized")
        self.hr_policies = {
            "working_hours": "Standard working hours are 9 AM to 5 PM, Monday through Friday.",
            "dress_code": "Business casual attire is expected during regular working days. Formal attire for client meetings.",
            "holidays": "The company observes national holidays. Please refer to the annual calendar for specific dates.",
            "work_from_home": "Employees may work from home up to 2 days per week with manager approval.",
            "benefits": "Health insurance, retirement plan, and annual bonuses are available for all full-time employees.",
        }
    
    async def process(self, message: str, user_id: str, user_info: Dict, role: str, context: str) -> str:
        """Process general HR related queries (expects context as JSON string)"""
        
        # Check if message mentions any of the predefined policies
        for policy, info in self.hr_policies.items():
            if policy.replace("_", " ") in message.lower():
                return f"Policy on {policy.replace('_', ' ')}: {info}"
        
        # For other queries, use LLM to generate a response
        return await self._generate_hr_response(message, user_info, role, context)
    
    async def _generate_hr_response(self, message: str, user_info: Dict, role: str, context: str) -> str:
        """Generate a response for general HR queries using LLM"""
        
        # Convert string context to list of dicts
        try:
            context_list = json.loads(context) if context else []
        except Exception as e:
            logger.warning(f"Context deserialization failed: {e}")
            context_list = []

        recent_context = context_list[-3:] if context_list else []
        context_text = "\n".join([f"{item['role']}: {item['content']}" for item in recent_context]) if recent_context else "No recent context"
        
        prompt = f"""
        You are an HR Assistant for a company. Respond to the following query from an employee.

        USER INFORMATION:
        Role: {role}
        Name: {user_info.get('name', 'Employee')}

        RECENT CONVERSATION:
        {context_text}

        CURRENT QUERY:
        {message}

        Provide a helpful, concise response. If you don't have specific information on a company policy,
        give general HR best practices but make it clear that the employee should confirm with their HR department.

        For sensitive or complex HR issues (like harassment, compensation disputes, termination), advise the 
        employee to contact HR directly rather than providing specific guidance.

        Your response:
        """
        
        try:
            response = await get_gemini_response(prompt, user_info.get("id", "unknown"), "system")
            return response
        except Exception as e:
            logger.error(f"Error generating HR response: {e}")
            return "I'm sorry, I'm having trouble processing your request at the moment. Please try again later or contact HR directly for assistance."
    
    async def handle_faq(self, question: str) -> str:
        """Handle frequently asked HR questions"""
        
        faqs = {
            "how do i apply for leave": "You can apply for leave through our HRMS portal. Go to the 'Leave Management' section and click on 'Apply for Leave'.",
            "what is the probation period": "The standard probation period is 3 months from your date of joining.",
            "how many sick days do i get": "Full-time employees receive 10 paid sick days per year.",
            "when are performance reviews": "Performance reviews are conducted bi-annually in June and December.",
            "how do i submit expenses": "Submit your expenses through the Finance portal with relevant receipts within 30 days of incurring them."
        }
        
        question_lower = question.lower()
        for faq_q, faq_a in faqs.items():
            if faq_q in question_lower:
                return faq_a
        
        return None  # No matching FAQ
