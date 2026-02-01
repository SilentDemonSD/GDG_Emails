import mimetypes
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email import encoders
from typing import Optional, Union
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(slots=True)
class EmailRecipients:
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    
    def all_recipients(self) -> list[str]:
        return self.to + self.cc + self.bcc
    
    def has_recipients(self) -> bool:
        return bool(self.to or self.cc or self.bcc)


@dataclass(slots=True, frozen=True)
class Attachment:
    filename: str
    content: bytes
    content_type: Optional[str] = None


@lru_cache(maxsize=128)
def _guess_mime_type(filename: str) -> str:
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or "application/octet-stream"


class MessageBuilder:
    
    __slots__ = ('template_path', '_template_content')
    
    # Class-level template cache for reuse across instances
    _template_cache: dict[str, str] = {}
    
    def __init__(self, template_path: str):
        """
        Initialize with HTML template path.
        
        Args:
            template_path: Path to base.html template file
        """
        self.template_path = Path(template_path)
        self._template_content: Optional[str] = None
    
    @property
    def template(self) -> str:
        if self._template_content is None:
            cache_key = str(self.template_path)
            
            if cache_key in MessageBuilder._template_cache:
                self._template_content = MessageBuilder._template_cache[cache_key]
            else:
                if not self.template_path.exists():
                    raise MessageBuilderError(f"Template not found: {self.template_path}")
                self._template_content = self.template_path.read_text(encoding="utf-8")
                MessageBuilder._template_cache[cache_key] = self._template_content
                
        return self._template_content
    
    @classmethod
    def clear_cache(cls) -> None:
        cls._template_cache.clear()
    
    def inject_content(self, content: str, placeholders: Optional[dict[str, str]] = None) -> str:
        """
        Inject HTML content into template.
        
        Args:
            content: HTML content for {{CONTENT}} placeholder
            placeholders: Additional placeholder replacements (e.g., {"FNAME": "John"})
        
        Returns:
            Complete HTML with injected content
        """
        html = self.template
        
        html = html.replace("{{CONTENT}}", content)
        
        if placeholders:
            for key, value in placeholders.items():
                html = html.replace(f"{{{{{key}}}}}", value)
        
        return html
    
    def build(
        self,
        sender: str,
        recipients: EmailRecipients,
        subject: str,
        html_content: str,
        placeholders: Optional[dict[str, str]] = None,
        attachments: Optional[list[Attachment]] = None,
        plain_text_fallback: Optional[str] = None
    ) -> MIMEMultipart:
        """
        Build complete MIME message.
        
        Args:
            sender: Sender email address
            recipients: EmailRecipients object
            subject: Email subject line
            html_content: HTML to inject into {{CONTENT}} placeholder
            placeholders: Additional template placeholders
            attachments: List of Attachment objects
            plain_text_fallback: Plain text version (default auto-generated)
        
        Returns:
            Fully constructed MIMEMultipart message
        """
        if not recipients.has_recipients():
            raise MessageBuilderError("At least one recipient required")
        
        # Determine message structure based on attachments
        if attachments:
            # mixed for attachments, with alternative for HTML/plain
            msg = MIMEMultipart("mixed")
            body_container = MIMEMultipart("alternative")
            msg.attach(body_container)
        else:
            # Simple alternative structure for HTML/plain
            msg = MIMEMultipart("alternative")
            body_container = msg
        
        # Set headers
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients.to)
        
        if recipients.cc:
            msg["Cc"] = ", ".join(recipients.cc)
        # Note: BCC is intentionally NOT added to headers (handled at SMTP level)
        
        # Inject content into template
        final_html = self.inject_content(html_content, placeholders)
        
        # Plain text fallback
        if plain_text_fallback is None:
            plain_text_fallback = "This email requires HTML support to view properly."
        
        # Attach plain text first, HTML second (email clients prefer later parts)
        body_container.attach(MIMEText(plain_text_fallback, "plain", "utf-8"))
        body_container.attach(MIMEText(final_html, "html", "utf-8"))
        
        # Process attachments
        if attachments:
            for attachment in attachments:
                self._attach_file(msg, attachment)
        
        return msg
    
    def _attach_file(self, msg: MIMEMultipart, attachment: Attachment) -> None:
        # Use cached MIME type lookup
        content_type = attachment.content_type or _guess_mime_type(attachment.filename)
        
        maintype, subtype = content_type.split("/", 1)
        
        if maintype == "text":
            part = MIMEText(attachment.content.decode("utf-8", errors="replace"), _subtype=subtype)
        elif maintype == "image":
            part = MIMEImage(attachment.content, _subtype=subtype)
        elif maintype == "audio":
            part = MIMEAudio(attachment.content, _subtype=subtype)
        else:
            part = MIMEBase(maintype, subtype)
            part.set_payload(attachment.content)
            encoders.encode_base64(part)
        
        # Set filename for download
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=attachment.filename
        )
        
        msg.attach(part)
    
    @staticmethod
    def create_attachment_from_file(file_path: Union[str, Path]) -> Attachment:
        path = Path(file_path)
        return Attachment(
            filename=path.name,
            content=path.read_bytes()
        )
    
    @staticmethod
    def create_attachment_from_upload(filename: str, content: bytes) -> Attachment:
        return Attachment(filename=filename, content=content)


class MessageBuilderError(Exception):
    pass
