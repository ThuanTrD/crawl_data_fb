"""
Facebook Lead Intelligence V1 - Phase 8: Lead Notification Formatter

Message Fields Required:
- Lead ID
- Tên
- Company
- Phone
- Email
- Location
- Product
- Quantity
- Requirement
- Intent
- Score
- Score band
- Facebook source
- Source URL
- Detected time

Rules:
- DO NOT hallucinate or fabricate missing information.
- If field is None, empty, or missing: strictly display "-".
- Telegram message must always include source URL.
"""

from typing import Dict, Any, Optional

def clean_val(val: Any) -> str:
    """Returns cleaned string or '-' if None/empty/null/none."""
    if val is None:
        return "-"
    s = str(val).strip()
    if not s or s.lower() in ('none', 'null', 'undefined', 'nan'):
        return "-"
    return s

def format_lead_telegram_message(lead_data: Dict[str, Any]) -> str:
    """
    Formats the canonical lead into Telegram Markdown message.
    Strictly replaces missing fields with '-'.
    """
    lead_id = clean_val(lead_data.get('lead_id') or lead_data.get('id'))
    full_name = clean_val(lead_data.get('full_name'))
    company = clean_val(lead_data.get('company_name') or lead_data.get('company'))
    phone = clean_val(lead_data.get('primary_phone') or lead_data.get('phone'))
    email = clean_val(lead_data.get('primary_email') or lead_data.get('email'))
    location = clean_val(lead_data.get('location'))
    product = clean_val(lead_data.get('product_interest') or lead_data.get('product'))
    quantity = clean_val(lead_data.get('quantity'))
    requirement = clean_val(lead_data.get('requirement'))
    intent = clean_val(lead_data.get('primary_intent') or lead_data.get('intent'))
    score = clean_val(lead_data.get('lead_score') or lead_data.get('score'))
    score_band = clean_val(lead_data.get('lead_tier') or lead_data.get('tier'))
    fb_source = clean_val(lead_data.get('source_name'))
    source_url = clean_val(lead_data.get('source_url') or lead_data.get('origin_url'))
    detected_time = clean_val(lead_data.get('detected_at') or lead_data.get('created_at'))

    # If source_url is missing but post_id exists, construct canonical fallback URL
    if source_url == "-" and lead_data.get('post_id'):
        source_url = f"https://www.facebook.com/{lead_data.get('post_id')}"

    return (
        "🎯 *[CƠ HỘI KINH DOANH MỚI - FACEBOOK LEAD]*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 *Lead ID:* `{lead_id}`\n"
        f"👤 *Tên:* {full_name}\n"
        f"🏢 *Company:* {company}\n"
        f"📞 *Phone:* `{phone}`\n"
        f"📧 *Email:* {email}\n"
        f"📍 *Location:* {location}\n"
        f"🏗️ *Product:* {product}\n"
        f"📦 *Quantity:* {quantity}\n"
        f"📝 *Requirement:* {requirement}\n"
        f"🎯 *Intent:* `{intent}`\n"
        f"⭐ *Score:* *{score}*\n"
        f"🏷️ *Score Band:* `{score_band}`\n"
        f"🌐 *Facebook Source:* {fb_source}\n"
        f"🔗 *Source URL:* {source_url}\n"
        f"⏰ *Detected Time:* `{detected_time}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
