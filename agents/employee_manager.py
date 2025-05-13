from typing import Dict, List, Optional
import logging
import pandas as pd
import os
from datetime import datetime
import json
import re

# Import Google Sheets API client
from services.google_sheets_service import GoogleSheetsService
from llms.gemini_client import get_gemini_response

logger = logging.getLogger(__name__)

class EmployeeManagerAgent:
    def __init__(self):
        self.sheets_service = GoogleSheetsService()
        self.spreadsheet_id = os.getenv("EMPLOYEE_SPREADSHEET_ID")
        self.sheet_name = os.getenv("EMPLOYEE_SHEET_NAME", "Employees")
        logger.info("Employee Manager Agent initialized with Google Sheets connection")
    
    async def process(self, message: str, user_id: str, user_info: Dict, role: str, context: List) -> str:
        """Main method to process employee data related requests"""
        
        # Determine specific intent within employee manager domain
        intent = await self._determine_sub_intent(message, user_info, context)
        
        if intent == "extract_info":
            return await self._extract_employee_info(message, user_info, role)
        elif intent == "update_info":
            return await self._update_employee_info(message, user_info, role)
        else:
            return await self._handle_general_employee_query(message, user_info, role)
    
    async def _determine_sub_intent(self, message: str, user_info: Dict, context: List) -> str:
        """Determine the specific intent within employee manager domain"""
        
        prompt = f"""
        As an Employee Manager intent classifier, determine what action the user wants to perform.
        
        USER PROFILE:
        {json.dumps(user_info)}
        
        USER MESSAGE:
        {message}
        
        Based on the message, classify into EXACTLY ONE of these categories:
        - extract_info: User wants to retrieve information about an employee
        - update_info: User wants to update information about an employee
        - general_query: Any other employee-related query
        
        Your response should be ONLY the category name without any additional text.
        """
        
        try:
            response = await get_gemini_response(prompt, user_info.get("id", "unknown"), "system")
            intent = response.strip().lower()
            logger.info(f"Employee Manager sub-intent determined as: {intent}")
            return intent
        except Exception as e:
            logger.error(f"Error determining employee manager sub-intent: {e}")
            return "general_query"
    
    async def _extract_employee_info(self, message: str, user_info: Dict, role: str) -> str:
        """Extract employee information based on phone number or other identifiers"""
        
        # Check if user has permission to access employee data
        if role != "hr" and user_info.get("role") != "hr":
            return "I'm sorry, you don't have permission to access employee information. Please contact your HR department."
        
        try:
            # Extract phone number or other identifiers from the message
            phone_pattern = r'(\+?\d{10,15}|\d{3}[-.\s]?\d{3}[-.\s]?\d{4})'
            phone_match = re.search(phone_pattern, message)
            
            if phone_match:
                phone_number = phone_match.group(0)
                # Clean up the phone number format
                phone_number = re.sub(r'[^0-9+]', '', phone_number)
            else:
                # Try to extract name or other identifiers
                prompt = f"""
                From this message, extract the employee identifier mentioned:
                
                MESSAGE: {message}
                
                If there's a name, extract the full name.
                If there's an employee ID, extract that.
                If there's an email, extract that.
                
                Return ONLY the extracted identifier without any additional text.
                """
                
                identifier = await get_gemini_response(prompt, user_info.get("id", "unknown"), "system")
                identifier = identifier.strip()
                
                if not identifier or identifier.lower() == "none":
                    return "I couldn't identify which employee you're referring to. Please provide a phone number, name, or employee ID."
            
            # Retrieve employee data from Google Sheets
            employee_data = await self._retrieve_employee_data(phone_number if phone_match else identifier)
            
            if not employee_data:
                return f"I couldn't find any employee matching: {phone_number if phone_match else identifier}"
            
            # Format the response
            response = f"Employee Information:\n\n"
            for key, value in employee_data.items():
                if key and value and value != "nan":
                    response += f"{key}: {value}\n"
            
            return response
        
        except Exception as e:
            logger.error(f"Error extracting employee info: {e}")
            return "Sorry, I encountered an error while retrieving employee information. Please try again later."
    
    async def _update_employee_info(self, message: str, user_info: Dict, role: str) -> str:
        """Update employee information in the Google Spreadsheet"""
        
        # Check if user has permission to update employee data
        if role != "hr" and user_info.get("role") != "hr":
            return "I'm sorry, you don't have permission to update employee information. Please contact your HR department."
        
        try:
            # Extract update details from the message
            prompt = f"""
            From this message, extract the employee identifier and the information to be updated:
            
            MESSAGE: {message}
            
            Format your response as a JSON object with these fields:
            - identifier: The employee identifier (phone number, name, or employee ID)
            - updates: A dictionary of fields to update with their new values
            
            Example: {{"identifier": "+1234567890", "updates": {{"Department": "Finance", "Position": "Senior Accountant"}}}}
            
            Return ONLY the JSON object without any additional text.
            """
            
            update_details_str = await get_gemini_response(prompt, user_info.get("id", "unknown"), "system")
            update_details = json.loads(update_details_str)
            
            identifier = update_details.get("identifier")
            updates = update_details.get("updates", {})
            
            if not identifier or not updates:
                return "I couldn't identify which employee to update or what information to update. Please provide more details."
            
            # Update employee data in Google Sheets
            success = await self._update_employee_data(identifier, updates)
            
            if success:
                updated_fields = ", ".join(updates.keys())
                return f"Successfully updated {updated_fields} for employee with identifier: {identifier}"
            else:
                return f"I couldn't find any employee matching: {identifier}"
        
        except Exception as e:
            logger.error(f"Error updating employee info: {e}")
            return "Sorry, I encountered an error while updating employee information. Please try again later."
    
    async def _handle_general_employee_query(self, message: str, user_info: Dict, role: str) -> str:
        """Handle general employee-related queries"""
        
        prompt = f"""
        You are an Employee Manager Assistant helping with HR queries.
        
        USER ROLE: {role}
        USER QUERY: {message}
        
        Respond to this query about employee management, keeping in mind:
        - If the user is not HR, be careful about sharing sensitive information
        - Give concise, professional responses
        - If you can't answer, suggest contacting HR
        
        Your response:
        """
        
        try:
            response = await get_gemini_response(prompt, user_info.get("id", "unknown"), "system")
            return response
        except Exception as e:
            logger.error(f"Error handling general employee query: {e}")
            return "I'm having trouble processing your request. Please try again later or contact your HR department."
    
    async def _retrieve_employee_data(self, identifier: str) -> Dict:
        """Retrieve employee data from Google Sheets based on identifier"""
        
        try:
            # Get all employee data from Google Sheets
            sheet_data = await self.sheets_service.get_sheet_data(self.spreadsheet_id, self.sheet_name)
            
            # Convert to DataFrame for easier manipulation
            df = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
            
            # Try to match by phone number (column B) first
            matched_row = df[df.iloc[:, 1].str.contains(identifier, case=False, na=False)]
            
            # If no match, try other columns
            if matched_row.empty:
                for col in df.columns:
                    matched_row = df[df[col].astype(str).str.contains(identifier, case=False, na=False)]
                    if not matched_row.empty:
                        break
            
            if matched_row.empty:
                return {}
            
            # Convert first matched row to dictionary
            employee_data = matched_row.iloc[0].to_dict()
            return employee_data
        
        except Exception as e:
            logger.error(f"Error retrieving employee data: {e}")
            return {}
    
    async def _update_employee_data(self, identifier: str, updates: Dict) -> bool:
        """Update employee data in Google Sheets"""
        
        try:
            # Get all employee data from Google Sheets
            sheet_data = await self.sheets_service.get_sheet_data(self.spreadsheet_id, self.sheet_name)
            
            # Convert to DataFrame for easier manipulation
            df = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
            
            # Try to find the row to update
            row_idx = -1
            
            # Try to match by phone number (column B) first
            matched_rows = df[df.iloc[:, 1].str.contains(identifier, case=False, na=False)]
            
            # If no match, try other columns
            if matched_rows.empty:
                for col in df.columns:
                    matched_rows = df[df[col].astype(str).str.contains(identifier, case=False, na=False)]
                    if not matched_rows.empty:
                        break
            
            if matched_rows.empty:
                return False
            
            # Get the row index (adding 2 to account for 0-indexing and header row)
            row_idx = matched_rows.index[0] + 2
            
            # Update the cell values
            for field, value in updates.items():
                if field in df.columns:
                    col_idx = df.columns.get_loc(field) + 1  # +1 for 1-indexing in Sheets API
                    await self.sheets_service.update_cell(
                        self.spreadsheet_id,
                        self.sheet_name,
                        row_idx,
                        col_idx,
                        value
                    )
            
            return True
        
        except Exception as e:
            logger.error(f"Error updating employee data: {e}")
            return False