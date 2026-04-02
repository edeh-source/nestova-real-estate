from django.core.mail.backends.base import BaseEmailBackend
import resend
from django.conf import settings

class ResendBackend(BaseEmailBackend):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        resend.api_key = settings.RESEND_API_KEY

    def send_messages(self, email_messages):
        num_sent = 0
        for message in email_messages:
            try:
                # Check if HTML content exists in alternatives (for EmailMultiAlternatives)
                html_content = None
                if hasattr(message, 'alternatives') and message.alternatives:
                    for content, mimetype in message.alternatives:
                        if mimetype == 'text/html':
                            html_content = content
                            break
                
                # If no HTML in alternatives, check content_subtype
                if not html_content and hasattr(message, 'content_subtype'):
                    if message.content_subtype == 'html':
                        html_content = message.body
                
                # Build params
                params = {
                    "from": message.from_email,
                    "to": message.to,
                    "subject": message.subject,
                }
                
                # Add HTML or plain text
                if html_content:
                    params["html"] = html_content
                else:
                    params["text"] = message.body
                
                resend.Emails.send(params)
                num_sent += 1
            except Exception as e:
                if not self.fail_silently:
                    raise
        return num_sent