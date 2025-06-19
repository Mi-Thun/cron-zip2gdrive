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
PARENT_FOLDER_PATH = "/home/mithun/sgc-project"
DATE_SUFFIX = datetime.date.today().strftime("%Y-%m-%d")
LOG_FILE = os.path.join(BASE_DIR, 'backup-cron.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

projects = {
    "3pcl-lms": True,
    "bg-ebg-185123": True,
    "bg-elending-8623": True,
    "bibili": True,
    "card-payment": True,
    "card-services": True,
    "database-docker": True,
    "dwh": True,
    "dwh-working_importer": True,
    "gastroliver": True,
    "golimit": True,
    "inteliqx": True,
    "limit-doc": True,
    "mcc": True,
    "rm-tagging": True,
    "samsuddin-portfolio": True,
    "section-roster": True,
    "sgcsoft-website": True,
    "sme": True,
    "tax-return": True,
    "tdtr-encashment": True,
    "tdtr-encashment-ssl": True,
    "#document": True
}

EXCLUDE_DIRS = {k for k, v in projects.items() if not v}
EXCLUDE_DIRS.update({"node_modules", "env", "venv", "__pycache__", ".idea", ".vscode"})
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
        logging.info(f"Zipped {source_dir} → {zip_file_path}")
    except Exception as e:
        logging.error(f"Error zipping {source_dir}: {e}")

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
            return items[0]['id']
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
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
        uploaded = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        logging.info(f"Uploaded: {os.path.basename(file_path)} → Drive ID: {uploaded.get('id')}")
    except Exception as e:
        logging.error(f"Failed to upload {file_path} to Drive: {e}")

if __name__ == "__main__":
    for entry in os.listdir(PARENT_FOLDER_PATH):
        full_path = os.path.join(PARENT_FOLDER_PATH, entry)
        if os.path.isdir(full_path):
            zip_filename = f"backup/{entry}_{DATE_SUFFIX}.zip"
            zip_path = os.path.join(BASE_DIR, zip_filename)
            zip_directory(full_path, zip_path)
            upload_to_drive(zip_path)
            delete_after_upload = True
            if delete_after_upload and os.path.exists(zip_path):
                os.remove(zip_path)
                logging.info(f"Deleted local zip file: {zip_path}")
        else:
            logging.warning(f"Skipping non-directory entry: {full_path}")
    logging.info("Backup process completed.")
