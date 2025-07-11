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
today = datetime.date.today()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

EXCLUDE_DIRS={"node_modules", "env", "venv", "__pycache__", ".idea", ".vscode"}
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
        folder_id = get_or_create_folder(service, f'{DATE_SUFFIX}_Backup')
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        uploaded = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        logging.info(f"Uploaded: {os.path.basename(file_path)} → Drive ID: {uploaded.get('id')}")
    except Exception as e:
        logging.error(f"Failed to upload {file_path} to Drive: {e}")

def folder_has_file_modified_today(folder_path):
    for root, subdirs, files in os.walk(folder_path):
        subdirs[:] = [d for d in subdirs if d not in EXCLUDE_DIRS]
        for fname in files:
            if any(fname.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                continue
            fpath = os.path.join(root, fname)
            try:
                mtime = datetime.date.fromtimestamp(os.path.getmtime(fpath))
                if mtime == today:
                    return True
            except Exception as e:
                logging.warning(f"Could not check mtime for {fpath}: {e}")
    return False

if __name__ == "__main__":
    # Check if today is the 1st day of the month for full backup
    is_monthly_backup = today.day == 9
    
    # Ensure backup directory exists
    backup_dir = os.path.join(BASE_DIR, 'backup')
    os.makedirs(backup_dir, exist_ok=True)
    
    if is_monthly_backup:
        logging.info("Monthly backup: Backing up all folders (1st day of the month)")
    else:
        logging.info("Daily backup: Only backing up folders with files modified today")
    
    # Authenticate once for all uploads
    try:
        creds = authenticate()
        service = build('drive', 'v3', credentials=creds)
        folder_id = get_or_create_folder(service, f'{DATE_SUFFIX}_Backup')
    except Exception as e:
        logging.error(f"Failed to authenticate or create Drive folder: {e}")
        exit(1)
    
    for entry in os.listdir(PARENT_FOLDER_PATH):
        if entry in EXCLUDE_DIRS:
            continue
        full_path = os.path.join(PARENT_FOLDER_PATH, entry)
        if os.path.isdir(full_path):
            try:
                # Backup all folders on 1st day of month, otherwise only modified ones
                should_backup = is_monthly_backup or folder_has_file_modified_today(full_path)
                
                if should_backup:
                    backup_type = "monthly" if is_monthly_backup else "daily"
                    logging.info(f"Starting {backup_type} backup for: {entry}")
                    
                    zip_filename = f"backup/{entry}.zip"
                    zip_path = os.path.join(BASE_DIR, zip_filename)
                    zip_directory(full_path, zip_path)
                    
                    # Upload using pre-authenticated service
                    file_metadata = {
                        'name': os.path.basename(zip_path),
                        'parents': [folder_id]
                    }
                    media = MediaFileUpload(zip_path, resumable=True)
                    uploaded = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                    logging.info(f"Uploaded: {os.path.basename(zip_path)} → Drive ID: {uploaded.get('id')}")
                    
                    delete_after_upload = True
                    if delete_after_upload and os.path.exists(zip_path):
                        os.remove(zip_path)
                        logging.info(f"Deleted local zip file: {zip_path}")
                else:
                    logging.info(f"Skipping {entry}: no file modified today.")
            except Exception as e:
                logging.error(f"Failed to backup {entry}: {e}")
                continue  # Continue with next folder
        else:
            logging.warning(f"Skipping non-directory entry: {full_path}")
    
    backup_type = "Monthly" if is_monthly_backup else "Daily"
    logging.info(f"{backup_type} backup process completed.")
