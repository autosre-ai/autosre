"""Email Integration for AutoSRE V2 Notifications.

Provides email notifications with:
- HTML templates
- SMTP/API delivery
- Template management
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, SecretStr

from autosre.notifications.notification_router import (
    ChannelConfig,
    DeliveryResult,
    Notification,
    NotificationChannel,
    NotificationHandler,
    NotificationPriority,
    NotificationStatus,
)
from autosre.utils.logging import get_logger

logger = get_logger(__name__)


class EmailTemplate(BaseModel):
    """An email template."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    subject_template: str
    html_template: str
    text_template: Optional[str] = None
    
    # Variables available in template
    variables: List[str] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def render(self, context: Dict[str, Any]) -> tuple[str, str, Optional[str]]:
        """Render template with context.
        
        Args:
            context: Template variables
            
        Returns:
            Tuple of (subject, html_body, text_body)
        """
        subject = self.subject_template
        html_body = self.html_template
        text_body = self.text_template
        
        # Simple template substitution
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            subject = subject.replace(placeholder, str(value))
            html_body = html_body.replace(placeholder, str(value))
            if text_body:
                text_body = text_body.replace(placeholder, str(value))
        
        return subject, html_body, text_body


# Default alert template
DEFAULT_ALERT_TEMPLATE = EmailTemplate(
    id="default-alert",
    name="Default Alert",
    subject_template="[{{priority}}] {{title}}",
    html_template="""
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; }
        .header { background: {{header_color}}; color: white; padding: 20px; }
        .header h1 { margin: 0; font-size: 20px; }
        .content { padding: 20px; }
        .details { background: #f9f9f9; padding: 15px; border-radius: 4px; margin: 15px 0; }
        .details dt { font-weight: bold; color: #666; }
        .details dd { margin: 5px 0 15px 0; }
        .button { display: inline-block; background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; }
        .footer { padding: 15px 20px; background: #f5f5f5; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{title}}</h1>
        </div>
        <div class="content">
            <p>{{message}}</p>
            
            <div class="details">
                <dl>
                    <dt>Priority</dt>
                    <dd>{{priority}}</dd>
                    <dt>Type</dt>
                    <dd>{{type}}</dd>
                    <dt>Source</dt>
                    <dd>{{source}}</dd>
                    <dt>Time</dt>
                    <dd>{{timestamp}}</dd>
                </dl>
            </div>
            
            {{#if source_url}}
            <p><a href="{{source_url}}" class="button">View Details</a></p>
            {{/if}}
        </div>
        <div class="footer">
            <p>This notification was sent by AutoSRE. ID: {{notification_id}}</p>
        </div>
    </div>
</body>
</html>
    """,
    text_template="""
{{title}}
================

{{message}}

Priority: {{priority}}
Type: {{type}}
Source: {{source}}
Time: {{timestamp}}

{{#if source_url}}
View Details: {{source_url}}
{{/if}}

---
This notification was sent by AutoSRE. ID: {{notification_id}}
    """,
    variables=["title", "message", "priority", "type", "source", "timestamp", "source_url", "notification_id", "header_color"],
)


class EmailMessage(BaseModel):
    """An email message."""
    
    to: List[str]
    cc: List[str] = Field(default_factory=list)
    bcc: List[str] = Field(default_factory=list)
    subject: str
    html_body: str
    text_body: Optional[str] = None
    
    # Optional sender override
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    
    # Headers
    headers: Dict[str, str] = Field(default_factory=dict)
    
    @classmethod
    def from_notification(
        cls,
        notification: Notification,
        recipients: List[str],
        template: Optional[EmailTemplate] = None,
    ) -> "EmailMessage":
        """Create EmailMessage from a Notification."""
        template = template or DEFAULT_ALERT_TEMPLATE
        
        # Map priority to color
        color_map = {
            NotificationPriority.CRITICAL: "#dc3545",
            NotificationPriority.URGENT: "#fd7e14",
            NotificationPriority.HIGH: "#ffc107",
            NotificationPriority.NORMAL: "#007bff",
            NotificationPriority.LOW: "#6c757d",
        }
        
        context = {
            "title": notification.title,
            "message": notification.message,
            "priority": notification.priority.value.upper(),
            "type": notification.notification_type.value.replace("_", " ").title(),
            "source": notification.source,
            "timestamp": notification.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "source_url": notification.source_url or "",
            "notification_id": notification.id,
            "header_color": color_map.get(notification.priority, "#007bff"),
            **notification.details,
        }
        
        subject, html_body, text_body = template.render(context)
        
        return cls(
            to=recipients,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            headers={
                "X-AutoSRE-Notification-ID": notification.id,
                "X-AutoSRE-Priority": notification.priority.value,
            },
        )


class EmailConfig(BaseModel):
    """Email-specific configuration."""
    
    # SMTP settings
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[SecretStr] = None
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    
    # API settings (alternative to SMTP)
    api_provider: Optional[str] = None  # sendgrid, mailgun, ses
    api_key: Optional[SecretStr] = None
    
    # Sender settings
    from_email: str = "noreply@autosre.local"
    from_name: str = "AutoSRE"
    reply_to: Optional[str] = None
    
    # Default recipients
    default_recipients: List[str] = Field(default_factory=list)
    
    # Templates
    template_id: Optional[str] = None


class EmailSender(NotificationHandler):
    """
    Email notification handler.
    
    Supports:
    - SMTP delivery
    - HTML templates
    - Multiple recipients
    
    Example:
        email = EmailSender()
        
        config = ChannelConfig(
            tenant_id="tenant-123",
            channel=NotificationChannel.EMAIL,
            name="Email",
            config={
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_user": "user",
                "smtp_password": "pass",
                "from_email": "alerts@example.com",
                "default_recipients": ["oncall@example.com"],
            },
        )
        
        result = await email.send(notification, config)
    """
    
    def __init__(self):
        self._templates: Dict[str, EmailTemplate] = {
            "default-alert": DEFAULT_ALERT_TEMPLATE,
        }
    
    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.EMAIL
    
    def register_template(self, template: EmailTemplate) -> None:
        """Register an email template."""
        self._templates[template.id] = template
    
    async def send(
        self,
        notification: Notification,
        config: ChannelConfig,
    ) -> DeliveryResult:
        """Send notification via email."""
        email_config = EmailConfig(**config.config)
        
        # Determine recipients
        recipients = notification.recipients or email_config.default_recipients
        if not recipients:
            return DeliveryResult(
                notification_id=notification.id,
                channel=NotificationChannel.EMAIL,
                success=False,
                status=NotificationStatus.FAILED,
                error_code="no_recipients",
                error_message="No email recipients configured",
            )
        
        # Get template
        template = None
        if email_config.template_id:
            template = self._templates.get(email_config.template_id)
        
        # Build message
        message = EmailMessage.from_notification(notification, recipients, template)
        message.from_email = email_config.from_email
        message.from_name = email_config.from_name
        message.reply_to = email_config.reply_to
        
        try:
            # Send via SMTP
            await self._send_smtp(message, email_config)
            
            return DeliveryResult(
                notification_id=notification.id,
                channel=NotificationChannel.EMAIL,
                recipient=", ".join(recipients),
                success=True,
                status=NotificationStatus.DELIVERED,
                delivered_at=datetime.now(timezone.utc),
            )
            
        except Exception as e:
            logger.error(
                "Email send failed",
                notification_id=notification.id,
                error=str(e),
            )
            
            return DeliveryResult(
                notification_id=notification.id,
                channel=NotificationChannel.EMAIL,
                success=False,
                status=NotificationStatus.FAILED,
                error_code="exception",
                error_message=str(e),
            )
    
    async def _send_smtp(
        self,
        message: EmailMessage,
        config: EmailConfig,
    ) -> None:
        """Send email via SMTP."""
        import smtplib
        
        # Build MIME message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = message.subject
        msg["From"] = f"{config.from_name} <{config.from_email}>"
        msg["To"] = ", ".join(message.to)
        
        if message.cc:
            msg["Cc"] = ", ".join(message.cc)
        if message.reply_to or config.reply_to:
            msg["Reply-To"] = message.reply_to or config.reply_to
        
        for key, value in message.headers.items():
            msg[key] = value
        
        # Add body parts
        if message.text_body:
            msg.attach(MIMEText(message.text_body, "plain"))
        msg.attach(MIMEText(message.html_body, "html"))
        
        # All recipients
        all_recipients = message.to + message.cc + message.bcc
        
        # Send in thread pool (SMTP is blocking)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._smtp_send_sync,
            msg,
            all_recipients,
            config,
        )
    
    def _smtp_send_sync(
        self,
        msg: MIMEMultipart,
        recipients: List[str],
        config: EmailConfig,
    ) -> None:
        """Synchronous SMTP send (for thread pool)."""
        import smtplib
        
        if config.smtp_use_ssl:
            smtp = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port)
        else:
            smtp = smtplib.SMTP(config.smtp_host, config.smtp_port)
            if config.smtp_use_tls:
                smtp.starttls()
        
        try:
            if config.smtp_user and config.smtp_password:
                smtp.login(config.smtp_user, config.smtp_password.get_secret_value())
            
            smtp.sendmail(config.from_email, recipients, msg.as_string())
        finally:
            smtp.quit()
    
    async def health_check(self, config: ChannelConfig) -> bool:
        """Check SMTP connectivity."""
        email_config = EmailConfig(**config.config)
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._smtp_check_sync,
                email_config,
            )
            return True
        except Exception:
            return False
    
    def _smtp_check_sync(self, config: EmailConfig) -> None:
        """Synchronous SMTP check."""
        import smtplib
        
        if config.smtp_use_ssl:
            smtp = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=5)
        else:
            smtp = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=5)
        
        try:
            smtp.noop()
        finally:
            smtp.quit()
