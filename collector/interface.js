/**
 * Facebook Collector Adapter Interface Contract (Phase 3)
 * Decouples collection mechanism from n8n & storage layer.
 */

class CollectorAdapter {
  /**
   * Fetches incremental items from source starting from last cursor.
   * @param {Object} sourceConfig
   *   - source_id: UUID
   *   - external_id: Facebook Page ID / Group ID
   *   - source_type: 'PAGE' | 'GROUP'
   *   - last_cursor: string | null
   *   - collection_interval_seconds: number
   *   - auth_secret_ref: string | null
   * @returns {Promise<{
   *   success: boolean,
   *   items: NormalizedEnvelopeItem[],
   *   new_cursor: string | null,
   *   metrics: { fetched_count: number, duration_ms: number, http_status: number },
   *   error?: { category: string, code: string, message: string, raw_response?: any }
   * }>}
   */
  async collect(sourceConfig) {
    throw new Error('Method collect() must be implemented by adapter subclass');
  }
}

/**
 * Normalized Envelope Schema definition
 * @typedef {Object} NormalizedEnvelopeItem
 * @property {string} source_id - UUID
 * @property {string} external_id - Facebook Post ID or Comment ID
 * @property {'POST' | 'COMMENT'} item_type
 * @property {string | null} external_parent_id - Parent Post ID if comment
 * @property {string} source_url - Link to post or source
 * @property {string | null} author_id
 * @property {string} author_name
 * @property {string} content - Message or body text
 * @property {string} published_at - ISO 8601 Timestamp
 * @property {Object} raw_payload - Original un-modified JSON
 * @property {string} collected_at - ISO 8601 Timestamp
 */

module.exports = {
  CollectorAdapter
};
