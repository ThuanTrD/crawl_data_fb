"""
Facebook Lead Intelligence V1 - Phase 8: Anti-Duplicate Notification Engine

Ensures the same lead is not notified repeatedly within a configured cooldown window (e.g. 24h).
Maintains notification history in lead_events and lead_notification_queue.
"""

import json
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict, Any

def is_duplicate_notification(
    cur,
    lead_id: str,
    cooldown_hours: int = 24
) -> Tuple[bool, Optional[str]]:
    """
    Checks if a notification for this lead was already dispatched within cooldown_hours.
    """
    # 1. Check lead_events audit trail
    cur.execute("""
        SELECT created_at 
        FROM public.lead_events 
        WHERE lead_id = %s 
          AND event_type = 'DISPATCHED_TELEGRAM' 
          AND created_at >= NOW() - INTERVAL '%s hours'
        ORDER BY created_at DESC 
        LIMIT 1;
    """, (lead_id, cooldown_hours))
    ev_row = cur.fetchone()
    if ev_row:
        return True, f"Lead was already notified via Telegram on {ev_row['created_at']}"

    # 2. Check lead_notification_queue
    cur.execute("""
        SELECT sent_at 
        FROM public.lead_notification_queue 
        WHERE lead_id = %s 
          AND status = 'SENT' 
          AND sent_at >= NOW() - INTERVAL '%s hours'
        ORDER BY sent_at DESC 
        LIMIT 1;
    """, (lead_id, cooldown_hours))
    q_row = cur.fetchone()
    if q_row:
        return True, f"Lead was queued and sent on {q_row['sent_at']}"

    return False, None

def record_notification_event(
    cur,
    lead_id: str,
    channel: str = 'TELEGRAM',
    message_text: str = '',
    delivery_status: str = 'SENT',
    error_message: Optional[str] = None
) -> str:
    """
    Records immutable audit event in lead_events.
    """
    event_type = 'DISPATCHED_TELEGRAM' if delivery_status == 'SENT' else 'NOTIFICATION_FAILED'
    cur.execute("""
        INSERT INTO public.lead_events (
            lead_id, event_type, old_state, new_state,
            triggered_by, notes, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
        RETURNING id;
    """, (
        lead_id, event_type,
        json.dumps({}),
        json.dumps({
            'channel': channel,
            'status': delivery_status,
            'message_preview': message_text[:200],
            'error': error_message
        }),
        'WF_LEAD_NOTIFICATION_V1',
        f'Lead notification {delivery_status} via {channel}'
    ))
    return str(cur.fetchone()['id'])
