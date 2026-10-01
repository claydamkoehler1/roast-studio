"""Public product-page capture and flexible AI bean documents."""
import http.client
import ipaddress
import json
import re
import socket
import ssl
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit, urljoin

MAX_BYTES = 4_000_000
MAX_TEXT = 100_000


def public_url(value):
    if not isinstance(value, str) or len(value) > 3000:
        raise ValueError('Enter a public product-page URL')
    p = urlsplit(value.strip())
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password or p.port not in (None, 80, 443):
        raise ValueError('Use a public http or https product-page link')
    if any(ord(c) < 32 for c in value) or p.hostname.lower() == 'localhost':
        raise ValueError('Use a public product-page link')
    return urlunsplit((p.scheme, p.netloc, p.path or '/', p.query, ''))


def public_address(host, port):
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError('Could not reach that store. Paste the page text instead.') from exc
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('Only public store pages can be imported')
    return addresses[0][4][0]


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.products = [], []
        self.skip = []
        self.script = None
        self.script_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script':
            self.script = attrs.get('type', '')
            self.script_parts = []
        if tag in ('script', 'style', 'svg', 'nav', 'footer', 'noscript'):
            self.skip.append(tag)
        if tag in ('p','div','h1','h2','h3','h4','li','tr','td','dt','dd','br','section') and not self.skip:
            self.parts.append('\n')
        if tag == 'meta' and attrs.get('name', attrs.get('property', '')) in ('description','og:title','og:description'):
            self.parts.append('\n' + attrs.get('content', '') + '\n')

    def handle_endtag(self, tag):
        if tag == 'script' and self.script == 'application/ld+json':
            try:
                self.collect_product(json.loads(''.join(self.script_parts)))
            except (ValueError, TypeError):
                pass
        if tag == 'script':
            self.script = None
        if tag in self.skip:
            # HTMLParser does not repair malformed markup; unwind a matching blocked tag.
            self.skip = self.skip[:len(self.skip)-1-self.skip[::-1].index(tag)]
        if tag in ('p','div','h1','h2','h3','li','tr','section') and not self.skip:
            self.parts.append('\n')

    def handle_data(self, text):
        if self.script == 'application/ld+json':
            self.script_parts.append(text)
        if not self.skip:
            self.parts.append(text)

    def collect_product(self, node):
        if isinstance(node, list):
            for value in node:
                self.collect_product(value)
        elif isinstance(node, dict):
            kinds = node.get('@type', [])
            if kinds == 'Product' or isinstance(kinds, list) and 'Product' in kinds:
                self.products.append(node)
            elif '@graph' in node:
                self.collect_product(node['@graph'])

    def text(self):
        text = '\n'.join(re.sub(r'\s+', ' ', line).strip() for line in ''.join(self.parts).splitlines())
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        if self.products:
            # Product JSON often preserves tasting notes hidden in expandable page panels.
            text = 'STRUCTURED PRODUCT DATA\n' + json.dumps(self.products, ensure_ascii=False) + '\n\nPAGE TEXT\n' + text
        return text


def capture_page(url):
    url = public_url(url)
    original = url
    for _ in range(5):
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == 'https' else 80)
        address = public_address(parts.hostname, port)
        connection = http.client.HTTPSConnection(parts.hostname, port, timeout=18) if parts.scheme == 'https' else http.client.HTTPConnection(parts.hostname, port, timeout=18)
        try:
            # Pin the validated address; retain hostname-based TLS verification and SNI.
            sock = socket.create_connection((address, port), timeout=18)
            if parts.scheme == 'https':
                try:
                    sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parts.hostname)
                except Exception:
                    sock.close()
                    raise
            connection.sock = sock
            connection.request('GET', urlunsplit(('', '', parts.path or '/', parts.query, '')),
                headers={'User-Agent':'Mozilla/5.0 (compatible; RoastingStudio/3.1; product-page import)', 'Accept':'text/html,text/plain', 'Accept-Encoding':'identity'})
            response = connection.getresponse()
            if response.status in (301,302,303,307,308):
                url = public_url(urljoin(url, response.getheader('Location', '')))
                continue
            if response.status != 200:
                raise ValueError(f'The store returned HTTP {response.status}. Paste the product-page text below instead.')
            content_type = response.getheader('Content-Type', '')
            if not any(kind in content_type for kind in ('text/html','application/xhtml+xml','text/plain')):
                raise ValueError('This link is not a readable web page. Paste the page text instead.')
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('This page is too large. Paste the relevant product-page text instead.')
            match = re.search(r'charset=["\s]*([^;"\s]+)', content_type, re.I)
            try:
                html = raw.decode(match.group(1) if match else 'utf-8', errors='replace')
            except LookupError:
                html = raw.decode('utf-8', errors='replace')
            parser = PageText()
            if 'text/plain' in content_type:
                text = html
            else:
                parser.feed(html)
                text = parser.text()
            if len(text.strip()) < 120:
                raise ValueError('The page did not expose enough product information. Paste its text instead.')
            return dict(url=url, requested_url=original, text=text[:MAX_TEXT], truncated=len(text)>MAX_TEXT, method='web page')
        except (OSError, http.client.HTTPException) as exc:
            raise ValueError('The store page could not be read. Paste the product-page text instead.') from exc
        finally:
            connection.close()
    raise ValueError('Too many redirects. Paste the final product-page link or its text.')


def validate_document(raw):
    if not isinstance(raw, dict):
        raise ValueError('Astra returned an unreadable bean profile')
    if raw.get('name') == 'IMPORT_UNREADABLE':
        raise ValueError('The page did not contain a readable coffee product. Paste its product description instead.')
    def text(value, limit=12000, optional=False):
        if not isinstance(value, str) or len(value)>limit or (not optional and not value.strip()):
            raise ValueError('Astra returned an incomplete bean profile')
        return value.strip()
    result={k:text(raw.get(k), 300 if k in ('name','origin','process','supplier') else 12000, k in ('origin','process','supplier')) for k in ('name','origin','process','supplier','summary','roasting_context')}
    for key in ('flavors','unknowns'):
        values=raw.get(key)
        if not isinstance(values,list) or len(values)>40:
            raise ValueError('Invalid bean profile notes')
        result[key]=[text(v,2000) for v in values]
    for key,fields in (('facts',('label','value')),('sections',('title','body'))):
        items=raw.get(key)
        if not isinstance(items,list) or len(items)>80:
            raise ValueError('Invalid bean profile sections')
        result[key]=[{field:text(item.get(field),12000) for field in fields} for item in items if isinstance(item,dict)]
        if len(result[key])!=len(items):
            raise ValueError('Invalid bean profile section')
    if not result['facts'] and not result['sections']:
        raise ValueError('No coffee details were found. Paste the product description and try again.')
    return result
