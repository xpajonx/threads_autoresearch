import os
import json
import io
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from execution.config import configs, retry

# Scopes for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']

class DriveSync:
    def __init__(self):
        self.creds = self._authenticate()
        self.service = build('drive', 'v3', credentials=self.creds)
        self.input_folder_id = os.getenv("GDRIVE_INPUT_FOLDER_ID")
        self.output_folder_id = os.getenv("GDRIVE_OUTPUT_FOLDER_ID")

    def _authenticate(self):
        creds = None
        token_path = configs.BASE_DIR / 'token.json'
        creds_path = configs.BASE_DIR / 'credentials.json'

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not creds_path.exists():
                    raise FileNotFoundError("credentials.json not found in root. Please provide it.")
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        return creds

    @retry(max_attempts=3)
    def find_file(self, name, folder_id):
        query = f"name = '{name}' and '{folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None

    @retry(max_attempts=3)
    def download_file(self, file_id, local_path):
        request = self.service.files().get_media(fileId=file_id)
        fh = io.FileIO(local_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        return local_path

    @retry(max_attempts=3)
    def upload_file(self, local_path, folder_id):
        file_name = os.path.basename(local_path)
        existing_id = self.find_file(file_name, folder_id)
        
        media = MediaFileUpload(local_path, resumable=True)
        
        if existing_id:
            # Update existing file
            self.service.files().update(
                fileId=existing_id,
                media_body=media
            ).execute()
            return existing_id
        else:
            # Create new file
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            return file.get('id')

    def find_path(self, path, root_id):
        """Resolve a path like 'Folder/Subfolder/File.md' in Drive."""
        parts = path.replace('\\', '/').split('/')
        current_id = root_id
        for part in parts:
            if not part: continue
            current_id = self.find_file(part, current_id)
            if not current_id:
                return None
        return current_id

    def sync_inputs(self, topic):
        """Download Source_of_Truth.md and Essay_*.md for the topic."""
        paths = {}
        
        if topic.startswith("FILE:"):
            # Direct file mode: The topic is a path to a specific markdown file
            file_path = topic.replace("FILE:", "")
            file_id = self.find_path(file_path, self.input_folder_id)
            
            if not file_id:
                print(f"File path '{file_path}' not found in input folder.")
                return {}
            
            # For direct files, we treat the file itself as Source_of_Truth.md
            local_sot = configs.TMP_DIR / "Source_of_Truth.md"
            self.download_file(file_id, str(local_sot))
            paths['sot'] = local_sot
            return paths

        # Dossier mode: topic is a folder containing Source_of_Truth.md
        # 1. Find topic subfolder
        topic_folder_id = self.find_file(topic, self.input_folder_id)
        if not topic_folder_id:
            print(f"Subfolder for topic '{topic}' not found in input folder.")
            return {}

        # 2. Find files in topic subfolder
        sot_name = "Source_of_Truth.md"
        essay_pattern = f"Essay_{topic}_Threads.md"
        
        sot_id = self.find_file(sot_name, topic_folder_id)
        essay_id = self.find_file(essay_pattern, topic_folder_id)
        
        if sot_id:
            local_sot = configs.TMP_DIR / sot_name
            self.download_file(sot_id, str(local_sot))
            paths['sot'] = local_sot
            
        if essay_id:
            local_essay = configs.TMP_DIR / essay_pattern
            self.download_file(essay_id, str(local_essay))
            paths['essay'] = local_essay
            
        return paths

    def sync_outputs(self, local_paths):
        """Upload results to output folder."""
        for path in local_paths:
            if os.path.exists(path):
                self.upload_file(path, self.output_folder_id)

if __name__ == "__main__":
    # Test sync
    # sync = DriveSync()
    # print("Drive Sync initialized.")
    pass
