"""
Deterministic email classifier using header-based and sender-based rules.

This module classifies emails into categories 6-11 based on deterministic rules
before falling back to AI classification for ambiguous cases.
"""

import re
import json
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


# ============================================================================
# SENDER REGISTRIES - Easy editing of known senders
# ============================================================================

MARKETING_DOMAINS = {
    "mailchimp.com",
    "sendgrid.net",
    "constantcontact.com",
    "hubspot.com",
    "marketo.com",
    "campaign-monitor.com",
    "mailgun.org",
    "postmarkapp.com",
    "amazonses.com",
}

NOTIFICATION_DOMAINS = {
    "microsoft.com",
    "google.com",
    "apple.com",
    "github.com",
    "slack.com",
    "atlassian.com",  # Jira
    "servicenow.com",
    "workday.com",
    "asana.com",
    "trello.com",
    "notion.so",
    "figma.com",
    "dropbox.com",
    "box.com",
    "zoom.us",
}

CALENDAR_SENDERS = {
    "calendar-notification@google.com",
    "calendar@microsoft.com",
    "noreply@calendar.microsoft.com",
    "teams@microsoft.com",
}

TRAVEL_DOMAINS = {
    # Airlines
    "delta.com",
    "united.com",
    "aa.com",  # American Airlines
    "southwest.com",
    "jetblue.com",
    "alaskaair.com",
    "spiritairlines.com",
    "frontier.com",
    # Hotels
    "marriott.com",
    "hilton.com",
    "ihg.com",
    "hyatt.com",
    "choicehotels.com",
    "wyndham.com",
    # Rental cars
    "hertz.com",
    "enterprise.com",
    "avis.com",
    "budget.com",
    "nationalcar.com",
    # Rideshare
    "uber.com",
    "lyft.com",
    # Booking platforms
    "expedia.com",
    "booking.com",
    "hotels.com",
    "kayak.com",
    "tripadvisor.com",
    "airbnb.com",
    "vrbo.com",
    "priceline.com",
}


# ============================================================================
# PATTERN MATCHERS
# ============================================================================

MARKETING_SENDER_PATTERNS = [
    r"^noreply@",
    r"^no-reply@",
    r"^marketing@",
    r"^newsletter@",
    r"^promotions@",
    r"^deals@",
    r"^offers@",
]

NOTIFICATION_SENDER_PATTERNS = [
    r"^noreply@",
    r"^no-reply@",
    r"^notifications@",
    r"^alerts@",
    r"^donotreply@",
    r"^mailer-daemon@",
    r"^no_reply@",
]

MARKETING_SUBJECT_KEYWORDS = [
    "unsubscribe",
    "% off",
    "percent off",
    "limited time",
    "sale",
    "deal",
    "promo code",
    "free shipping",
    "discount",
    "save now",
    "special offer",
]

NOTIFICATION_SUBJECT_PATTERNS = [
    r"your order",
    r"shipping update",
    r"password reset",
    r"security alert",
    r"verification code",
    r"new sign-in",
    r"account activity",
    r"confirm your email",
    r"reset your password",
]

CALENDAR_SUBJECT_PATTERNS = [
    r"^invitation:",
    r"^updated invitation:",
    r"^canceled:",
    r"^accepted:",
    r"^declined:",
    r"^tentative:",
    r"meeting invitation",
    r"event invitation",
]

TRAVEL_SUBJECT_KEYWORDS = [
    "booking confirmation",
    "itinerary",
    "flight confirmation",
    "check-in",
    "reservation",
    "trip summary",
    "boarding pass",
    "e-ticket",
    "hotel confirmation",
]

URGENCY_KEYWORDS = [
    "urgent",
    "asap",
    "important",
    "critical",
    "deadline",
    "action required",
    "immediate",
    "time sensitive",
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


def contains_pattern(text: str, patterns: List[str]) -> Optional[str]:
    """Check if text contains any of the regex patterns."""
    if not text:
        return None
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return pattern
    return None


def contains_keyword(text: str, keywords: List[str]) -> Optional[str]:
    """Check if text contains any of the keywords."""
    if not text:
        return None
    text_lower = text.lower()
    for keyword in keywords:
        if keyword.lower() in text_lower:
            return keyword
    return None


def parse_recipients(recipients_json: str) -> List[Dict[str, str]]:
    """Parse JSON string of recipients into list of dicts."""
    if not recipients_json:
        return []
    try:
        return json.loads(recipients_json)
    except (json.JSONDecodeError, TypeError):
        return []


def is_sole_recipient(to_recipients: List[Dict[str, str]], user_email: str) -> bool:
    """Check if user is the sole To: recipient."""
    if not to_recipients:
        return False
    return len(to_recipients) == 1 and to_recipients[0].get("address", "").lower() == user_email.lower()


def user_in_cc_only(to_recipients: List[Dict[str, str]], cc_recipients: List[Dict[str, str]], user_email: str) -> bool:
    """Check if user is only in CC field, not in To field."""
    user_email_lower = user_email.lower()

    # Check if user is in To: field
    for recipient in to_recipients:
        if recipient.get("address", "").lower() == user_email_lower:
            return False

    # Check if user is in CC: field
    for recipient in cc_recipients:
        if recipient.get("address", "").lower() == user_email_lower:
            return True

    return False


def has_urgency_language(subject: str, body: str) -> bool:
    """Check if email contains urgency language."""
    text = f"{subject or ''} {body or ''}"
    return contains_keyword(text, URGENCY_KEYWORDS) is not None


# ============================================================================
# CATEGORY CLASSIFIERS
# ============================================================================

def check_calendar(email: Dict) -> Optional[Dict]:
    """
    Category 8 — Calendar invites

    Rules:
    1. Email has text/calendar MIME type or .ics attachment
    2. Subject contains calendar patterns
    3. Sender is a calendar system
    """
    subject = email.get("subject", "")
    from_address = email.get("from_address", "")
    body = email.get("body", "")

    # Check for .ics attachment in body (Graph API embeds calendar data)
    if "text/calendar" in body.lower() or ".ics" in body.lower():
        return {
            "category_id": 8,
            "rule": "Calendar MIME type or .ics attachment detected",
            "confidence": 0.95
        }

    # Check for calendar subject patterns
    matched_pattern = contains_pattern(subject, CALENDAR_SUBJECT_PATTERNS)
    if matched_pattern:
        return {
            "category_id": 8,
            "rule": f"Calendar subject pattern: {matched_pattern}",
            "confidence": 0.90
        }

    # Check for calendar system senders
    if from_address.lower() in CALENDAR_SENDERS:
        return {
            "category_id": 8,
            "rule": f"Calendar system sender: {from_address}",
            "confidence": 0.90
        }

    return None


def check_marketing(email: Dict) -> Optional[Dict]:
    """
    Category 6 — Marketing

    Rules:
    1. Check for List-Unsubscribe header
    2. Sender address matches marketing patterns
    3. Sender domain is a known marketing platform
    4. Subject contains promotional language

    Note: Excludes travel and notification domains to avoid misclassification
    """
    from_address = email.get("from_address", "")
    subject = email.get("subject", "")
    domain = extract_domain(from_address)

    # Skip if this is a travel or notification domain (checked later)
    if domain in TRAVEL_DOMAINS or domain in NOTIFICATION_DOMAINS:
        return None

    # Check for List-Unsubscribe header (if headers are available)
    headers = email.get("headers", {})
    if headers and "list-unsubscribe" in str(headers).lower():
        return {
            "category_id": 6,
            "rule": "List-Unsubscribe header present",
            "confidence": 0.95
        }

    # Check sender patterns
    matched_pattern = contains_pattern(from_address, MARKETING_SENDER_PATTERNS)
    if matched_pattern:
        # But make sure it's not a notification (noreply is common for both)
        if not contains_keyword(subject, NOTIFICATION_SUBJECT_PATTERNS):
            return {
                "category_id": 6,
                "rule": f"Marketing sender pattern: {matched_pattern}",
                "confidence": 0.85
            }

    # Check for known marketing domains
    if domain in MARKETING_DOMAINS:
        return {
            "category_id": 6,
            "rule": f"Marketing platform domain: {domain}",
            "confidence": 0.90
        }

    # Check subject for promotional language
    matched_keyword = contains_keyword(subject, MARKETING_SUBJECT_KEYWORDS)
    if matched_keyword:
        return {
            "category_id": 6,
            "rule": f"Marketing keyword in subject: {matched_keyword}",
            "confidence": 0.85
        }

    return None


def check_travel(email: Dict) -> Optional[Dict]:
    """
    Category 11 — Travel

    Rules:
    1. Known travel senders (airlines, hotels, rental cars, rideshare, booking platforms)
    2. Subject contains booking/travel patterns
    """
    from_address = email.get("from_address", "")
    subject = email.get("subject", "")
    domain = extract_domain(from_address)

    # Check for known travel domains
    if domain in TRAVEL_DOMAINS:
        return {
            "category_id": 11,
            "rule": f"Travel domain: {domain}",
            "confidence": 0.90
        }

    # Check subject for travel keywords
    matched_keyword = contains_keyword(subject, TRAVEL_SUBJECT_KEYWORDS)
    if matched_keyword:
        return {
            "category_id": 11,
            "rule": f"Travel keyword in subject: {matched_keyword}",
            "confidence": 0.85
        }

    return None


def check_notification(email: Dict, user_email: str) -> Optional[Dict]:
    """
    Category 7 — Notification

    Rules:
    1. Sender address matches notification patterns
    2. Known notification senders
    3. Subject contains notification patterns
    4. Exclude if user is sole recipient and body contains urgency language
    """
    from_address = email.get("from_address", "")
    subject = email.get("subject", "")
    body = email.get("body", "")
    to_recipients = parse_recipients(email.get("to_recipients", ""))
    domain = extract_domain(from_address)

    # Check for notification sender patterns
    matched_pattern = contains_pattern(from_address, NOTIFICATION_SENDER_PATTERNS)
    if matched_pattern:
        # Check exclusion: sole recipient + urgency language
        if is_sole_recipient(to_recipients, user_email) and has_urgency_language(subject, body):
            logger.debug(f"Email from {from_address} has urgency language for sole recipient, not classifying as notification")
            return None

        return {
            "category_id": 7,
            "rule": f"Notification sender pattern: {matched_pattern}",
            "confidence": 0.85
        }

    # Check for known notification domains
    if domain in NOTIFICATION_DOMAINS:
        # Check exclusion
        if is_sole_recipient(to_recipients, user_email) and has_urgency_language(subject, body):
            logger.debug(f"Email from {domain} has urgency language for sole recipient, not classifying as notification")
            return None

        return {
            "category_id": 7,
            "rule": f"Notification domain: {domain}",
            "confidence": 0.88
        }

    # Check for notification subject patterns
    matched_pattern = contains_pattern(subject, NOTIFICATION_SUBJECT_PATTERNS)
    if matched_pattern:
        return {
            "category_id": 7,
            "rule": f"Notification subject pattern: {matched_pattern}",
            "confidence": 0.85
        }

    return None


def check_fyi(email: Dict, user_email: str) -> Optional[Dict]:
    """
    Category 9 — FYI

    Rules:
    1. User is in CC field only (not in To:)
    2. The To: field has 3+ recipients (group email)
    3. Do NOT classify as FYI if:
       - Email mentions user by name in body
       - Subject contains urgency language
    """
    subject = email.get("subject", "")
    body = email.get("body", "")
    to_recipients = parse_recipients(email.get("to_recipients", ""))
    cc_recipients = parse_recipients(email.get("cc_recipients", ""))
    from_name = email.get("from_name", "")

    # Rule 1: User in CC only
    if user_in_cc_only(to_recipients, cc_recipients, user_email):
        # Check exclusions
        if has_urgency_language(subject, body):
            logger.debug(f"Email in CC has urgency language, not classifying as FYI")
            return None

        # TODO: Check if email mentions user by name (need user's name)
        # For now, we'll skip this check

        return {
            "category_id": 9,
            "rule": "User in CC field only",
            "confidence": 0.88
        }

    # Rule 2: 3+ recipients in To: field
    if len(to_recipients) >= 3:
        # Check exclusions
        if has_urgency_language(subject, body):
            logger.debug(f"Group email has urgency language, not classifying as FYI")
            return None

        # TODO: Check if email mentions user by name

        return {
            "category_id": 9,
            "rule": f"Group email with {len(to_recipients)} recipients",
            "confidence": 0.85
        }

    return None


# ============================================================================
# MAIN CLASSIFIER
# ============================================================================

def classify_deterministic(email: Dict, user_email: str = None) -> Optional[Dict]:
    """
    Classify an email using deterministic rules.

    Args:
        email: Email dictionary from SQLite database with fields:
            - message_id, from_address, from_name, subject, body_preview, body
            - received_at, importance, conversation_id, has_attachments
            - to_recipients (JSON string), cc_recipients (JSON string)
            - headers (optional dict)
        user_email: Email address of the user (for FYI classification)

    Returns:
        Dictionary with category_id, rule, and confidence (0.85-0.95)
        or None if the email needs AI classification

    Category order (most specific first):
        8. Calendar (MIME type is most reliable)
        6. Marketing (clear promotional indicators)
        11. Travel (specific domains)
        7. Notification (system-generated)
        9. FYI (positional/recipient-based)
    """
    if not email:
        return None

    from_address = email.get("from_address", "")
    subject = email.get("subject", "")

    logger.debug(f"Classifying email: {from_address} - {subject}")

    # Check in order of specificity

    # 1. Calendar (highest specificity - MIME type)
    result = check_calendar(email)
    if result:
        logger.info(f"Classified as Calendar: {result['rule']}")
        return result

    # 2. Marketing (clear promotional indicators)
    result = check_marketing(email)
    if result:
        logger.info(f"Classified as Marketing: {result['rule']}")
        return result

    # 3. Travel (specific domains and keywords)
    result = check_travel(email)
    if result:
        logger.info(f"Classified as Travel: {result['rule']}")
        return result

    # 4. Notification (system-generated)
    if user_email:
        result = check_notification(email, user_email)
        if result:
            logger.info(f"Classified as Notification: {result['rule']}")
            return result

    # 5. FYI (requires user_email for recipient checking)
    if user_email:
        result = check_fyi(email, user_email)
        if result:
            logger.info(f"Classified as FYI: {result['rule']}")
            return result

    # No deterministic classification found - needs AI
    logger.debug(f"No deterministic classification for: {from_address} - {subject}")
    return None
