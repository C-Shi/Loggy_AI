import re
import json

class LogRedactor:
    def __init__(self):
        # 1. JWT: Header.Payload.Signature (Base64 character sets)
        self.jwt_pattern = re.compile(r'\beyJhbGciOi[-_a-zA-Z0-9\.]+\.[-_a-zA-Z0-9\.]+\.[-_a-zA-Z0-9\._~]*\b')
        
        # 2. Generic API Key / Secret Detection (Matches common hex/base64/bearer string patterns)
        self.api_key_pattern = re.compile(r'(?i)(api[_-]?key|secret|password|bearer|auth|token)["\s]*[:=]["\s]*[a-zA-Z0-9_\-\.\~]{16,64}')
        
        # 3. Standard RFC 5322 Email
        self.email_pattern = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')
        
        # 4. Luhn-like Credit Card Sequences (13 to 16 digit lengths)
        self.credit_card_pattern = re.compile(r'\b(?:\d[ -]*?){13,16}\b')     

    def redact(self, text: str) -> str:
        """Applies destructive placeholder mask to known sensitive patterns."""
        if not text:
            return text
        text = self.jwt_pattern.sub('[REDACTED_JWT]', text)
        text = self.api_key_pattern.sub('[REDACTED_API_KEY]', text)
        text = self.email_pattern.sub('[REDACTED_EMAIL]', text)
        text = self.credit_card_pattern.sub('[REDACTED_CREDIT_CARD]', text)
        return text