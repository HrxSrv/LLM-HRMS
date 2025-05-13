from typing import List, Dict, Any
import logging
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    def __init__(self):
        """Initialize Google Sheets API client"""
        try:
            # Path to service account credentials JSON file
            creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials/google-service-account.json")
            
            # Scopes required for Google Sheets
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            
            # Create credentials
            credentials = service_account.Credentials.from_service_account_file(
                creds_path, scopes=scopes
            )
            
            # Build the service
            self.service = build('sheets', 'v4', credentials=credentials)
            logger.info("Google Sheets service initialized successfully")
        
        except Exception as e:
            logger.error(f"Error initializing Google Sheets service: {e}")
            self.service = None
    
    def normalize_range(self, range_name: str) -> str:
        """
        Normalize a range string by:
        1. Adding sheet name if missing
        2. Properly quoting sheet names with spaces
        """
        if "!" in range_name:
            # Range already includes sheet name
            sheet_name, cell_range = range_name.split("!", 1)
            
            # Add quotes to sheet name if it contains spaces and isn't already quoted
            if " " in sheet_name and not (sheet_name.startswith("'") and sheet_name.endswith("'")):
                sheet_name = f"'{sheet_name}'"
                
            return f"{sheet_name}!{cell_range}"
        else:
            # Assume range_name is just the sheet name
            sheet_name = range_name
            
            # Add quotes to sheet name if it contains spaces and isn't already quoted
            if " " in sheet_name and not (sheet_name.startswith("'") and sheet_name.endswith("'")):
                sheet_name = f"'{sheet_name}'"
                
            return f"{sheet_name}!A:Z"
    async def get_sheet_data(self, spreadsheet_id: str, range_name: str) -> List[List[str]]:
        range_name = self.normalize_range(range_name)
        """Retrieve data from a Google Sheet range"""
        try:
            if not self.service:
                logger.error("Google Sheets service not initialized")
                return []
            
            # Call the Sheets API
            sheet = self.service.spreadsheets()
            result = sheet.values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            # Get the values from the result
            values = result.get('values', [])
            
            if not values:
                logger.warning(f"No data found in sheet {range_name}")
                return []
                
            return values
            
        except HttpError as error:
            logger.error(f"Google Sheets API error: {error}")
            return []
        except Exception as e:
            logger.error(f"Error retrieving sheet data: {e}")
            return []
    
    async def update_cell(self, spreadsheet_id: str, sheet_name: str, row: int, col: int, value: Any) -> bool:
        """Update a specific cell in a Google Sheet"""
        try:
            if not self.service:
                logger.error("Google Sheets service not initialized")
                return False
            
            # Convert row, col to A1 notation
            col_letter = chr(64 + col) if col <= 26 else chr(64 + col // 26) + chr(64 + col % 26)
            range_name = f"{sheet_name}!{col_letter}{row}"
            
            # Prepare request body
            body = {
                'values': [[value]]
            }
            
            # Call the Sheets API
            sheet = self.service.spreadsheets()
            result = sheet.values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            logger.info(f"Cell {range_name} updated successfully")
            return True
            
        except HttpError as error:
            logger.error(f"Google Sheets API error: {error}")
            return False
        except Exception as e:
            logger.error(f"Error updating cell: {e}")
            return False
    
    async def append_row(self, spreadsheet_id: str, sheet_name: str, values: List[Any]) -> bool:
        """Append a row to a Google Sheet"""
        try:
            if not self.service:
                logger.error("Google Sheets service not initialized")
                return False
            
            # Prepare request body
            body = {
                'values': [values]
            }
            
            # Call the Sheets API
            sheet = self.service.spreadsheets()
            result = sheet.values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            logger.info(f"Row appended successfully to {sheet_name}")
            return True
            
        except HttpError as error:
            logger.error(f"Google Sheets API error: {error}")
            return False
        except Exception as e:
            logger.error(f"Error appending row: {e}")
            return False