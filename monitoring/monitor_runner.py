"""
Facebook Lead Intelligence V1 - Phase 7: Central Monitoring & Recovery Runner

Orchestrates:
1. Controlled source recovery (reactivating expired backoff)
2. Health summary aggregation (10 core metrics)
3. Daily source quality metric calculation
4. Incident evaluation & Telegram alert dispatch
5. Audit logging in facebook_processing_jobs
"""

import os
import sys
import json
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.append(os.path.dirname(__file__))
from state_machine import recover_eligible_sources
from health_checker import generate_health_summary, evaluate_alert_conditions
from daily_metrics import calculate_daily_source_metrics
from alert_dispatcher import format_telegram_alert, format_health_summary_message, dispatch_telegram_message

DB_URI = os.getenv(
    'SUPABASE_DB_URI',
    'postgresql://postgres.qllwfecwujzhuwexrlqi:tRpWn0s3s8OxILhQ@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres'
)

def run_monitoring_cycle() -> Dict[str, Any]:
    """Executes a full monitoring, recovery, and alerting pass"""
    conn = psycopg2.connect(DB_URI)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Controlled Recovery
    recovered_sources = recover_eligible_sources(cur)
    conn.commit()

    # 2. Health Summary
    health = generate_health_summary(cur)

    # 3. Daily Metrics
    daily = calculate_daily_source_metrics(cur)
    conn.commit()

    # 4. Evaluate Alert Conditions
    alerts = evaluate_alert_conditions(health)

    # 5. Dispatch Alerts
    dispatched_alerts = 0
    for alert in alerts:
        msg = format_telegram_alert(alert)
        if dispatch_telegram_message(msg):
            dispatched_alerts += 1

    # 6. Audit in facebook_processing_jobs
    cur.execute("""
        INSERT INTO public.facebook_processing_jobs (
            job_type, status, items_total, items_processed, items_failed,
            execution_context, started_at, completed_at
        ) VALUES (
            'MONITORING_HEALTH_CHECK', 'COMPLETED', %s, %s, %s,
            %s, NOW() - INTERVAL '1 second', NOW()
        );
    """, (
        health.get('total_sources', 0),
        len(recovered_sources),
        len(alerts),
        json.dumps({
            'health': health,
            'alerts_count': len(alerts),
            'recovered_count': len(recovered_sources)
        })
    ))
    conn.commit()

    cur.close()
    conn.close()

    return {
        'status': 'HEALTHY' if len(alerts) == 0 else 'WARNING',
        'recovered_sources': recovered_sources,
        'health_summary': health,
        'alerts_triggered': alerts,
        'daily_metrics_count': len(daily)
    }

if __name__ == '__main__':
    res = run_monitoring_cycle()
    print(json.dumps(res, indent=2))
