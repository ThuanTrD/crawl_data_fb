/**
 * Facebook Lead Intelligence V1 - Phase 5: Keyword Filter
 * 
 * Filters raw items BEFORE calling AI:
 * - Saves latency and API costs.
 * - Filters out non-construction noise.
 */

const KEYWORD_GROUPS = {
  'MUA_HANG': [
    'báo giá',
    'xin giá',
    'giá bao nhiêu',
    'cần mua',
    'đang tìm mua',
    'tìm mua',
    'ai bán',
    'mua ở đâu',
    'cần cung cấp'
  ],
  'DICH_VU': [
    'cần thiết kế',
    'cần thi công',
    'tìm nhà thầu',
    'tìm thầu',
    'cần kỹ sư',
    'cần kiến trúc sư',
    'cần bóc tách',
    'cần dự toán'
  ],
  'VAT_LIEU': [
    'thép',
    'xi măng',
    'gạch',
    'cát',
    'đá',
    'bê tông',
    'sắt',
    'tôn',
    'vật liệu xây dựng'
  ],
  'SOFTWARE': [
    'autocad',
    'revit',
    'bim',
    'tekla',
    'civil 3d',
    'sketchup',
    'etabs',
    'sap2000',
    'plaxis',
    'enjicad'
  ],
  'CONSTRUCTION': [
    'công trình',
    'xây dựng',
    'nhà phố',
    'biệt thự',
    'nhà xưởng',
    'dự án'
  ]
};

/**
 * Checks text against 5 keyword groups.
 * @param {string} text 
 * @returns {object} { matched: boolean, matched_groups: string[], matched_keywords: string[] }
 */
function checkKeywordFilter(text) {
  if (!text || typeof text !== 'string') {
    return {
      matched: false,
      matched_groups: [],
      matched_keywords: []
    };
  }

  const normalized = text.normalize('NFC').toLowerCase();
  const matchedGroups = new Set();
  const matchedKeywords = new Set();

  for (const [groupName, keywords] of Object.entries(KEYWORD_GROUPS)) {
    for (const kw of keywords) {
      // Use boundary-safe word or substring matching
      const kwLower = kw.toLowerCase();
      // For short keywords like 'đá', 'cát', 'sắt', 'tôn', 'bim', require word boundary
      let isMatch = false;
      if (kwLower.length <= 4) {
        const regex = new RegExp(`(^|[\\s,.;:!?()\\[\\]\\/\\-])${kwLower}([\\s,.;:!?()\\[\\]\\/\\-]|$)`, 'i');
        isMatch = regex.test(normalized);
      } else {
        isMatch = normalized.includes(kwLower);
      }

      if (isMatch) {
        matchedGroups.add(groupName);
        matchedKeywords.add(kw);
      }
    }
  }

  return {
    matched: matchedGroups.size > 0,
    matched_groups: Array.from(matchedGroups),
    matched_keywords: Array.from(matchedKeywords)
  };
}

module.exports = {
  KEYWORD_GROUPS,
  checkKeywordFilter
};
