from google import genai
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

# Google Sheets Setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = r"C:\Users\hp\Downloads\hrms-457411-a7416cd9d4cb.json"
credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
service = build('sheets', 'v4', credentials=credentials)
sheet_id = '1rkOep246FNR9vm3vOcgcenZLBTxWQa3F_wqS4HTqxLY'

# A: Timestamp | B: Employee ID | C: Name | D: Leave Date | E: Status | F: Type

def process_leave_request(command: str):

    parse_prompt = f"""Convert this leave command to JSON:
    {command}
    
    Output format:
    {{
        "action": "add/update/delete",
        "employee_id": 123,
        "date": "YYYY-MM-DD",
        "status": "Pending/Cancelled/Approved",
        "type": "sick/vacation/personal"
    }}"""
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=parse_prompt
    )
    
    # Extract JSON from response
    # json_str = response.text.replace('```json', '').replace('```', '').strip()
    # action_data = eval(json_str)

    json_str = response.text.split('```json')[1].split('```')[0].strip()
    try:
        action_data = eval(json_str)
    except:
        return "Failed to parse Gemini response"
    
    # Execute Sheets operation
    sheet = service.spreadsheets()
    range_name = 'Sheet1!A:F'
    
    # Add new leave
    if action_data['action'] == 'add':
        new_row = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            action_data['employee_id'],
            "Employee Name", 
            action_data['date'],
            "Pending",
            action_data.get('type', 'personal')
        ]
        sheet.values().append(
            spreadsheetId=sheet_id,
            range=range_name,
            body={'values': [new_row]},
            valueInputOption='USER_ENTERED'
        ).execute()
        return "Leave request submitted!"
    
    # Update/Delete existing
    result = sheet.values().get(spreadsheetId=sheet_id, range=range_name).execute()
    rows = result.get('values', [])
    
    for i, row in enumerate(rows):
        if str(row[1]) == str(action_data['employee_id']) and row[3] == action_data['date']:
            if action_data['action'] == 'delete':
                sheet.values().clear(
                    spreadsheetId=sheet_id,
                    range=f'Sheet1!A{i+1}:F{i+1}'
                ).execute()
                return "Leave deleted!"
            
            if action_data['action'] == 'update':
                update_range = f'Sheet1!E{i+1}'
                sheet.values().update(
                    spreadsheetId=sheet_id,
                    range=update_range,
                    body={'values': [[action_data['status']]]},  
                    valueInputOption='USER_ENTERED'
                ).execute()
                return "Leave updated!"
    
    return "No matching leave found"

# Example usage
# print(process_leave_request("I need to take a vacation day next Friday"))
print(process_leave_request("add leave for employee_id =123 for 2024-05-01"))