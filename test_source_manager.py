#!/usr/bin/env python3
"""
Test Suite for Facebook Source Manager (Phase 2)
Tests:
  1. Global Kill Switch evaluation
  2. Eligibility filtering (enabled, status, next_run_at, backoff_until)
  3. Yield-based prioritization (yield_score DESC, leads_yield_count DESC)
  4. Non-ACTIVE source exclusion (PAUSED, RATE_LIMITED, BLOCKED, AUTH_ERROR)
  5. Schedule bump (next_run_at update) and Audit Logging (facebook_collection_logs)
"""

import psycopg2
import json
import sys
from datetime import datetime, timezone

DB_CONFIG = {
    "host": "aws-0-ap-southeast-2.pooler.supabase.com",
    "port": 5432,
    "user": "postgres.qllwfecwujzhuwexrlqi",
    "password": "tRpWn0s3s8OxILhQ",
    "dbname": "postgres",
    "sslmode": "require"
}

def run_tests():
    print("==================================================================")
    print("  RUNNING FACEBOOK SOURCE MANAGER TEST SUITE (PHASE 2)")
    print("==================================================================")
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    passed = 0
    failed = 0

    # ------------------------------------------------------------------
    # TEST 1: Global Kill Switch Check
    # ------------------------------------------------------------------
    print("\n--- TEST 1: Global Kill Switch Evaluation ---")
    try:
        # Step A: Test normal state (TRUE)
        cur.execute("SELECT flag_value, state, (flag_value = TRUE AND state = 'CLOSED') FROM public.system_flags WHERE id = 'FB_GLOBAL_COLLECTION_ENABLED';")
        flag_val, state, allowed = cur.fetchone()
        assert allowed == True, "Default kill switch state should allow collection"
        print("  ✓ Step A: Kill Switch is CLOSED/TRUE -> Collection allowed: PASS")

        # Step B: Toggle kill switch to FALSE and verify halt
        cur.execute("UPDATE public.system_flags SET flag_value = FALSE WHERE id = 'FB_GLOBAL_COLLECTION_ENABLED';")
        cur.execute("SELECT (flag_value = TRUE AND state = 'CLOSED') FROM public.system_flags WHERE id = 'FB_GLOBAL_COLLECTION_ENABLED';")
        assert cur.fetchone()[0] == False, "Toggled kill switch should block collection"
        print("  ✓ Step B: Kill Switch set to FALSE -> Collection blocked: PASS")

        # Step C: Restore kill switch
        cur.execute("UPDATE public.system_flags SET flag_value = TRUE WHERE id = 'FB_GLOBAL_COLLECTION_ENABLED';")
        conn.commit()
        print("  ✓ Step C: Restored Kill Switch to TRUE: PASS")
        passed += 1
    except Exception as e:
        print(f"  ✗ TEST 1 FAILED: {e}")
        failed += 1

    # ------------------------------------------------------------------
    # TEST 2: Eligibility Filtering & Ineligible Source Exclusion
    # ------------------------------------------------------------------
    print("\n--- TEST 2: Eligibility Filtering & Non-ACTIVE Exclusion ---")
    try:
        # Reset mock sources to due state
        cur.execute("""
            UPDATE public.facebook_sources
            SET next_run_at = NOW() - INTERVAL '10 minutes'
            WHERE external_id IN ('mock_page_robot_hot', 'mock_page_cad_vietnam');
        """)
        conn.commit()

        # Execute Node 3 Query
        query = """
        SELECT 
            external_id, name, status, enabled, yield_score, leads_yield_count
        FROM public.facebook_sources
        WHERE enabled = TRUE
          AND status = 'ACTIVE'
          AND (next_run_at IS NULL OR next_run_at <= NOW())
          AND (backoff_until IS NULL OR backoff_until <= NOW())
          AND circuit_breaker_tripped = FALSE
        ORDER BY yield_score DESC, leads_yield_count DESC, next_run_at ASC;
        """
        cur.execute(query)
        rows = cur.fetchall()
        
        external_ids = [r[0] for r in rows]
        print(f"  Returned Sources Count: {len(rows)}")
        for r in rows:
            print(f"    - {r[0]}: {r[1]} (yield: {r[4]}, leads: {r[5]})")

        assert len(rows) == 2, f"Expected exactly 2 eligible sources, got {len(rows)}"
        assert 'mock_page_robot_hot' in external_ids, "mock_page_robot_hot must be included"
        assert 'mock_page_cad_vietnam' in external_ids, "mock_page_cad_vietnam must be included"
        
        # Verify specific exclusions
        assert 'mock_page_disabled' not in external_ids, "Disabled source must be excluded"
        assert 'mock_page_paused' not in external_ids, "Paused source must be excluded"
        assert 'mock_page_rate_limited' not in external_ids, "Rate limited source must be excluded"
        assert 'mock_page_blocked' not in external_ids, "Blocked source must be excluded"
        assert 'mock_page_auth_error' not in external_ids, "Auth error source must be excluded"
        assert 'mock_page_future_run' not in external_ids, "Future run source must be excluded"
        assert 'mock_page_backoff_cooldown' not in external_ids, "Backoff cooldown source must be excluded"

        print("  ✓ All 7 ineligible mock sources strictly excluded: PASS")
        passed += 1
    except Exception as e:
        print(f"  ✗ TEST 2 FAILED: {e}")
        failed += 1

    # ------------------------------------------------------------------
    # TEST 3: Yield-based Prioritization Ranking
    # ------------------------------------------------------------------
    print("\n--- TEST 3: Yield-based Prioritization Ranking ---")
    try:
        cur.execute(query)
        rows = cur.fetchall()
        first_source = rows[0][0]
        second_source = rows[1][0]
        first_yield = float(rows[0][4])
        second_yield = float(rows[1][4])

        assert first_source == 'mock_page_robot_hot', f"Highest yield must be #1, got {first_source}"
        assert first_yield > second_yield, f"Rank 1 ({first_yield}) must exceed Rank 2 ({second_yield})"
        print(f"  ✓ Rank 1: {first_source} (Yield: {first_yield}) > Rank 2: {second_source} (Yield: {second_yield}): PASS")
        passed += 1
    except Exception as e:
        print(f"  ✗ TEST 3 FAILED: {e}")
        failed += 1

    # ------------------------------------------------------------------
    # TEST 4: Schedule Bump & Audit Logging
    # ------------------------------------------------------------------
    print("\n--- TEST 4: Schedule Bump & Collection Audit Logging ---")
    try:
        cur.execute("SELECT id, collection_interval_seconds, last_cursor FROM public.facebook_sources WHERE external_id = 'mock_page_robot_hot';")
        source_id, interval, last_cursor = cur.fetchone()

        # Step A: Update next_run_at (Simulating Node 6)
        cur.execute("""
            UPDATE public.facebook_sources
            SET next_run_at = NOW() + (%s || ' seconds')::INTERVAL,
                updated_at = NOW()
            WHERE id = %s
            RETURNING next_run_at > NOW();
        """, (interval, source_id))
        is_future = cur.fetchone()[0]
        assert is_future == True, "next_run_at must be moved into the future"
        print(f"  ✓ Schedule bumped by {interval}s into future: PASS")

        # Step B: Insert collection audit log (Simulating Node 7)
        cur.execute("""
            INSERT INTO public.facebook_collection_logs (
                source_id, method, checkpoint_cursor_start, items_fetched, items_new, http_status, duration_ms
            ) VALUES (
                %s, 'QUEUE_DISPATCH', %s, 0, 0, 200, 15
            ) RETURNING id;
        """, (source_id, last_cursor))
        log_id = cur.fetchone()[0]
        assert log_id is not None, "Log ID must be generated"
        print(f"  ✓ Collection log generated (ID: {log_id}): PASS")

        conn.commit()
        passed += 1
    except Exception as e:
        print(f"  ✗ TEST 4 FAILED: {e}")
        failed += 1

    # ------------------------------------------------------------------
    # TEST 5: Idempotency & Queue Depletion on Re-check
    # ------------------------------------------------------------------
    print("\n--- TEST 5: Queue Idempotency (Prevent Duplicate Ingestion) ---")
    try:
        # Check remaining eligible sources
        cur.execute(query)
        remaining = cur.fetchall()
        rem_ids = [r[0] for r in remaining]
        assert 'mock_page_robot_hot' not in rem_ids, "mock_page_robot_hot should no longer be eligible immediately"
        print(f"  ✓ Source immediately locked from duplicate dispatch: PASS (Remaining: {len(remaining)})")
        passed += 1
    except Exception as e:
        print(f"  ✗ TEST 5 FAILED: {e}")
        failed += 1

    print("\n==================================================================")
    print(f"  TOTAL TESTS: {passed + failed} | PASSED: {passed} | FAILED: {failed}")
    print("==================================================================")

    cur.close()
    conn.close()
    return failed == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
