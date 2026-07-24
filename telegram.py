#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Telegram Notifier Module
Sends ONLY Valid Hits to your Telegram for instant alerts.
"""

import requests
import os
from datetime import datetime

# ============================================================
#  CONFIG - PUT YOUR CREDENTIALS HERE
# ============================================================
DEFAULT_BOT_TOKEN = "8672176593:AAFMftQVQ76lQeWJ1Ug2-BLH90o4_upwK0w" # <-- ضع توكن البوت هنا
DEFAULT_CHAT_ID = "8684227781"       # <-- ضع شات آيدي هنا


class TelegramNotifier:
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.token = bot_token or DEFAULT_BOT_TOKEN
        self.chat_id = chat_id or DEFAULT_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.session = requests.Session()

    # --------------------------------------------------------
    def send_message(self, text: str) -> bool:
        if self.token == "8672176593:AAFMftQVQ76lQeWJ1Ug2-BLH90o4_upwK0w" or not self.token:
            print("[Telegram] Skipped (no token configured)")
            return False
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            r = self.session.post(url, json=payload, timeout=15)
            return r.status_code == 200
        except Exception as e:
            print(f"[Telegram] Send error: {e}")
            return False

    # --------------------------------------------------------
    def send_document(self, file_path: str, caption: str = "") -> bool:
        if self.token == "8672176593:AAFMftQVQ76lQeWJ1Ug2-BLH90o4_upwK0w" or not self.token:
            print("[Telegram] Skipped (no token configured)")
            return False
        if not os.path.exists(file_path):
            return False
        try:
            url = f"{self.base_url}/sendDocument"
            with open(file_path, 'rb') as fh:
                files = {"document": fh}
                data = {
                    "chat_id": self.chat_id,
                    "caption": caption[:1024],
                    "parse_mode": "Markdown"
                }
                r = self.session.post(url, data=data, files=files, timeout=30)
            return r.status_code == 200
        except Exception as e:
            print(f"[Telegram] Document error: {e}")
            return False

    # --------------------------------------------------------
    def send_valids(self, tool_name: str, valids: list, total_checked: int):
        """
        Sends a summary of valid hits to Telegram.
        If hits are many, splits into chunks.
        """
        if not valids:
            return

        # Summary message
        summary = (
            f"✅ *{tool_name} — Valid Hits Found*\n\n"
            f"📊 Total Checked: `{total_checked:,}`\n"
            f"🎯 Valid Hits: `{len(valids):,}`\n"
            f"📈 Rate: `{(len(valids)/total_checked*100):.1f}%`\n"
            f"⏰ `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        )
        self.send_message(summary)

        # Send hits in code blocks (chunks of 40 to avoid limits)
        batch_size = 40
        for i in range(0, len(valids), batch_size):
            batch = valids[i:i + batch_size]
            chunk_text = "\n".join(batch)
            if len(chunk_text) > 3800:
                chunk_text = chunk_text[:3800]
            text = f"🎯 *Hits ({i+1}-{min(i+batch_size, len(valids))}):*\n```\n{chunk_text}\n```"
            self.send_message(text)

 # --------------------------------------------------------
    def send_file_alert(self, file_path: str, tool_name: str, stats: dict):
        caption = (
            f"📁 *{tool_name} Results File*\n\n"
            f"✅ Valid: `{stats.get('valid', 0):,}`\n"
            f"📊 Total: `{stats.get('total', 0):,}`"
        )
        self.send_document(file_path, caption)