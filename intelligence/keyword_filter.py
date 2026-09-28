"""
Facebook Lead Intelligence V1 - Phase 5: Keyword Filter (Python)
"""

import re
import unicodedata
from typing import Dict, Any, List, Set

KEYWORD_GROUPS = {
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
}

def check_keyword_filter(text: str) -> Dict[str, Any]:
    if not text or not isinstance(text, str):
        return {
            'matched': False,
            'matched_groups': [],
            'matched_keywords': []
        }

    normalized = unicodedata.normalize('NFC', text).lower()
    matched_groups: Set[str] = set()
    matched_keywords: Set[str] = set()

    for group_name, keywords in KEYWORD_GROUPS.items():
        for kw in keywords:
            kw_lower = kw.lower()
            if len(kw_lower) <= 4:
                pattern = rf'(?:^|[\s,.;:!?()\[\]/\-]){re.escape(kw_lower)}(?:[\s,.;:!?()\[\]/\-]|$)'
                if re.search(pattern, normalized, re.IGNORECASE):
                    matched_groups.add(group_name)
                    matched_keywords.add(kw)
            else:
                if kw_lower in normalized:
                    matched_groups.add(group_name)
                    matched_keywords.add(kw)

    return {
        'matched': len(matched_groups) > 0,
        'matched_groups': sorted(list(matched_groups)),
        'matched_keywords': sorted(list(matched_keywords))
    }
