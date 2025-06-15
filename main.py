# https://console.cloud.google.com/apis/library/drive.googleapis.com?project=backup-463008&inv=1&invt=Ab0K4w
# pip install --user google-api-python-client google-auth-httplib2 google-auth-oauthlib
# chmod +x /home/mithun/zip.py
# crontab -e

import os
import zipfile
import datetime
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, 'backup-cron.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

EXCLUDE_DIRS = {"node_modules", "env", "venv", "__pycache__", ".idea", ".vscode"}
EXCLUDE_EXTENSIONS = {".pyc", ".log", ".cache"}

def zip_directory(source_dir, zip_file_path):
    try:
        with zipfile.ZipFile(zip_file_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
            for foldername, subfolders, filenames in os.walk(source_dir):
                subfolders[:] = [d for d in subfolders if d not in EXCLUDE_DIRS]
                for filename in filenames:
                    if any(filename.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                        continue
                    file_path = os.path.join(foldername, filename)
                    arcname = os.path.relpath(file_path, start=source_dir)
                    zipf.write(file_path, arcname)
        logging.info(f"Zipped {source_dir} to {zip_file_path} with maximum compression.")
    except Exception as e:
        logging.error(f"Error zipping directory: {e}")
        raise

def authenticate():
    creds_path = os.path.join(BASE_DIR, 'credentials.json')
    creds = None
    token_path = os.path.join(BASE_DIR, 'token.pickle')
    try:
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, ['https://www.googleapis.com/auth/drive.file'])
                creds = flow.run_console(port=0)
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        logging.info("Google Drive authentication successful.")
        return creds
    except Exception as e:
        logging.error(f"Authentication failed: {e}")
        raise

def get_or_create_folder(service, folder_name):
    try:
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])
        if items:
            logging.info(f"Found existing folder '{folder_name}' on Google Drive.")
            return items[0]['id']
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        logging.info(f"Created folder '{folder_name}' on Google Drive.")
        return folder.get('id')
    except Exception as e:
        logging.error(f"Error getting or creating folder: {e}")
        raise

def upload_to_drive(file_path):
    try:
        creds = authenticate()
        service = build('drive', 'v3', credentials=creds)
        folder_id = get_or_create_folder(service, 'Code-Backup')
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        logging.info(f"Uploaded '{file_path}' to Google Drive 'Code-Backup' folder with file ID: {file.get('id')}")
    except Exception as e:
        logging.error(f"Error uploading to Google Drive: {e}")
        raise

if __name__ == "__main__":
    parent_folder_path = "/home/mithun/sgc-project"
    output_zip_path = os.path.join(BASE_DIR, f"backup-{(datetime.date.today()).strftime('%Y-%m-%d')}.zip")
    try:
        zip_directory(parent_folder_path, output_zip_path)
        upload_to_drive(output_zip_path)
    except Exception as e:
        logging.critical(f"Backup process failed: {e}")