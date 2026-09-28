/**
 * Error Classifier & Backoff Engine for Facebook Collector (Phase 3)
 */

const ErrorCategory = {
  RATE_LIMIT: 'RATE_LIMIT',
  AUTH_ERROR: 'AUTH_ERROR',
  PERMISSION_ERROR: 'PERMISSION_ERROR',
  SERVER_ERROR: 'SERVER_ERROR',
  TIMEOUT: 'TIMEOUT',
  UNKNOWN: 'UNKNOWN'
};

function classifyError(httpStatus, errorBody = {}) {
  const status = Number(httpStatus);
  const code = errorBody?.error?.code || errorBody?.code || '';
  const subcode = errorBody?.error?.error_subcode || '';

  // 1. Rate Limit (HTTP 429 or Meta Specific Codes: 4, 17, 32, 613)
  if (status === 429 || [4, 17, 32, 613].includes(Number(code))) {
    return {
      category: ErrorCategory.RATE_LIMIT,
      code: String(code || '429'),
      message: errorBody?.error?.message || 'Facebook API rate limit reached (calls threshold exceeded)',
      is_retryable: true,
      requires_backoff: true
    };
  }

  // 2. Auth Error (HTTP 401 or Meta Code 190 Session Expired)
  if (status === 401 || Number(code) === 190) {
    return {
      category: ErrorCategory.AUTH_ERROR,
      code: String(code || '401'),
      message: errorBody?.error?.message || 'Facebook Page Access Token expired or invalid',
      is_retryable: false,
      requires_source_update: 'AUTH_ERROR'
    };
  }

  // 3. Permission Error (HTTP 403 or Meta Code 10, 200)
  if (status === 403 || [10, 200].includes(Number(code))) {
    return {
      category: ErrorCategory.PERMISSION_ERROR,
      code: String(code || '403'),
      message: errorBody?.error?.message || 'Insufficient permissions to read source feed/comments',
      is_retryable: false,
      requires_source_update: 'PERMISSION_ERROR'
    };
  }

  // 4. Server Error (HTTP 5xx or Meta Code 1, 2)
  if (status >= 500 && status < 600 || [1, 2].includes(Number(code))) {
    return {
      category: ErrorCategory.SERVER_ERROR,
      code: String(code || status),
      message: errorBody?.error?.message || 'Upstream Meta internal server error',
      is_retryable: true,
      requires_backoff: true
    };
  }

  // 5. Timeout
  if (status === 408 || String(errorBody).toLowerCase().includes('timeout') || code === 'ETIMEDOUT') {
    return {
      category: ErrorCategory.TIMEOUT,
      code: 'TIMEOUT',
      message: 'Request timed out waiting for Facebook response',
      is_retryable: true,
      requires_backoff: true
    };
  }

  return {
    category: ErrorCategory.UNKNOWN,
    code: String(code || status || 'UNKNOWN'),
    message: errorBody?.error?.message || String(errorBody) || 'Unknown error occurred',
    is_retryable: false,
    requires_backoff: false
  };
}

/**
 * Calculates exponential backoff with jitter
 * @param {number} consecutiveRateLimits
 * @param {number} baseSeconds
 * @param {number} maxSeconds
 * @returns {number} Wait seconds
 */
function calculateBackoffSeconds(consecutiveRateLimits = 1, baseSeconds = 60, maxSeconds = 3600) {
  const exponent = Math.min(consecutiveRateLimits, 6);
  const exponential = baseSeconds * Math.pow(2, exponent - 1);
  const capped = Math.min(exponential, maxSeconds);
  // Full jitter: random between 0.8 and 1.2 of capped
  const jitter = 0.8 + Math.random() * 0.4;
  return Math.round(capped * jitter);
}

/**
 * Evaluates state transition for a source upon error
 * @param {Object} currentSource
 * @param {Object} classifiedError
 * @returns {Object} updates to apply to facebook_sources
 */
function evaluateSourceErrorTransition(currentSource, classifiedError) {
  const updates = {
    last_error_at: new Date().toISOString(),
    last_error_code: classifiedError.code,
    last_error_message: classifiedError.message,
    consecutive_errors: (currentSource.consecutive_errors || 0) + 1
  };

  if (classifiedError.category === ErrorCategory.RATE_LIMIT) {
    const rateLimits = (currentSource.consecutive_rate_limits || 0) + 1;
    const backoffSec = calculateBackoffSeconds(rateLimits, 120, 7200);
    const backoffUntil = new Date(Date.now() + backoffSec * 1000).toISOString();
    
    updates.consecutive_rate_limits = rateLimits;
    updates.backoff_until = backoffUntil;
    updates.next_run_at = backoffUntil;

    // After 3 consecutive rate limits -> Mark source RATE_LIMITED
    if (rateLimits >= 3) {
      updates.status = 'RATE_LIMITED';
    }
  } else if (classifiedError.requires_source_update) {
    updates.status = classifiedError.requires_source_update;
  } else {
    // Other consecutive errors: after 5 errors -> Mark source PAUSED
    if (updates.consecutive_errors >= 5) {
      updates.status = 'PAUSED';
      updates.last_error_message = `Auto-paused: 5 consecutive failures. Last: ${classifiedError.message}`;
    }
  }

  return updates;
}

module.exports = {
  ErrorCategory,
  classifyError,
  calculateBackoffSeconds,
  evaluateSourceErrorTransition
};
