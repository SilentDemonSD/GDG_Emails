import smtplib
import ssl
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from functools import lru_cache


@lru_cache(maxsize=1)
def _get_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


@dataclass(frozen=True, slots=True)
class SMTPConfig:
    host: str = "smtp.gmail.com"
    port: int = 587
    use_tls: bool = True
    timeout: int = 30


# Thread pool for async operations
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="smtp_worker")


class SMTPClient:
    
    __slots__ = ('sender_email', 'app_password', 'config', '_connection')
    
    def __init__(self, sender_email: str, app_password: str, config: Optional[SMTPConfig] = None):
        self.sender_email = sender_email
        self.app_password = app_password
        self.config = config or SMTPConfig()
        self._connection: Optional[smtplib.SMTP] = None
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
    
    async def __aenter__(self):
        await self.connect_async()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect_async()
        return False
    
    def connect(self) -> None:
        try:
            self._connection = smtplib.SMTP(
                self.config.host, 
                self.config.port,
                timeout=self.config.timeout
            )
            self._connection.ehlo()
            
            if self.config.use_tls:
                # Use cached SSL context for performance
                self._connection.starttls(context=_get_ssl_context())
                self._connection.ehlo()
            
            self._connection.login(self.sender_email, self.app_password)
        except smtplib.SMTPAuthenticationError as e:
            raise SMTPClientError(
                "Authentication failed. Verify your email and App Password. "
                "Ensure 2FA is enabled and you're using an App Password, not your regular password."
            ) from e
        except smtplib.SMTPException as e:
            raise SMTPClientError(f"SMTP connection error: {str(e)}") from e
        except Exception as e:
            raise SMTPClientError(f"Connection failed: {str(e)}") from e
    
    async def connect_async(self) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self.connect)
    
    def disconnect(self) -> None:
        if self._connection:
            try:
                self._connection.quit()
            except smtplib.SMTPException:
                pass
            finally:
                self._connection = None
    
    async def disconnect_async(self) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self.disconnect)
    
    def send(self, message: MIMEMultipart, recipients: list[str]) -> dict:
        """
        Send email to specified recipients with optimized message serialization.
        
        Args:
            message: Fully constructed MIME message
            recipients: All recipient addresses (To + CC + BCC)
        
        Returns:
            dict with 'success' bool and 'message' or 'errors' detail
        """
        if not self._connection:
            raise SMTPClientError("Not connected. Use context manager or call connect() first.")
        
        try:
            # Pre-serialize message for performance
            message_str = message.as_string()
            
            rejected = self._connection.sendmail(
                self.sender_email,
                recipients,
                message_str
            )
            
            if rejected:
                return {
                    "success": False,
                    "errors": rejected,
                    "message": f"Some recipients rejected: {list(rejected.keys())}"
                }
            
            return {
                "success": True,
                "message": f"Email sent successfully to {len(recipients)} recipient(s)"
            }
            
        except smtplib.SMTPRecipientsRefused as e:
            return {
                "success": False,
                "errors": e.recipients,
                "message": "All recipients were refused"
            }
        except smtplib.SMTPSenderRefused as e:
            raise SMTPClientError(f"Sender address refused: {e.smtp_error.decode()}") from e
        except smtplib.SMTPDataError as e:
            raise SMTPClientError(f"Message data error: {e.smtp_error.decode()}") from e
        except smtplib.SMTPException as e:
            raise SMTPClientError(f"Failed to send email: {str(e)}") from e
    
    async def send_async(self, message: MIMEMultipart, recipients: list[str]) -> dict:
        """Async send using thread pool for non-blocking operation."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self.send, message, recipients)
    
    def send_batch(self, message_builder_func, recipients_list: list[dict]) -> list[dict]:
        """
        Send batch emails to multiple recipient sets.
        
        Args:
            message_builder_func: Callable that takes recipient dict and returns (message, recipients)
            recipients_list: List of recipient dicts with 'to', 'cc', 'bcc' keys
        
        Returns:
            List of result dicts for each send attempt
        """
        results = []
        for recipient_data in recipients_list:
            try:
                message, all_recipients = message_builder_func(recipient_data)
                result = self.send(message, all_recipients)
                result["recipient_data"] = recipient_data
                results.append(result)
            except Exception as e:
                results.append({
                    "success": False,
                    "message": str(e),
                    "recipient_data": recipient_data
                })
        return results
    
    async def send_batch_async(self, message_builder_func, recipients_list: list[dict]) -> list[dict]:
        """
        Async batch send with concurrent execution.
        
        Args:
            message_builder_func: Callable that takes recipient dict and returns (message, recipients)
            recipients_list: List of recipient dicts
        
        Returns:
            List of result dicts for each send attempt
        """
        async def send_one(recipient_data: dict) -> dict:
            try:
                message, all_recipients = message_builder_func(recipient_data)
                result = await self.send_async(message, all_recipients)
                result["recipient_data"] = recipient_data
                return result
            except Exception as e:
                return {
                    "success": False,
                    "message": str(e),
                    "recipient_data": recipient_data
                }
        
        # Execute all sends concurrently
        tasks = [send_one(rd) for rd in recipients_list]
        return await asyncio.gather(*tasks)


class SMTPClientError(Exception):
    pass
