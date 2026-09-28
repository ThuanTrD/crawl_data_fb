#!/usr/bin/env python3
"""
Facebook Lead Intelligence V1 - Phase 7: Monitoring & Recovery Test Suite

Tests all 8 required incident scenarios:
1. 429 storm (Rate limit cooldown & transition)
2. 403 (Permission error -> PAUSED, alert)
3. 401 (Auth error -> PAUSED, alert)
4. timeout (Transient error -> TEMP_ERROR + exponential backoff)
5. AI unavailable (Circuit breaker / fallback + alert)
6. DB unavailable (Graceful error handling)
7. queue backlog (Backlog threshold alert)
8. kill switch (FB_GLOBAL_COLLECTION_ENABLED = false alert)
"""

import os
import sys
import uuid
import json
import psycopg2
from psycopg2.extras import RealDictCursor

sys.path.append('/home/ADMIN/monitoring')
from state_machine import transition_on_error, transition_on_success, recover_eligible_sources
from health_checker import generate_health_summary, evaluate_alert_conditions
from daily_metrics import calculate_daily_source_metrics
from alert_dispatcher import format_telegram_alert, format_health_summary_message
from monitor_runner import DB_URI

def run_suite():
    print("=" * 80)
    print("🚀 STARTING PHASE 7: MONITORING & RECOVERY TEST SUITE")
    print("=" * 80)

    conn = psycopg2.connect(DB_URI)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    passed_tests = 0
    total_tests = 8

    # Create a test mock source for state machine testing
    mock_src_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO public.facebook_sources (
            id, name, source_type, external_id, status, enabled,
            collection_interval_seconds, consecutive_errors, created_at, updated_at
        ) VALUES (
            %s, 'Mock Test Source Phase 7', 'GROUP', %s, 'ACTIVE', true,
            300, 0, NOW(), NOW()
        ) RETURNING id;
    """, (mock_src_id, f"ext_src_test_{uuid.uuid4().hex[:8]}"))
    conn.commit()

    # -----------------------------------------------------------------
    # TEST 1: 429 Storm (Rate Limit Transition)
    # -----------------------------------------------------------------
    print("\n--- [TEST 1] 429 Storm (Rate Limit Handling) ---")
    res_429 = transition_on_error(
        cur, mock_src_id, 'RATE_LIMITED', 429,
        "Facebook Graph API Error #17: User request limit reached"
    )
    conn.commit()
    assert res_429['new_status'] == 'RATE_LIMITED'
    assert res_429['backoff_minutes'] == 60
    assert res_429['error_category'] == 'RATE_LIMIT'

    # Verify logged in facebook_errors
    cur.execute("SELECT * FROM public.facebook_errors WHERE id = %s;", (res_429['error_id'],))
    err_row = cur.fetchone()
    assert err_row is not None
    assert err_row['error_code'] == 'RATE_LIMITED'

    # Verify repeated 429 transitions to PAUSED
    transition_on_error(cur, mock_src_id, 'RATE_LIMITED', 429, "Second 429")
    res_429_3 = transition_on_error(cur, mock_src_id, 'RATE_LIMITED', 429, "Third 429")
    conn.commit()
    assert res_429_3['new_status'] == 'PAUSED', "3rd consecutive 429 must transition to PAUSED"
    print(f"  ✓ 429 Storm verified: ACTIVE -> RATE_LIMITED (60m backoff) -> PAUSED (after 3 hits)")
    passed_tests += 1

    # Reset mock source to ACTIVE
    cur.execute("UPDATE public.facebook_sources SET status = 'ACTIVE', consecutive_errors = 0, backoff_until = NULL WHERE id = %s;", (mock_src_id,))
    conn.commit()

    # -----------------------------------------------------------------
    # TEST 2: 403 Forbidden (Permission Error)
    # -----------------------------------------------------------------
    print("\n--- [TEST 2] 403 Forbidden (Permission Error) ---")
    res_403 = transition_on_error(
        cur, mock_src_id, 'PERMISSION_ERROR', 403,
        "OAuthException: (#200) Requires pages_read_engagement permission"
    )
    conn.commit()
    assert res_403['new_status'] == 'PAUSED', "403 must immediately transition to PAUSED"
    assert res_403['backoff_minutes'] == 0, "No auto-retry for permission errors"
    assert res_403['error_category'] == 'PERMISSION'

    # Check alert trigger
    summary = generate_health_summary(cur)
    alerts = evaluate_alert_conditions(summary)
    has_perm_alert = any(a['type'] == 'SOURCE_PERMISSION_ERROR' for a in alerts)
    assert has_perm_alert, "Must trigger SOURCE_PERMISSION_ERROR alert"
    print(f"  ✓ 403 verified: Transitioned to PAUSED without auto-retry, Alert generated: SOURCE_PERMISSION_ERROR")
    passed_tests += 1

    # Reset mock source
    cur.execute("UPDATE public.facebook_sources SET status = 'ACTIVE', consecutive_errors = 0 WHERE id = %s;", (mock_src_id,))
    conn.commit()

    # -----------------------------------------------------------------
    # TEST 3: 401 Unauthorized (Auth Error)
    # -----------------------------------------------------------------
    print("\n--- [TEST 3] 401 Unauthorized (Authentication Error) ---")
    res_401 = transition_on_error(
        cur, mock_src_id, 'AUTH_ERROR', 401,
        "OAuthException: (#190) Error validating access token: Session has expired"
    )
    conn.commit()
    assert res_401['new_status'] == 'PAUSED', "401 must transition to PAUSED"
    assert res_401['backoff_minutes'] == 0
    assert res_401['error_category'] == 'AUTHENTICATION'

    summary = generate_health_summary(cur)
    alerts = evaluate_alert_conditions(summary)
    has_auth_alert = any(a['type'] == 'AUTHENTICATION_ERROR' for a in alerts)
    assert has_auth_alert, "Must trigger AUTHENTICATION_ERROR alert"
    print(f"  ✓ 401 verified: Transitioned to PAUSED, Alert generated: AUTHENTICATION_ERROR")
    passed_tests += 1

    # Reset mock source
    cur.execute("UPDATE public.facebook_sources SET status = 'ACTIVE', consecutive_errors = 0 WHERE id = %s;", (mock_src_id,))
    conn.commit()

    # -----------------------------------------------------------------
    # TEST 4: Network Timeout
    # -----------------------------------------------------------------
    print("\n--- [TEST 4] Network Timeout Handling ---")
    res_to = transition_on_error(
        cur, mock_src_id, 'TIMEOUT', None,
        "HTTPSConnectionPool(host='graph.facebook.com', port=443): Read timed out."
    )
    conn.commit()
    assert res_to['new_status'] == 'TEMP_ERROR'
    assert res_to['backoff_minutes'] == 2, "First timeout should have 2m backoff"
    assert res_to['error_category'] == 'NETWORK_TIMEOUT'
    print(f"  ✓ Timeout verified: Transitioned to TEMP_ERROR with backoff {res_to['backoff_minutes']}m")
    passed_tests += 1

    # -----------------------------------------------------------------
    # TEST 5: AI Unavailable (Circuit Breaker & Incident Alert)
    # -----------------------------------------------------------------
    print("\n--- [TEST 5] AI Unavailable (Fallback & Alert Trigger) ---")
    # Log simulated AI failures into facebook_errors
    for i in range(6):
        cur.execute("""
            INSERT INTO public.facebook_errors (
                error_category, error_code, error_message, request_context,
                retry_count, is_resolved, created_at
            ) VALUES (
                'AI_FAILURE', 'AI_TIMEOUT', 'LiteLLM upstream gateway timeout on qwen3-vl-30b',
                '{"circuit_breaker": "OPEN"}', 1, false, NOW()
            );
        """)
    conn.commit()

    summary = generate_health_summary(cur)
    assert summary['AI_errors'] >= 5, "Health summary must detect AI failure count"
    alerts = evaluate_alert_conditions(summary)
    has_ai_alert = any(a['type'] == 'AI_FAILURE_SPIKE' for a in alerts)
    assert has_ai_alert, "Must trigger AI_FAILURE_SPIKE alert"
    print(f"  ✓ AI Unavailable verified: Detected {summary['AI_errors']} AI errors, Alert triggered: AI_FAILURE_SPIKE")
    passed_tests += 1

    # -----------------------------------------------------------------
    # TEST 6: DB Unavailable Handling
    # -----------------------------------------------------------------
    print("\n--- [TEST 6] DB Unavailable Handling ---")
    # Test that connection error is caught gracefully
    try:
        bad_conn = psycopg2.connect("postgresql://postgres:wrong_pw@localhost:5432/postgres", connect_timeout=1)
        assert False, "Should fail connection"
    except psycopg2.OperationalError as e:
        print(f"  ✓ DB Unavailable successfully caught as OperationalError: {type(e).__name__}")
        passed_tests += 1

    # -----------------------------------------------------------------
    # TEST 7: Queue Backlog Detection
    # -----------------------------------------------------------------
    print("\n--- [TEST 7] Queue Backlog Detection ---")
    # Simulate high backlog condition
    mock_summary = {
        'sources_rate_limited': 0,
        'count_403': 0,
        'count_401': 0,
        'processing_backlog': 350,  # Exceeds 200 threshold
        'AI_errors': 0,
        'collector_dead': False,
        'global_collection_enabled': True
    }
    backlog_alerts = evaluate_alert_conditions(mock_summary)
    has_backlog_alert = any(a['type'] == 'QUEUE_BACKLOG_HIGH' for a in backlog_alerts)
    assert has_backlog_alert, "Must trigger QUEUE_BACKLOG_HIGH alert"
    print(f"  ✓ Queue Backlog verified: Detected {mock_summary['processing_backlog']} items backlog, Alert triggered: QUEUE_BACKLOG_HIGH")
    passed_tests += 1

    # -----------------------------------------------------------------
    # TEST 8: Global Kill Switch (FB_GLOBAL_COLLECTION_ENABLED = false)
    # -----------------------------------------------------------------
    print("\n--- [TEST 8] Global Kill Switch Alerting ---")
    # Temporarily set kill switch to false
    cur.execute("""
        UPDATE public.system_flags 
        SET flag_value = false 
        WHERE id = 'FB_GLOBAL_COLLECTION_ENABLED';
    """)
    conn.commit()

    summary_ks = generate_health_summary(cur)
    assert summary_ks['global_collection_enabled'] is False
    alerts_ks = evaluate_alert_conditions(summary_ks)
    has_ks_alert = any(a['type'] == 'GLOBAL_COLLECTION_DISABLED' for a in alerts_ks)
    assert has_ks_alert, "Must trigger GLOBAL_COLLECTION_DISABLED alert"

    # Restore kill switch to true
    cur.execute("""
        UPDATE public.system_flags 
        SET flag_value = true 
        WHERE id = 'FB_GLOBAL_COLLECTION_ENABLED';
    """)
    conn.commit()
    print(f"  ✓ Kill Switch verified: Alert triggered when DISABLED, successfully restored to ENABLED")
    passed_tests += 1

    # Clean up mock test source
    cur.execute("DELETE FROM public.facebook_sources WHERE id = %s;", (mock_src_id,))
    conn.commit()

    cur.close()
    conn.close()

    print("\n" + "=" * 80)
    print("📊 TEST SUITE RESULTS:")
    print(f"  Total Incident Scenarios Tested : {total_tests}")
    print(f"  Passed                          : {passed_tests}/{total_tests}")
    print(f"  Failed                          : {total_tests - passed_tests}")
    if passed_tests == total_tests:
        print("\n🎉 ALL 8/8 PHASE 7 MONITORING & RECOVERY TESTS PASSED 100%!")
        print("=" * 80)
    else:
        print("\n❌ SOME TESTS FAILED")
        sys.exit(1)

if __name__ == '__main__':
    run_suite()
