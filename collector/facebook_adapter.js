/**
 * Facebook Graph API Adapter Implementation (Phase 3)
 * Uses official Graph API endpoints with incremental cursor / since timestamp.
 */

const { CollectorAdapter } = require('./interface');
const { classifyError } = require('./error_classifier');

class FacebookGraphApiAdapter extends CollectorAdapter {
  constructor(apiBase = 'https://graph.facebook.com/v20.0', timeoutMs = 15000) {
    super();
    this.apiBase = apiBase;
    this.timeoutMs = timeoutMs;
  }

  /**
   * Resolves token dynamically: from sourceConfig or environment variable
   */
  resolveAccessToken(sourceConfig) {
    // 1. From source secret reference (if specified)
    if (sourceConfig.auth_secret_ref && sourceConfig.auth_secret_ref.startsWith('EAA')) {
      return sourceConfig.auth_secret_ref;
    }
    // 2. From environment variable (dynamic, no hardcoding)
    const envToken = process.env[`FB_PAGE_TOKEN_${sourceConfig.external_id}`] || process.env.FB_GRAPH_API_TOKEN;
    if (envToken) {
      return envToken;
    }
    return null;
  }

  async collect(sourceConfig) {
    const startTime = Date.now();
    const token = this.resolveAccessToken(sourceConfig);

    if (!token) {
      return {
        success: false,
        items: [],
        new_cursor: null,
        metrics: { fetched_count: 0, duration_ms: Date.now() - startTime, http_status: 401 },
        error: {
          category: 'AUTH_ERROR',
          code: 'NO_TOKEN',
          message: `No access token found for source ${sourceConfig.external_id}`
        }
      };
    }

    const fields = [
      'id', 'message', 'created_time', 'permalink_url',
      'reactions.summary(true)',
      'comments.summary(true){id,from,message,created_time,like_count,parent}'
    ].join(',');

    let url = `${this.apiBase}/${sourceConfig.external_id}/feed?fields=${fields}&limit=25&access_token=${token}`;
    
    // Incremental cursor / since timestamp
    if (sourceConfig.last_cursor) {
      // If cursor is a UNIX timestamp or ISO string, send as since
      const isNum = /^\d+$/.test(sourceConfig.last_cursor);
      const sinceParam = isNum ? sourceConfig.last_cursor : Math.floor(new Date(sourceConfig.last_cursor).getTime() / 1000);
      if (!isNaN(sinceParam) && sinceParam > 0) {
        url += `&since=${sinceParam}`;
      } else {
        url += `&after=${encodeURIComponent(sourceConfig.last_cursor)}`;
      }
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

      const response = await fetch(url, { signal: controller.signal });
      clearTimeout(timeoutId);

      const durationMs = Date.now() - startTime;
      const json = await response.json();

      if (!response.ok || json.error) {
        const classified = classifyError(response.status, json);
        return {
          success: false,
          items: [],
          new_cursor: sourceConfig.last_cursor,
          metrics: { fetched_count: 0, duration_ms: durationMs, http_status: response.status },
          error: classified
        };
      }

      // Parse and normalize into Envelope Items
      const rawPosts = Array.isArray(json.data) ? json.data : [];
      const envelopeItems = [];
      let latestPublishedAt = sourceConfig.last_cursor;

      const nowIso = new Date().toISOString();

      for (const post of rawPosts) {
        if (!post.id) continue;

        // Track newest published_at for cursor
        if (!latestPublishedAt || new Date(post.created_time) > new Date(latestPublishedAt)) {
          latestPublishedAt = post.created_time;
        }

        // 1. Post Envelope Item
        envelopeItems.push({
          source_id: sourceConfig.source_id,
          external_id: post.id,
          item_type: 'POST',
          external_parent_id: null,
          source_url: post.permalink_url || `https://facebook.com/${post.id}`,
          author_id: post.from?.id || sourceConfig.external_id,
          author_name: post.from?.name || sourceConfig.name || 'Page',
          content: post.message || '',
          published_at: post.created_time,
          raw_payload: post,
          collected_at: nowIso
        });

        // 2. Comments Envelope Items
        const comments = post.comments?.data || [];
        for (const c of comments) {
          if (!c.id) continue;
          envelopeItems.push({
            source_id: sourceConfig.source_id,
            external_id: c.id,
            item_type: 'COMMENT',
            external_parent_id: c.parent?.id || post.id,
            source_url: post.permalink_url || `https://facebook.com/${post.id}`,
            author_id: c.from?.id || null,
            author_name: c.from?.name || 'Anonymous',
            content: c.message || '',
            published_at: c.created_time,
            raw_payload: c,
            collected_at: nowIso
          });
        }
      }

      // Next cursor from paging or latest timestamp
      const newCursor = json.paging?.cursors?.after || latestPublishedAt || sourceConfig.last_cursor;

      return {
        success: true,
        items: envelopeItems,
        new_cursor: newCursor,
        metrics: {
          fetched_count: envelopeItems.length,
          duration_ms: durationMs,
          http_status: 200
        }
      };

    } catch (err) {
      const isAbort = err.name === 'AbortError';
      const classified = classifyError(isAbort ? 408 : 500, err.message);
      return {
        success: false,
        items: [],
        new_cursor: sourceConfig.last_cursor,
        metrics: { fetched_count: 0, duration_ms: Date.now() - startTime, http_status: isAbort ? 408 : 500 },
        error: classified
      };
    }
  }
}

module.exports = {
  FacebookGraphApiAdapter
};
