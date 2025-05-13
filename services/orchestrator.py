from typing import Dict, List, Optional, Tuple
import logging
from enum import Enum
import json

# Import agent modules
from agents.leave_manager import LeaveManagerAgent
from agents.employee_manager import EmployeeManagerAgent
from agents.general_hr_manager import GeneralHRAgent
# from agents.policy_advisor import PolicyAdvisorAgent
# from agents.payroll_assistant import PayrollAssistantAgent
# from agents.onboarding_agent import OnboardingAgent

from llms.gemini_client import get_gemini_response
from services.context_service import store_chat_context

logger = logging.getLogger(__name__)

class AgentType(Enum):
    LEAVE_MANAGER = "leave_manager"
    EMPLOYEE_MANAGER = "employee_manager"
    GENERAL_HR = "general_hr"
    # POLICY_ADVISOR = "policy_advisor"
    # PAYROLL_ASSISTANT = "payroll_assistant"
    # ONBOARDING = "onboarding"

class Orchestrator:
    def __init__(self):
        # Initialize all agent instances
        self.agents = {
            AgentType.LEAVE_MANAGER: LeaveManagerAgent(),
            AgentType.EMPLOYEE_MANAGER: EmployeeManagerAgent(),
            AgentType.GENERAL_HR: GeneralHRAgent(),
            # AgentType.POLICY_ADVISOR: PolicyAdvisorAgent(),
            # AgentType.PAYROLL_ASSISTANT: PayrollAssistantAgent(),
            # AgentType.ONBOARDING: OnboardingAgent(),
        }
        
    async def determine_intent(self, message: str, user_info: Dict, context: str) -> Tuple[AgentType, float]:
        """Determine the user's intent and route to appropriate agent"""
        
        # Use LLM to determine intent
        prompt = f"""
        As an HRMS intent classifier, determine which specialized HR agent should handle this request.
        
        USER PROFILE:
        {json.dumps(user_info)}
        
        CONVERSATION CONTEXT:
        # {(context if context else [])}
        
        USER MESSAGE:
        {message}
        
        Based on the message, classify the intent into exactly ONE of these categories:
        - leave_manager: For leave requests, approvals, leave balance inquiries
        - employee_manager: For requests to find or extract or change specific information of someone from HR records, 
        - general_hr: For general HR inquiries or anything that doesn't fit above categories
        
        Your response should be ONLY the category name without any additional text or explanation.
        """
        
        try:
            intent_response = await get_gemini_response(prompt, user_info.get("id", "unknown"), "system")
            intent = intent_response.strip().lower()
            
            # Map the text response to enum
            for agent_type in AgentType:
                if agent_type.value == intent:
                    logger.info(f"Intent determined as {agent_type.value} for message: {message[:50]}...")
                    return agent_type, 0.9  # Confidence score
                    
            # Default to general HR if no match
            logger.warning(f"Could not determine specific intent, defaulting to general HR for: {message[:50]}...")
            return AgentType.GENERAL_HR, 0.5
            
        except Exception as e:
            logger.error(f"Error determining intent: {e}")
            return AgentType.GENERAL_HR, 0.3
    
    async def process_message(self, message: str, user_id: str, user_info: Dict, role: str, context: str) -> str:
        """Main orchestration method to process incoming messages"""
        
        # Determine user intent
        agent_type, confidence = await self.determine_intent(message, user_info, context)
        
        # If HR admin with specific role commands, override intent detection
        if role == "hr" and any(keyword in message.lower() for keyword in ["force leave", "override", "admin action"]):
            agent_type = AgentType.LEAVE_MANAGER
            logger.info(f"Intent overridden to {agent_type.value} based on HR admin command")
        
        # Get appropriate agent
        agent = self.agents[agent_type]
        
        # Process through the selected agent
        response = await agent.process(message, user_id, user_info, role, context)
        
        # Store interaction in context
        store_chat_context(user_id, message, response)
        
        # For low confidence scenarios, get a backup response
        if confidence < 0.6 and agent_type != AgentType.GENERAL_HR:
            backup_response = await self.agents[AgentType.GENERAL_HR].process(
                message, user_id, user_info, role, context
            )
            
            # Use LLM to decide the best response
            final_response = await self._select_best_response(
                message, response, backup_response, agent_type.value, "general_hr", confidence
            )
            return final_response
        
        return response
    
    async def _select_best_response(
        self, message: str, primary_response: str, backup_response: str, 
        primary_agent: str, backup_agent: str, confidence: float
    ) -> str:
        """When confidence is low, decide which response is better"""
        
        prompt = f"""
        As an HRMS response evaluator, determine which of these responses better addresses the user's query:
        
        USER QUERY: {message}
        
        RESPONSE FROM {primary_agent.upper()} (confidence: {confidence}):
        {primary_response}
        
        RESPONSE FROM {backup_agent.upper()}:
        {backup_response}
        
        Select the better response by answering with ONLY "primary" or "backup".
        """
        
        try:
            selection = await get_gemini_response(prompt, "system", "system")
            selection = selection.strip().lower()
            
            if "primary" in selection:
                return primary_response
            else:
                return backup_response
                
        except Exception as e:
            logger.error(f"Error selecting best response: {e}")
            return primary_response  # Default to primary on error

# Create a singleton instance
orchestrator = Orchestrator()