"""
Facebook Lead Intelligence V1 - Phase 4: Database Deduplication & Storage Engine
"""

import sys
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

sys.path.append('/home/ADMIN/normalizer')
from normalizer import normalize_raw_item

DB_URI = os.getenv(
    'DATABASE_URL',
    'postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres'
)

class NormalizerDedupEngine:
    def __init__(self, db_uri: str = DB_URI):
        self.db_uri = db_uri

    def get_connection(self):
        return psycopg2.connect(self.db_uri)

    def process_raw_items_batch(self, limit: int = 50, raw_items_list: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Processes a batch of raw items from database or provided list.
        Executes normalization, dual deduplication, database persistence, and dead-letter routing.
        """
        conn = self.get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        results = {
            'job_id': None,
            'total_items': 0,
            'processed_posts': 0,
            'processed_comments': 0,
            'skipped_duplicate_ids': 0,
            'detected_duplicate_contents': 0,
            'failed_dead_letter': 0,
            'queue_ready_items': [],
            'errors': []
        }

        try:
            # 1. Start Job Record with status 'RUNNING'
            cur.execute("""
                INSERT INTO public.facebook_processing_jobs (
                    job_type, status, items_total, started_at
                ) VALUES ('RAW_NORMALIZATION', 'RUNNING', 0, NOW())
                RETURNING id;
            """)
            job_id = cur.fetchone()['id']
            results['job_id'] = str(job_id)
            conn.commit()

            # 2. Fetch pending items if not supplied
            if raw_items_list is None:
                cur.execute("""
                    SELECT id, source_id, item_type, external_item_id, raw_payload, received_at, processing_attempts
                    FROM public.facebook_raw_items
                    WHERE processing_status = 'PENDING'
                    ORDER BY received_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED;
                """, (limit,))
                items_to_process = cur.fetchall()
            else:
                items_to_process = raw_items_list

            results['total_items'] = len(items_to_process)
            
            # Update job total
            cur.execute("""
                UPDATE public.facebook_processing_jobs
                SET items_total = %s
                WHERE id = %s
            """, (results['total_items'], job_id))
            conn.commit()

            for item in items_to_process:
                raw_item_id = item.get('id')
                source_id = item.get('source_id')
                
                # A. Normalization
                norm = normalize_raw_item(item)
                if not norm['success']:
                    # Dead-letter path
                    results['failed_dead_letter'] += 1
                    err_msg = norm.get('message', 'Unknown normalization error')
                    results['errors'].append({'raw_item_id': str(raw_item_id), 'error': err_msg})
                    
                    if raw_item_id:
                        cur.execute("""
                            UPDATE public.facebook_raw_items
                            SET processing_status = 'FAILED',
                                processing_attempts = processing_attempts + 1,
                                last_error = %s
                            WHERE id = %s
                        """, (err_msg, raw_item_id))

                    cur.execute("""
                        INSERT INTO public.facebook_errors (
                            source_id, raw_item_id, error_category, error_code, error_message, request_context
                        ) VALUES (%s, %s, 'DATA_PARSE_ERROR', 'NORMALIZATION_FAILED', %s, %s)
                    """, (source_id, raw_item_id, err_msg, Json(item.get('raw_payload') or {})))
                    conn.commit()
                    continue

                category = norm['category']
                external_id = norm['external_id']
                content_hash = norm['content_hash']
                content = norm['content']

                # B. Dedup Check 1: External ID
                if category == 'POST':
                    cur.execute("SELECT id FROM public.facebook_posts WHERE post_id = %s LIMIT 1", (external_id,))
                    existing_external = cur.fetchone()
                else:
                    cur.execute("SELECT id FROM public.facebook_comments WHERE comment_id = %s LIMIT 1", (external_id,))
                    existing_external = cur.fetchone()

                if existing_external:
                    # Item already stored! Mark raw item as PROCESSED with duplicate external ID
                    results['skipped_duplicate_ids'] += 1
                    if raw_item_id:
                        cur.execute("""
                            UPDATE public.facebook_raw_items
                            SET processing_status = 'PROCESSED',
                                last_error = 'DUPLICATE_EXTERNAL_ID',
                                processed_at = NOW()
                            WHERE id = %s
                        """, (raw_item_id,))
                        conn.commit()
                    continue

                # C. Dedup Check 2: Content Hash
                is_duplicate_content = False
                duplicate_of_id = None

                if content and len(content) > 0:
                    if category == 'POST':
                        cur.execute("SELECT id FROM public.facebook_posts WHERE content_hash = %s LIMIT 1", (content_hash,))
                    else:
                        cur.execute("SELECT id FROM public.facebook_comments WHERE content_hash = %s LIMIT 1", (content_hash,))
                    
                    content_match = cur.fetchone()
                    if content_match:
                        is_duplicate_content = True
                        duplicate_of_id = content_match['id']
                        results['detected_duplicate_contents'] += 1

                # D. Store in PostgreSQL
                target_record_id = None
                metadata_payload = {
                    'normalized_at': datetime.now(timezone.utc).isoformat(),
                    'raw_payload': norm['raw_payload'],
                    'detected_language': norm['language'],
                    'content_hash': content_hash,
                    'is_duplicate_content': is_duplicate_content,
                    'duplicate_of_id': str(duplicate_of_id) if duplicate_of_id else None
                }

                if category == 'POST':
                    page_id = str(norm['raw_payload'].get('page_id') or source_id)
                    cur.execute("""
                        INSERT INTO public.facebook_posts (
                            raw_item_id, source_id, post_id, page_id, author_id, author_name,
                            message, permalink_url, created_time, reactions_count, comments_count, shares_count,
                            content_hash, language, is_duplicate_content, duplicate_of_id, metadata
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (post_id) DO UPDATE SET
                            updated_at = NOW(),
                            reactions_count = EXCLUDED.reactions_count,
                            comments_count = EXCLUDED.comments_count,
                            shares_count = EXCLUDED.shares_count
                        RETURNING id;
                    """, (
                        raw_item_id, source_id, external_id, page_id, norm['author_id'], norm['author_name'],
                        norm['content'], norm['source_url'], norm['published_at'], norm['reactions_count'],
                        norm['comments_count'], norm['shares_count'], content_hash, norm['language'],
                        is_duplicate_content, duplicate_of_id, Json(metadata_payload)
                    ))
                    target_record_id = cur.fetchone()['id']
                    results['processed_posts'] += 1

                else: # COMMENT or REPLY
                    comment_type = 'REPLY' if category == 'REPLY' else 'COMMENT'
                    cur.execute("""
                        INSERT INTO public.facebook_comments (
                            raw_item_id, source_id, post_id, comment_id, parent_comment_id,
                            author_id, author_name, message, created_time, like_count,
                            content_hash, language, comment_type, is_duplicate_content, duplicate_of_id, metadata
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (comment_id) DO NOTHING
                        RETURNING id;
                    """, (
                        raw_item_id, source_id, norm['post_id'], external_id, norm['parent_comment_id'],
                        norm['author_id'], norm['author_name'], norm['content'], norm['published_at'],
                        norm['reactions_count'], content_hash, norm['language'], comment_type,
                        is_duplicate_content, duplicate_of_id, Json(metadata_payload)
                    ))
                    row = cur.fetchone()
                    if row:
                        target_record_id = row['id']
                    results['processed_comments'] += 1

                # E. Update raw item status
                if raw_item_id:
                    cur.execute("""
                        UPDATE public.facebook_raw_items
                        SET processing_status = 'PROCESSED',
                            processed_at = NOW(),
                            last_error = NULL
                        WHERE id = %s
                    """, (raw_item_id,))

                # F. Queue ready item
                results['queue_ready_items'].append({
                    'id': str(target_record_id) if target_record_id else None,
                    'raw_item_id': str(raw_item_id) if raw_item_id else None,
                    'source_id': str(source_id),
                    'category': category,
                    'external_id': external_id,
                    'post_id': norm['post_id'],
                    'parent_comment_id': norm['parent_comment_id'],
                    'author_name': norm['author_name'],
                    'content': norm['content'],
                    'content_hash': content_hash,
                    'language': norm['language'],
                    'is_duplicate_content': is_duplicate_content,
                    'duplicate_of_id': str(duplicate_of_id) if duplicate_of_id else None,
                    'created_time': norm['published_at']
                })
                conn.commit()

            # Complete Job with status 'COMPLETED'
            cur.execute("""
                UPDATE public.facebook_processing_jobs
                SET status = 'COMPLETED',
                    items_processed = %s,
                    items_failed = %s,
                    completed_at = NOW()
                WHERE id = %s
            """, (results['processed_posts'] + results['processed_comments'] + results['skipped_duplicate_ids'],
                  results['failed_dead_letter'], job_id))
            conn.commit()

        except Exception as e:
            conn.rollback()
            if results['job_id']:
                cur.execute("""
                    UPDATE public.facebook_processing_jobs
                    SET status = 'FAILED',
                        error_message = %s,
                        completed_at = NOW()
                    WHERE id = %s
                """, (str(e), results['job_id']))
                conn.commit()
            raise e
        finally:
            cur.close()
            conn.close()

        return results

if __name__ == '__main__':
    engine = NormalizerDedupEngine()
    print("NormalizerDedupEngine initialized successfully.")
