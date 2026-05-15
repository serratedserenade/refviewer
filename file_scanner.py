import os

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".ico")


def scan_directory(path: str) -> list[str]:
    file_list = []
    clean_path = path.strip().strip('"').strip("'")

    if not os.path.isdir(clean_path):
        raise ValueError(f"Invalid directory selected: {clean_path}")

    for root, _, files in os.walk(clean_path):
        for file in sorted(files):  # ← Sort within each directory
            if file.lower().endswith(IMAGE_EXTENSIONS):
                file_list.append(os.path.join(root, file))

    file_list.sort()  # ← Sort the final result for cross-directory consistency
    return file_list