"""
Override classifier for catching Work emails misclassified into Other categories.

This module runs AFTER the deterministic classifier and checks if emails
classified into Categories 6-11 (Other) should actually be in the Work pipeline
based on urgency, sender importance, or personal direction.
"""

import re
import json
import logging
from typing import Dict, Optional, List
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ============================================================================
# VIP CONFIGURATION - Customize these lists
# ============================================================================

# VIP_SENDERS: Add email addresses of important contacts
# Examples: your boss, direct reports, key clients, executive team
VIP_SENDERS = [
    # "boss@company.com",
    # "ceo@company.com",
    # "important.client@client.com",
]

# VIP_DOMAINS: Add domains where all senders are important
# Examples: executive team domain, key client companies
VIP_DOMAINS = [
    # "executive.company.com",
    # "keyclient.com",
]

# USER_CONFIG: Hardcoded for now, will be made dynamic later
USER_EMAIL = "user@company.com"  # Replace with actual user email
USER_FIRST_NAME = "User"  # Replace with actual user first name


# ============================================================================
# URGENCY PATTERNS
# ============================================================================

URGENCY_KEYWORDS = [
    "urgent",
    "asap",
    "time-sensitive",
    "time sensitive",
    "immediate attention",
    "action required",
    "critical",
    "deadline today",
    "due today",
    "due immediately",
    "needs your approval",
    "please respond by",
    "respond asap",
    "priority",
    "high priority",
    "blocker",
    "blocking",
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_domain(email_address: str) -> str:
    """Extract domain from email address."""
    if not email_address:
        return ""
    match = re.search(r"@([\w\.-]+)$", email_address.lower())
    return match.group(1) if match else ""


def parse_recipients(recipients_json: str) -> List[Dict[str, str]]:
    """Parse JSON string of recipients into list of dicts."""
    if not recipients_json:
        return []
    try:
        return json.loads(recipients_json)
    except (json.JSONDecodeError, TypeError):
        return []


def is_sole_to_recipient(to_recipients: List[Dict[str, str]], user_email: str) -> bool:
    """Check if user is the sole To: recipient."""
    if not to_recipients:
        return False
    if len(to_recipients) != 1:
        return False
    return to_recipients[0].get("address", "").lower() == user_email.lower()


def contains_urgency_language(text: str) -> Optional[str]:
    """
    Check if text contains urgency keywords.

    Returns the matched keyword if found, None otherwise.
    """
    if not text:
        return None
    text_lower = text.lower()
    for keyword in URGENCY_KEYWORDS:
        if keyword in text_lower:
            return keyword
    return None


def is_vip_sender(from_address: str) -> bool:
    """Check if sender is in VIP list or VIP domain."""
    if not from_address:
        return False

    from_address_lower = from_address.lower()

    # Check VIP senders list
    for vip in VIP_SENDERS:
        if vip.lower() == from_address_lower:
            return True

    # Check VIP domains
    domain = extract_domain(from_address)
    for vip_domain in VIP_DOMAINS:
        if vip_domain.lower() == domain:
            return True

    return False


def has_direct_address(body: str, first_name: str) -> Optional[str]:
    """
    Check if email body contains direct address to the user.

    Looks for patterns like:
    - "Mo, can you..."
    - "Hi Mo, please..."
    - "Mo - could you..."

    Returns the matched pattern if found, None otherwise.
    """
    if not body or not first_name:
        return None

    # Patterns that indicate direct address
    patterns = [
        rf"\b{re.escape(first_name)},\s+(can|could|would|will|please)",
        rf"hi\s+{re.escape(first_name)},",
        rf"hello\s+{re.escape(first_name)},",
        rf"hey\s+{re.escape(first_name)},",
        rf"{re.escape(first_name)}\s*[-:]\s*(can|could|would|will|please)",
        rf"@{re.escape(first_name)}\b",  # @ mentions
    ]

    for pattern in patterns:
        match = re.search(pattern, body, re.IGNORECASE)
        if match:
            return match.group(0)

    return None


def check_reply_chain_participation(conversation_id: str, user_email: str, db: Session) -> bool:
    """
    Check if user previously participated in this conversation thread.

    Looks for any email in the same conversation where the user was the sender.
    """
    if not conversation_id or not user_email or not db:
        return False

    # Import here to avoid circular imports
    from ..models import Email

    # Check if there's any email in this conversation sent by the user
    user_sent = db.query(Email).filter(
        Email.conversation_id == conversation_id,
        Email.from_address == user_email
    ).first()

    return user_sent is not None


# ============================================================================
# OVERRIDE CHECKS
# ============================================================================

def check_urgency_override(email: Dict) -> Optional[Dict]:
    """
    Trigger 1: Urgency Language

    Check if body or subject contains urgent keywords.
    """
    subject = email.get("subject", "")
    body = email.get("body", "")

    text = f"{subject} {body}"
    matched_keyword = contains_urgency_language(text)

    if matched_keyword:
        return {
            "override": True,
            "reason": f"Contains urgency language: '{matched_keyword}'",
            "trigger": "urgency_language"
        }

    return None


def check_vip_override(email: Dict) -> Optional[Dict]:
    """
    Trigger 2: VIP Sender

    Check if sender is in VIP list or domain.
    """
    from_address = email.get("from_address", "")

    if is_vip_sender(from_address):
        return {
            "override": True,
            "reason": f"Email from VIP sender: {from_address}",
            "trigger": "vip_sender"
        }

    return None


def check_sole_recipient_override(email: Dict, current_category: int, user_email: str) -> Optional[Dict]:
    """
    Trigger 3: Sole Recipient + FYI Mismatch

    If user is sole To: recipient AND classified as FYI (category 9),
    this is likely directed work, not FYI.
    """
    # Only check if current category is FYI (9)
    if current_category != 9:
        return None

    to_recipients = parse_recipients(email.get("to_recipients", ""))

    if is_sole_to_recipient(to_recipients, user_email):
        return {
            "override": True,
            "reason": "Sole To: recipient but classified as FYI - likely needs action",
            "trigger": "sole_recipient_mismatch"
        }

    return None


def check_reply_chain_override(email: Dict, user_email: str, db: Session) -> Optional[Dict]:
    """
    Trigger 4: Reply Chain Participation

    If user previously sent in this conversation thread, new messages need attention.
    """
    conversation_id = email.get("conversation_id", "")

    if check_reply_chain_participation(conversation_id, user_email, db):
        return {
            "override": True,
            "reason": "User previously participated in this conversation thread",
            "trigger": "reply_chain_participation"
        }

    return None


def check_direct_address_override(email: Dict, first_name: str) -> Optional[Dict]:
    """
    Trigger 5: Direct Address

    Email body contains user's first name in context of question/request.
    """
    body = email.get("body", "")

    matched_pattern = has_direct_address(body, first_name)

    if matched_pattern:
        return {
            "override": True,
            "reason": f"Email directly addresses user: '{matched_pattern}'",
            "trigger": "direct_address"
        }

    return None


# ============================================================================
# MAIN OVERRIDE CHECKER
# ============================================================================

def check_override(
    email: Dict,
    current_category: int,
    user_email: str = USER_EMAIL,
    first_name: str = USER_FIRST_NAME,
    db: Session = None
) -> Dict:
    """
    Check if an email in Categories 6-11 should be overridden to Work pipeline.

    Args:
        email: Email dictionary with fields:
            - message_id, from_address, subject, body
            - to_recipients (JSON string), cc_recipients (JSON string)
            - conversation_id
        current_category: Current category ID (6-11)
        user_email: User's email address for recipient checking
        first_name: User's first name for direct address detection
        db: Database session for reply chain checking

    Returns:
        Dictionary with:
        - override: True if email should be overridden, False otherwise
        - reason: Human-readable explanation (if override=True)
        - trigger: Trigger type that caused override (if override=True)

    Override triggers (if ANY match, override to Work):
    1. Urgency Language
    2. VIP Sender
    3. Sole Recipient + FYI Mismatch
    4. Reply Chain Participation
    5. Direct Address
    """
    # Only check emails in categories 6-11 (Other categories)
    if current_category not in [6, 7, 8, 9, 11]:
        return {"override": False}

    from_address = email.get("from_address", "")
    subject = email.get("subject", "")

    logger.debug(f"Checking override for: {from_address} - {subject} (Category {current_category})")

    # Check all triggers in order

    # 1. Urgency Language (highest priority)
    result = check_urgency_override(email)
    if result:
        logger.info(f"Override triggered: {result['trigger']} - {result['reason']}")
        return result

    # 2. VIP Sender
    result = check_vip_override(email)
    if result:
        logger.info(f"Override triggered: {result['trigger']} - {result['reason']}")
        return result

    # 3. Sole Recipient + FYI Mismatch
    result = check_sole_recipient_override(email, current_category, user_email)
    if result:
        logger.info(f"Override triggered: {result['trigger']} - {result['reason']}")
        return result

    # 4. Reply Chain Participation
    if db:
        result = check_reply_chain_override(email, user_email, db)
        if result:
            logger.info(f"Override triggered: {result['trigger']} - {result['reason']}")
            return result

    # 5. Direct Address
    result = check_direct_address_override(email, first_name)
    if result:
        logger.info(f"Override triggered: {result['trigger']} - {result['reason']}")
        return result

    # No override needed
    logger.debug(f"No override needed for: {from_address} - {subject}")
    return {"override": False}


# ============================================================================
# CONFIGURATION HELPERS
# ============================================================================

def add_vip_sender(email_address: str):
    """Add an email address to the VIP senders list."""
    if email_address and email_address not in VIP_SENDERS:
        VIP_SENDERS.append(email_address.lower())
        logger.info(f"Added VIP sender: {email_address}")


def add_vip_domain(domain: str):
    """Add a domain to the VIP domains list."""
    if domain and domain not in VIP_DOMAINS:
        VIP_DOMAINS.append(domain.lower())
        logger.info(f"Added VIP domain: {domain}")


def get_vip_config() -> Dict:
    """Get current VIP configuration."""
    return {
        "vip_senders": VIP_SENDERS.copy(),
        "vip_domains": VIP_DOMAINS.copy()
    }
