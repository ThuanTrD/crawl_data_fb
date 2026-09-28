/**
 * Facebook Lead Intelligence V1 - Phase 4: Normalizer & Deduplicator Engine
 * 
 * Rules:
 * 1. Normalize Unicode NFC.
 * 2. Normalize whitespace (tabs, NBSP, zero-width spaces -> single space).
 * 3. Normalize newlines (\r\n, \r -> \n, max 2 consecutive newlines).
 * 4. Strictly preserve Vietnamese diacritics and letters.
 * 5. Strictly preserve original meaning (no auto-spelling modification).
 * 6. Generate SHA-256 content hash.
 * 7. Fast, accurate language detection (vi, en, other, empty).
 * 8. Hierarchical classification: POST vs COMMENT vs REPLY.
 * 9. Defensive execution - never throw unhandled exceptions.
 */

const crypto = require('crypto');

/**
 * Normalizes Unicode to NFC and cleans up whitespace/newlines defensively.
 * @param {string|any} text 
 * @returns {string} Cleaned normalized string
 */
function normalizeText(text) {
  if (text === null || text === undefined) {
    return '';
  }
  
  let s = String(text).normalize('NFC');
  
  // Unify newlines
  s = s.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  
  // Clean line by line
  const lines = s.split('\n');
  const cleanedLines = lines.map(line => {
    // Replace horizontal whitespace: standard space, tabs, NBSP (\u00A0), zero-width spaces (\u200B, \u200C, \u200D, \uFEFF)
    return line.replace(/[\t\u00A0\u200B\u200C\u200D\uFEFF ]+/g, ' ').trim();
  });
  
  s = cleanedLines.join('\n');
  
  // Collapse 3 or more consecutive newlines into exactly 2 (\n\n) to preserve paragraphs
  s = s.replace(/\n{3,}/g, '\n\n');
  
  // Trim outer edges
  return s.trim();
}

/**
 * Computes deterministic SHA-256 hash of normalized text.
 * @param {string} text 
 * @returns {string} 64-character hex hash
 */
function generateContentHash(text) {
  const content = text || '';
  return crypto.createHash('sha256').update(content, 'utf8').digest('hex');
}

/**
 * Detects language based on Vietnamese diacritics, Vietnamese domain keywords, and English patterns.
 * @param {string} text 
 * @returns {'vi'|'en'|'other'|'empty'}
 */
function detectLanguage(text) {
  if (!text || text.trim().length === 0) {
    return 'empty';
  }
  
  const norm = text.normalize('NFC');
  
  // 1. Vietnamese tone marks & specific characters:
  const viDiacriticsRegex = /[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ]/;
  if (viDiacriticsRegex.test(norm)) {
    return 'vi';
  }
  
  // 2. Vietnamese unaccented common keywords in construction/B2B context
  const viKeywordsRegex = /\b(gia|bao gia|tu van|be tong|phan mem|thiet bi|cong trinh|du an|lien he|cho em|minh|ben em|anh chi|inbox|ib|sdt|zalo|catalogue|thi cong|robot|can tim|ban quyen|xin gia|cho hoi|hop dong|ho so|du toan)\b/i;
  if (viKeywordsRegex.test(norm)) {
    return 'vi';
  }
  
  // 3. English keywords in B2B & general engineering context
  const enKeywordsRegex = /\b(the|and|is|for|with|in|to|of|from|we|our|you|your|please|price|quotation|quote|construction|software|service|project|specifications|license|contact|equipment|inquiry|hello|thanks|regards|testing|robotics|concrete|cad|structural)\b/i;
  if (enKeywordsRegex.test(norm)) {
    return 'en';
  }
  
  // 4. Check if standard Latin ASCII letters dominate
  const latinLetters = (norm.match(/[a-zA-Z]/g) || []).length;
  if (latinLetters > norm.length * 0.3) {
    return 'en';
  }
  
  return 'other';
}

/**
 * Classifies the item into POST, COMMENT, or REPLY and resolves parent linkage.
 * @param {object} rawItem 
 * @returns {object}
 */
function classifyItemType(rawItem) {
  const payload = rawItem.raw_payload || {};
  const declaredType = (rawItem.item_type || payload.item_type || 'POST').toUpperCase();
  const externalId = String(rawItem.external_item_id || rawItem.external_id || payload.id || payload.external_id || '').trim();
  const externalParentId = rawItem.external_parent_id || payload.parent_id || payload.external_parent_id || null;
  const rawParentCommentId = payload.parent_comment_id || payload.comment_parent_id || null;

  let category = 'POST';
  let postId = null;
  let commentId = null;
  let parentCommentId = null;

  if (declaredType === 'COMMENT' || declaredType === 'REPLY' || rawParentCommentId || (externalParentId && externalParentId !== externalId)) {
    commentId = externalId;
    
    if (declaredType === 'REPLY' || rawParentCommentId) {
      category = 'REPLY';
      parentCommentId = rawParentCommentId ? String(rawParentCommentId) : (externalParentId && externalParentId.includes('_') ? externalParentId : null);
      if (payload.post_id) {
        postId = String(payload.post_id);
      } else if (externalParentId) {
        const lastUnderscore = externalParentId.lastIndexOf('_');
        postId = lastUnderscore > 0 ? externalParentId.substring(0, lastUnderscore) : externalParentId;
      } else {
        postId = 'unknown_post';
      }
    } else {
      category = 'COMMENT';
      parentCommentId = null;
      postId = String(payload.post_id || externalParentId || 'unknown_post');
    }
  } else {
    category = 'POST';
    postId = externalId;
  }

  return {
    category, // 'POST', 'COMMENT', 'REPLY'
    postId,
    commentId,
    parentCommentId,
    targetTable: category === 'POST' ? 'facebook_posts' : 'facebook_comments'
  };
}

/**
 * Full item normalization pipeline. Defensive, returns safe structured object.
 * @param {object} rawItem 
 * @returns {object}
 */
function normalizeRawItem(rawItem) {
  try {
    if (!rawItem || typeof rawItem !== 'object') {
      return {
        success: false,
        error: 'INVALID_ITEM_FORMAT',
        message: 'Raw item must be a non-null object'
      };
    }

    const payload = rawItem.raw_payload || {};
    
    // Mandatory validation: external_id must exist
    const rawExtId = rawItem.external_item_id || rawItem.external_id || payload.id || payload.external_id;
    if (!rawExtId || !String(rawExtId).trim() || String(rawExtId).trim() === 'null' || String(rawExtId).trim() === 'undefined') {
      return {
        success: false,
        raw_item_id: rawItem?.id || null,
        error: 'MISSING_EXTERNAL_ID',
        message: 'Raw item is missing required external_id or payload.id'
      };
    }
    const externalId = String(rawExtId).trim();

    const rawContent = rawItem.content !== undefined ? rawItem.content : (payload.message || payload.text || payload.content || '');
    
    // 1. Text Normalization (NFC, whitespace, newline)
    const normalizedContent = normalizeText(rawContent);
    
    // 2. Content Hash
    const contentHash = generateContentHash(normalizedContent);
    
    // 3. Language Detection
    const language = detectLanguage(normalizedContent);
    
    // 4. Hierarchy Classification
    const hierarchy = classifyItemType(rawItem);
    
    // 5. Metadata & Provenance extraction
    const authorId = rawItem.author_id || payload.from?.id || payload.author_id || null;
    const authorName = rawItem.author_name || payload.from?.name || payload.author_name || null;
    const publishedAt = rawItem.published_at || payload.created_time || payload.published_at || rawItem.received_at || new Date().toISOString();
    
    // Defensive check on date validity
    let validatedPublishedAt;
    try {
      const d = new Date(publishedAt);
      validatedPublishedAt = isNaN(d.getTime()) ? new Date().toISOString() : d.toISOString();
    } catch {
      validatedPublishedAt = new Date().toISOString();
    }

    return {
      success: true,
      raw_item_id: rawItem.id || null,
      source_id: rawItem.source_id,
      category: hierarchy.category,
      target_table: hierarchy.targetTable,
      external_id: externalId,
      post_id: hierarchy.postId || externalId,
      comment_id: hierarchy.commentId,
      parent_comment_id: hierarchy.parentCommentId,
      author_id: authorId ? String(authorId) : null,
      author_name: authorName ? String(authorName).normalize('NFC').trim() : null,
      content: normalizedContent,
      content_hash: contentHash,
      language: language,
      published_at: validatedPublishedAt,
      source_url: rawItem.source_url || payload.permalink_url || payload.url || null,
      reactions_count: Number(payload.reactions_count || payload.reactions?.summary?.total_count || payload.like_count || 0),
      comments_count: Number(payload.comments_count || payload.comments?.summary?.total_count || 0),
      shares_count: Number(payload.shares_count || payload.shares?.count || 0),
      raw_payload: payload
    };
  } catch (err) {
    return {
      success: false,
      raw_item_id: rawItem?.id || null,
      error: 'NORMALIZATION_EXCEPTION',
      message: err.message || String(err),
      stack: err.stack
    };
  }
}

module.exports = {
  normalizeText,
  generateContentHash,
  detectLanguage,
  classifyItemType,
  normalizeRawItem
};
