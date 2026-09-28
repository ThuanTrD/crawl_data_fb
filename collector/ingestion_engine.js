/**
 * Ingestion Engine & Pipeline Controller (Phase 3)
 * Handles ingestion idempotency, database transactions, error tracking & checkpoints.
 */

const crypto = require('crypto');
const { evaluateSourceErrorTransition } = require('./error_classifier');

class IngestionEngine {
  constructor(pgClient) {
    this.pg = pgClient;
  }

  /**
   * Evaluates Global Kill Switch and Circuit Breaker
   */
  async isCollectionAllowed() {
    const res = await this.pg.query(
      "SELECT (flag_value = TRUE AND state = 'CLOSED') AS allowed FROM public.system_flags WHERE id = 'FB_GLOBAL_COLLECTION_ENABLED';"
    );
    return res.rows[0]?.allowed === true;
  }

  /**
   * Processes collection run for a single source
   */
  async processSourceCollection(sourceConfig, adapter) {
    const startTime = Date.now();

    // 1. Check Global Kill Switch
    const globalAllowed = await this.isCollectionAllowed();
    if (!globalAllowed) {
      return {
        status: 'HALTED_BY_GLOBAL_KILL_SWITCH',
        source_id: sourceConfig.source_id,
        items_ingested: 0
      };
    }

    // 2. Check Per-Source Status and Enabled Flag
    const srcRes = await this.pg.query(
      "SELECT enabled, status, backoff_until, consecutive_errors, consecutive_rate_limits FROM public.facebook_sources WHERE id = $1;",
      [sourceConfig.source_id]
    );
    const liveSource = srcRes.rows[0];

    if (!liveSource || !liveSource.enabled) {
      return { status: 'SOURCE_DISABLED', source_id: sourceConfig.source_id, items_ingested: 0 };
    }

    if (liveSource.status !== 'ACTIVE') {
      return { status: `SOURCE_STATUS_${liveSource.status}`, source_id: sourceConfig.source_id, items_ingested: 0 };
    }

    if (liveSource.backoff_until && new Date(liveSource.backoff_until) > new Date()) {
      return { status: 'SOURCE_IN_BACKOFF', source_id: sourceConfig.source_id, backoff_until: liveSource.backoff_until };
    }

    // 3. Execute Collector Adapter
    const collectResult = await adapter.collect(sourceConfig);
    const durationMs = Date.now() - startTime;

    // 4. Handle Collector Errors
    if (!collectResult.success || collectResult.error) {
      const err = collectResult.error;
      const transitionUpdates = evaluateSourceErrorTransition(liveSource, err);

      // Update facebook_sources state
      await this.pg.query(`
        UPDATE public.facebook_sources
        SET 
          status = COALESCE($1, status),
          last_error_at = $2,
          last_error_code = $3,
          last_error_message = $4,
          consecutive_errors = $5,
          consecutive_rate_limits = COALESCE($6, consecutive_rate_limits),
          backoff_until = $7,
          next_run_at = COALESCE($8, next_run_at),
          updated_at = NOW()
        WHERE id = $9;
      `, [
        transitionUpdates.status || null,
        transitionUpdates.last_error_at,
        transitionUpdates.last_error_code,
        transitionUpdates.last_error_message,
        transitionUpdates.consecutive_errors,
        transitionUpdates.consecutive_rate_limits || null,
        transitionUpdates.backoff_until || null,
        transitionUpdates.next_run_at || null,
        sourceConfig.source_id
      ]);

      // Record in facebook_errors
      await this.pg.query(`
        INSERT INTO public.facebook_errors (
          source_id, error_category, error_code, error_message, request_context, retry_count
        ) VALUES ($1, $2, $3, $4, $5, $6);
      `, [
        sourceConfig.source_id,
        err.category,
        err.code,
        err.message,
        JSON.stringify({ external_id: sourceConfig.external_id, last_cursor: sourceConfig.last_cursor }),
        transitionUpdates.consecutive_errors
      ]);

      // Record failure in facebook_collection_logs
      await this.pg.query(`
        INSERT INTO public.facebook_collection_logs (
          source_id, method, checkpoint_cursor_start, items_fetched, items_new, http_status, duration_ms
        ) VALUES ($1, $2, $3, 0, 0, $4, $5);
      `, [
        sourceConfig.source_id,
        sourceConfig.access_method || 'GRAPH_API',
        sourceConfig.last_cursor || '',
        collectResult.metrics?.http_status || 500,
        durationMs
      ]);

      return {
        status: 'ERROR',
        error_category: err.category,
        error_code: err.code,
        message: err.message,
        source_status_now: transitionUpdates.status || liveSource.status
      };
    }

    // 5. Handle Successful Ingestion
    let itemsNew = 0;
    let itemsDuplicate = 0;

    for (const item of collectResult.items) {
      // Calculate SHA-256 hash of raw payload
      const rawString = JSON.stringify(item.raw_payload);
      const payloadHash = crypto.createHash('sha256').update(rawString, 'utf8').digest('hex');

      // Idempotent Insert into facebook_raw_items
      const rawInsertRes = await this.pg.query(`
        INSERT INTO public.facebook_raw_items (
          source_id, item_type, external_item_id, payload_hash, raw_payload, ingested_channel, processing_status
        ) VALUES ($1, $2, $3, $4, $5, $6, 'PENDING')
        ON CONFLICT (payload_hash) DO NOTHING
        RETURNING id;
      `, [
        sourceConfig.source_id,
        item.item_type,
        item.external_id,
        payloadHash,
        rawString,
        sourceConfig.access_method || 'GRAPH_API'
      ]);

      if (rawInsertRes.rows.length === 0) {
        itemsDuplicate += 1;
        continue; // Already processed
      }

      const rawItemId = rawInsertRes.rows[0].id;
      itemsNew += 1;

      // Upsert into Normalized Entities Table
      if (item.item_type === 'POST') {
        await this.pg.query(`
          INSERT INTO public.facebook_posts (
            raw_item_id, source_id, post_id, page_id, author_id, author_name,
            message, permalink_url, created_time, reactions_count, crawled_at
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
          ON CONFLICT (post_id) DO UPDATE SET
            message = EXCLUDED.message,
            reactions_count = EXCLUDED.reactions_count,
            updated_at = NOW();
        `, [
          rawItemId,
          sourceConfig.source_id,
          item.external_id,
          sourceConfig.external_id,
          item.author_id,
          item.author_name,
          item.content,
          item.source_url,
          item.published_at,
          item.raw_payload?.reactions?.summary?.total_count || 0
        ]);
      } else if (item.item_type === 'COMMENT') {
        await this.pg.query(`
          INSERT INTO public.facebook_comments (
            raw_item_id, source_id, post_id, comment_id, parent_comment_id,
            author_id, author_name, message, created_time, like_count, crawled_at
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
          ON CONFLICT (comment_id) DO UPDATE SET
            message = EXCLUDED.message,
            like_count = EXCLUDED.like_count;
        `, [
          rawItemId,
          sourceConfig.source_id,
          item.external_parent_id || '',
          item.external_id,
          item.raw_payload?.parent?.id || null,
          item.author_id,
          item.author_name,
          item.content,
          item.published_at,
          item.raw_payload?.like_count || 0
        ]);
      }
    }

    // 6. Advance Checkpoint & Reset Error State
    await this.pg.query(`
      UPDATE public.facebook_sources
      SET 
        last_cursor = COALESCE($1, last_cursor),
        current_checkpoint_cursor = COALESCE($1, current_checkpoint_cursor),
        last_collected_at = NOW(),
        last_crawled_at = NOW(),
        last_success_at = NOW(),
        consecutive_errors = 0,
        consecutive_rate_limits = 0,
        backoff_until = NULL,
        status = 'ACTIVE',
        updated_at = NOW()
      WHERE id = $2;
    `, [
      collectResult.new_cursor || null,
      sourceConfig.source_id
    ]);

    // 7. Insert Log Entry into facebook_collection_logs
    await this.pg.query(`
      INSERT INTO public.facebook_collection_logs (
        source_id, method, checkpoint_cursor_start, checkpoint_cursor_end,
        items_fetched, items_new, items_duplicated, http_status, duration_ms
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, 200, $8);
    `, [
      sourceConfig.source_id,
      sourceConfig.access_method || 'GRAPH_API',
      sourceConfig.last_cursor || '',
      collectResult.new_cursor || '',
      collectResult.items.length,
      itemsNew,
      itemsDuplicate,
      durationMs
    ]);

    // 8. Update Daily Metrics
    const today = new Date().toISOString().split('T')[0];
    await this.pg.query(`
      INSERT INTO public.facebook_source_metrics (
        source_id, metric_date, total_posts_collected, total_comments_collected, total_errors, avg_latency_ms
      ) VALUES ($1, $2, $3, $4, 0, $5)
      ON CONFLICT (source_id, metric_date) DO UPDATE SET
        total_posts_collected = public.facebook_source_metrics.total_posts_collected + EXCLUDED.total_posts_collected,
        total_comments_collected = public.facebook_source_metrics.total_comments_collected + EXCLUDED.total_comments_collected,
        avg_latency_ms = (public.facebook_source_metrics.avg_latency_ms + EXCLUDED.avg_latency_ms) / 2,
        updated_at = NOW();
    `, [
      sourceConfig.source_id,
      today,
      collectResult.items.filter(i => i.item_type === 'POST').length,
      collectResult.items.filter(i => i.item_type === 'COMMENT').length,
      durationMs
    ]);

    return {
      status: 'SUCCESS',
      source_id: sourceConfig.source_id,
      items_fetched: collectResult.items.length,
      items_new: itemsNew,
      items_duplicated: itemsDuplicate,
      new_cursor: collectResult.new_cursor,
      duration_ms: durationMs
    };
  }
}

module.exports = {
  IngestionEngine
};
