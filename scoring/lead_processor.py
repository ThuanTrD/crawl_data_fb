"""
Facebook Lead Intelligence V1 - Phase 6: Canonical Lead Processor & Orchestrator

Complete Pipeline:
facebook_lead_signals
        ↓
Lead validation
        ↓
Entity resolution
        ↓
Lead creation/update
        ↓
Lead scoring
        ↓
lead_sources
        ↓
lead_events
"""

import os
import sys
import uuid
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, List, Optional

sys.path.append(os.path.dirname(__file__))
from scoring_engine import calculate_lead_score
from dedup_resolver import (
    resolve_entity,
    compute_dedup_fingerprint,
    normalize_phone,
    normalize_email
)

DB_URI = os.getenv(
    'SUPABASE_DB_URI',
    'postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres'
)

def process_single_signal(cur, signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processes one signal according to Phase 6 complete pipeline specifications.
    """
    signal_id = signal['id']
    intent = str(signal.get('intent') or 'IGNORE').strip().upper()

    # Step 1: Lead Validation
    if intent == 'IGNORE':
        cur.execute("UPDATE public.facebook_lead_signals SET status = 'DISCARDED' WHERE id = %s;", (signal_id,))
        return {
            'action': 'DISCARDED',
            'signal_id': str(signal_id),
            'reason': 'Non-commercial / IGNORE intent'
        }

    raw_text = signal.get('raw_text') or ''
    if not raw_text.strip():
        cur.execute("UPDATE public.facebook_lead_signals SET status = 'DISCARDED' WHERE id = %s;", (signal_id,))
        return {
            'action': 'DISCARDED',
            'signal_id': str(signal_id),
            'reason': 'Empty message content'
        }

    # Step 2: Scoring (Deterministic, no AI)
    score_res = calculate_lead_score(signal)
    lead_score = score_res['total_score']
    lead_tier = score_res['tier']

    # Extract & Normalize Contact & Context Attributes
    phones = signal.get('extracted_phones') or []
    primary_phone = normalize_phone(phones[0]) if phones and len(phones) > 0 else None

    emails = signal.get('extracted_emails') or []
    primary_email = normalize_email(emails[0]) if emails and len(emails) > 0 else None

    meta = signal.get('signal_metadata') or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}

    company_name = meta.get('company')
    full_name = meta.get('customer_name') or signal.get('author_name')
    product_interest = signal.get('product_mention') or meta.get('product') or "Vật liệu / Kỹ thuật xây dựng"
    product_group = signal.get('product_category') or "CONSTRUCTION"
    is_quote_requested = intent in ('REQUEST_QUOTE', 'LOOKING_TO_BUY', 'URGENT_NEED')
    customer_type = 'BUSINESS' if company_name else 'INDIVIDUAL'

    source_id = signal.get('source_id')
    post_id = signal.get('post_id')
    comment_id = signal.get('comment_id')
    author_id = signal.get('author_id')
    detected_at = signal.get('detected_at') or signal.get('created_at')

    fingerprint = compute_dedup_fingerprint(
        phone=primary_phone,
        email=primary_email,
        author_id=author_id,
        source_id=source_id,
        post_id=post_id
    )

    # Step 3: Entity Resolution (Strict Order: phone -> email -> company -> name -> semantic/author)
    resolution, existing_lead, match_rule, match_conf = resolve_entity(
        cur=cur,
        phone=primary_phone,
        email=primary_email,
        company=company_name,
        customer_name=full_name,
        author_id=author_id,
        source_id=source_id,
        post_id=post_id,
        intent=intent
    )

    # Step 4: Lead Creation / Update
    if existing_lead and resolution in ('EXISTING_LEAD', 'EXISTING_CUSTOMER') and match_conf >= 0.8:
        # HIGH CONFIDENCE MERGE INTO EXISTING LEAD
        lead_id = existing_lead['id']
        old_score = existing_lead.get('lead_score', 0)
        old_tier = existing_lead.get('lead_tier', 'LOW')
        new_score = max(old_score, lead_score)

        # Determine new tier
        if new_score >= 80: new_tier = 'VERY_HIGH'
        elif new_score >= 60: new_tier = 'HIGH'
        elif new_score >= 30: new_tier = 'MEDIUM'
        else: new_tier = 'LOW'

        cur.execute("""
            UPDATE public.leads
            SET
                primary_phone = COALESCE(primary_phone, %s),
                primary_email = COALESCE(primary_email, %s),
                full_name = COALESCE(full_name, %s),
                company_name = COALESCE(company_name, %s),
                lead_score = %s,
                lead_tier = %s,
                is_quote_requested = is_quote_requested OR %s,
                resolution = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING *;
        """, (
            primary_phone, primary_email, full_name, company_name,
            new_score, new_tier, is_quote_requested, resolution, lead_id
        ))

        # Step 5: Provenance Mapping in lead_sources
        cur.execute("""
            INSERT INTO public.lead_sources (
                lead_id, source_id, signal_id, raw_item_id,
                origin_type, origin_external_id, origin_url,
                platform, post_id, comment_id, detected_at, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id;
        """, (
            lead_id, source_id, signal_id, signal.get('raw_item_id'),
            signal.get('entity_type', 'POST'), comment_id or post_id or signal_id, None,
            'facebook', post_id, comment_id, detected_at
        ))

        # Step 6: Scoring Audit Record in lead_scores
        cur.execute("""
            INSERT INTO public.lead_scores (
                lead_id, signal_id, intent_score, contact_score,
                profile_score, context_score, total_score, tier,
                scoring_rules_applied, scored_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id;
        """, (
            lead_id, signal_id,
            score_res['intent_score'], score_res['contact_score'],
            score_res['profile_score'], score_res['context_score'],
            lead_score, lead_tier,
            json.dumps(score_res['scoring_rules_applied'])
        ))

        # Step 7: Lead Events Logging (LEAD_UPDATED, LEAD_SCORE_UPDATED)
        event_type = 'LEAD_SCORE_UPDATED' if new_score > old_score else 'LEAD_UPDATED'
        cur.execute("""
            INSERT INTO public.lead_events (
                lead_id, event_type, old_state, new_state,
                triggered_by, notes, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id;
        """, (
            lead_id, event_type,
            json.dumps({'score': old_score, 'tier': old_tier}),
            json.dumps({'score': new_score, 'tier': new_tier, 'signal_id': str(signal_id), 'match_rule': match_rule}),
            'PHASE_6_LEAD_PROCESSOR',
            f'Merged via {match_rule} (confidence {match_conf})'
        ))

        cur.execute("UPDATE public.facebook_lead_signals SET status = 'MERGED' WHERE id = %s;", (signal_id,))

        return {
            'action': 'MERGED',
            'lead_id': str(lead_id),
            'signal_id': str(signal_id),
            'resolution': resolution,
            'match_rule': match_rule,
            'lead_score': new_score,
            'lead_tier': new_tier
        }

    else:
        # LOW CONFIDENCE (POSSIBLE_DUPLICATE) OR BRAND NEW LEAD
        # Do not merge automatically when confidence is low! Create separate record.
        lead_id = uuid.uuid4()
        actual_resolution = 'POSSIBLE_DUPLICATE' if resolution == 'POSSIBLE_DUPLICATE' else 'NEW'

        lead_metadata = {
            'source_text': raw_text[:300],
            'detected_at': str(detected_at),
            'match_rule': match_rule,
            'match_confidence': match_conf
        }
        if existing_lead:
            lead_metadata['possible_duplicate_of'] = str(existing_lead['id'])

        cur.execute("""
            INSERT INTO public.leads (
                id, primary_phone, primary_email, full_name, company_name,
                customer_type, product_interest, product_group, primary_intent,
                status, resolution, lead_score, lead_tier, is_quote_requested,
                dedup_fingerprint, metadata, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, NOW(), NOW()
            ) RETURNING *;
        """, (
            str(lead_id), primary_phone, primary_email, full_name, company_name,
            customer_type, product_interest, product_group, intent,
            'NEW', actual_resolution, lead_score, lead_tier, is_quote_requested,
            fingerprint, json.dumps(lead_metadata)
        ))

        # Step 5: Provenance Mapping in lead_sources
        cur.execute("""
            INSERT INTO public.lead_sources (
                lead_id, source_id, signal_id, raw_item_id,
                origin_type, origin_external_id, origin_url,
                platform, post_id, comment_id, detected_at, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id;
        """, (
            str(lead_id), source_id, signal_id, signal.get('raw_item_id'),
            signal.get('entity_type', 'POST'), comment_id or post_id or signal_id, None,
            'facebook', post_id, comment_id, detected_at
        ))

        # Step 6: Scoring Audit Record in lead_scores
        cur.execute("""
            INSERT INTO public.lead_scores (
                lead_id, signal_id, intent_score, contact_score,
                profile_score, context_score, total_score, tier,
                scoring_rules_applied, scored_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id;
        """, (
            str(lead_id), signal_id,
            score_res['intent_score'], score_res['contact_score'],
            score_res['profile_score'], score_res['context_score'],
            lead_score, lead_tier,
            json.dumps(score_res['scoring_rules_applied'])
        ))

        # Step 7: Lead Events Logging (LEAD_CREATED + LEAD_DUPLICATE_DETECTED if possible duplicate)
        cur.execute("""
            INSERT INTO public.lead_events (
                lead_id, event_type, old_state, new_state,
                triggered_by, notes, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id;
        """, (
            str(lead_id), 'LEAD_CREATED',
            json.dumps({}),
            json.dumps({'score': lead_score, 'tier': lead_tier, 'intent': intent, 'signal_id': str(signal_id)}),
            'PHASE_6_LEAD_PROCESSOR',
            f'Canonical lead created from Facebook {signal.get("entity_type", "POST")}'
        ))

        if actual_resolution == 'POSSIBLE_DUPLICATE':
            cur.execute("""
                INSERT INTO public.lead_events (
                    lead_id, event_type, old_state, new_state,
                    triggered_by, notes, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                RETURNING id;
            """, (
                str(lead_id), 'LEAD_DUPLICATE_DETECTED',
                json.dumps({}),
                json.dumps({'match_rule': match_rule, 'confidence': match_conf, 'suspected_id': str(existing_lead['id'])}),
                'PHASE_6_LEAD_PROCESSOR',
                f'Low confidence match via {match_rule}, kept unmerged to avoid false merge'
            ))

        cur.execute("UPDATE public.facebook_lead_signals SET status = 'CONVERTED_TO_LEAD' WHERE id = %s;", (signal_id,))

        return {
            'action': 'CREATED',
            'lead_id': str(lead_id),
            'signal_id': str(signal_id),
            'resolution': actual_resolution,
            'match_rule': match_rule,
            'lead_score': lead_score,
            'lead_tier': lead_tier
        }

def run_scoring_batch(batch_size: int = 100) -> Dict[str, Any]:
    """
    Batched execution of lead processing.
    """
    conn = psycopg2.connect(DB_URI)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT *
        FROM public.facebook_lead_signals
        WHERE status = 'NEW'
        ORDER BY created_at ASC
        LIMIT %s;
    """, (batch_size,))

    signals = cur.fetchall()
    results = {
        'total_fetched': len(signals),
        'created': 0,
        'merged': 0,
        'discarded': 0,
        'errors': 0,
        'items': []
    }

    for sig in signals:
        try:
            res = process_single_signal(cur, dict(sig))
            conn.commit()
            results['items'].append(res)
            if res['action'] == 'CREATED':
                results['created'] += 1
            elif res['action'] == 'MERGED':
                results['merged'] += 1
            elif res['action'] == 'DISCARDED':
                results['discarded'] += 1
        except Exception as e:
            conn.rollback()
            results['errors'] += 1
            results['items'].append({
                'action': 'ERROR',
                'signal_id': str(sig.get('id')),
                'error': str(e)
            })

    cur.close()
    conn.close()
    return results

if __name__ == '__main__':
    print("Executing Phase 6 Lead Management batch...")
    summary = run_scoring_batch()
    print(json.dumps(summary, indent=2))
