"""
Facebook Lead Intelligence V1 - Phase 8: Central Lead Notification Runner

Orchestrates:
1. Configuration loading from public.system_flags (LEAD_NOTIFICATION_ENABLED, LEAD_NOTIFICATION_MIN_SCORE)
2. Eligibility filtering (score >= min_score OR intent = 'REQUEST_QUOTE')
3. Anti-duplicate verification (24h cooldown)
4. Message formatting (Lead ID, Tên, Company, Phone, Email, Location, Product, Quantity, Requirement, Intent, Score, Score band, Facebook source, Source URL, Detected time)
5. Robust delivery with retry queue (no lead loss on failure)
6. Event auditing in lead_events and facebook_errors
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, List, Optional

sys.path.append(os.path.dirname(__file__))
from lead_formatter import format_lead_telegram_message
from anti_duplicate import is_duplicate_notification, record_notification_event
from telegram_dispatcher import get_telegram_credentials, send_telegram_notification

DB_URI = os.getenv(
    'SUPABASE_DB_URI',
    'postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres'
)

def run_notification_cycle(limit: int = 50) -> Dict[str, Any]:
    """Runs a complete lead notification evaluation and dispatch cycle"""
    conn = psycopg2.connect(DB_URI)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Load Configurations from system_flags
    cur.execute("SELECT flag_value FROM public.system_flags WHERE id = 'LEAD_NOTIFICATION_ENABLED';")
    flag_enabled = cur.fetchone()
    is_enabled = flag_enabled['flag_value'] if flag_enabled else True

    if not is_enabled:
        cur.close()
        conn.close()
        return {
            'status': 'DISABLED',
            'message': 'Lead notification is globally disabled via LEAD_NOTIFICATION_ENABLED'
        }

    cur.execute("SELECT config_payload FROM public.system_flags WHERE id = 'LEAD_NOTIFICATION_MIN_SCORE';")
    flag_score = cur.fetchone()
    min_score = 60
    cooldown_hours = 24
    if flag_score and flag_score.get('config_payload'):
        min_score = int(flag_score['config_payload'].get('min_score', 60))
        cooldown_hours = int(flag_score['config_payload'].get('cooldown_hours', 24))

    token, chat_id = get_telegram_credentials(cur)

    # 2. Query Eligible Leads
    cur.execute("""
        SELECT 
            l.id as lead_id,
            l.full_name,
            l.company_name,
            l.primary_phone,
            l.primary_email,
            l.product_interest,
            l.primary_intent,
            l.lead_score,
            l.lead_tier,
            l.status,
            l.created_at,
            l.metadata as lead_metadata,
            ls.source_id,
            ls.origin_url as source_url,
            ls.post_id,
            ls.comment_id,
            ls.detected_at,
            fs.name as source_name,
            fs.url as fb_source_url
        FROM public.leads l
        LEFT JOIN LATERAL (
            SELECT source_id, origin_url, post_id, comment_id, detected_at
            FROM public.lead_sources
            WHERE lead_id = l.id
            ORDER BY created_at ASC
            LIMIT 1
        ) ls ON true
        LEFT JOIN public.facebook_sources fs ON fs.id = ls.source_id
        WHERE (l.lead_score >= %s OR l.primary_intent = 'REQUEST_QUOTE')
          AND l.status != 'SPAM'
        ORDER BY l.created_at DESC
        LIMIT %s;
    """, (min_score, limit))
    eligible_leads = cur.fetchall()

    results = {
        'total_evaluated': len(eligible_leads),
        'dispatched': 0,
        'skipped_cooldown': 0,
        'failed': 0,
        'items': []
    }

    for row in eligible_leads:
        lead_id = str(row['lead_id'])
        lead_dict = dict(row)

        # Extract context fields from lead_metadata or signal_metadata
        meta = lead_dict.get('lead_metadata') or {}
        if isinstance(meta, str):
            try: meta = json.loads(meta)
            except Exception: meta = {}

        lead_dict['location'] = meta.get('location')
        lead_dict['quantity'] = meta.get('quantity')
        lead_dict['requirement'] = meta.get('requirement')

        # Fallback source URL to facebook page URL if specific post URL is absent
        if not lead_dict.get('source_url') and lead_dict.get('fb_source_url'):
            lead_dict['source_url'] = lead_dict.get('fb_source_url')

        # 3. Anti-Duplicate Check
        is_dup, dup_reason = is_duplicate_notification(cur, lead_id, cooldown_hours)
        if is_dup:
            results['skipped_cooldown'] += 1
            results['items'].append({
                'lead_id': lead_id,
                'action': 'SKIPPED_COOLDOWN',
                'reason': dup_reason
            })
            continue

        # 4. Format Message with Strict Missing Value Policy
        msg_text = format_lead_telegram_message(lead_dict)

        # 5. Enqueue & Dispatch
        cur.execute("""
            INSERT INTO public.lead_notification_queue (
                lead_id, channel, status, payload, created_at
            ) VALUES (%s, 'TELEGRAM', 'PENDING', %s, NOW())
            RETURNING id;
        """, (lead_id, json.dumps({'message': msg_text})))
        queue_id = str(cur.fetchone()['id'])
        conn.commit()

        success, delivery_id, err_msg = send_telegram_notification(
            message_text=msg_text,
            bot_token=token,
            chat_id=chat_id,
            max_retries=3
        )

        if success:
            cur.execute("""
                UPDATE public.lead_notification_queue 
                SET status = 'SENT', sent_at = NOW() 
                WHERE id = %s;
            """, (queue_id,))
            record_notification_event(
                cur=cur,
                lead_id=lead_id,
                channel='TELEGRAM',
                message_text=msg_text,
                delivery_status='SENT'
            )
            cur.execute("UPDATE public.leads SET last_contacted_at = NOW() WHERE id = %s;", (lead_id,))
            conn.commit()

            results['dispatched'] += 1
            results['items'].append({
                'lead_id': lead_id,
                'action': 'DISPATCHED',
                'delivery_id': delivery_id
            })
        else:
            # Resilient error handling: Do not lose lead, mark for retry
            cur.execute("""
                UPDATE public.lead_notification_queue 
                SET status = 'FAILED', 
                    retry_count = retry_count + 1, 
                    error_message = %s,
                    next_retry_at = NOW() + INTERVAL '10 minutes'
                WHERE id = %s;
            """, (err_msg, queue_id))
            record_notification_event(
                cur=cur,
                lead_id=lead_id,
                channel='TELEGRAM',
                message_text=msg_text,
                delivery_status='FAILED',
                error_message=err_msg
            )
            cur.execute("""
                INSERT INTO public.facebook_errors (
                    error_category, error_code, error_message, request_context, created_at
                ) VALUES ('NOTIFICATION_FAILURE', 'TELEGRAM_ERROR', %s, %s, NOW());
            """, (err_msg, json.dumps({'lead_id': lead_id, 'queue_id': queue_id})))
            conn.commit()

            results['failed'] += 1
            results['items'].append({
                'lead_id': lead_id,
                'action': 'FAILED_QUEUED_FOR_RETRY',
                'error': err_msg
            })

    cur.close()
    conn.close()
    return results

if __name__ == '__main__':
    res = run_notification_cycle()
    print(json.dumps(res, indent=2))
