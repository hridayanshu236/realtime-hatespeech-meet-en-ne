import os
import zipfile
import urllib.request
import sys
import subprocess

def install_gdown():
    try:
        import gdown
    except ImportError:
        print("gdown not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])

def download_and_extract_model():
    install_gdown()
    import gdown

    # The actual Google Drive file ID of the zipped model
    FILE_ID = "15JHFlitkOxKrFy1ePdoJHWuZ4oCGd3aK"

    url = f"https://drive.google.com/uc?id={FILE_ID}"
    output_zip = "model_temp.zip"
    extract_dir = "models/xlmroberta_finetuned"

    print("Downloading the hate speech model from Google Drive...")
    try:
        gdown.download(url, output_zip, quiet=False)
    except Exception as e:
        print(f"Failed to download. Error: {e}")
        sys.exit(1)

    if not os.path.exists(output_zip):
        print("Download failed, zip file not found.")
        sys.exit(1)

    print("Extracting model files...")
    os.makedirs(extract_dir, exist_ok=True)
    
    with zipfile.ZipFile(output_zip, 'r') as zip_ref:
        # Extract files directly to the directory, flattening if they are inside a folder
        for member in zip_ref.namelist():
            filename = os.path.basename(member)
            if not filename:
                continue
            
            source = zip_ref.open(member)
            target = open(os.path.join(extract_dir, filename), "wb")
            with source, target:
                import shutil
                shutil.copyfileobj(source, target)

    print("Cleaning up...")
    os.remove(output_zip)

    print(f"Success! Model files have been placed in {extract_dir}.")
    print("You can now run the backend server.")

if __name__ == "__main__":
    download_and_extract_model()
