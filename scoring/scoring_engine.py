"""
Facebook Lead Intelligence V1 - Phase 6: Lead Scoring Engine (Deterministic)

Exact User Specification:
- REQUEST_QUOTE: +30
- LOOKING_TO_BUY: +25
- LOOKING_FOR_SERVICE: +25
- product: +10
- quantity: +5
- location: +5
- timeline: +5
- phone: +5
- email: +5

Bands:
- 0-29: LOW
- 30-59: MEDIUM
- 60-79: HIGH
- 80+: VERY_HIGH
"""

from typing import Dict, Any, List

def calculate_lead_score(signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes deterministic lead score (0-100) and assigns tier band.
    No AI involved.
    """
    rules_applied: List[Dict[str, Any]] = []
    intent = str(signal.get('intent') or 'IGNORE').strip().upper()
    metadata = signal.get('signal_metadata') or {}
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    # 1. Intent base score
    intent_score = 0
    if intent == 'REQUEST_QUOTE':
        intent_score = 30
        rules_applied.append({'rule': 'INTENT_REQUEST_QUOTE', 'points': 30})
    elif intent == 'LOOKING_TO_BUY':
        intent_score = 25
        rules_applied.append({'rule': 'INTENT_LOOKING_TO_BUY', 'points': 25})
    elif intent == 'LOOKING_FOR_SERVICE':
        intent_score = 25
        rules_applied.append({'rule': 'INTENT_LOOKING_FOR_SERVICE', 'points': 25})
    elif intent == 'URGENT_NEED':
        intent_score = 30
        rules_applied.append({'rule': 'INTENT_URGENT_NEED', 'points': 30})
    elif intent == 'PARTNERSHIP':
        intent_score = 15
        rules_applied.append({'rule': 'INTENT_PARTNERSHIP', 'points': 15})
    elif intent == 'HIRING':
        intent_score = 10
        rules_applied.append({'rule': 'INTENT_HIRING', 'points': 10})
    elif intent in ('RESEARCH', 'COMPARISON', 'RECOMMENDATION', 'EXISTING_CUSTOMER'):
        intent_score = 10
        rules_applied.append({'rule': f'INTENT_{intent}', 'points': 10})
    elif intent in ('DISCUSSION', 'INFORMATION'):
        intent_score = 5
        rules_applied.append({'rule': f'INTENT_{intent}', 'points': 5})
    else:
        intent_score = 0

    # 2. Product (+10)
    product_score = 0
    product = signal.get('product_mention') or metadata.get('product') or signal.get('product_category')
    if product and str(product).strip() and str(product).strip().upper() != 'NONE':
        product_score = 10
        rules_applied.append({'rule': 'HAS_PRODUCT', 'points': 10, 'value': str(product)})

    # 3. Quantity (+5)
    quantity_score = 0
    quantity = metadata.get('quantity')
    if quantity and str(quantity).strip() and str(quantity).strip().upper() != 'NONE':
        quantity_score = 5
        rules_applied.append({'rule': 'HAS_QUANTITY', 'points': 5, 'value': str(quantity)})

    # 4. Location (+5)
    location_score = 0
    location = metadata.get('location')
    if location and str(location).strip() and str(location).strip().upper() != 'NONE':
        location_score = 5
        rules_applied.append({'rule': 'HAS_LOCATION', 'points': 5, 'value': str(location)})

    # 5. Timeline (+5)
    timeline_score = 0
    timeline = metadata.get('timeline') or metadata.get('requirement')
    if timeline and str(timeline).strip() and str(timeline).strip().upper() != 'NONE':
        timeline_score = 5
        rules_applied.append({'rule': 'HAS_TIMELINE', 'points': 5, 'value': str(timeline)})

    # 6. Phone (+5)
    phone_score = 0
    phones = signal.get('extracted_phones') or []
    if phones and len(phones) > 0 and str(phones[0]).strip():
        phone_score = 5
        rules_applied.append({'rule': 'HAS_PHONE', 'points': 5, 'value': str(phones[0])})

    # 7. Email (+5)
    email_score = 0
    emails = signal.get('extracted_emails') or []
    if emails and len(emails) > 0 and str(emails[0]).strip():
        email_score = 5
        rules_applied.append({'rule': 'HAS_EMAIL', 'points': 5, 'value': str(emails[0])})

    # Total Score
    total_score = intent_score + product_score + quantity_score + location_score + timeline_score + phone_score + email_score
    total_score = max(0, min(100, total_score))

    # Band Tier Classification: 0-29 LOW, 30-59 MEDIUM, 60-79 HIGH, 80+ VERY_HIGH
    if total_score >= 80:
        tier = 'VERY_HIGH'
    elif total_score >= 60:
        tier = 'HIGH'
    elif total_score >= 30:
        tier = 'MEDIUM'
    else:
        tier = 'LOW'

    return {
        'intent_score': intent_score,
        'contact_score': phone_score + email_score,
        'profile_score': 0,
        'context_score': product_score + quantity_score + location_score + timeline_score,
        'total_score': total_score,
        'tier': tier,
        'scoring_rules_applied': rules_applied
    }
