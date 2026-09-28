"""
Facebook Lead Intelligence V1 - Phase 5: AI Lead Detection & Extraction Pipeline
"""

import sys
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

sys.path.append('/home/ADMIN/intelligence')
from keyword_filter import check_keyword_filter
from qwen_detector import detect_lead

DB_URI = os.getenv(
    'DATABASE_URL',
    'postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres'
)

class AILeadDetectionPipeline:
    def __init__(self, db_uri: str = DB_URI):
        self.db_uri = db_uri

    def get_connection(self):
        return psycopg2.connect(self.db_uri)

    def process_item(self, item: Dict[str, Any], cur) -> Optional[Dict[str, Any]]:
        """
        Processes a single post or comment through Keyword Filter -> Context Bundling -> AI Detection -> Storage.
        """
        entity_type = item.get('entity_type', 'POST')
        text = item.get('message') or item.get('raw_text') or ''
        source_id = item.get('source_id')
        raw_item_id = item.get('raw_item_id')
        author_id = item.get('author_id')
        author_name = item.get('author_name')

        if entity_type == 'POST':
            post_id = item.get('post_id')
            comment_id = None
            entity_id = post_id
            context = None
        else: # COMMENT or REPLY
            post_id = item.get('post_id')
            comment_id = item.get('comment_id')
            entity_id = comment_id
            
            # Retrieve Parent Post context
            context = None
            if post_id:
                cur.execute("SELECT message, author_name FROM public.facebook_posts WHERE post_id = %s LIMIT 1", (post_id,))
                p_row = cur.fetchone()
                if p_row and p_row.get('message'):
                    context = f"BÀI ĐĂNG GỐC CỦA {p_row.get('author_name') or 'Tác giả'}:\n{p_row.get('message')}"

        # 1. Keyword Filter (Filter before calling AI)
        combined_text_for_filter = f"{context or ''} {text}"
        kw_res = check_keyword_filter(combined_text_for_filter)
        if not kw_res['matched']:
            # Non-construction noise: do not call AI
            return {
                'entity_id': entity_id,
                'entity_type': entity_type,
                'status': 'SKIPPED_NO_KEYWORDS',
                'signal_id': None
            }

        # 2. AI Lead Detection (Qwen AI with deterministic fallback & zero-hallucination guardrails)
        ai_res = detect_lead(text, context)
        lead_data = ai_res['data']

        # 3. Format fields for PostgreSQL
        intent = lead_data['intent']
        category = lead_data['category']
        product = lead_data['product']
        confidence = lead_data['confidence']
        ai_model = ai_res['ai_model']
        ai_raw = ai_res['ai_raw_response']

        phones_arr = [lead_data['phone']] if lead_data['phone'] else []
        emails_arr = [lead_data['email']] if lead_data['email'] else []

        signal_metadata = {
            'matched_groups': kw_res['matched_groups'],
            'matched_keywords': kw_res['matched_keywords'],
            'commercial_intent': lead_data['commercial_intent'],
            'construction_relevant': lead_data['construction_relevant'],
            'quantity': lead_data['quantity'],
            'requirement': lead_data['requirement'],
            'location': lead_data['location'],
            'budget': lead_data['budget'],
            'timeline': lead_data['timeline'],
            'customer_name': lead_data['customer_name'],
            'company': lead_data['company'],
            'validation_errors': ai_res.get('validation_errors', []),
            'context_attached': bool(context)
        }

        # 4. Insert into facebook_lead_signals
        cur.execute("""
            INSERT INTO public.facebook_lead_signals (
                raw_item_id, source_id, entity_type, entity_id, post_id, comment_id,
                author_id, author_name, raw_text, intent, product_category, product_mention,
                extracted_phones, extracted_emails, confidence_score, extraction_method,
                ai_model, ai_prompt_version, signal_metadata, ai_raw_response, status, detected_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, 'v1.0', %s, %s, 'NEW', NOW()
            ) RETURNING id;
        """, (
            raw_item_id, source_id, entity_type, entity_id, post_id, comment_id,
            author_id, author_name, text, intent, category, product,
            phones_arr, emails_arr, confidence,
            'QWEN_AI' if ai_model == 'qwen3-vl-30b' else 'HYBRID',
            ai_model, Json(signal_metadata), Json(ai_raw),
        ))
        signal_id = cur.fetchone()['id']

        return {
            'entity_id': entity_id,
            'entity_type': entity_type,
            'status': 'DETECTED',
            'signal_id': str(signal_id),
            'intent': intent,
            'product': product,
            'phone': lead_data['phone'],
            'email': lead_data['email'],
            'confidence': confidence,
            'commercial': lead_data['commercial_intent']
        }

    def run_batch(self, limit: int = 50) -> Dict[str, Any]:
        conn = self.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        summary = {
            'job_id': None,
            'total_evaluated': 0,
            'signals_created': 0,
            'skipped_keywords': 0,
            'commercial_leads': 0,
            'signals': []
        }

        try:
            # Start Job
            cur.execute("""
                INSERT INTO public.facebook_processing_jobs (
                    job_type, status, items_total, started_at
                ) VALUES ('INTENT_EXTRACTION', 'RUNNING', 0, NOW())
                RETURNING id;
            """)
            job_id = cur.fetchone()['id']
            summary['job_id'] = str(job_id)
            conn.commit()

            # Find posts without signals
            cur.execute("""
                SELECT p.id as post_uuid, p.raw_item_id, p.source_id, p.post_id, p.author_id, p.author_name, p.message
                FROM public.facebook_posts p
                LEFT JOIN public.facebook_lead_signals s ON s.entity_id = p.post_id
                WHERE s.id IS NULL
                ORDER BY p.created_time DESC
                LIMIT %s;
            """, (limit,))
            candidate_posts = cur.fetchall()

            # Find comments without signals
            cur.execute("""
                SELECT c.id as comment_uuid, c.raw_item_id, c.source_id, c.post_id, c.comment_id, c.author_id, c.author_name, c.message
                FROM public.facebook_comments c
                LEFT JOIN public.facebook_lead_signals s ON s.entity_id = c.comment_id
                WHERE s.id IS NULL
                ORDER BY c.created_time DESC
                LIMIT %s;
            """, (limit,))
            candidate_comments = cur.fetchall()

            all_items = []
            for cp in candidate_posts:
                all_items.append({
                    'entity_type': 'POST',
                    'post_id': cp['post_id'],
                    'message': cp['message'],
                    'source_id': cp['source_id'],
                    'raw_item_id': cp['raw_item_id'],
                    'author_id': cp['author_id'],
                    'author_name': cp['author_name']
                })
            for cc in candidate_comments:
                all_items.append({
                    'entity_type': 'COMMENT',
                    'post_id': cc['post_id'],
                    'comment_id': cc['comment_id'],
                    'message': cc['message'],
                    'source_id': cc['source_id'],
                    'raw_item_id': cc['raw_item_id'],
                    'author_id': cc['author_id'],
                    'author_name': cc['author_name']
                })

            summary['total_evaluated'] = len(all_items)

            for item in all_items:
                res = self.process_item(item, cur)
                if res:
                    if res['status'] == 'DETECTED':
                        summary['signals_created'] += 1
                        if res.get('commercial'):
                            summary['commercial_leads'] += 1
                        summary['signals'].append(res)
                    elif res['status'] == 'SKIPPED_NO_KEYWORDS':
                        summary['skipped_keywords'] += 1
                conn.commit()

            # Complete Job
            cur.execute("""
                UPDATE public.facebook_processing_jobs
                SET status = 'COMPLETED',
                    items_processed = %s,
                    items_failed = 0,
                    completed_at = NOW()
                WHERE id = %s;
            """, (summary['signals_created'] + summary['skipped_keywords'], job_id))
            conn.commit()

        except Exception as e:
            conn.rollback()
            if summary['job_id']:
                cur.execute("""
                    UPDATE public.facebook_processing_jobs
                    SET status = 'FAILED',
                        error_message = %s,
                        completed_at = NOW()
                    WHERE id = %s;
                """, (str(e), summary['job_id']))
                conn.commit()
            raise e
        finally:
            cur.close()
            conn.close()

        return summary

if __name__ == '__main__':
    pipeline = AILeadDetectionPipeline()
    print("AILeadDetectionPipeline ready.")
