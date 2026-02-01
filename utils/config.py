from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
DEFAULT_TEMPLATE = TEMPLATES_DIR / "base.html"
DEFAULT_CONTENT = TEMPLATES_DIR / "content.html"
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
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".rtf", ".csv", ".odt", ".ods", ".odp",
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg",
    # Archives
    ".zip", ".rar", ".7z", ".tar", ".gz",
    # Code/Data
    ".json", ".xml", ".html", ".css", ".js", ".py",
}


def get_template_path() -> Path:
    if DEFAULT_TEMPLATE.exists():
        return DEFAULT_TEMPLATE
    
    # Fallback to root-level base.html for backward compatibility
    root_template = PROJECT_ROOT / "base.html"
    if root_template.exists():
        return root_template
    
    raise FileNotFoundError(
        f"Email template not found. Expected at: {DEFAULT_TEMPLATE}"
    )


def validate_attachment_size(size_bytes: int) -> tuple[bool, Optional[str]]:
    """
    Validate attachment size.
    
    Returns:
        Tuple of (is_valid, error_message or None)
    """
    max_bytes = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    
    if size_bytes > max_bytes:
        size_mb = size_bytes / (1024 * 1024)
        return False, f"File size ({size_mb:.1f}MB) exceeds limit ({MAX_ATTACHMENT_SIZE_MB}MB)"
    
    return True, None


def validate_attachment_type(filename: str) -> tuple[bool, Optional[str]]:
    """
    Validate attachment file extension.
    
    Returns:
        Tuple of (is_valid, error_message or None)
    """
    ext = Path(filename).suffix.lower()
    
    if not ext:
        return False, "File has no extension"
    
    if ext not in ALLOWED_ATTACHMENT_TYPES:
        return False, f"File type '{ext}' not allowed"
    
    return True, None
