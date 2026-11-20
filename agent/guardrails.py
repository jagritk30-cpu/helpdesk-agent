"""
Guardrails for the HR/IT Helpdesk Agent.

Three layers:
1. Scope guard   — refuse questions unrelated to HR or IT.
2. Prompt injection detection — block attempts to override agent instructions.
3. PII redaction — scrub emails, phone numbers, Aadhaar numbers from outputs.
"""

import re
from dataclasses import dataclass

# ── Scope guard ───────────────────────────────────────────────────────────────

# Domain-specific keywords that must be present for a valid HR/IT question
_HR_IT_KEYWORDS = [
    # HR-specific
    "leave", "attendance", "payroll", "salary", "payslip", "pay slip",
    "increment", "appraisal", "performance review", "pip", "promotion",
    "probation", "notice period", "resignation", "offboarding", "onboarding",
    "reimbursement", "expense", "travel allowance", "travel policy",
    "insurance", "health benefit", "wellness", "gym reimbursement",
    "maternity", "paternity", "bereavement", "comp-off", "compensatory",
    "employee id", "employee number", "hire date", "joining date",
    "hr policy", "hr department", "human resources",
    # IT-specific
    "laptop", "computer", "device", "equipment", "asset",
    "password", "vpn", "wi-fi", "wifi", "corporate network",
    "software installation", "software request", "it access",
    "it ticket", "helpdesk ticket", "support ticket",
    "mfa", "2fa", "multi-factor", "authenticat",
    "slack", "jira", "confluence", "salesforce",
    "it support", "it department", "it helpdesk",
    "monitor", "keyboard", "phone", "printer", "scanner",
    "data security", "data breach", "phishing",
    # Compound HR/IT phrases
    "my leave", "leave balance", "leave days", "leave remaining",
    "annual leave", "sick leave", "casual leave",
    "work from home", "remote work", "flexi", "working hours",
    "pay slip", "salary credit", "salary structure",
    "my assets", "assigned laptop", "my device",
    "my ticket", "open ticket", "it issue",
]

_SCOPE_REJECTION = (
    "I'm your HR/IT Helpdesk assistant. I can only answer questions about "
    "HR policies (leave, payroll, benefits, onboarding) or IT support "
    "(devices, software, network, access). "
    "Your question appears to be outside that scope. "
    "Please contact the relevant team directly."
)

def is_in_scope(text: str) -> bool:
    """Return True if the query is likely HR/IT related."""
    low = text.lower()
    return any(kw in low for kw in _HR_IT_KEYWORDS)


# ── Prompt injection detection ────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    # Classic instruction overrides
    r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context)",
    r"disregard\s+(all\s+)?(previous|prior|your|the)\s+(instructions?|prompts?|rules?)",
    r"forget\s+(all\s+)?(previous|prior|your|the)\s+(instructions?|prompts?|rules?|context)",
    r"you\s+are\s+now\s+a",
    r"act\s+as\s+(if\s+you\s+(are|were)|a\s+different)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"new\s+system\s+prompt",
    r"override\s+(your\s+)?(instructions?|rules?|guidelines?|system)",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode",
    r"bypass\s+(your\s+)?(safety|filter|restriction|guardrail)",
    r"print\s+(your\s+)?(system\s+prompt|instructions?|context)",
    r"reveal\s+(your\s+)?(system\s+prompt|internal|hidden|secret)",
    r"what\s+are\s+your\s+(hidden\s+)?(instructions?|rules?|guidelines?)",
    r"repeat\s+the\s+(text|words|content|prompt)\s+above",
    r"output\s+(your\s+)?(system\s+prompt|instructions?)",
    r"translate\s+(your\s+)?(instructions?|system\s+prompt)",
    r"start\s+your\s+response\s+with",
    # Roleplay attacks
    r"play(ing)?\s+(the\s+role|a\s+role|pretend|act)",
    r"you\s+are\s+an?\s+(evil|unrestricted|uncensored|unfiltered)",
    # Token smuggling
    r"<\|?(system|user|assistant|im_start|im_end)\|?>",
    r"\[INST\]|\[/INST\]|<<SYS>>",
]

_COMPILED_INJECTION = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _INJECTION_PATTERNS]

_INJECTION_REJECTION = (
    "⚠️ I detected a prompt injection attempt in your message. "
    "I'm designed to help with HR and IT questions only, following my "
    "original instructions. Please ask a genuine HR/IT question."
)

def has_prompt_injection(text: str) -> bool:
    return any(p.search(text) for p in _COMPILED_INJECTION)


# ── PII redaction ─────────────────────────────────────────────────────────────

_PII_PATTERNS = [
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "[EMAIL REDACTED]"),
    # Indian phone numbers (10-digit, with or without +91 / 0 prefix)
    (re.compile(r"(?<!\d)(\+?91[\s\-]?)?[6-9]\d{9}(?!\d)"), "[PHONE REDACTED]"),
    # Aadhaar numbers (12 digits, possibly space-separated in groups)
    (re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"), "[AADHAAR REDACTED]"),
    # PAN card (Indian)
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "[PAN REDACTED]"),
    # Credit/debit card numbers (basic Luhn-pattern)
    (re.compile(r"\b(?:\d[\s\-]?){13,16}\b"), "[CARD REDACTED]"),
]


def redact_pii(text: str) -> str:
    """Remove PII from agent outputs."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ── Combined check ────────────────────────────────────────────────────────────

@dataclass
class GuardrailResult:
    blocked: bool
    reason: str | None   # 'injection' | 'out_of_scope' | None
    message: str | None  # rejection message to return to user


def check_input(user_message: str) -> GuardrailResult:
    """
    Run all input guardrails. Returns a GuardrailResult.
    If blocked=True, return result.message to the user and do not call the LLM.
    """
    if has_prompt_injection(user_message):
        return GuardrailResult(blocked=True, reason="injection", message=_INJECTION_REJECTION)
    if not is_in_scope(user_message):
        return GuardrailResult(blocked=True, reason="out_of_scope", message=_SCOPE_REJECTION)
    return GuardrailResult(blocked=False, reason=None, message=None)


def sanitize_output(agent_response: str) -> str:
    """Redact any PII that may have slipped into agent output."""
    return redact_pii(agent_response)
