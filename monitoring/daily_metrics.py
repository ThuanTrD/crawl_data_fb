"""
Facebook Lead Intelligence V1 - Phase 7: Daily Source Quality Metrics Calculator

Calculates per-source daily metrics:
- posts/day
- relevant_posts/day
- lead/day
- qualified_lead/day
- spam_rate
- duplicate_rate
- error_rate

Rule: Does NOT output subjective "best source" rankings.
Only delivers raw, unbiased metrics for human operators to evaluate.
"""

from datetime import date
from typing import Dict, Any, List
import psycopg2

def calculate_daily_source_metrics(cur, target_date: date = None) -> List[Dict[str, Any]]:
    """
    Computes daily quality metrics for each Facebook source and upserts into facebook_source_metrics.
    """
    if target_date is None:
        target_date = date.today()

    cur.execute("""
        SELECT id, name, external_id, status 
        FROM public.facebook_sources 
        ORDER BY name ASC;
    """)
    sources = cur.fetchall()
    metrics_list = []

    for s in sources:
        source_id = str(s['id'])

        # 1. Posts collected today
        cur.execute("""
            SELECT count(*) as posts_count 
            FROM public.facebook_posts 
            WHERE source_id = %s AND DATE(COALESCE(crawled_at, created_time)) = %s;
        """, (source_id, target_date))
        posts_count = cur.fetchone()['posts_count']

        # 2. Relevant posts today
        cur.execute("""
            SELECT count(*) as relevant_count 
            FROM public.facebook_lead_signals 
            WHERE source_id = %s 
              AND DATE(created_at) = %s 
              AND intent != 'IGNORE';
        """, (source_id, target_date))
        relevant_posts_count = cur.fetchone()['relevant_count']

        # 3. Leads generated today
        cur.execute("""
            SELECT count(*) as leads_count 
            FROM public.lead_sources ls
            JOIN public.leads l ON l.id = ls.lead_id
            WHERE ls.source_id = %s AND DATE(ls.created_at) = %s;
        """, (source_id, target_date))
        leads_count = cur.fetchone()['leads_count']

        # 4. Qualified leads today (HIGH, VERY_HIGH, HOT)
        cur.execute("""
            SELECT count(*) as qualified_count 
            FROM public.lead_sources ls
            JOIN public.leads l ON l.id = ls.lead_id
            WHERE ls.source_id = %s 
              AND DATE(ls.created_at) = %s 
              AND l.lead_tier IN ('HIGH', 'VERY_HIGH', 'HOT');
        """, (source_id, target_date))
        qualified_leads_count = cur.fetchone()['qualified_count']

        # 5. Duplicates detected
        cur.execute("""
            SELECT count(*) as dup_count 
            FROM public.facebook_posts 
            WHERE source_id = %s 
              AND DATE(COALESCE(crawled_at, created_time)) = %s 
              AND is_duplicate_content = true;
        """, (source_id, target_date))
        dup_count = cur.fetchone()['dup_count']

        # 6. Errors encountered
        cur.execute("""
            SELECT count(*) as err_count 
            FROM public.facebook_errors 
            WHERE source_id = %s AND DATE(created_at) = %s;
        """, (source_id, target_date))
        err_count = cur.fetchone()['err_count']

        # Computed rates
        spam_rate = 0.0
        if posts_count > 0:
            non_relevant = max(0, posts_count - relevant_posts_count)
            spam_rate = round(non_relevant / posts_count, 4)

        duplicate_rate = 0.0
        if posts_count > 0:
            duplicate_rate = round(dup_count / posts_count, 4)

        error_rate = 0.0
        total_attempts = posts_count + err_count
        if total_attempts > 0:
            error_rate = round(err_count / total_attempts, 4)

        # Upsert into facebook_source_metrics
        cur.execute("""
            INSERT INTO public.facebook_source_metrics (
                source_id, metric_date, total_posts_collected, total_comments_collected,
                total_leads_generated, total_hot_leads, total_errors, avg_latency_ms,
                posts_count, relevant_posts_count, leads_count, qualified_leads_count,
                spam_rate, duplicate_rate, error_rate, updated_at
            ) VALUES (
                %s, %s, %s, 0,
                %s, %s, %s, 0,
                %s, %s, %s, %s,
                %s, %s, %s, NOW()
            )
            ON CONFLICT (source_id, metric_date) DO UPDATE SET
                total_posts_collected = EXCLUDED.total_posts_collected,
                total_leads_generated = EXCLUDED.total_leads_generated,
                total_hot_leads = EXCLUDED.total_hot_leads,
                total_errors = EXCLUDED.total_errors,
                posts_count = EXCLUDED.posts_count,
                relevant_posts_count = EXCLUDED.relevant_posts_count,
                leads_count = EXCLUDED.leads_count,
                qualified_leads_count = EXCLUDED.qualified_leads_count,
                spam_rate = EXCLUDED.spam_rate,
                duplicate_rate = EXCLUDED.duplicate_rate,
                error_rate = EXCLUDED.error_rate,
                updated_at = NOW();
        """, (
            source_id, target_date, posts_count,
            leads_count, qualified_leads_count, err_count,
            posts_count, relevant_posts_count, leads_count, qualified_leads_count,
            spam_rate, duplicate_rate, error_rate
        ))

        metrics_list.append({
            'source_id': source_id,
            'source_name': s['name'],
            'status': s['status'],
            'metric_date': str(target_date),
            'posts_per_day': posts_count,
            'relevant_posts_per_day': relevant_posts_count,
            'lead_per_day': leads_count,
            'qualified_lead_per_day': qualified_leads_count,
            'spam_rate': float(spam_rate),
            'duplicate_rate': float(duplicate_rate),
            'error_rate': float(error_rate)
        })

    return metrics_list
