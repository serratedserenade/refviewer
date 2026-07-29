import os

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff", ".ico")


def scan_directory(path: str) -> list[str]:
    """Recursively collects every supported image file under `path`.

    Raises ValueError if `path` is not a directory. Surrounding whitespace and
    quotes are stripped first, so paths pasted from a shell or file manager work.
    """
    clean_path = path.strip().strip('"').strip("'")

    if not os.path.isdir(clean_path):
        raise ValueError(f"Invalid directory selected: {clean_path}")

    file_list = []
    for root, _, files in os.walk(clean_path):
        for file in files:
            if file.lower().endswith(IMAGE_EXTENSIONS):
                file_list.append(os.path.join(root, file))

    # Sorted once at the end so ordering is stable across directory boundaries.
    file_list.sort()
    return file_list