"""
Facebook Lead Intelligence V1 - Phase 7: Source State Machine & Controlled Recovery

State Transitions:
ACTIVE
  ↓ (transient error / 5xx / timeout)
TEMP_ERROR (exponential backoff)
  ↓ (429 rate limit)
RATE_LIMITED (cooldown backoff)
  ↓ (repeated failures / threshold)
PAUSED

Hard Errors:
AUTH_ERROR (401) ──→ PAUSED (no auto-retry)
PERMISSION_ERROR (403) ──→ PAUSED (no auto-retry)
BLOCKED ──→ PAUSED (no auto-retry)

Controlled Recovery:
- Resets to ACTIVE ONLY when backoff_until expired for RATE_LIMITED or TEMP_ERROR.
- Never spams retries.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple

VALID_STATES = {
    'ACTIVE', 'TEMP_ERROR', 'RATE_LIMITED', 'PAUSED',
    'AUTH_ERROR', 'PERMISSION_ERROR', 'BLOCKED', 'DISABLED'
}

def transition_on_error(
    cur,
    source_id: str,
    error_code: str,
    http_status: Optional[int],
    error_message: str,
    request_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Evaluates error and transitions source state accordingly.
    Inserts error log into facebook_errors.
    """
    cur.execute("SELECT status, consecutive_errors, name FROM public.facebook_sources WHERE id = %s FOR UPDATE;", (source_id,))
    source = cur.fetchone()
    if not source:
        return {'error': 'Source not found'}

    current_status = source['status']
    current_consecutive = source.get('consecutive_errors') or 0
    new_consecutive = current_consecutive + 1

    new_status = current_status
    backoff_minutes = 0
    error_category = 'COLLECTOR_FAILURE'

    # 1. Authentication Error (401)
    if http_status == 401 or error_code == 'AUTH_ERROR':
        new_status = 'PAUSED'
        error_category = 'AUTHENTICATION'
        backoff_minutes = 0  # No auto-retry

    # 2. Permission Error (403)
    elif http_status == 403 or error_code == 'PERMISSION_ERROR':
        new_status = 'PAUSED'
        error_category = 'PERMISSION'
        backoff_minutes = 0  # No auto-retry

    # 3. Rate Limit Error (429)
    elif http_status == 429 or error_code == 'RATE_LIMITED':
        error_category = 'RATE_LIMIT'
        if new_consecutive >= 3:
            new_status = 'PAUSED'
            backoff_minutes = 0
        else:
            new_status = 'RATE_LIMITED'
            backoff_minutes = 60  # 1 hour cooldown

    # 4. Blocked
    elif error_code == 'BLOCKED':
        new_status = 'PAUSED'
        error_category = 'ACCOUNT_BLOCKED'
        backoff_minutes = 0

    # 5. Network Timeout or 5xx Server Errors
    elif error_code == 'TIMEOUT' or (http_status and 500 <= http_status < 600):
        error_category = 'NETWORK_TIMEOUT' if error_code == 'TIMEOUT' else 'SERVER_5XX'
        if new_consecutive >= 5:
            new_status = 'PAUSED'
            backoff_minutes = 0
        else:
            new_status = 'TEMP_ERROR'
            # Exponential backoff: 2m, 5m, 15m, 30m
            backoff_minutes = min(60, 2 ** (new_consecutive - 1) * 2)

    else:
        error_category = 'UNKNOWN_FAILURE'
        if new_consecutive >= 3:
            new_status = 'TEMP_ERROR'
            backoff_minutes = 15

    # Update facebook_sources
    if backoff_minutes > 0:
        cur.execute("""
            UPDATE public.facebook_sources
            SET
                status = %s,
                consecutive_errors = %s,
                backoff_until = NOW() + INTERVAL '%s minutes',
                last_error_at = NOW(),
                last_error_message = %s,
                updated_at = NOW()
            WHERE id = %s;
        """, (new_status, new_consecutive, backoff_minutes, error_message[:500], source_id))
    else:
        cur.execute("""
            UPDATE public.facebook_sources
            SET
                status = %s,
                consecutive_errors = %s,
                backoff_until = NULL,
                last_error_at = NOW(),
                last_error_message = %s,
                updated_at = NOW()
            WHERE id = %s;
        """, (new_status, new_consecutive, error_message[:500], source_id))

    # Log to facebook_errors
    import json
    cur.execute("""
        INSERT INTO public.facebook_errors (
            source_id, error_category, error_code, error_message,
            request_context, retry_count, is_resolved, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, FALSE, NOW())
        RETURNING id;
    """, (
        source_id, error_category, str(error_code or http_status), error_message,
        json.dumps(request_context or {}), new_consecutive
    ))
    error_id = cur.fetchone()['id']

    return {
        'source_id': source_id,
        'source_name': source.get('name'),
        'previous_status': current_status,
        'new_status': new_status,
        'consecutive_errors': new_consecutive,
        'backoff_minutes': backoff_minutes,
        'error_category': error_category,
        'error_id': str(error_id)
    }

def transition_on_success(cur, source_id: str):
    """
    Resets error counters upon successful collection.
    """
    cur.execute("""
        UPDATE public.facebook_sources
        SET
            status = 'ACTIVE',
            consecutive_errors = 0,
            backoff_until = NULL,
            last_collected_at = NOW(),
            last_successful_collected_at = NOW(),
            updated_at = NOW()
        WHERE id = %s AND status IN ('ACTIVE', 'TEMP_ERROR', 'RATE_LIMITED');
    """, (source_id,))

def recover_eligible_sources(cur) -> List[Dict[str, Any]]:
    """
    Controlled Recovery: Re-activates sources in RATE_LIMITED or TEMP_ERROR
    whose backoff_until has strictly elapsed.
    NEVER recovers PAUSED, AUTH_ERROR, PERMISSION_ERROR, BLOCKED, or DISABLED automatically.
    """
    cur.execute("""
        UPDATE public.facebook_sources
        SET
            status = 'ACTIVE',
            consecutive_errors = 0,
            backoff_until = NULL,
            updated_at = NOW()
        WHERE status IN ('RATE_LIMITED', 'TEMP_ERROR')
          AND backoff_until IS NOT NULL
          AND NOW() >= backoff_until
        RETURNING id, name, status, last_error_message;
    """)
    recovered = cur.fetchall()
    return [dict(r) for r in recovered]
