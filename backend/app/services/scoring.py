"""
Email urgency scoring engine.

Analyzes emails using 8 signal extractors to calculate an urgency score (0-100).
Combines deadline detection, sender analysis, language processing, and thread activity.
"""

import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from sqlalchemy.orm import Session

# Import VIP senders from override checker
from .classifier_override import VIP_SENDERS, VIP_DOMAINS

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# User domain for external/internal detection
USER_DOMAIN = "live.com"  # Configurable per user

# Signal weights (must sum to 1.0)
SIGNAL_WEIGHTS = {
    "explicit_deadline": 0.25,
    "sender_seniority": 0.15,
    "importance_flag": 0.10,
    "urgency_language": 0.15,
    "thread_velocity": 0.10,
    "client_external": 0.05,
    "age_of_email": 0.10,
    "followup_overdue": 0.10,
}

# Urgency floor and escalation settings
URGENCY_FLOOR_THRESHOLD = 90  # Score threshold for floor (configurable 80-100)
TASK_LIMIT = 20  # Maximum Today items (configurable 5-50)
STALE_ESCALATION_ENABLED = True  # Enable stale escalation

# Stale escalation curve (days -> bonus points per day)
STALE_ESCALATION_CURVE = {
    "tier_1": {"days": (0, 3), "bonus_per_day": 2},    # Days 0-3: +2/day
    "tier_2": {"days": (4, 5), "bonus_per_day": 5},    # Days 4-5: +5/day
    "tier_3": {"days": (6, 10), "bonus_per_day": 10},  # Days 6-10: +10/day
    "tier_4": {"days": (11, 999), "force_today": True} # Day 11+: force Today
}

# ============================================================================
# DATE PATTERNS FOR DEADLINE DETECTION
# ============================================================================

# Relative time expressions
RELATIVE_TIME_PATTERNS = [
    (r'\btoday\b', 0),
    (r'\btonigh?t\b', 0),
    (r'\bthis evening\b', 0),
    (r'\btomorrow\b', 1),
    (r'\bthis week\b', 4),  # Approximate to mid-week
    (r'\bnext week\b', 7),
    (r'\bend of week\b', 5),
    (r'\bthis month\b', 15),
    (r'\bnext month\b', 30),
]

# Day of week patterns
DAY_PATTERNS = [
    (r'\bnext\s+monday\b', 1),
    (r'\bnext\s+tuesday\b', 2),
    (r'\bnext\s+wednesday\b', 3),
    (r'\bnext\s+thursday\b', 4),
    (r'\bnext\s+friday\b', 5),
    (r'\bnext\s+saturday\b', 6),
    (r'\bnext\s+sunday\b', 7),
    (r'\bthis\s+monday\b', 1),
    (r'\bthis\s+tuesday\b', 2),
    (r'\bthis\s+wednesday\b', 3),
    (r'\bthis\s+thursday\b', 4),
    (r'\bthis\s+friday\b', 5),
    (r'\bthis\s+saturday\b', 6),
    (r'\bthis\s+sunday\b', 7),
    (r'\bmonday\b', 1),
    (r'\btuesday\b', 2),
    (r'\bwednesday\b', 3),
    (r'\bthursday\b', 4),
    (r'\bfriday\b', 5),
]

# Time of day patterns
TIME_OF_DAY_PATTERNS = [
    r'\bEOD\b',
    r'\bCOB\b',
    r'\bend of (day|business)\b',
    r'\bclose of business\b',
    r'\bby end of day\b',
    r'\bby close of business\b',
]

# Deadline indicator patterns
DEADLINE_PATTERNS = [
    r'\bby\s+',
    r'\bdue\s+',
    r'\bdeadline\s+',
    r'\bbefore\s+',
    r'\bneeded\s+by\s+',
    r'\brequired\s+by\s+',
    r'\bmust\s+be\s+done\s+by\s+',
]

# Month names for date parsing
MONTH_NAMES = {
    'january': 1, 'jan': 1,
    'february': 2, 'feb': 2,
    'march': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'may': 5,
    'june': 6, 'jun': 6,
    'july': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'december': 12, 'dec': 12,
}

# ============================================================================
# URGENCY LANGUAGE PATTERNS
# ============================================================================

URGENCY_KEYWORDS = {
    "strong": [
        r'\bASAP\b',
        r'\burgent\b',
        r'\bimmediately\b',
        r'\bcritical\b',
        r'\bemergency\b',
        r'\btime-critical\b',
        r'\basap\b',
        r'\bright now\b',
        r'\bneeds? immediate\b',
    ],
    "medium": [
        r'\btime-sensitive\b',
        r'\bpriority\b',
        r'\baction required\b',
        r'\bplease respond\b',
        r'\bresponse needed\b',
        r'\breview and respond\b',
        r'\bneeds? (your )?attention\b',
        r'\brequires? (your )?action\b',
        r'\bimportant\b',
    ],
    "mild": [
        r'\bwhen you (get a|have) chance\b',
        r'\bno rush\b',
        r'\blow priority\b',
        r'\bwhenever you (can|have time)\b',
        r'\bno hurry\b',
        r'\bat your convenience\b',
    ]
}

# ============================================================================
# SIGNAL 1: EXPLICIT DEADLINE
# ============================================================================

def extract_explicit_deadline(email: Dict) -> int:
    """
    Detect explicit deadlines in email and calculate urgency based on days until deadline.

    Args:
        email: Email dictionary with subject, body, body_preview

    Returns:
        Score 0-100 (0 days = 100, 1 day = 85, 2 days = 70, etc.)
    """
    subject = email.get("subject", "").lower()
    body = email.get("body", "").lower()
    body_preview = email.get("body_preview", "").lower()

    # Combine all text for analysis
    text = f"{subject} {body_preview} {body[:1000]}"  # Limit body to first 1000 chars

    deadline_date = _find_deadline_in_text(text)

    if not deadline_date:
        return 0

    # Calculate days until deadline
    today = datetime.now().date()
    days_until = (deadline_date - today).days

    # Score based on days until deadline
    if days_until < 0:
        # Past deadline - maximum urgency
        return 100
    elif days_until == 0:
        return 100
    elif days_until == 1:
        return 85
    elif days_until == 2:
        return 70
    elif days_until == 3:
        return 55
    elif days_until in [4, 5]:
        return 40
    elif days_until in [6, 7]:
        return 25
    else:  # 8+ days
        return 10


def _find_deadline_in_text(text: str) -> Optional[datetime.date]:
    """
    Extract the earliest deadline date from text using various patterns.

    Returns:
        datetime.date object or None if no deadline found
    """
    today = datetime.now().date()
    found_dates = []

    # Check for relative time expressions
    for pattern, days_offset in RELATIVE_TIME_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            deadline = today + timedelta(days=days_offset)
            found_dates.append(deadline)

    # Check for day of week patterns
    for pattern, target_day in DAY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            current_day = today.weekday()  # 0 = Monday
            days_ahead = (target_day - current_day) % 7
            if days_ahead == 0 and "next" in pattern:
                days_ahead = 7
            deadline = today + timedelta(days=days_ahead)
            found_dates.append(deadline)

    # Check for EOD/COB (assume same day if before 5pm, else next day)
    for pattern in TIME_OF_DAY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            current_hour = datetime.now().hour
            if current_hour < 17:  # Before 5pm
                found_dates.append(today)
            else:
                found_dates.append(today + timedelta(days=1))

    # Check for explicit dates like "February 15" or "Feb 15"
    month_day_pattern = r'\b(' + '|'.join(MONTH_NAMES.keys()) + r')\s+(\d{1,2})(?:st|nd|rd|th)?\b'
    for match in re.finditer(month_day_pattern, text, re.IGNORECASE):
        month_name = match.group(1).lower()
        day = int(match.group(2))
        month = MONTH_NAMES[month_name]

        try:
            year = today.year
            deadline = datetime(year, month, day).date()

            # If date is in the past, assume next year
            if deadline < today:
                deadline = datetime(year + 1, month, day).date()

            found_dates.append(deadline)
        except ValueError:
            continue

    # Check for numeric dates like "2/15" or "02/15/2024"
    date_patterns = [
        r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b',  # MM/DD/YYYY
        r'\b(\d{1,2})/(\d{1,2})/(\d{2})\b',   # MM/DD/YY
        r'\b(\d{1,2})/(\d{1,2})\b',            # MM/DD
    ]

    for pattern in date_patterns:
        for match in re.finditer(pattern, text):
            try:
                if len(match.groups()) == 3:
                    month, day, year = match.groups()
                    year = int(year)
                    if year < 100:  # Two-digit year
                        year += 2000
                else:  # MM/DD without year
                    month, day = match.groups()
                    year = today.year

                month = int(month)
                day = int(day)

                deadline = datetime(year, month, day).date()

                # If date is in the past, assume next year (for MM/DD format)
                if deadline < today and len(match.groups()) == 2:
                    deadline = datetime(year + 1, month, day).date()

                found_dates.append(deadline)
            except ValueError:
                continue

    # Return earliest deadline found
    if found_dates:
        return min(found_dates)

    return None


# ============================================================================
# SIGNAL 2: SENDER SENIORITY
# ============================================================================

def extract_sender_seniority(email: Dict, user_domain: str = USER_DOMAIN) -> int:
    """
    Score email based on sender importance.

    Args:
        email: Email dictionary with from_address
        user_domain: User's email domain for internal/external detection

    Returns:
        Score: VIP = 90, External = 40, Internal peer = 20, Unknown = 10
    """
    sender_email = email.get("from_address", "").lower()

    if not sender_email:
        return 10

    # Check if sender is VIP
    if sender_email in [vip.lower() for vip in VIP_SENDERS]:
        return 90

    # Check if sender domain is VIP
    sender_domain = sender_email.split('@')[-1] if '@' in sender_email else ''
    if sender_domain in [domain.lower() for domain in VIP_DOMAINS]:
        return 90

    # Check if external domain
    if sender_domain and sender_domain != user_domain.lower():
        return 40

    # Internal peer
    if sender_domain == user_domain.lower():
        return 20

    return 10


# ============================================================================
# SIGNAL 3: IMPORTANCE FLAG
# ============================================================================

def extract_importance_flag(email: Dict) -> int:
    """
    Score based on Graph API importance flag.

    Args:
        email: Email dictionary with importance field

    Returns:
        Score: high = 80, normal = 0, low = -20
    """
    importance = email.get("importance", "normal").lower()

    if importance == "high":
        return 80
    elif importance == "low":
        return -20
    else:  # normal
        return 0


# ============================================================================
# SIGNAL 4: URGENCY LANGUAGE
# ============================================================================

def extract_urgency_language(email: Dict) -> int:
    """
    Detect urgency keywords in subject and body.

    Args:
        email: Email dictionary with subject, body, body_preview

    Returns:
        Score: Strong urgency = 90, Medium = 60, Mild = -10
    """
    subject = email.get("subject", "").lower()
    body = email.get("body", "").lower()
    body_preview = email.get("body_preview", "").lower()

    # Combine text, prioritize subject
    text = f"{subject} {subject} {body_preview} {body[:500]}"

    # Check strong urgency (highest priority)
    for pattern in URGENCY_KEYWORDS["strong"]:
        if re.search(pattern, text, re.IGNORECASE):
            return 90

    # Check medium urgency
    for pattern in URGENCY_KEYWORDS["medium"]:
        if re.search(pattern, text, re.IGNORECASE):
            return 60

    # Check mild urgency (deprioritize)
    for pattern in URGENCY_KEYWORDS["mild"]:
        if re.search(pattern, text, re.IGNORECASE):
            return -10

    return 0


# ============================================================================
# SIGNAL 5: THREAD VELOCITY
# ============================================================================

def extract_thread_velocity(email: Dict, db: Session = None) -> int:
    """
    Calculate thread activity in last 24 hours.

    Args:
        email: Email dictionary with conversation_id
        db: Database session for querying thread

    Returns:
        Score: 5+ replies = 80, 3-4 = 60, 2 = 40, 1 = 20, 0 = 0
    """
    if not db:
        return 0

    conversation_id = email.get("conversation_id")
    if not conversation_id:
        return 0

    try:
        from ..models import Email as EmailModel

        # Query emails in same conversation from last 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        count = db.query(EmailModel).filter(
            EmailModel.conversation_id == conversation_id,
            EmailModel.received_at >= cutoff_time
        ).count()

        # Score based on reply count
        if count >= 5:
            return 80
        elif count >= 3:
            return 60
        elif count == 2:
            return 40
        elif count == 1:
            return 20
        else:
            return 0

    except Exception as e:
        logger.error(f"Error calculating thread velocity: {e}")
        return 0


# ============================================================================
# SIGNAL 6: CLIENT EXTERNAL
# ============================================================================

def extract_client_external(email: Dict, user_domain: str = USER_DOMAIN) -> int:
    """
    Check if sender is external to prioritize client-facing emails.

    Args:
        email: Email dictionary with from_address
        user_domain: User's email domain

    Returns:
        Score: External = 50, Internal = 0
    """
    sender_email = email.get("from_address", "").lower()

    if not sender_email or '@' not in sender_email:
        return 0

    sender_domain = sender_email.split('@')[-1]

    if sender_domain != user_domain.lower():
        return 50

    return 0


# ============================================================================
# SIGNAL 7: AGE OF EMAIL
# ============================================================================

def extract_age_of_email(email: Dict) -> int:
    """
    Calculate urgency based on email age (older = more urgent as it's been waiting).

    ADJUSTED: Age is capped at 40 points maximum to prevent emails from rising
    to the top based on age alone.

    Args:
        email: Email dictionary with received_at

    Returns:
        Score: 0-2 hrs = 0, 2-12 hrs = 10, 12-24 hrs = 20, 1-2 days = 30,
               2+ days = 40 (capped)
    """
    received_at = email.get("received_at")

    if not received_at:
        return 0

    # Handle both datetime objects and strings
    if isinstance(received_at, str):
        try:
            received_at = datetime.fromisoformat(received_at.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return 0

    # Calculate hours since received
    now = datetime.utcnow()
    if received_at.tzinfo:
        # Make now timezone-aware if received_at is
        from datetime import timezone
        now = datetime.now(timezone.utc)

    age_delta = now - received_at
    hours_old = age_delta.total_seconds() / 3600
    days_old = hours_old / 24

    # Score based on age (capped at 40)
    if hours_old < 2:
        return 0
    elif hours_old < 12:
        return 10
    elif hours_old < 24:
        return 20
    elif days_old < 2:
        return 30
    else:  # 2+ days (capped at 40)
        return 40


# ============================================================================
# SIGNAL 8: FOLLOWUP OVERDUE
# ============================================================================

def extract_followup_overdue(email: Dict) -> int:
    """
    Check if followup email has passed its deadline.
    Only applies to Category 4 (Time-Sensitive/Follow-Up) emails.

    Args:
        email: Email dictionary with category_id, subject, body

    Returns:
        Score: Days overdue * 15, capped at 100. 0 if not Category 4 or no deadline.
    """
    category_id = email.get("category_id")

    # Only apply to Category 4 (Time-Sensitive)
    if category_id != 4:
        return 0

    # Try to find a deadline
    subject = email.get("subject", "").lower()
    body = email.get("body", "").lower()
    body_preview = email.get("body_preview", "").lower()

    text = f"{subject} {body_preview} {body[:1000]}"
    deadline_date = _find_deadline_in_text(text)

    if not deadline_date:
        return 0

    # Check if deadline has passed
    today = datetime.now().date()
    days_overdue = (today - deadline_date).days

    if days_overdue > 0:
        # Calculate score: days overdue * 15, capped at 100
        score = min(days_overdue * 15, 100)
        return score

    return 0


# ============================================================================
# URGENCY FLOOR AND STALE ESCALATION
# ============================================================================

def apply_stale_escalation(email: Dict, raw_score: float) -> Tuple[float, int, int, bool]:
    """
    Apply stale escalation to increase urgency for old emails.

    Progressive curve:
    - Days 0-3: +2 points per day
    - Days 4-5: +5 points per day
    - Days 6-10: +10 points per day
    - Day 11+: Force to Today unconditionally

    Args:
        email: Email dictionary with received_at field
        raw_score: Raw urgency score before escalation

    Returns:
        Tuple of (adjusted_score, stale_days, stale_bonus, force_today)
    """
    if not STALE_ESCALATION_ENABLED:
        return raw_score, 0, 0, False

    received_at = email.get("received_at")
    if not received_at:
        return raw_score, 0, 0, False

    # Handle datetime objects or strings
    if isinstance(received_at, str):
        try:
            received_at = datetime.fromisoformat(received_at.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return raw_score, 0, 0, False

    # Calculate stale days
    now = datetime.utcnow()
    if received_at.tzinfo:
        from datetime import timezone
        now = datetime.now(timezone.utc)

    stale_days = (now - received_at).days

    # Apply escalation curve
    stale_bonus = 0
    force_today = False

    for tier_name, tier_config in STALE_ESCALATION_CURVE.items():
        day_min, day_max = tier_config["days"]

        if day_min <= stale_days <= day_max:
            if tier_config.get("force_today"):
                # Day 11+: Force to Today
                force_today = True
                # Set score to 100 to ensure it's prioritized
                adjusted_score = 100
                stale_bonus = 100 - raw_score  # Bonus needed to reach 100
                return adjusted_score, stale_days, int(stale_bonus), force_today
            else:
                # Calculate bonus for this tier
                bonus_per_day = tier_config["bonus_per_day"]
                days_in_tier = stale_days - day_min + 1
                stale_bonus += days_in_tier * bonus_per_day
            break

    # Apply bonus to raw score, clamped to 0-100
    adjusted_score = max(0, min(100, raw_score + stale_bonus))

    return adjusted_score, stale_days, int(stale_bonus), force_today


def apply_urgency_floor(
    email: Dict,
    adjusted_score: float,
    urgency_floor: float = URGENCY_FLOOR_THRESHOLD
) -> Tuple[float, bool]:
    """
    Check if email meets urgency floor threshold.

    If adjusted_score >= urgency_floor, sets floor_override flag.
    Floor items are unconditionally assigned to Today.

    Args:
        email: Email dictionary
        adjusted_score: Score after stale escalation
        urgency_floor: Threshold for floor (default: 90)

    Returns:
        Tuple of (final_score, floor_override)
    """
    floor_override = adjusted_score >= urgency_floor

    return adjusted_score, floor_override


# ============================================================================
# MAIN SCORING FUNCTION
# ============================================================================

def score_email(email: Dict, db: Session = None, user_domain: str = USER_DOMAIN) -> Dict:
    """
    Calculate comprehensive urgency score for an email using 8 signals.

    Args:
        email: Email dictionary with all fields
        db: Optional database session for thread velocity
        user_domain: User's email domain for external/internal detection

    Returns:
        Dictionary with:
        - urgency_score: Final score (0-100)
        - signals: Raw signal scores (0-100 or negative)
        - weights: Applied weights for each signal
        - breakdown: Weighted contribution of each signal
    """
    # Extract all signals
    signals = {
        "explicit_deadline": extract_explicit_deadline(email),
        "sender_seniority": extract_sender_seniority(email, user_domain),
        "importance_flag": extract_importance_flag(email),
        "urgency_language": extract_urgency_language(email),
        "thread_velocity": extract_thread_velocity(email, db),
        "client_external": extract_client_external(email, user_domain),
        "age_of_email": extract_age_of_email(email),
        "followup_overdue": extract_followup_overdue(email),
    }

    # Calculate weighted contributions
    breakdown = {}
    weighted_sum = 0

    for signal_name, raw_score in signals.items():
        weight = SIGNAL_WEIGHTS[signal_name]
        weighted_score = raw_score * weight
        breakdown[f"{signal_name}_weighted"] = round(weighted_score, 2)
        weighted_sum += weighted_score

    # Calculate raw score (before escalation and floor)
    raw_score = max(0, min(100, weighted_sum))

    # Apply stale escalation
    adjusted_score, stale_days, stale_bonus, force_today = apply_stale_escalation(
        email, raw_score
    )

    # Apply urgency floor check
    final_score, floor_override = apply_urgency_floor(
        email, adjusted_score, URGENCY_FLOOR_THRESHOLD
    )

    return {
        "urgency_score": int(round(final_score)),
        "raw_score": round(raw_score, 2),
        "stale_bonus": stale_bonus,
        "adjusted_score": round(adjusted_score, 2),
        "stale_days": stale_days,
        "force_today": force_today,
        "floor_override": floor_override,
        "signals": signals,
        "weights": SIGNAL_WEIGHTS,
        "breakdown": breakdown
    }
