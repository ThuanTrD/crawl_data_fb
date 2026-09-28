"""
Facebook Lead Intelligence V1 - External Webhook & Google Sheets Dispatcher

Dispatches qualified leads (Hot Leads / Leads with Phone) to external webhook URLs
(e.g., Google Apps Script, Lark Base Webhook, Zapier, Make, Internal CRM).
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, Optional

def dispatch_lead_webhook(webhook_url: str, lead_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Sends lead payload to webhook URL via HTTP POST"""
    if not webhook_url or not webhook_url.startswith("http"):
        return False, "Invalid webhook URL"

    payload = json.dumps({
        "event": "LEAD_DETECTED",
        "lead_id": str(lead_data.get("id")),
        "full_name": lead_data.get("full_name") or "-",
        "phone": lead_data.get("primary_phone") or "-",
        "email": lead_data.get("primary_email") or "-",
        "company": lead_data.get("company_name") or "-",
        "product": lead_data.get("product_interest") or "-",
        "intent": lead_data.get("primary_intent") or "-",
        "score": lead_data.get("lead_score") or 0,
        "tier": lead_data.get("lead_tier") or "LOW",
        "source_group": lead_data.get("source_name") or "Facebook",
        "post_url": lead_data.get("source_url") or "-",
        "timestamp": lead_data.get("created_at") or ""
    }).encode("utf-8")

    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "FacebookLeadIntelligence-Webhook/1.0"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status in (200, 201, 204):
                return True, None
            return False, f"HTTP {response.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTPError {e.code}: {e.reason}"
    except Exception as err:
        return False, str(err)
