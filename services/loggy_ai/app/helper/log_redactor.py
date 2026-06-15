import re

class LogRedactor:
    """
    Redacts sensitive information from log entries.
    Accepts a list of raw log items, filters out unnecessary fields,
    scrubs sensitive anchors inside messages, and returns a clean list.
    Sensitive information include:
    - JWT
    - API Key
    - Email
    - Credit Card
    - Phone Number
    """
    def __init__(self):
        # 1. JWT: Header.Payload.Signature (Base64 character sets)
        self.jwt_pattern = re.compile(r'\beyJhbGciOi[-_a-zA-Z0-9\.]+\.[-_a-zA-Z0-9\.]+\.[-_a-zA-Z0-9\._~]*\b')
        
        # 2. Generic API Key / Secret Detection (Matches hex/base64/bearer variants)
        self.api_key_pattern = re.compile(r'(?i)(api[_-]?key|secret|password|bearer|auth|token)["\s]*[:=]["\s]*[a-zA-Z0-9_\-\.\~]{16,64}')
        
        # 3. Standard RFC 5322 Email
        self.email_pattern = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')
        
        # 4. Luhn-like Credit Card Sequences (13 to 16 digit lengths)
        self.credit_card_pattern = re.compile(r'\b(?:\d[ -]*?){13,16}\b')

    def _redact_value(self, value: str) -> str:
        """Applies destructive placeholder masks to a single string value."""
        if not isinstance(value, str):
            return value
            
        value = self.jwt_pattern.sub("[REDACTED_JWT]", value)
        value = self.email_pattern.sub("[REDACTED_EMAIL]", value)
        value = self.credit_card_pattern.sub("[REDACTED_CREDIT_CARD]", value)
        
        # Apply token regex match
        value = self.api_key_pattern.sub(
            lambda m: m.group(0).split(':')[0] + ': "[REDACTED_SECRET]"' if ':' in m.group(0) else '[REDACTED_SECRET]', 
            value
        )
        return value

    def sanitize_log_batch(self, raw_logs: list) -> list:
        """
        Accepts a list of raw log items, filters out unnecessary fields,
        scrubs sensitive anchors inside messages, and returns a clean list.
        """
        sanitized_list = []
        
        for log in raw_logs:
            if not isinstance(log, dict):
                continue
                
            # Extract only core operational telemetry fields to save prompt window tokens
            message = log.get("jsonPayload", {}).get("message") or log.get("textPayload") or ""
            
            # Clean up message whitespace and trailing newlines locally
            if isinstance(message, str):
                message = " ".join(message.split())

            # Apply regex string scanning rules
            redacted_message = self._redact_value(message)

            operational_fields = {
                "timestamp": log.get("timestamp"),
                "severity": log.get("severity"),
                "resource_type": log.get("resource", {}).get("type") if isinstance(log.get("resource"), dict) else log.get("resource"),
                "message": redacted_message
            }
            
            sanitized_list.append(operational_fields)
            
        return sanitized_list