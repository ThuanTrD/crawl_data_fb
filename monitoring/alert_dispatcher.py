"""
Facebook Lead Intelligence V1 - Phase 7: Telegram Alert & Health Summary Dispatcher

Dispatches alerts for:
- Nhiều source bị rate limit
- Source permission error (403)
- Authentication error (401)
- Processing backlog quá lớn
- AI failure tăng mạnh
- Database failure
- Collector chết
- Global collection bị disable

Also formats real-time Operational Health Summary:
sources_active, sources_paused, sources_rate_limited,
posts_collected, posts_relevant, leads_detected, qualified_leads,
errors, 429_count, AI_errors
"""

import os
import json
import urllib.request
from typing import Dict, Any, List

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

def format_telegram_alert(alert: Dict[str, Any]) -> str:
    """Formats a single alert for Telegram notification"""
    level = alert.get('level', 'INFO')
    icon = '🚨' if level == 'CRITICAL' else ('⚠️' if level == 'WARNING' else 'ℹ️')
    return (
        f"{icon} *[FB LEAD INTEL ALERT - {level}]*\n"
        f"*Loại sự cố:* `{alert.get('type')}`\n"
        f"*Nội dung:* {alert.get('message')}\n"
        f"*Thời gian:* `NOW`"
    )

def format_health_summary_message(summary: Dict[str, Any]) -> str:
    """Formats the required operational health summary"""
    return (
        "📊 *HỆ THỐNG FACEBOOK LEAD INTELLIGENCE V1 - BÁO CÁO VẬN HÀNH*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🟢 *Trạng thái Nguồn (Sources):*\n"
        f"  • Đang hoạt động (sources_active): *{summary.get('sources_active', 0)}*\n"
        f"  • Tạm dừng (sources_paused): *{summary.get('sources_paused', 0)}*\n"
        f"  • Bị giới hạn (sources_rate_limited): *{summary.get('sources_rate_limited', 0)}*\n\n"
        "📥 *Thu thập & Xử lý (Data Pipeline):*\n"
        f"  • Bài viết đã thu thập (posts_collected): *{summary.get('posts_collected', 0)}*\n"
        f"  • Bài viết liên quan ngành (posts_relevant): *{summary.get('posts_relevant', 0)}*\n"
        f"  • Tín hiệu tiềm năng (leads_detected): *{summary.get('leads_detected', 0)}*\n"
        f"  • Khách hàng đạt chuẩn (qualified_leads): *{summary.get('qualified_leads', 0)}*\n\n"
        "⚠️ *Lỗi & Cảnh báo (Errors & Health):*\n"
        f"  • Tổng số lỗi 24h (errors): *{summary.get('errors', 0)}*\n"
        f"  • Số lần chạm Rate Limit 429 (429_count): *{summary.get('429_count', 0)}*\n"
        f"  • Lỗi cổng AI (AI_errors): *{summary.get('AI_errors', 0)}*\n"
        f"  • Hàng đợi tồn đọng (processing_backlog): *{summary.get('processing_backlog', 0)}*\n"
        f"  • Global Kill Switch: *{'BẬT (Hoạt động)' if summary.get('global_collection_enabled') else 'TẮT (Đã ngắt)'}*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

def dispatch_telegram_message(message_text: str) -> bool:
    """
    Sends message to Telegram via Bot API if configured, or prints to log.
    """
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = json.dumps({
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message_text,
            'parse_mode': 'Markdown'
        }).encode('utf-8')
        req = urllib.request.Request(
            url, data=payload, headers={'Content-Type': 'application/json'}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"Telegram dispatch failed: {e}")
            return False
    else:
        # Logging fallback
        print("\n--- [TELEGRAM DISPATCH CONSOLE] ---")
        print(message_text)
        print("----------------------------------\n")
        return True
