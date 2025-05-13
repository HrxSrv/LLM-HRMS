import logging
from typing import Dict, Optional, List
import os
from datetime import datetime, timedelta
import json

# Google API imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
logger = logging.getLogger(__name__)

# Load Google API credentials
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/documents'
]

def get_google_credentials():
    """Get Google API credentials from service account file or environment"""
    try:
        # Try to load from service account file
        service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        
        if service_account_file and os.path.exists(service_account_file):
            credentials = service_account.Credentials.from_service_account_file(
                service_account_file, scopes=SCOPES)
            return credentials
        
        # If no file, try to use credentials from environment variable
        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            creds_info = json.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(
                creds_info, scopes=SCOPES)
            return credentials
            
        logger.error("No Google API credentials found")
        return None
        
    except Exception as e:
        logger.error(f"Error loading Google credentials: {str(e)}")
        return None

async def update_gsuite_resources(task_result: Dict) -> bool:
    """
    Update Google Workspace resources based on task results
    
    Args:
        task_result: Task processing result containing necessary details
        
    Returns:
        Boolean indicating success
    """
    try:
        if not task_result.get("success"):
            return False
            
        task_type = task_result.get("task_type")
        
        if task_type == "leave_approval":
            # Update calendar for leave
            if task_result.get("details", {}).get("calendar_update_required"):
                await update_calendar_for_leave(task_result.get("details", {}))
                
            # Update leave tracking spreadsheet
            await update_leave_tracking_spreadsheet(task_result.get("details", {}))
            
            # Send email notification
            await send_leave_approval_email(task_result.get("details", {}))
            
        # Add handling for other task types here
            
        return True
        
    except Exception as e:
        logger.error(f"Error updating G-Suite resources: {str(e)}")
        return False

async def update_calendar_for_leave(leave_details: Dict) -> Optional[str]:
    """
    Create calendar event for approved leave
    
    Args:
        leave_details: Details of the approved leave
        
    Returns:
        Calendar event ID or None if failed
    """
    try:
        credentials = get_google_credentials()
        if not credentials:
            return None
            
        service = build('calendar', 'v3', credentials=credentials)
        
        # Get employee details
        employee_name = leave_details.get("employee_name", "Employee")
        start_date = leave_details.get("start_date")
        end_date = leave_details.get("end_date")
        leave_type = leave_details.get("leave_type", "Leave")
        
        # Create event
        event = {
            'summary': f"{employee_name} - {leave_type}",
            'description': f"Approved leave for {employee_name}",
            'start': {
                'date': start_date.split(' ')[0] if ' ' in start_date else start_date,
                'timeZone': 'UTC',
            },
            'end': {
                'date': end_date.split(' ')[0] if ' ' in end_date else end_date,
                'timeZone': 'UTC',
            },
            'colorId': '5',  # Default color (adjust as needed)
        }
        
        # Get calendar ID from environment (default to primary)
        calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        
        # Create the event
        event = service.events().insert(calendarId=calendar_id, body=event).execute()
        
        logger.info(f"Calendar event created: {event.get('htmlLink')}")
        return event.get('id')
        
    except HttpError as error:
        logger.error(f"Error creating calendar event: {error}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error creating calendar event: {str(e)}")
        return None

async def update_leave_tracking_spreadsheet(leave_details: Dict) -> bool:
    """
    Update leave tracking spreadsheet with approved leave
    
    Args:
        leave_details: Details of the approved leave
        
    Returns:
        Boolean indicating success
    """
    try:
        credentials = get_google_credentials()
        if not credentials:
            return False
            
        service = build('sheets', 'v4', credentials=credentials)
        
        # Get spreadsheet ID from environment
        spreadsheet_id = os.getenv("LEAVE_TRACKING_SPREADSHEET_ID")
        if not spreadsheet_id:
            logger.error("No leave tracking spreadsheet ID configured")
            return False
            
        # Prepare data for the spreadsheet
        employee_name = leave_details.get("employee_name", "Employee")
        employee_id = leave_details.get("employee_id", "")
        start_date = leave_details.get("start_date", "")
        end_date = leave_details.get("end_date", "")
        leave_type = leave_details.get("leave_type", "")
        leave_id = leave_details.get("leave_id", "")
        
        # Format date for spreadsheet
        approval_date = datetime.now().strftime("%Y-%m-%d")
        
        # Data to append
        values = [
            [
                employee_id, 
                employee_name, 
                leave_type,
                start_date,
                end_date,
                approval_date,
                "Approved",
                leave_id
            ]
        ]
        
        body = {
            'values': values
        }
        
        # Append data to spreadsheet
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range="Leave Records!A:H",  # Adjust range as needed
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()
        
        logger.info(f"Spreadsheet updated: {result.get('updates').get('updatedCells')} cells updated")
        return True
        
    except HttpError as error:
        logger.error(f"Error updating spreadsheet: {error}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error updating spreadsheet: {str(e)}")
        return False

async def send_leave_approval_email(leave_details: Dict) -> bool:
    """
    Send email notification for leave approval
    
    Args:
        leave_details: Details of the approved leave
        
    Returns:
        Boolean indicating success
    """
    # Implementation for sending emails via Gmail API
    # This is a placeholder for the email sending functionality
    logger.info(f"Email notification would be sent for leave approval: {leave_details.get('leave_id')}")
    return True

async def generate_hr_document(document_type: str, details: Dict) -> Optional[str]:
    """
    Generate HR document using Google Docs
    
    Args:
        document_type: Type of document to generate
        details: Document details
        
    Returns:
        Document ID or None if failed
    """
    # Implementation for document generation
    # This is a placeholder for document generation functionality
    logger.info(f"Document generation would happen for {document_type}")
    return None