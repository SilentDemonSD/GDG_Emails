import re
from typing import Optional


# RFC 5322 simplified email regex pattern
EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def is_valid_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
    
    Returns:
        True if valid format, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    
    email = email.strip()
    
    # Basic length checks
    if len(email) < 3 or len(email) > 254:
        return False
    
    # Check for exactly one @
    if email.count("@") != 1:
        return False
    
    local, domain = email.rsplit("@", 1)
    
    # Local part length (max 64 chars)
    if len(local) > 64 or len(local) < 1:
        return False
    
    # Domain length
    if len(domain) < 3:
        return False
    
    return bool(EMAIL_PATTERN.match(email))


def validate_email_list(emails: str, separator: str = ",") -> tuple[list[str], list[str]]:
    """
    Validate comma-separated email list.
    
    Args:
        emails: Comma-separated email string
        separator: Delimiter character
    
    Returns:
        Tuple of (valid_emails, invalid_emails)
    """
    if not emails or not emails.strip():
        return [], []
    
    valid = []
    invalid = []
    
    for email in emails.split(separator):
        email = email.strip()
        if not email:
            continue
        
        if is_valid_email(email):
            valid.append(email)
        else:
            invalid.append(email)
    
    return valid, invalid


def parse_email_input(email_string: str) -> tuple[list[str], Optional[str]]:
    """
    Parse and validate email input string.
    
    Args:
        email_string: User input with comma-separated emails
    
    Returns:
        Tuple of (valid_emails, error_message or None)
    """
    valid, invalid = validate_email_list(email_string)
    
    if invalid:
        return valid, f"Invalid email(s): {', '.join(invalid)}"
    
    return valid, None


def is_gmail_address(email: str) -> bool:
    if not is_valid_email(email):
        return False
    return email.lower().endswith(("@gmail.com", "@googlemail.com"))


def sanitize_email_input(email_string: str) -> str:
    """
    Clean up email input string.
    
    Handles various separators and whitespace.
    """
    # Normalize common separators to comma
    normalized = email_string.replace(";", ",").replace("\n", ",").replace("\t", ",")
    
    # Remove multiple commas and extra whitespace
    parts = [p.strip() for p in normalized.split(",") if p.strip()]
    
    return ", ".join(parts)
