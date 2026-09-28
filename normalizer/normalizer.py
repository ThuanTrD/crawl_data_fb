"""
Facebook Lead Intelligence V1 - Phase 4: Normalizer & Deduplication Engine (Python)

Conforms 100% to normalizer.js specifications:
1. Unicode NFC normalization.
2. Whitespace & Newline normalization.
3. Preserves Vietnamese diacritics, letters, meaning.
4. Deterministic SHA-256 content hash.
5. Fast, accurate language detection (vi, en, other, empty).
6. POST / COMMENT / REPLY hierarchy resolution.
7. Defensive execution with dead-letter classification.
"""

import re
import unicodedata
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional

WS_PATTERN = re.compile(r'[\t\u00A0\u200B\u200C\u200D\uFEFF ]+')

VI_DIACRITICS = re.compile(
    r'[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ'
    r'ÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ]'
)

VI_KEYWORDS = re.compile(
    r'\b(gia|bao gia|tu van|be tong|phan mem|thiet bi|cong trinh|du an|lien he|cho em|minh|ben em|anh chi|inbox|ib|sdt|zalo|catalogue|thi cong|robot|can tim|ban quyen|xin gia|cho hoi|hop dong|ho so|du toan)\b',
    re.IGNORECASE
)

EN_KEYWORDS = re.compile(
    r'\b(the|and|is|for|with|in|to|of|from|we|our|you|your|please|price|quotation|quote|construction|software|service|project|specifications|license|contact|equipment|inquiry|hello|thanks|regards|testing|robotics|concrete|cad|structural)\b',
    re.IGNORECASE
)

def normalize_text(text: Any) -> str:
    if text is None:
        return ""
    
    s = unicodedata.normalize('NFC', str(text))
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    
    lines = s.split('\n')
    cleaned_lines = [WS_PATTERN.sub(' ', line).strip() for line in lines]
    s = '\n'.join(cleaned_lines)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()

def generate_content_hash(text: str) -> str:
    content = (text or "").encode('utf-8')
    return hashlib.sha256(content).hexdigest()

def detect_language(text: str) -> str:
    if not text or not text.strip():
        return 'empty'
    
    norm = unicodedata.normalize('NFC', text)
    if VI_DIACRITICS.search(norm):
        return 'vi'
    if VI_KEYWORDS.search(norm):
        return 'vi'
    if EN_KEYWORDS.search(norm):
        return 'en'
    
    latin_letters = len(re.findall(r'[a-zA-Z]', norm))
    if latin_letters > len(norm) * 0.3:
        return 'en'
    
    return 'other'

def classify_item_type(raw_item: Dict[str, Any]) -> Dict[str, Any]:
    payload = raw_item.get('raw_payload') or {}
    declared_type = str(raw_item.get('item_type') or payload.get('item_type') or 'POST').upper()
    external_id = str(raw_item.get('external_item_id') or raw_item.get('external_id') or payload.get('id') or payload.get('external_id') or '')
    external_parent_id = raw_item.get('external_parent_id') or payload.get('parent_id') or payload.get('external_parent_id') or None
    raw_parent_comment_id = payload.get('parent_comment_id') or payload.get('comment_parent_id') or None

    category = 'POST'
    post_id = None
    comment_id = None
    parent_comment_id = None

    if declared_type in ('COMMENT', 'REPLY') or raw_parent_comment_id or (external_parent_id and external_parent_id != external_id):
        comment_id = external_id
        if declared_type == 'REPLY' or raw_parent_comment_id:
            category = 'REPLY'
            parent_comment_id = str(raw_parent_comment_id) if raw_parent_comment_id else (str(external_parent_id) if '_' in str(external_parent_id) else None)
            if payload.get('post_id'):
                post_id = str(payload.get('post_id'))
            elif external_parent_id:
                ext_str = str(external_parent_id)
                last_idx = ext_str.rfind('_')
                post_id = ext_str[:last_idx] if last_idx > 0 else ext_str
            else:
                post_id = 'unknown_post'
        else:
            category = 'COMMENT'
            parent_comment_id = None
            post_id = str(payload.get('post_id') or external_parent_id or 'unknown_post')
    else:
        category = 'POST'
        post_id = external_id

    return {
        'category': category,
        'postId': post_id,
        'commentId': comment_id,
        'parentCommentId': parent_comment_id,
        'targetTable': 'facebook_posts' if category == 'POST' else 'facebook_comments'
    }

def normalize_raw_item(raw_item: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not raw_item or not isinstance(raw_item, dict):
            return {
                'success': False,
                'error': 'INVALID_ITEM_FORMAT',
                'message': 'Raw item must be a non-null dictionary'
            }

        payload = raw_item.get('raw_payload') or {}
        
        # Mandatory validation: external_id must exist
        external_id = raw_item.get('external_item_id') or raw_item.get('external_id') or payload.get('id') or payload.get('external_id')
        if not external_id or not str(external_id).strip() or str(external_id).strip() in ('None', 'null', 'undefined'):
            return {
                'success': False,
                'raw_item_id': raw_item.get('id'),
                'error': 'MISSING_EXTERNAL_ID',
                'message': 'Raw item is missing required external_id or payload.id'
            }
        external_id = str(external_id).strip()

        raw_content = raw_item.get('content')
        if raw_content is None:
            raw_content = payload.get('message') or payload.get('text') or payload.get('content') or ''
        
        # 1. Text Normalization (NFC, whitespace, newline)
        normalized_content = normalize_text(raw_content)
        
        # 2. Content Hash
        content_hash = generate_content_hash(normalized_content)
        
        # 3. Language Detection
        language = detect_language(normalized_content)
        
        # 4. Hierarchy Classification
        hierarchy = classify_item_type(raw_item)
        
        # 5. Metadata & Provenance extraction
        from_obj = payload.get('from') or {}
        author_id = raw_item.get('author_id') or from_obj.get('id') or payload.get('author_id') or None
        author_name = raw_item.get('author_name') or from_obj.get('name') or payload.get('author_name') or None
        published_at = raw_item.get('published_at') or payload.get('created_time') or payload.get('published_at') or raw_item.get('received_at') or datetime.now(timezone.utc).isoformat()
        
        try:
            if isinstance(published_at, datetime):
                validated_published_at = published_at.isoformat()
            else:
                validated_published_at = datetime.fromisoformat(str(published_at).replace('Z', '+00:00')).isoformat()
        except Exception:
            validated_published_at = datetime.now(timezone.utc).isoformat()

        author_name_norm = unicodedata.normalize('NFC', str(author_name)).strip() if author_name else None

        return {
            'success': True,
            'raw_item_id': raw_item.get('id'),
            'source_id': raw_item.get('source_id'),
            'category': hierarchy['category'],
            'target_table': hierarchy['targetTable'],
            'external_id': external_id,
            'post_id': hierarchy['postId'] or external_id,
            'comment_id': hierarchy['commentId'],
            'parent_comment_id': hierarchy['parentCommentId'],
            'author_id': str(author_id) if author_id else None,
            'author_name': author_name_norm,
            'content': normalized_content,
            'content_hash': content_hash,
            'language': language,
            'published_at': validated_published_at,
            'source_url': raw_item.get('source_url') or payload.get('permalink_url') or payload.get('url'),
            'reactions_count': int(payload.get('reactions_count') or payload.get('reactions', {}).get('summary', {}).get('total_count', 0) or payload.get('like_count', 0) or 0),
            'comments_count': int(payload.get('comments_count') or payload.get('comments', {}).get('summary', {}).get('total_count', 0) or 0),
            'shares_count': int(payload.get('shares_count') or payload.get('shares', {}).get('count', 0) or 0),
            'raw_payload': payload
        }
    except Exception as err:
        return {
            'success': False,
            'raw_item_id': raw_item.get('id') if isinstance(raw_item, dict) else None,
            'error': 'NORMALIZATION_EXCEPTION',
            'message': str(err)
        }
