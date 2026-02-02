"""
AI-powered email classifier using Claude API.

This module classifies emails into Work categories (1-5) using Claude 3.5 Sonnet
for nuanced understanding of email content and context.
"""

import os
import json
import time
import logging
from typing import Dict, Optional
from datetime import datetime
from dotenv import load_dotenv
import anthropic

load_dotenv()
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-3-5-sonnet-20241022"
MAX_TOKENS = 300
TEMPERATURE = 0.1  # Low temperature for consistent classification

# Retry configuration for rate limiting
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

SYSTEM_PROMPT = """You are an expert email triage assistant. Your job is to classify work emails into one of 5 categories based on what action the recipient needs to take.

CATEGORIES:

1. BLOCKING
   Definition: Critical blockers that prevent progress on important work. These require IMMEDIATE action.
   Examples:
   - "Production is down - need your approval to deploy fix"
   - "Cannot proceed with launch until you sign off on legal terms"
   - "Build is broken by your last commit, blocking entire team"
   Key indicators: Someone is blocked waiting for you, production issues, critical deadlines

2. ACTION REQUIRED
   Definition: Important tasks that need completion. This includes both replies AND to-dos.
   - Reply: You need to write back with information, decision, or response
   - To-Do: You need to DO something other than just reply (review code, complete task, make decision)
   Examples:
   - "Can you review this pull request?" (To-Do: review required)
   - "What's your opinion on the proposal?" (Reply: response needed)
   - "Please approve this expense report" (To-Do: approval action)
   - "Need your feedback by EOD" (Reply: feedback needed)
   Key indicators: Direct questions, requests for action, "can you", "please", "need your"

3. WAITING ON
   Definition: You already took action and are waiting for someone else to respond or complete something.
   Examples:
   - "Thanks for the info, I'll review and get back to you" (they're working on it)
   - "Got it, working on this now" (they're handling it)
   - Follow-up on something you already sent
   Key indicators: Status updates from others, confirmations, "working on it", "will get back to you"

4. TIME-SENSITIVE
   Definition: Has a specific deadline or time constraint that requires attention soon but isn't blocking anyone right now.
   Examples:
   - "Reminder: Report due Friday"
   - "Meeting tomorrow at 2pm - please review attached agenda"
   - "Early bird registration ends this week"
   Key indicators: Specific dates/times mentioned, "due by", "deadline", "reminder", upcoming events

5. FYI
   Definition: Informational only, no action needed. Good to know but doesn't require response or task.
   Examples:
   - "FYI: Team lunch on Friday"
   - "Just keeping you in the loop on project status"
   - Weekly newsletter or status update where you're CC'd
   - Automated notifications that don't need action
   Key indicators: "FYI", "for your information", status updates, newsletters, you're CC'd

CLASSIFICATION GUIDELINES:

- If someone is BLOCKED waiting for you → Category 1 (Blocking)
- If you need to DO something or REPLY → Category 2 (Action Required)
- If you're waiting for THEM → Category 3 (Waiting On)
- If there's a DEADLINE but not blocking → Category 4 (Time-Sensitive)
- If it's just INFO with no action → Category 5 (FYI)

CONFIDENCE SCORING:
- 0.9-1.0: Very clear category (obvious blocking issue, direct request, explicit deadline)
- 0.7-0.89: Clear category (most signals point to one category)
- 0.5-0.69: Moderate confidence (could go either way, use context)
- 0.3-0.49: Low confidence (ambiguous, multiple interpretations)

When in doubt:
- Direct questions or requests → Action Required (2)
- Time pressure but not blocking → Time-Sensitive (4)
- No clear action needed → FYI (5)

Respond ONLY with valid JSON in this exact format:
{
  "category_id": <number 1-5>,
  "category_name": "<category name>",
  "confidence": <number 0.0-1.0>,
  "reasoning": "<brief 1-2 sentence explanation>"
}"""


# ============================================================================
# API CLIENT
# ============================================================================

def get_client() -> anthropic.Anthropic:
    """Initialize and return Anthropic client."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ============================================================================
# EMAIL FORMATTING
# ============================================================================

def format_email_for_classification(email: Dict) -> str:
    """
    Format email data into a clear message for Claude.

    Args:
        email: Email dictionary with fields from database

    Returns:
        Formatted string with email details
    """
    # Parse recipients if they're JSON strings
    to_recipients = email.get("to_recipients", "[]")
    cc_recipients = email.get("cc_recipients", "[]")

    if isinstance(to_recipients, str):
        try:
            to_recipients = json.loads(to_recipients)
        except (json.JSONDecodeError, TypeError):
            to_recipients = []

    if isinstance(cc_recipients, str):
        try:
            cc_recipients = json.loads(cc_recipients)
        except (json.JSONDecodeError, TypeError):
            cc_recipients = []

    # Format recipients
    to_list = [r.get("address", "") for r in to_recipients if isinstance(r, dict)]
    cc_list = [r.get("address", "") for r in cc_recipients if isinstance(r, dict)]

    to_str = ", ".join(to_list) if to_list else "Not specified"
    cc_str = ", ".join(cc_list) if cc_list else "None"

    # Get body preview (first 500 characters)
    body = email.get("body", "") or email.get("body_preview", "")
    body_preview = body[:500] if body else "[No body content]"

    # Format received date
    received_at = email.get("received_at")
    if isinstance(received_at, datetime):
        received_str = received_at.strftime("%Y-%m-%d %H:%M")
    elif received_at:
        received_str = str(received_at)
    else:
        received_str = "Unknown"

    message = f"""EMAIL TO CLASSIFY:

From: {email.get('from_name', 'Unknown')} <{email.get('from_address', 'unknown@unknown.com')}>
To: {to_str}
CC: {cc_str}
Subject: {email.get('subject', '[No subject]')}
Received: {received_str}
Importance: {email.get('importance', 'normal')}
Has Attachments: {email.get('has_attachments', False)}
Conversation ID: {email.get('conversation_id', 'N/A')}

Body Preview:
{body_preview}

Please classify this email into one of the 5 categories."""

    return message


# ============================================================================
# API INTERACTION
# ============================================================================

def call_claude_api(client: anthropic.Anthropic, user_message: str) -> Dict:
    """
    Call Claude API with retry logic for rate limiting.

    Args:
        client: Anthropic client instance
        user_message: Formatted email content

    Returns:
        Parsed JSON response from Claude

    Raises:
        Exception: If API call fails after all retries
    """
    retry_delay = INITIAL_RETRY_DELAY

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            # Extract text from response
            response_text = response.content[0].text

            # Parse JSON response
            try:
                result = json.loads(response_text)
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Claude response as JSON: {response_text}")
                logger.error(f"Parse error: {str(e)}")
                # Try to extract JSON from response if it's embedded in text
                import re
                json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group(0))
                        return result
                    except json.JSONDecodeError:
                        pass
                raise

        except anthropic.RateLimitError as e:
            # Rate limit hit (429)
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"Rate limit hit, retrying in {retry_delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Rate limit exceeded after {MAX_RETRIES} retries")
                raise

        except (anthropic.InternalServerError, anthropic.APIConnectionError) as e:
            # API server errors (500, 503) or connection issues
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"API error: {str(e)}, retrying in {retry_delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error(f"API error after {MAX_RETRIES} retries: {str(e)}")
                raise

        except anthropic.APIError as e:
            # Other API errors
            logger.error(f"Claude API error: {str(e)}")
            raise

    raise Exception(f"Failed to get response from Claude API after {MAX_RETRIES} retries")


# ============================================================================
# MAIN CLASSIFIER
# ============================================================================

def classify_with_ai(email: Dict) -> Dict:
    """
    Classify an email using Claude AI.

    Args:
        email: Email dictionary with fields:
            - message_id, from_address, from_name, subject, body
            - to_recipients (JSON string or list), cc_recipients (JSON string or list)
            - received_at, importance, has_attachments, conversation_id

    Returns:
        Dictionary with:
        - category_id: int (1-5)
        - confidence: float (0.0-1.0)
        - reasoning: str (explanation)

    Default behavior on error:
        Returns category_id=2 (Action Required) with low confidence as safe default
    """
    if not email:
        logger.error("Empty email provided to classifier")
        return {
            "category_id": 2,
            "confidence": 0.3,
            "reasoning": "Empty email, defaulted to Action Required"
        }

    from_address = email.get("from_address", "unknown")
    subject = email.get("subject", "[No subject]")

    logger.info(f"Classifying email: {from_address} - {subject}")

    try:
        # Initialize client
        client = get_client()

        # Format email for Claude
        user_message = format_email_for_classification(email)

        # Call API with retry logic
        result = call_claude_api(client, user_message)

        # Validate response
        if not isinstance(result, dict):
            raise ValueError(f"Expected dict response, got {type(result)}")

        category_id = result.get("category_id")
        confidence = result.get("confidence")
        reasoning = result.get("reasoning", "")

        # Validate category_id
        if not isinstance(category_id, int) or category_id < 1 or category_id > 5:
            logger.error(f"Invalid category_id: {category_id}, defaulting to 2")
            category_id = 2
            confidence = 0.3
            reasoning = f"Invalid category returned, defaulted to Action Required. Original: {reasoning}"

        # Validate confidence
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            logger.warning(f"Invalid confidence: {confidence}, setting to 0.5")
            confidence = 0.5

        logger.info(f"Classified as category {category_id} with confidence {confidence}")

        return {
            "category_id": int(category_id),
            "confidence": float(confidence),
            "reasoning": str(reasoning)
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response: {str(e)}")
        return {
            "category_id": 2,
            "confidence": 0.3,
            "reasoning": "Failed to parse AI response, defaulted to Action Required"
        }

    except Exception as e:
        logger.error(f"Error classifying email: {str(e)}")
        return {
            "category_id": 2,
            "confidence": 0.3,
            "reasoning": f"Classification error: {str(e)[:100]}"
        }


# ============================================================================
# BATCH CLASSIFICATION
# ============================================================================

def classify_batch(emails: list, delay_between_calls: float = 0.5) -> list:
    """
    Classify multiple emails with rate limit protection.

    Args:
        emails: List of email dictionaries
        delay_between_calls: Delay in seconds between API calls (default 0.5s)

    Returns:
        List of classification results in same order as input
    """
    results = []

    for i, email in enumerate(emails):
        logger.info(f"Classifying email {i + 1}/{len(emails)}")

        result = classify_with_ai(email)
        results.append(result)

        # Add delay between calls to avoid rate limiting
        if i < len(emails) - 1:
            time.sleep(delay_between_calls)

    return results
