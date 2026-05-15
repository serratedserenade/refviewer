import os

IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.tiff', '.ico')

def scan_directory(path: str) -> list[str]:
    file_list = []
    clean_path = path.strip().strip('"').strip("'")
    
    if not os.path.isdir(clean_path):
        raise ValueError(f"Invalid directory selected: {clean_path}")
        
    for root, _, files in os.walk(clean_path):
        for file in files:
            if file.lower().endswith(IMAGE_EXTENSIONS):
                file_list.append(os.path.join(root, file))
                    
    return file_list