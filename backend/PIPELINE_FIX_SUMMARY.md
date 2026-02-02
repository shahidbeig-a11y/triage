# Pipeline Endpoint Fix Summary

## Problem
The `POST /api/emails/pipeline/run` endpoint was hanging and never returning, while all individual endpoints (`/fetch`, `/classify-deterministic`, `/check-overrides`, `/classify-ai`) worked fine.

## Root Cause
The pipeline function had two issues:

### 1. **Variable Scoping Issue**
The `user` variable was defined inside a try block but referenced outside of it, which could cause undefined behavior if the fetch stage failed.

### 2. **Async/Sync Blocking Issue** (Main Cause)
The pipeline is an `async` function that was calling **blocking synchronous functions** (`classify_with_ai()`) directly. When running with a single uvicorn worker:

- The `classify_with_ai()` function makes synchronous HTTP requests to the Anthropic API
- These blocking calls prevent the event loop from processing other requests
- With a single worker, this can cause the request to hang indefinitely

This is a classic async/sync mixing problem in Python's asyncio.

## Solution Applied

### Fix 1: Variable Scoping
Moved user variable initialization outside the try block to ensure it's always defined:

```python
# Before (BROKEN):
try:
    user = db.query(User).first()
    # ...
except Exception as e:
    # ...

user_email = user.email  # Could be undefined!

# After (FIXED):
user = db.query(User).first()
user_email = user.email if user else None
user_first_name = "User"
# ... then try block
```

### Fix 2: Non-Blocking AI Classification
Used `asyncio.to_thread()` to run blocking AI classification in a thread pool:

```python
# Before (BLOCKING):
result = classify_with_ai(email_dict)

# After (NON-BLOCKING):
result = await asyncio.to_thread(classify_with_ai, email_dict)
```

This allows the event loop to continue processing other requests while the AI API call is in progress.

### Fix 3: Non-Blocking Sleep
Replaced blocking `time.sleep()` with non-blocking `asyncio.sleep()`:

```python
# Before (BLOCKING):
time.sleep(0.5)

# After (NON-BLOCKING):
await asyncio.sleep(0.5)
```

## Why Individual Endpoints Worked

The individual endpoints worked because:
- They process a smaller set of operations
- The event loop has more opportunities to yield control
- The blocking operations are shorter in duration

The pipeline combined all these operations, amplifying the blocking effect.

## Changes Made

**File: `app/services/pipeline.py`**

1. Added `import asyncio` for thread pool execution
2. Moved user variable initialization outside try block (lines 52-59)
3. Added safe user_first_name extraction with error handling
4. Wrapped `classify_with_ai()` call in `await asyncio.to_thread()` (line 156)
5. Replaced `time.sleep()` with `await asyncio.sleep()` (lines 180, 188)

## Testing

Run the test script:
```bash
./test_pipeline_endpoint.sh
```

Or test manually:
```bash
curl -X POST "http://localhost:8000/api/emails/pipeline/run?fetch_count=10"
```

Expected result: Pipeline should complete and return a comprehensive report within a reasonable time (depends on number of emails to process).

## Technical Details

### Why `asyncio.to_thread()` Works

When you call `await asyncio.to_thread(func, args)`:
1. The function is executed in a separate thread from the thread pool
2. The event loop remains free to handle other requests
3. The async function awaits the thread completion without blocking
4. Other concurrent requests can be processed in parallel

### Async/Sync Best Practices

**DO:**
- Use `await asyncio.to_thread()` for CPU-intensive or blocking I/O operations
- Use `asyncio.sleep()` instead of `time.sleep()` in async functions
- Make async functions truly async by avoiding blocking calls

**DON'T:**
- Call blocking sync functions directly from async functions
- Use synchronous HTTP clients (requests, httpx.Client) in async code
- Use `time.sleep()` in async functions

## Performance Impact

The fix actually **improves** performance:
- Event loop can process other requests concurrently
- Better resource utilization with thread pool
- Non-blocking sleep allows better scheduling

## Related Documentation

- Python asyncio: https://docs.python.org/3/library/asyncio.html
- FastAPI async/await: https://fastapi.tiangolo.com/async/
- Thread pool execution: https://docs.python.org/3/library/asyncio-task.html#running-in-threads
