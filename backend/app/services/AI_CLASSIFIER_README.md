# AI Email Classifier

The AI classifier uses Claude 3.5 Sonnet to classify work emails into categories 1-5 based on nuanced understanding of email content, context, and required actions.

## Purpose

Handles emails that can't be deterministically classified - typically direct work emails that require understanding of intent, urgency, and action requirements.

## Categories

The AI classifies into 5 Work categories:

### 1. Blocking 🚨
**Definition:** Critical blockers that prevent progress on important work.

**Key Indicators:**
- Someone is blocked waiting for you
- Production issues
- Critical system failures
- Team can't proceed without your action

**Examples:**
- "Production is down - need your approval to deploy fix"
- "Cannot proceed with launch until you sign off"
- "Build is broken by your last commit, blocking entire team"

---

### 2. Action Required ⚡
**Definition:** Tasks that need completion - either replies OR to-dos.

**Two types:**
- **Reply:** You need to write back (answer question, provide info, give decision)
- **To-Do:** You need to DO something (review code, approve request, complete task)

**Key Indicators:**
- Direct questions or requests
- "Can you", "please", "need your"
- Requests for review, approval, feedback
- Decision needed from you

**Examples:**
- "Can you review this pull request?" (To-Do)
- "What's your opinion on the proposal?" (Reply)
- "Please approve this expense report" (To-Do)
- "Need your feedback by EOD" (Reply)

---

### 3. Waiting On ⏳
**Definition:** You already took action, now waiting for someone else.

**Key Indicators:**
- Status updates from others
- "Working on it", "will get back to you"
- Confirmations they received your request
- Follow-up on something you already sent

**Examples:**
- "Thanks for the info, I'll review and get back to you"
- "Got it, working on this now"
- "Received your request, processing it"

---

### 4. Time-Sensitive ⏰
**Definition:** Has a deadline or time constraint but isn't blocking anyone right now.

**Key Indicators:**
- Specific dates/times mentioned
- "Due by", "deadline", "reminder"
- Upcoming events or meetings
- Time-bound but not urgent

**Examples:**
- "Reminder: Report due Friday"
- "Meeting tomorrow at 2pm - please review agenda"
- "Early bird registration ends this week"

---

### 5. FYI 📋
**Definition:** Informational only, no action needed.

**Key Indicators:**
- "FYI", "for your information"
- Status updates where you're CC'd
- Newsletters, announcements
- Updates where no response expected

**Examples:**
- "FYI: Team lunch on Friday"
- "Just keeping you in the loop"
- Weekly status update
- Automated notification

---

## Usage

```python
from app.services import classify_with_ai

# Prepare email data
email = {
    "from_name": "Colleague",
    "from_address": "colleague@company.com",
    "subject": "Can you review this PR?",
    "body": "I've finished the feature implementation...",
    "to_recipients": '[{"address": "user@company.com"}]',
    "cc_recipients": '[]',
    "received_at": datetime.now(),
    "importance": "normal",
    "has_attachments": False,
    "conversation_id": "conv-123"
}

# Classify
result = classify_with_ai(email)

# Result format:
# {
#   "category_id": 2,
#   "confidence": 0.85,
#   "reasoning": "Direct request for code review..."
# }
```

---

## Configuration

### Environment Variables

Add to `.env` file:

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### Model Settings

In `app/services/classifier_ai.py`:

```python
MODEL = "claude-3-5-sonnet-20241022"  # Latest Sonnet model
MAX_TOKENS = 300                       # Enough for JSON response
TEMPERATURE = 0.1                      # Low for consistent results
```

### Retry Configuration

```python
MAX_RETRIES = 3               # Number of retry attempts
INITIAL_RETRY_DELAY = 1.0     # Starting delay in seconds
# Exponential backoff: 1s → 2s → 4s
```

---

## Error Handling

### Rate Limiting (429)

The classifier automatically handles rate limits with exponential backoff:

```python
Attempt 1: Wait 1 second, retry
Attempt 2: Wait 2 seconds, retry
Attempt 3: Wait 4 seconds, retry
After 3 attempts: Raise exception
```

### API Server Errors (500, 503)

Same retry logic applies to server errors:
- Temporary issues are retried
- After max retries, returns safe default

### Safe Default

If classification fails completely:

```python
{
  "category_id": 2,           # Action Required (safe choice)
  "confidence": 0.3,          # Low confidence
  "reasoning": "Classification error..."
}
```

### JSON Parse Errors

If Claude returns invalid JSON:
1. Attempts to extract JSON using regex
2. If extraction fails, returns safe default
3. Logs error for debugging

---

## Confidence Scoring

The AI returns confidence scores to indicate certainty:

| Range | Meaning | Examples |
|-------|---------|----------|
| 0.9-1.0 | Very clear | Production outage, explicit deadline |
| 0.7-0.89 | Clear | Direct request, obvious category |
| 0.5-0.69 | Moderate | Some ambiguity, context-dependent |
| 0.3-0.49 | Low | Uncertain, multiple interpretations |

**When to trust low confidence:**
- Review classification manually
- May need user correction
- Could benefit from more context

---

## System Prompt

The classifier uses a detailed system prompt that includes:

1. **Category Definitions:** Clear description of each category
2. **Examples:** 2-3 realistic examples per category
3. **Key Indicators:** What signals to look for
4. **Edge Cases:** Reply vs To-Do distinction, Blocking vs Time-Sensitive
5. **Confidence Guidelines:** How to score certainty
6. **JSON Format:** Exact response structure

Full prompt is ~1500 tokens, optimized for accuracy and consistency.

---

## API Costs

### Claude 3.5 Sonnet Pricing (as of Jan 2025)

- Input: $3.00 per million tokens
- Output: $15.00 per million tokens

### Per Email Cost

Typical email classification:
- Input: ~800 tokens (prompt + email)
- Output: ~100 tokens (JSON response)

**Cost per email:** ~$0.0024 + ~$0.0015 = **$0.0039** (less than 1 cent)

### Example Costs

| Emails | Cost |
|--------|------|
| 100 | $0.39 |
| 1,000 | $3.90 |
| 10,000 | $39.00 |

**Optimization tip:** Run deterministic classifier first to reduce AI calls by ~70%.

---

## Performance

### Response Time

- Typical: 1-2 seconds per email
- With retry: Up to 8 seconds (worst case)
- Batch processing: Add 0.5s delay between calls

### Rate Limits

Claude API rate limits:
- Tier 1: 50 requests/minute
- Tier 2: 1,000 requests/minute
- Tier 3: 2,000 requests/minute

**Built-in protection:** Classifier adds 0.5s delay in batch mode to stay under limits.

---

## Batch Processing

```python
from app.services.classifier_ai import classify_batch

emails = [email1, email2, email3, ...]

# Classify with rate limit protection
results = classify_batch(emails, delay_between_calls=0.5)

# results = [
#   {"category_id": 2, "confidence": 0.85, ...},
#   {"category_id": 1, "confidence": 0.95, ...},
#   ...
# ]
```

---

## Testing

### Without API Key (Simulated)

```bash
python3 test_ai_classifier.py
```

Shows expected responses for different email types.

### With API Key (Real)

```python
# Set API key in .env
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Test single classification
from app.services import classify_with_ai

email = {
    "from_address": "test@example.com",
    "subject": "Test email",
    "body": "Can you review this?",
    # ... other fields
}

result = classify_with_ai(email)
print(result)
```

---

## Integration with Classification Pipeline

```
1. Fetch emails → status='unprocessed'
   ↓
2. Deterministic classifier → ~70% classified to categories 6-11
   ↓
3. Override checker → ~10% reset to unprocessed
   ↓
4. AI classifier → Remaining ~30% classified to categories 1-5
   ↓
5. All emails classified
```

---

## Logging

The classifier logs all operations:

```python
import logging
logging.basicConfig(level=logging.INFO)

# Logs include:
# - Email being classified
# - API calls and retries
# - Classification results
# - Errors and warnings
```

**Log messages:**
```
INFO: Classifying email: colleague@company.com - Review request
INFO: Classified as category 2 with confidence 0.85
WARNING: Rate limit hit, retrying in 1.0s
ERROR: Failed to parse Claude response: ...
```

---

## Common Issues

### Issue: API Key Not Found

**Error:** `ValueError: ANTHROPIC_API_KEY not found in environment variables`

**Solution:**
1. Create/edit `.env` file in backend directory
2. Add: `ANTHROPIC_API_KEY=sk-ant-xxxxx`
3. Restart server

---

### Issue: Rate Limit Exceeded

**Error:** `RateLimitError: Rate limit exceeded`

**Solution:**
- Automatic retry with backoff (built-in)
- Reduce batch size
- Add longer delay between calls
- Upgrade API tier

---

### Issue: JSON Parse Error

**Error:** `Failed to parse Claude response as JSON`

**Possible causes:**
- Claude returned explanatory text instead of pure JSON
- Response truncated (increase MAX_TOKENS)
- Network error corrupted response

**Solution:**
- Classifier automatically extracts JSON from text
- If extraction fails, returns safe default
- Check logs for full response

---

## Future Enhancements

1. **Caching:** Cache classifications for similar emails
2. **Learning:** Track user corrections to improve prompt
3. **Batch API:** Use Claude's batch API for async processing
4. **Custom Categories:** Allow users to define their own categories
5. **Multi-language:** Support non-English emails
6. **Attachments:** Analyze attachment names/types for better classification

---

## Advanced Usage

### Custom System Prompt

```python
from app.services.classifier_ai import classify_with_ai

# Modify SYSTEM_PROMPT in classifier_ai.py
# Add company-specific examples
# Adjust category definitions
```

### Adjusting Confidence Threshold

```python
result = classify_with_ai(email)

if result["confidence"] < 0.6:
    # Low confidence, maybe needs manual review
    send_to_manual_review(email, result)
else:
    # High confidence, use classification
    apply_classification(email, result)
```

### Combining with Deterministic Rules

```python
# 1. Try deterministic first (fast, free)
det_result = classify_deterministic(email, user_email)

if det_result:
    # Check for override
    override = check_override(email, det_result["category_id"], user_email, db)

    if override["override"]:
        # Need AI classification
        ai_result = classify_with_ai(email)
        return ai_result
    else:
        # Keep deterministic
        return det_result
else:
    # 2. Use AI for work emails
    ai_result = classify_with_ai(email)
    return ai_result
```

---

## Summary

The AI classifier provides:
- ✅ Nuanced understanding of email content
- ✅ Distinction between Reply vs To-Do actions
- ✅ Confidence scoring for uncertainty
- ✅ Automatic retry with rate limit protection
- ✅ Safe defaults for error cases
- ✅ Low cost per classification (<1 cent)
- ✅ Fast response (1-2 seconds)

Perfect for handling the ~30% of emails that require human-like judgment about priority and action requirements.
