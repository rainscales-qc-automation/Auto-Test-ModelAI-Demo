import gspread
from google.oauth2.service_account import Credentials

SERVICE_ACCOUNT_FILE = "service-google-sheet.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

client = gspread.authorize(creds)

SHEET_ID = "1ZLOMBoicK059LWTgYUU3hvtOVmAy9syStMVQ8vrYlDg"
sheet = client.open_by_key(SHEET_ID).sheet1

data = sheet.get_all_records()

for row in data:
    print(row)
