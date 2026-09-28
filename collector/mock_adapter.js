/**
 * Mock Facebook Collector Adapter (Phase 3)
 * For local integration testing, regression tests, and error simulation.
 */

const { CollectorAdapter } = require('./interface');
const { classifyError } = require('./error_classifier');

class MockFacebookAdapter extends CollectorAdapter {
  constructor(options = {}) {
    super();
    this.simulatedError = options.simulatedError || null;
    this.batchSize = options.batchSize || 3;
  }

  setSimulatedError(errorType) {
    this.simulatedError = errorType;
  }

  async collect(sourceConfig) {
    const startTime = Date.now();
    const nowIso = new Date().toISOString();

    // 1. Simulate Error Scenarios if requested
    if (this.simulatedError) {
      let status = 500;
      let body = { error: { message: 'Simulated server error', code: 2 } };

      if (this.simulatedError === '429' || this.simulatedError === 'RATE_LIMIT') {
        status = 429;
        body = { error: { message: 'User request limit reached', code: 4 } };
      } else if (this.simulatedError === '401' || this.simulatedError === 'AUTH_ERROR') {
        status = 401;
        body = { error: { message: 'Error validating access token: Session has expired', code: 190 } };
      } else if (this.simulatedError === '403' || this.simulatedError === 'PERMISSION_ERROR') {
        status = 403;
        body = { error: { message: 'Permissions error: (#10) Application does not have capability', code: 10 } };
      } else if (this.simulatedError === 'timeout' || this.simulatedError === 'TIMEOUT') {
        status = 408;
        body = 'ETIMEDOUT: Connection timed out';
      }

      const classified = classifyError(status, body);
      return {
        success: false,
        items: [],
        new_cursor: sourceConfig.last_cursor,
        metrics: { fetched_count: 0, duration_ms: 45, http_status: status },
        error: classified
      };
    }

    // 2. Generate Realistic Mock Incremental Data
    const baseTime = Date.now();
    const items = [];

    for (let i = 1; i <= this.batchSize; i++) {
      const postId = `mock_post_${sourceConfig.external_id}_${baseTime}_${i}`;
      const postTime = new Date(baseTime - (this.batchSize - i) * 60000).toISOString();

      const rawPost = {
        id: postId,
        message: `[MOCK CÔNG TRÌNH ${i}] Dự án nhà xưởng công nghiệp Hải Dương. Cần tìm đối tác cung ứng Robot xoa nền bê tông hoặc license CAD. Liên hệ: 0912${i}4567${i}`,
        created_time: postTime,
        permalink_url: `https://facebook.com/${sourceConfig.external_id}/posts/${postId}`,
        from: { id: sourceConfig.external_id, name: sourceConfig.name },
        reactions: { summary: { total_count: 24 + i * 5 } }
      };

      // Post Envelope
      items.push({
        source_id: sourceConfig.source_id,
        external_id: postId,
        item_type: 'POST',
        external_parent_id: null,
        source_url: rawPost.permalink_url,
        author_id: sourceConfig.external_id,
        author_name: sourceConfig.name,
        content: rawPost.message,
        published_at: postTime,
        raw_payload: rawPost,
        collected_at: nowIso
      });

      // Child Comment Envelope
      const commentId = `mock_cmt_${postId}_c1`;
      const cmtTime = new Date(baseTime - (this.batchSize - i) * 30000).toISOString();
      const rawCmt = {
        id: commentId,
        message: `Bên em có thi công gạt phẳng bê tông, báo giá vào email thicong${i}@xaydung.vn nhé.`,
        created_time: cmtTime,
        from: { id: `user_cmt_${i}`, name: `Kỹ sư ${i}` }
      };

      items.push({
        source_id: sourceConfig.source_id,
        external_id: commentId,
        item_type: 'COMMENT',
        external_parent_id: postId,
        source_url: rawPost.permalink_url,
        author_id: rawCmt.from.id,
        author_name: rawCmt.from.name,
        content: rawCmt.message,
        published_at: cmtTime,
        raw_payload: rawCmt,
        collected_at: nowIso
      });
    }

    const newCursor = `cursor_token_${baseTime}`;

    return {
      success: true,
      items: items,
      new_cursor: newCursor,
      metrics: {
        fetched_count: items.length,
        duration_ms: 65,
        http_status: 200
      }
    };
  }
}

module.exports = {
  MockFacebookAdapter
};
