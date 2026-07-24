#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NOBODYxSOUDZ2 Checkers Engine
Office365 MX | O365 Combo | Country Sorter | Webmail Sorter
"""

import os
import dns.resolver
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Optional
from datetime import datetime
from collections import defaultdict
import threading
import zipfile
import re

# ============================================================
#  OFFICE365 MX CHECKER
# ============================================================
O365_MX_DOMAINS = [
    'protection.outlook.com',
    'mail.protection.outlook.com',
    'outlook.com',
    'office365.com'
]


def check_office365_mx(email: str) -> bool:
    try:
        domain = email.split('@')[1]
        resolver = dns.resolver.Resolver()
        resolver.timeout = 3
        resolver.lifetime = 3
        mx_records = resolver.resolve(domain, 'MX')
        for mx in mx_records:
            mx_server = str(mx.exchange).lower().rstrip('.')
            for o365 in O365_MX_DOMAINS:
                if o365 in mx_server:
                    return True
        return False
    except Exception:
        return False


def check_single_email(email: str) -> Tuple[str, bool]:
    return (email, check_office365_mx(email))


def process_office365_check_parallel(emails: List[str], progress_callback=None, max_workers: int = 50) -> List[str]:
    valid_office365 = []
    total = len(emails)
    completed = 0
    results_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_email = {executor.submit(check_single_email, email): email for email in emails}
        for future in as_completed(future_to_email):
            email, is_valid = future.result()
            completed += 1
            if is_valid:
                with results_lock:
                    valid_office365.append(email)
            if progress_callback and (completed % 50 == 0 or completed == total):
                progress_callback(completed, total, len(valid_office365))

    if progress_callback:
        progress_callback(total, total, len(valid_office365))
    return valid_office365

# ============================================================
#  COMBO CHECKER (Business domains only, no webmail)
# ============================================================
EXCLUDED_WEBMAIL = [
    'gmail.com', 'yahoo.com', 'yahoo.co.uk', 'yahoo.fr', 'yahoo.de', 'yahoo.co.jp',
    'aol.com', 'hotmail.com', 'hotmail.co.uk', 'hotmail.fr', 'hotmail.de',
    'outlook.com', 'live.com', 'msn.com', 'mail.com', 'gmx.com', 'gmx.net',
    'web.de', 'gmx.de', 't-online.de', 'freenet.de', 'arcor.de',
    'mail.ru', 'yandex.ru', 'rambler.ru', 'bk.ru', 'list.ru', 'inbox.ru',
    'orange.fr', 'sfr.fr', 'free.fr', 'laposte.net',
    'libero.it', 'tin.it', 'alice.it', 'virgilio.it',
    'terra.es', 'telefonica.net',
    'uol.com.br', 'bol.com.br', 'ig.com.br', 'terra.com.br',
    'qq.com', '163.com', '126.com', 'sina.com', 'sohu.com',
    'naver.com', 'daum.net', 'hanmail.net',
    'bigpond.com', 'optusnet.com.au', 'iinet.net.au',
    'btinternet.com', 'virginmedia.com', 'sky.com', 'talktalk.net',
    'cox.net', 'comcast.net', 'verizon.net', 'att.net', 'charter.net',
    'rogers.com', 'bell.net', 'shaw.ca', 'telus.net',
    'ziggo.nl', 'kpnmail.nl', 'xs4all.nl',
    'icloud.com', 'me.com', 'mac.com', 'protonmail.com', 'yandex.com',
]


def is_business_domain(email: str) -> bool:
    try:
        domain = email.split('@')[1].lower()
        for wm in EXCLUDED_WEBMAIL:
            if domain == wm or domain.endswith('.' + wm):
                return False
        return True
    except Exception:
        return False


def check_single_combo(combo: str) -> Tuple[str, bool, str]:
    email = combo.split(':')[0].strip()
    if not is_business_domain(email):
        return (combo, False, 'webmail')
    if check_office365_mx(email):
        return (combo, True, 'valid')
    return (combo, False, 'invalid')


def process_combo_checker_parallel(combos: List[str], progress_callback=None, max_workers: int = 50) -> Tuple[List[str], int, int]:
    valid_office365 = []
    skipped_webmail = 0
    invalid_mx = 0
    total = len(combos)
    completed = 0
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_combo = {executor.submit(check_single_combo, combo): combo for combo in combos}
        for future in as_completed(future_to_combo):
            combo, is_valid, status = future.result()
            completed += 1
            with lock:
                if status == 'webmail':
                    skipped_webmail += 1
                elif status == 'valid':
                    valid_office365.append(combo)
                else:
                    invalid_mx += 1
            if progress_callback and (completed % 50 == 0 or completed == total):
                progress_callback(completed, total, len(valid_office365), skipped_webmail, invalid_mx)

    if progress_callback:
        progress_callback(total, total, len(valid_office365), skipped_webmail, invalid_mx)
    return valid_office365, skipped_webmail, invalid_mx

# ============================================================
#  COUNTRY SORTER
# ============================================================
COUNTRY_TLDS = {
    'au': 'Australia',
    'us': 'USA',
    'uk': 'UK',
    'gb': 'UK',
    'de': 'Germany',
    'fr': 'France',
    'it': 'Italy',
    'es': 'Spain',
    'ca': 'Canada',
    'br': 'Brazil',
    'jp': 'Japan',
    'cn': 'China',
    'in': 'India',
    'ru': 'Russia',
    'kw': 'Kuwait',
    'ax': 'Aland Islands',
    'sa': 'Saudi Arabia',
    'nz': 'New Zealand',
    'mx': 'Mexico',
    'qa': 'Qatar',
    'bh': 'Bahrain',
    'om': 'Oman',
    'at': 'Austria',
    'cy': 'Cyprus',
    'dk': 'Denmark',
    'nl': 'Netherlands',
    'fi': 'Finland',
    'gi': 'Gibraltar',
    'gr': 'Greece',
    'gl': 'Greenland',
    'hk': 'Hong Kong',
    'ir': 'Iran',
    'ie': 'Ireland',
    'il': 'Israel',
    'lv': 'Latvia',
    'lb': 'Lebanon',
    'lu': 'Luxembourg',
    'mt': 'Malta',
    'mc': 'Monaco',
    'no': 'Norway',
    'pt': 'Portugal',
    'ro': 'Romania',
    'sg': 'Singapore',
    'se': 'Sweden',
    'ch': 'Switzerland',
    'tr': 'Turkey',
    'ae': 'UAE'
}


WEBMAIL_COUNTRY_MAP = {
    'yahoo.com': 'USA',
    'gmail.com': 'USA',
    'aol.com': 'USA',
    'hotmail.com': 'USA',
    'hotmail.co.uk': 'UK',
    'hotmail.fr': 'France',
    'hotmail.de': 'Germany',
    'hotmail.com.au': 'Australia',
    'hotmail.com.mx': 'Mexico',
    'hotmail.com.ar': 'Argentina',
    'live.ca': 'Canada',
    'live.com.au': 'Australia',
    'live.co.uk': 'UK',
    'live.com.pt': 'Portugal',
    'live.in': 'India',
    'live.cn': 'China',
    'live.jp': 'Japan',
    'live.be': 'Belgium',
    'outlook.com': 'USA',
    'outlook.co.uk': 'UK',
    'outlook.de': 'Germany',
    'outlook.fr': 'France',
    'outlook.it': 'Italy',
    'outlook.es': 'Spain',
    'hotmail.co.jp': 'Japan',
    'hotmail.com.br': 'Brazil',
    'hotmail.es': 'Spain',
    'hotmail.it': 'Italy',
    'hotmail.com.tw': 'Taiwan',
    'googlemail.com': 'USA',
    'protonmail.com': 'Switzerland',
    'rediffmail.com': 'India',
    'rambler.ru': 'Russia',
    'yandex.com': 'Russia',
    'yandex.ru': 'Russia',
    'yandex.kz': 'Kazakhstan',
    'yandex.com.tr': 'Turkey',
    'mail.ru': 'Russia',
    'bk.ru': 'Russia',
    'list.ru': 'Russia',
    'inbox.ru': 'Russia',
    'gmx.com': 'Germany',
    'gmx.net': 'Germany',
    'gmx.at': 'Austria',
    'gmx.ch': 'Switzerland',
    'web.de': 'Germany',
    'mail.com': 'Germany',
    'freenet.de': 'Germany',
    'me.com': 'USA',
    'icloud.com': 'USA',
    'sbcglobal.net': 'USA',
    'bellsouth.net': 'USA',
    'netscape.net': 'USA',
    'att.net': 'USA',
    'verizon.net': 'USA',
    'btinternet.com': 'UK',
    'virginmedia.com': 'UK',
    'orange.fr': 'France',
    'sfr.fr': 'France',
    'free.fr': 'France',
    'wanadoo.fr': 'France',
    'laposte.net': 'France',
    'terra.es': 'Spain',
    'telefonica.net': 'Spain',
    'libero.it': 'Italy',
    'tin.it': 'Italy',
    'alice.it': 'Italy',
    'virgilio.it': 'Italy',
    'naver.com': 'South Korea',
    'daum.net': 'South Korea',
    'hanmail.net': 'South Korea',
    'nate.com': 'South Korea',
    'yahoo.co.jp': 'Japan',
    'yahoo.com.tw': 'Taiwan',
    'yahoo.com.au': 'Australia',
    'yahoo.com.br': 'Brazil',
    'yahoo.com.mx': 'Mexico',
    'yahoo.com.ar': 'Argentina',
    'yahoo.com.ph': 'Philippines',
    'yahoo.co.uk': 'UK',
    'yahoo.fr': 'France',
    'yahoo.de': 'Germany',
    'yahoo.it': 'Italy',
    'yahoo.es': 'Spain',
    'yahoo.se': 'Sweden',
    'yahoo.no': 'Norway',
    'yahoo.dk': 'Denmark',
    'yahoo.fi': 'Finland',
    'bol.com.br': 'Brazil',
    'uol.com.br': 'Brazil',
    'terra.com.br': 'Brazil',
    'ig.com.br': 'Brazil',
    'r7.com': 'Brazil',
    'globo.com': 'Brazil',
    'globomail.com': 'Brazil',
    'zipmail.com.br': 'Brazil',
    'oi.com.br': 'Brazil',
    'pop.com.br': 'Brazil',
    'terra.com': 'USA',
    'terra.com.mx': 'Mexico',
    'terra.cl': 'Chile',
    'terra.com.ar': 'Argentina',
    'terra.com.co': 'Colombia',
    'terra.com.ve': 'Venezuela',
    'terra.com.pe': 'Peru',
    'terra.cr': 'Costa Rica',
    'terra.com.pa': 'Panama',
    'terra.gt': 'Guatemala',
    'terra.com.hn': 'Honduras',
    'terra.com.ni': 'Nicaragua',
    'terra.com.sv': 'El Salvador',
    'terra.com.bo': 'Bolivia',
    'terra.com.py': 'Paraguay',
    'terra.com.uy': 'Uruguay',
    'terra.ec': 'Ecuador',
    'terra.com.do': 'Dominican Republic',
    'terra.pr': 'Puerto Rico',
    'terra.com.cu': 'Cuba',
}


def get_country_from_domain(email: str) -> str:
    try:
        domain = email.split('@')[1].lower()
        if ':' in domain:
            domain = domain.split(':')[0]
        if domain in WEBMAIL_COUNTRY_MAP:
            return WEBMAIL_COUNTRY_MAP[domain]
        tld = domain.split('.')[-1]
        if tld in COUNTRY_TLDS:
            return COUNTRY_TLDS[tld]
        return 'Unknown'
    except Exception:
        return 'Unknown'


def process_country_sort(emails: List[str], sort_type='all', target_country=None, progress_callback=None, use_whois=False):
    country_dict = defaultdict(list)
    unknowns = []
    total = len(emails)
    for i, email in enumerate(emails):
        country = get_country_from_domain(email)
        if country == 'Unknown':
            unknowns.append(email)
        else:
            country_dict[country].append(email)
        if progress_callback and (i % 100 == 0 or i == total - 1):
            progress_callback(i + 1, total, len(country_dict))

    if sort_type == 'unique' and target_country:
        return country_dict.get(target_country, []), dict(country_dict), unknowns
    return None, dict(country_dict), unknowns


def create_country_zip_from_results(country_dict, unknowns=None):
    zip_path = f"countries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for country, lines in country_dict.items():
            if not lines or country == 'Unknown':
                continue
            fname = f"{country.replace(' ', '_').lower()}.txt"
            with open(fname, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            zf.write(fname)
            os.remove(fname)

        if unknowns:
            fname = "unknown_countries.txt"
            with open(fname, 'w', encoding='utf-8') as f:
                f.write('\n'.join(unknowns))
            zf.write(fname)
            os.remove(fname)

        summary = "summary.txt"
        total = sum(len(v) for v in country_dict.values()) + len(unknowns or [])
        with open(summary, 'w', encoding='utf-8') as f:
            f.write("COUNTRY DISTRIBUTION SUMMARY\n")
            f.write(f"Total: {total:,}\n\n")
            for c, lines in sorted(country_dict.items(), key=lambda x: len(x[1]), reverse=True):
                if c != 'Unknown':
                    pct = (len(lines) / total * 100) if total else 0
                    f.write(f"{c}: {len(lines):,} ({pct:.1f}%)\n")
            if unknowns:
                pct = (len(unknowns) / total * 100) if total else 0
                f.write(f"\nUnknown: {len(unknowns):,} ({pct:.1f}%)\n")
        zf.write(summary)
        os.remove(summary)
    return zip_path

# ============================================================
#  WEBMAIL SORTER
# ============================================================
def get_domain_from_line(line: str) -> Optional[str]:
    line = line.strip()
    if not line:
        return None
    email_part = line.split(':', 1)[0].strip() if ':' in line else line.strip()
    if '@' not in email_part:
        return None
    domain = email_part.split('@')[1].lower()
    if ':' in domain:
        domain = domain.split(':')[0]
    return domain


def sort_by_target_domain(lines: List[str], target: str) -> List[str]:
    target = target.lower().strip().lstrip('@')
    results = []
    for line in lines:
        if target in line.lower():
            results.append(line)
        else:
            dom = get_domain_from_line(line)
            if dom and (dom == target or target in dom):
                results.append(line)
    return results


def extract_all_domains(lines: List[str]) -> Dict[str, List[str]]:
    d = defaultdict(list)
    for line in lines:
        domain = get_domain_from_line(line)
        if domain:
            d[domain].append(line)
        else:
            d['unknown_domain'].append(line)
    return dict(d)


def process_webmail_sort(lines: List[str], sort_type='all', target_domain=None, progress_callback=None):
    total = len(lines)
    if progress_callback:
        progress_callback(0, total)

    if sort_type == 'target' and target_domain:
        res = sort_by_target_domain(lines, target_domain)
        if progress_callback:
            progress_callback(total, total)
        return res, {}
    else:
        d = extract_all_domains(lines)
        if progress_callback:
            progress_callback(total, total)
        return None, d


def create_target_domain_file(filtered_lines: List[str], target_domain: str) -> str:
    safe = target_domain.replace('.', '_').replace('@', '')
    out = f"{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(filtered_lines))
    return out


def create_domain_zip_file(domain_dict: Dict[str, List[str]], base_name="domains"):
    zip_path = f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for domain, lines in domain_dict.items():
            if not lines or domain == 'unknown_domain':
                continue
            fname = f"{domain.replace('.', '_')}.txt"
            with open(fname, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            zf.write(fname)
            os.remove(fname)

        if 'unknown_domain' in domain_dict and domain_dict['unknown_domain']:
            fname = "unknown_domains.txt"
            with open(fname, 'w', encoding='utf-8') as f:
                f.write('\n'.join(domain_dict['unknown_domain']))
            zf.write(fname)
            os.remove(fname)

        summary = "summary.txt"
        total = sum(len(v) for v in domain_dict.values())
        with open(summary, 'w', encoding='utf-8') as f:
            f.write("DOMAIN EXTRACTION SUMMARY\n")
            f.write(f"Total: {total:,}\n")
            for dom, lines in sorted(domain_dict.items(), key=lambda x: len(x[1]), reverse=True):
                if dom != 'unknown_domain':
                    pct = (len(lines) / total * 100) if total else 0
                    f.write(f"{dom}: {len(lines):,} ({pct:.1f}%)\n")
        zf.write(summary)
        os.remove(summary)
    return zip_path