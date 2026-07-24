#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Proxy Manager - Parse & Rotate Proxies
Supports: http:// https:// socks4:// socks5:// host:port host:port:user:pass
"""

from typing import List, Optional, Dict
from urllib.parse import urlparse


class ProxyManager:
    def __init__(self, proxy_lines: List[str] = None):
        self.proxies: List[Dict] = []
        if proxy_lines:
            for line in proxy_lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parsed = self._parse(line)
                if parsed:
                    self.proxies.append(parsed)
        self._index = 0

    def _parse(self, line: str) -> Optional[Dict]:
        if '://' in line:
            parsed = urlparse(line)
            if parsed.hostname and parsed.port:
                return {
                    'url': line,
                    'scheme': parsed.scheme,
                    'host': parsed.hostname,
                    'port': parsed.port,
                    'username': parsed.username,
                    'password': parsed.password,
                    'raw': line
                }
            return None

        parts = line.split(':')
        if len(parts) == 2:
            host, port = parts
            try:
                port_num = int(port)
                return {
                    'url': f'http://{host}:{port}',
                    'scheme': 'http',
                    'host': host,
                    'port': port_num,
                    'raw': line
                }
            except ValueError:
                return None
        elif len(parts) == 4:
            host, port, user, pwd = parts
            try:
                port_num = int(port)
                return {
                    'url': f'http://{user}:{pwd}@{host}:{port}',
                    'scheme': 'http',
                    'host': host,
                    'port': port_num,
                    'username': user,
                    'password': pwd,
                    'raw': line
                }
            except ValueError:
                return None
        return None

    def get_next(self) -> Optional[Dict]:
        if not self.proxies:
            return None
        p = self.proxies[self._index % len(self.proxies)]
        self._index += 1
        return p

    def get_requests_format(self, proxy_dict: Optional[Dict] = None) -> Optional[Dict]:
        p = proxy_dict or self.get_next()
        if not p:
            return None
        url = p['url']
        return {'http': url, 'https': url}

    def get_proxy_url(self, proxy_dict: Optional[Dict] = None) -> Optional[str]:
        p = proxy_dict or self.get_next()
        if not p:
            return None
        return p['url']

    def count(self) -> int:
        return len(self.proxies)