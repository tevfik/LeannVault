import os
import shutil
from pathlib import Path

SOURCE_DIR = Path("PLACEHOLDER_SOURCE_DIR")
TARGET_DIR = Path("PLACEHOLDER_TARGET_DIR")
MAX_SIZE_MB = 500
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

def collect_subset():
    current_size = 0
    file_count = 0
    
    # Priority extensions
    extensions = ['.json', '.pptx', '.docx', '.pdf']
    
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Scanning {SOURCE_DIR} for subset (Target: {MAX_SIZE_MB}MB)...")
    
    for root, dirs, files in os.walk(SOURCE_DIR):
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix.lower() in extensions:
                file_size = file_path.stat().st_size
                if current_size + file_size <= MAX_SIZE_BYTES:
                    # Create relative path in target
                    rel_path = file_path.relative_to(SOURCE_DIR)
                    target_path = TARGET_DIR / rel_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    shutil.copy2(file_path, target_path)
                    current_size += file_size
                    file_count += 1
                    
                    if file_count % 100 == 0:
                        print(f"Copied {file_count} files ({current_size / (1024*1024):.2f} MB)...")
                else:
                    if current_size > 0: # If we have at least one file
                         print(f"Reached limit: {current_size / (1024*1024):.2f} MB, {file_count} files.")
                         return

    print(f"Finished: {current_size / (1024*1024):.2f} MB, {file_count} files copied.")

if __name__ == "__main__":
    collect_subset()
