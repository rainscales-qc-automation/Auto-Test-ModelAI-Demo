import os
import json
import gspread
from google.oauth2.service_account import Credentials

from config.settings import cf


class GoogleSheetConnector:
    """
    GoogleSheetConnector is responsible for connecting to Google Sheets
    using a service account key file and providing methods to read data.
    """

    def __init__(self, service_account_file=None, sheet_id=None):
        """ Initialize the sheet connector. """
        self.service_account_file = service_account_file or os.path.join(cf.SERVICE_ACCOUNT_FILE)
        self.sheet_id = sheet_id or cf.SHEET_ID
        self.client = None
        self.sheet = None
        self.scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        self.detail_rule = 'E'
        self.test_case_id = 'F'
        self.test_case_description = 'G'
        self.video_name_colum = 'H'
        self.camera_name_colum = 'I'
        self.start_time_colum = 'K'
        self.end_time_colum = 'L'
        self.event_start_time_colum = 'M'
        self.event_end_time_colum = 'N'
        self.expected_status_column = 'O'
        self.expected_result_column = 'P'

    def connect(self):
        """ Connect to Google Sheets using the provided service account file. """
        credentials = Credentials.from_service_account_file(self.service_account_file, scopes=self.scopes)
        self.client = gspread.authorize(credentials)
        return self.client

    def open_sheet(self, sheet_name):
        """ Open a specific sheet by name. """
        if self.client is None:
            self.connect()
        spreadsheet = self.client.open_by_key(self.sheet_id)
        self.sheet = spreadsheet.worksheet(sheet_name)
        return self.sheet

    def get_all_records(self, sheet_name):
        """ Retrieve all records from the specified sheet as a list of dictionaries. """
        sheet = self.open_sheet(sheet_name)
        return sheet.get_all_records()

    def get_filled_blank_merged_cell(self, sheet_name):
        """Get all data of sheet, automatically fill blank cells in merged cell area"""
        sheet = self.open_sheet(sheet_name)
        data = sheet.get_all_values()

        headers = data[0]
        rows = data[1:]

        # Fill empty cells vertically (like merged cell)
        for col_idx in range(len(headers)):
            last_value = None
            for row_idx in range(len(rows)):
                cell = rows[row_idx][col_idx]
                if cell:
                    last_value = cell
                else:
                    rows[row_idx][col_idx] = last_value

        filled_data = [dict(zip(headers, row)) for row in rows]
        return filled_data

    def get_values(self, sheet_name, cell_range):
        """
        Retrieve raw cell values from a given range.
        param cell_range: A1 notation range (e.g., "A1:C10").
        """
        sheet = self.open_sheet(sheet_name)
        return sheet.get(cell_range)

    def get_all_video_names(self, sheet_name):
        """ Get all video names from the sheet. """
        sheet = self.open_sheet(sheet_name)
        col_range = f"{self.video_name_colum}2:{self.video_name_colum}"
        values = sheet.get(col_range)
        return [v[0] for v in values if v]

    def get_videos_with_camera(self, sheet_name):
        """
        Get video names with camera names
        Returns: List[Dict] with keys: video_name, camera_name
        """
        sheet = self.open_sheet(sheet_name)

        # Get video column (H) and camera column (I)
        video_col_idx = ord(self.video_name_colum) - ord('A')
        camera_col_idx = ord(self.camera_name_colum) - ord('A')

        all_values = sheet.get_all_values()
        rows = all_values[1:]  # Skip header

        videos_info = []
        for row in rows:
            if len(row) <= max(video_col_idx, camera_col_idx):
                continue

            video_name = row[video_col_idx].strip()
            camera_name = row[camera_col_idx].strip()

            if video_name:  # Only add if video_name exists
                videos_info.append({
                    'video_name': video_name,
                    'camera_name': camera_name
                })

        return videos_info

    def get_info_row_by_video_name(self, sheet_name, video_name):
        """ Get all related information in the same row as the given video name. """
        sheet = self.open_sheet(sheet_name)
        all_values = sheet.get_all_values()
        headers = all_values[0]
        rows = all_values[1:]

        for row in rows:
            if len(row) > 7 and row[7].strip() == video_name.strip():
                return dict(zip(headers, row))

        return None

    def get_info_rows_by_video_names(self, sheet_name, video_names):
        sheet = self.open_sheet(sheet_name)
        all_values = sheet.get_all_values()
        headers = all_values[0]
        rows = all_values[1:]

        video_names = [v.strip() for v in video_names if v]

        def col_to_index(col):
            return ord(col.upper()) - ord('A')

        needed_columns = [
            self.test_case_id,
            self.test_case_description,
            self.video_name_colum,
            self.camera_name_colum,
            self.start_time_colum,
            self.end_time_colum,
            self.event_start_time_colum,
            self.event_end_time_colum,
            self.expected_status_column,
            self.expected_result_column,
        ]
        needed_indexes = [col_to_index(c) for c in needed_columns]

        matched_rows = []
        for row in rows:
            if len(row) > 7 and row[7].strip() in video_names:
                filtered_data = {}
                for col, idx in zip(needed_columns, needed_indexes):
                    if idx < len(headers):
                        header = headers[idx]
                        value = row[idx].strip() if idx < len(row) and row[idx] else ""

                        # Nếu đây là cột expected_result_column → parse JSON
                        if col == self.expected_result_column and value:
                            try:
                                value = json.loads(value)
                            except json.JSONDecodeError:
                                pass  # giữ nguyên nếu không parse được

                        filtered_data[header] = value
                matched_rows.append(filtered_data)

        return matched_rows


if __name__ == '__main__':
    sheet_connector = GoogleSheetConnector(cf.SERVICE_ACCOUNT_FILE, cf.SHEET_ID)
    client_sheet = sheet_connector.connect()

    # Test new method
    videos = sheet_connector.get_videos_with_camera('USEPHONE_Smoke')
    print(f"Found {len(videos)} videos")
    for v in videos:
        print(f"  {v['video_name']} - {v['camera_name']}")
    print(sheet_connector.get_info_rows_by_video_names('USEPHONE_Smoke', [v['video_name'] for v in videos]))