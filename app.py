import tkinter as tk
from tkinter import ttk
import os
import datetime
import os
import zipfile
import datetime
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

PARENT_FOLDER_PATH = "/home/mithun/sgc-project"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATE_SUFFIX = datetime.date.today().strftime("%Y-%m-%d")


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

def run_backup(selected_projects):
    for entry in selected_projects:
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

def start_gui():
    root = tk.Tk()
    root.title("Select Projects to Zip and Upload")

    folders = [f for f in os.listdir(PARENT_FOLDER_PATH) if os.path.isdir(os.path.join(PARENT_FOLDER_PATH, f))]
    vars = {}

    for folder in folders:
        var = tk.BooleanVar(value=True)
        chk = ttk.Checkbutton(root, text=folder, variable=var)
        chk.pack(anchor='w')
        vars[folder] = var

    def on_submit():
        selected = [folder for folder, var in vars.items() if var.get()]
        root.destroy()
        run_backup(selected)

    btn = ttk.Button(root, text="Start Backup", command=on_submit)
    btn.pack()
    root.mainloop()

if __name__ == "__main__":
    start_gui()