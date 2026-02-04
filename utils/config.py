from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
CONTENTS_DIR = TEMPLATES_DIR / "contents"
ATTACH_DIR = PROJECT_ROOT / "attach"


@dataclass
class SMTPSettings:
    host: str = "smtp.gmail.com"
    port: int = 587
    use_tls: bool = True
    timeout: int = 30


class GoogleColors:
    BLUE = "#1a73e8"
    RED = "#ea4335"
    YELLOW = "#fbbc04"
    GREEN = "#34a853"
    DARK_BLUE = "#153563"
    GRAY_BG = "#fbf9fa"
    TEXT_PRIMARY = "#202124"
    TEXT_SECONDARY = "#5f6368"


MAX_ATTACHMENT_SIZE_MB = 25
MAX_TOTAL_ATTACHMENT_SIZE_MB = 25
ALLOWED_ATTACHMENT_TYPES = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".rtf", ".csv", ".odt", ".ods", ".odp",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".json", ".xml", ".html", ".css", ".js", ".py",
}


def validate_attachment_size(size_bytes: int) -> tuple[bool, Optional[str]]:
    max_bytes = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        size_mb = size_bytes / (1024 * 1024)
        return False, f"File size ({size_mb:.1f}MB) exceeds limit ({MAX_ATTACHMENT_SIZE_MB}MB)"
    return True, None


def validate_attachment_type(filename: str) -> tuple[bool, Optional[str]]:
    if ext := Path(filename).suffix.lower():
        return (
            (False, f"File type '{ext}' not allowed")
            if ext not in ALLOWED_ATTACHMENT_TYPES
            else (True, None)
        )
    else:
        return False, "File has no extension"
