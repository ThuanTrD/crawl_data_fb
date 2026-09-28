"""
Facebook Lead Intelligence V1 - Phase 7: Health Summary & Alert Evaluator

Aggregates real-time health metrics:
- sources_active
- sources_paused
- sources_rate_limited
- posts_collected
- posts_relevant
- leads_detected
- qualified_leads
- errors
- 429_count
- AI_errors

Evaluates 8 Telegram Alert triggers.
"""

from typing import Dict, Any, List

def generate_health_summary(cur) -> Dict[str, Any]:
    """
    Queries database for complete operational health summary.
    """
    # 1. Sources breakdown
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE status = 'ACTIVE' AND enabled = true) as sources_active,
            COUNT(*) FILTER (WHERE status = 'PAUSED') as sources_paused,
            COUNT(*) FILTER (WHERE status = 'RATE_LIMITED') as sources_rate_limited,
            COUNT(*) as total_sources
        FROM public.facebook_sources;
    """)
    src_stats = cur.fetchone()

    # 2. Posts & Relevance
    cur.execute("SELECT count(*) as posts_collected FROM public.facebook_posts;")
    posts_collected = cur.fetchone()['posts_collected']

    cur.execute("""
        SELECT count(*) as posts_relevant 
        FROM public.facebook_lead_signals 
        WHERE intent != 'IGNORE';
    """)
    posts_relevant = cur.fetchone()['posts_relevant']

    # 3. Signals & Qualified Leads
    cur.execute("SELECT count(*) as leads_detected FROM public.facebook_lead_signals;")
    leads_detected = cur.fetchone()['leads_detected']

    cur.execute("""
        SELECT count(*) as qualified_leads 
        FROM public.leads 
        WHERE lead_tier IN ('HIGH', 'VERY_HIGH', 'HOT');
    """)
    qualified_leads = cur.fetchone()['qualified_leads']

    # 4. Errors in last 24 hours
    cur.execute("""
        SELECT 
            COUNT(*) as total_errors,
            COUNT(*) FILTER (WHERE error_code = '429' OR error_category = 'RATE_LIMIT') as count_429,
            COUNT(*) FILTER (WHERE error_category = 'AI_FAILURE') as count_ai_errors,
            COUNT(*) FILTER (WHERE error_code = '401' OR error_category = 'AUTHENTICATION') as count_401,
            COUNT(*) FILTER (WHERE error_code = '403' OR error_category = 'PERMISSION') as count_403
        FROM public.facebook_errors
        WHERE created_at >= NOW() - INTERVAL '24 hours';
    """)
    err_stats = cur.fetchone()

    # 5. Processing Backlog
    cur.execute("""
        SELECT 
            (SELECT count(*) FROM public.facebook_raw_items WHERE processing_status = 'PENDING') +
            (SELECT count(*) FROM public.facebook_lead_signals WHERE status = 'NEW') as processing_backlog;
    """)
    backlog = cur.fetchone()['processing_backlog']

    # 6. Global Kill Switch State
    cur.execute("SELECT flag_value FROM public.system_flags WHERE id = 'FB_GLOBAL_COLLECTION_ENABLED';")
    flag_row = cur.fetchone()
    global_enabled = True
    if flag_row:
        val = flag_row['flag_value']
        global_enabled = (val is True or str(val).lower() == 'true')

    # 7. Collector Liveness (Last collection activity)
    cur.execute("""
        SELECT MAX(last_successful_collected_at) as last_success
        FROM public.facebook_sources
        WHERE status = 'ACTIVE' AND enabled = true;
    """)
    last_success_row = cur.fetchone()
    last_success = last_success_row['last_success'] if last_success_row else None

    collector_dead = False
    if src_stats['sources_active'] > 0 and last_success is None:
        # Never collected yet or stale
        collector_dead = False
    elif src_stats['sources_active'] > 0 and last_success:
        import datetime
        diff_hours = (datetime.datetime.now(datetime.timezone.utc) - last_success).total_seconds() / 3600
        if diff_hours > 2.0:
            collector_dead = True

    return {
        'sources_active': src_stats['sources_active'],
        'sources_paused': src_stats['sources_paused'],
        'sources_rate_limited': src_stats['sources_rate_limited'],
        'total_sources': src_stats['total_sources'],
        'posts_collected': posts_collected,
        'posts_relevant': posts_relevant,
        'leads_detected': leads_detected,
        'qualified_leads': qualified_leads,
        'errors': err_stats['total_errors'],
        '429_count': err_stats['count_429'],
        'AI_errors': err_stats['count_ai_errors'],
        'count_401': err_stats['count_401'],
        'count_403': err_stats['count_403'],
        'processing_backlog': backlog,
        'global_collection_enabled': global_enabled,
        'collector_dead': collector_dead
    }

def evaluate_alert_conditions(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Evaluates incident triggers for Telegram alerting.
    """
    alerts = []

    # 1. Nhiều source bị rate limit
    if summary.get('sources_rate_limited', 0) >= 3:
        alerts.append({
            'level': 'WARNING',
            'type': 'MULTIPLE_SOURCES_RATE_LIMITED',
            'message': f"⚠️ Cảnh báo: {summary['sources_rate_limited']} sources đang bị Rate Limited (429)!"
        })

    # 2. Source permission error
    if summary.get('count_403', 0) > 0:
        alerts.append({
            'level': 'CRITICAL',
            'type': 'SOURCE_PERMISSION_ERROR',
            'message': f"⛔ Lỗi Phân Quyền (403 Forbidden): Có {summary['count_403']} lỗi quyền truy cập Facebook source trong 24h qua."
        })

    # 3. Authentication error
    if summary.get('count_401', 0) > 0:
        alerts.append({
            'level': 'CRITICAL',
            'type': 'AUTHENTICATION_ERROR',
            'message': f"🔑 Lỗi Xác Thực (401 Unauthorized): Facebook Token hết hạn hoặc không hợp lệ ({summary['count_401']} lỗi)."
        })

    # 4. Processing backlog quá lớn
    if summary.get('processing_backlog', 0) > 200:
        alerts.append({
            'level': 'WARNING',
            'type': 'QUEUE_BACKLOG_HIGH',
            'message': f"📦 Hàng đợi xử lý quá tải: {summary['processing_backlog']} items đang tồn đọng!"
        })

    # 5. AI failure tăng mạnh
    if summary.get('AI_errors', 0) >= 5:
        alerts.append({
            'level': 'WARNING',
            'type': 'AI_FAILURE_SPIKE',
            'message': f"🤖 Cổng AI gặp sự cố: {summary['AI_errors']} lỗi AI trong 24h qua. Hệ thống đang bật Rule-based Fallback."
        })

    # 6. Collector chết
    if summary.get('collector_dead', False):
        alerts.append({
            'level': 'CRITICAL',
            'type': 'COLLECTOR_STALLED',
            'message': "🚨 Collector không thu thập dữ liệu mới trong hơn 2 giờ qua trong khi nguồn đang ACTIVE!"
        })

    # 7. Global collection bị disable
    if not summary.get('global_collection_enabled', True):
        alerts.append({
            'level': 'ALERT',
            'type': 'GLOBAL_COLLECTION_DISABLED',
            'message': "🛑 Kill Switch Kích Hoạt: Toàn bộ tiến trình thu thập Facebook đã bị TẮT (FB_GLOBAL_COLLECTION_ENABLED = FALSE)."
        })

    return alerts
