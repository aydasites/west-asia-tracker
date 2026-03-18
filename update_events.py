#!/usr/bin/env python3
"""
West-Asia Strike Tracker — Auto-Updater
Runs every 6 hours via GitHub Actions.
Fetches RSS feeds, extracts strike events using keyword matching,
deduplicates, and injects new events into index.html.
"""

import re
import html
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError

# ─── RSS FEEDS ──────────────────────────────────────────────────────────────
RSS_FEEDS = [
    ("Al Jazeera",        "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Reuters",           "https://feeds.reuters.com/reuters/topNews"),
    ("Reuters World",     "https://feeds.reuters.com/reuters/worldNews"),
    ("Breaking Defense",  "https://breakingdefense.com/feed/"),
    ("Times of Israel",   "https://www.timesofisrael.com/feed/"),
    ("Arab News",         "https://www.arabnews.com/rss.xml"),
    ("Jerusalem Post",    "https://www.jpost.com/Rss/RssFeedsHeadlines.aspx"),
    ("BBC World",         "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Middle East Eye",   "https://www.middleeasteye.net/rss"),
    ("NPR World",        "https://feeds.npr.org/1004/rss.xml"),
    ("The Guardian",      "https://www.theguardian.com/world/rss"),
    ("Defense One",       "https://www.defenseone.com/rss/"),
]

LOOKBACK_HOURS = 48  # how far back to check for new articles (wide window; dedup prevents repeats)

# ─── KEYWORD PATTERNS ───────────────────────────────────────────────────────
STRIKE_RX = re.compile(
    r'\b(drone|UAV|unmanned|missile|ballistic|cruise missile|rocket|projectile|'
    r'Shahed|Samad|Yafa|Ababil|Fateh|Kheibar|Zolfaghar|Emad|Ghadr|Sejjil|Qiam|'
    r'strike|struck|attack|launched|fired|intercepted|Iron Dome|Arrow missile|'
    r"David's Sling|Patriot|shot down|downed|air defense|'barrage'|salvo|'volley'|"
    r'airstrike|air strike|bombardment|shelling)\b',
    re.IGNORECASE
)

REGION_RX = re.compile(
    r'\b(Iran|Iranian|IRGC|Israel|Israeli|IDF|Gaza|West Bank|Lebanon|Lebanese|'
    r'Hezbollah|Yemen|Yemeni|Houthi|Ansarallah|Hamas|Syria|Syrian|Iraq|Iraqi|'
    r'Jordan|Jordanian|Saudi Arabia|Saudi|UAE|Emirati|Kuwait|Kuwaiti|Qatar|Qatari|'
    r'Bahrain|Bahraini|Oman|Omani|Red Sea|Persian Gulf|Gulf|Middle East|West Asia|'
    r'Tel Aviv|Haifa|Jerusalem|Eilat|Beirut|Sanaa|Tehran|Baghdad|Riyadh|Dubai|'
    r'Abu Dhabi|Manama|Doha|Kuwait City|Amman|Damascus)\b',
    re.IGNORECASE
)

# ─── GEOCODING ──────────────────────────────────────────────────────────────
GEO = {
    # Countries
    'Iran':          [32.4,  53.7],   'Israel':        [31.5,  34.8],
    'Yemen':         [15.5,  48.5],   'Lebanon':       [33.9,  35.5],
    'Syria':         [34.8,  38.7],   'Iraq':          [33.2,  43.7],
    'Jordan':        [31.2,  36.5],   'Saudi Arabia':  [24.0,  45.0],
    'UAE':           [24.5,  54.4],   'Kuwait':        [29.3,  47.5],
    'Qatar':         [25.3,  51.2],   'Bahrain':       [26.0,  50.55],
    'Oman':          [22.0,  57.5],   'Pakistan':      [30.4,  69.3],
    'US':            [38.9, -77.0],   'UK':            [51.5,  -0.1],
    # Cities / regions
    'Tel Aviv':      [32.08, 34.78],  'Haifa':         [32.82, 34.99],
    'Jerusalem':     [31.77, 35.22],  'Eilat':         [29.56, 34.95],
    'Ashkelon':      [31.67, 34.57],  'Be\'er Sheva':  [31.25, 34.79],
    'Ashdod':        [31.80, 34.65],  'Netivot':       [31.42, 34.59],
    'Sderot':        [31.52, 34.60],  'Nahariya':      [33.01, 35.10],
    'Beirut':        [33.89, 35.50],  'Dahiyeh':       [33.83, 35.49],
    'Tyre':          [33.27, 35.20],  'Sidon':         [33.56, 35.37],
    'Baalbek':       [34.00, 36.21],  'Tripoli':       [34.44, 35.85],
    'Tehran':        [35.69, 51.39],  'Isfahan':       [32.66, 51.68],
    'Tabriz':        [38.08, 46.29],  'Natanz':        [33.72, 51.73],
    'Sanaa':         [15.35, 44.21],  'Hodeidah':      [14.80, 42.95],
    'Aden':          [12.78, 45.04],  'Taiz':          [13.58, 44.02],
    'Baghdad':       [33.34, 44.40],  'Erbil':         [36.19, 44.01],
    'Mosul':         [36.34, 43.13],  'Basra':         [30.51, 47.78],
    'Damascus':      [33.51, 36.29],  'Aleppo':        [36.20, 37.16],
    'Latakia':       [35.52, 35.79],  'Palmyra':       [34.55, 38.28],
    'Riyadh':        [24.69, 46.72],  'Jeddah':        [21.49, 39.19],
    'Dhahran':       [26.29, 50.15],  'Aramco':        [26.29, 50.15],
    'Dubai':         [25.20, 55.27],  'Abu Dhabi':     [24.47, 54.37],
    'Sharjah':       [25.34, 55.39],  'Fujairah':      [25.13, 56.33],
    'Manama':        [26.22, 50.59],  'Doha':          [25.29, 51.53],
    'Kuwait City':   [29.37, 47.98],  'Muscat':        [23.61, 58.59],
    'Amman':         [31.96, 35.95],  'Aqaba':         [29.53, 34.99],
    'Red Sea':       [20.00, 38.00],  'Strait of Hormuz': [26.57, 56.25],
    'Persian Gulf':  [26.50, 52.00],  'Gulf of Aden':  [12.00, 47.00],
}

# Origin country aliases → canonical name
ORIGIN_MAP = [
    (r'\bIran(?:ian)?\b|\bIRGC\b|\bPasdar\b',          'Iran'),
    (r'\bHouthi\b|\bAnsarallah\b|\bYemen(?:i)?\b',      'Yemen'),
    (r'\bHezbollah\b',                                   'Lebanon'),
    (r'\bHamas\b|\bIslamic Jihad\b|\bGaza\b',           None),   # skip — mostly domestic
    (r'\bIsrael(?:i)?\b|\bIDF\b|\bMossad\b',            'Israel'),
    (r'\bUnited States\b|\bUS \b|\bAmerica[n]?\b|\bPentagon\b|\bUSAF\b|\bUSN\b', 'US'),
    (r'\bUnited Kingdom\b|\bUK\b|\bBritish\b|\bRAF\b',  'UK'),
]

# Target country aliases → canonical name (for oc/tcc fields)
TARGET_COUNTRY_MAP = {
    'Israel': 'Israel', 'Tel Aviv': 'Israel', 'Haifa': 'Israel', 'Jerusalem': 'Israel',
    'Eilat': 'Israel', 'Ashkelon': 'Israel', 'Ashdod': 'Israel', 'Netivot': 'Israel',
    'Iran': 'Iran', 'Tehran': 'Iran', 'Isfahan': 'Iran', 'Natanz': 'Iran',
    'Yemen': 'Yemen', 'Sanaa': 'Yemen', 'Hodeidah': 'Yemen',
    'Lebanon': 'Lebanon', 'Beirut': 'Lebanon', 'Dahiyeh': 'Lebanon',
    'Syria': 'Syria', 'Damascus': 'Syria', 'Aleppo': 'Syria',
    'Iraq': 'Iraq', 'Baghdad': 'Iraq', 'Erbil': 'Iraq',
    'Jordan': 'Jordan', 'Amman': 'Jordan',
    'Saudi Arabia': 'Saudi Arabia', 'Riyadh': 'Saudi Arabia', 'Dhahran': 'Saudi Arabia', 'Aramco': 'Saudi Arabia',
    'UAE': 'UAE', 'Dubai': 'UAE', 'Abu Dhabi': 'UAE', 'Sharjah': 'UAE',
    'Kuwait': 'Kuwait', 'Kuwait City': 'Kuwait',
    'Qatar': 'Qatar', 'Doha': 'Qatar',
    'Bahrain': 'Bahrain', 'Manama': 'Bahrain',
    'Oman': 'Oman', 'Muscat': 'Oman',
    'Red Sea': 'Red Sea', 'Persian Gulf': 'Red Sea',
}

# ─── HELPERS ────────────────────────────────────────────────────────────────
def classify_weapon(text):
    t = text.lower()
    if re.search(r'shahed|samad|yafa|ababil|loiter|one.way attack|uav|drone', t):
        return 'drone', 'Attack Drone'
    if re.search(r'ballistic|fateh|kheibar|zolfaghar|emad|ghadr|sejjil|qiam|qasem', t):
        return 'ballistic', 'Ballistic Missile'
    if re.search(r'cruise missile|subsonic cruise', t):
        return 'cruise', 'Cruise Missile'
    if re.search(r'\brocket\b', t):
        return 'missile', 'Rocket'
    if re.search(r'\bmissile\b', t):
        return 'missile', 'Missile'
    return 'missile', 'Projectile'

def classify_outcome(text):
    t = text.lower()
    if re.search(r'intercept|shot down|downed|destroy|iron dome|arrow|patriot|air defense|air defence|thwart', t):
        # Check if partial
        if re.search(r'some|partial|several|few|number of', t):
            return 'partial'
        return 'intercepted'
    if re.search(r'\bhit\b|struck|damaged|wound|injur|kill|dead|casualt|explo|land|impact', t):
        return 'hit'
    return 'hit'

def extract_quantity(text):
    patterns = [
        r'(\d+)\s*(?:attack\s*)?(?:drones?|UAVs?|ballistic missiles?|cruise missiles?|missiles?|rockets?|projectiles?)',
        r'(?:launched?|fired?|dispatched?|sent)\s+(?:a\s+total\s+of\s+)?(\d+)',
        r'(?:barrage|salvo|volley)\s+of\s+(\d+)',
        r'(\d+)\s+(?:were|have been)\s+(?:fired|launched|intercepted|downed)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return '1+'

def detect_origin(text):
    for pattern, country in ORIGIN_MAP:
        if re.search(pattern, text, re.IGNORECASE):
            return country
    return None

def find_best_geo(text):
    """Return (place_name, [lat, lon]) for the most specific match in text."""
    # Try cities first (longer = more specific)
    for place in sorted(GEO.keys(), key=len, reverse=True):
        if len(place) > 4 and re.search(r'\b' + re.escape(place) + r'\b', text, re.IGNORECASE):
            return place, GEO[place]
    return None, None

def infer_target_country(place_name):
    if not place_name:
        return 'Unknown'
    return TARGET_COUNTRY_MAP.get(place_name, place_name)

def parse_pubdate(date_str):
    if not date_str:
        return None
    for fmt in [
        '%a, %d %b %Y %H:%M:%S %z',
        '%a, %d %b %Y %H:%M:%S GMT',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%SZ',
        '%a, %d %b %Y %H:%M:%S +0000',
    ]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None

# ─── FETCH FEED ─────────────────────────────────────────────────────────────
def fetch_feed(name, url, cutoff):
    articles = []
    try:
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        })
        with urlopen(req, timeout=20) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        items = root.findall('.//item') or root.findall('.//atom:entry', ns)

        for item in items:
            title = (item.findtext('title') or
                     item.findtext('atom:title', namespaces=ns) or '')
            desc  = (item.findtext('description') or
                     item.findtext('atom:summary', namespaces=ns) or
                     item.findtext('atom:content', namespaces=ns) or '')
            pub   = (item.findtext('pubDate') or
                     item.findtext('atom:published', namespaces=ns) or '')
            # Extract article link
            link_el = item.find('link')
            link = ''
            if link_el is not None and link_el.text:
                link = link_el.text.strip()
            else:
                atom_link = item.find('atom:link', ns)
                if atom_link is not None:
                    link = atom_link.get('href', '').strip()

            title = html.unescape(re.sub(r'<[^>]+>', '', title)).strip()
            desc  = html.unescape(re.sub(r'<[^>]+>', '', desc)).strip()

            pub_dt = parse_pubdate(pub)
            if pub_dt:
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                if pub_dt < cutoff:
                    continue
                date_str = pub_dt.strftime('%Y-%m-%d')
            else:
                date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')

            combined = f"{title} {desc}"
            if STRIKE_RX.search(combined) and REGION_RX.search(combined):
                articles.append({
                    'title':    title,
                    'desc':     desc[:400],
                    'date':     date_str,
                    'source':   name,
                    'combined': combined,
                    'link':     link,
                })
    except Exception as e:
        print(f"  ✗ {name}: {e}")
    return articles

# ─── BUILD EVENT ─────────────────────────────────────────────────────────────
def build_event(article, next_id):
    text = article['combined']

    origin = detect_origin(text)
    if not origin:
        return None   # can't determine who launched

    origin_coords = GEO.get(origin)
    if not origin_coords:
        return None

    target_name, target_coords = find_best_geo(text)
    if not target_coords:
        return None

    # If the only geo we found IS the origin country, look harder for a target
    if target_name == origin:
        return None

    target_country = infer_target_country(target_name)

    # Skip domestic news (origin == target country)
    if origin == target_country:
        return None

    category, weapon_type = classify_weapon(text)
    outcome   = classify_outcome(text)
    quantity  = extract_quantity(text)

    short_title = article['title'][:120]

    return {
        'id':  str(next_id),
        'd':   article['date'],
        't':   short_title,
        'c':   category,
        'ty':  weapon_type,
        'dt':  f"Auto-detected — {article['source']}",
        'q':   quantity,
        'fr':  origin,
        'fc':  origin_coords,
        'to':  target_name or target_country,
        'tc':  target_coords,
        'tt':  'Unknown',
        's':   outcome,
        'n':   article['desc'] or short_title,
        'sr':  article['source'],
        'url': article.get('link', ''),
        'oc':  origin,
        'tcc': target_country,
    }

# ─── DEDUPLICATION ───────────────────────────────────────────────────────────
def fingerprint(title, date):
    """Stable dedup key: date + top 8 meaningful words from title."""
    words = sorted(set(re.findall(r'\b[a-zA-Z]{4,}\b', title.lower())))[:8]
    return f"{date}:{'|'.join(words)}"

def existing_fingerprints(html_content):
    fps = set()
    for m in re.finditer(r"\{id:'[^']*',d:'(\d{4}-\d{2}-\d{2})',t:'([^']*)'", html_content):
        fps.add(fingerprint(m.group(2), m.group(1)))
    return fps

def max_event_id(html_content):
    ids = re.findall(r"id:'(\d+)'", html_content)
    return max((int(i) for i in ids), default=73)

# ─── INJECT INTO HTML ────────────────────────────────────────────────────────
def esc(s):
    return str(s).replace("\\", "\\\\").replace("'", "\\'").replace('\n', ' ').replace('\r', '')

def format_event_js(ev):
    fc, tc = ev['fc'], ev['tc']
    return (
        f"  {{id:'{esc(ev['id'])}',d:'{esc(ev['d'])}',t:'{esc(ev['t'])}',\n"
        f"   c:'{esc(ev['c'])}',ty:'{esc(ev['ty'])}',dt:'{esc(ev['dt'])}',q:'{esc(ev['q'])}',\n"
        f"   fr:'{esc(ev['fr'])}',fc:[{fc[0]},{fc[1]}],"
        f"to:'{esc(ev['to'])}',tc:[{tc[0]},{tc[1]}],\n"
        f"   tt:'{esc(ev['tt'])}',s:'{esc(ev['s'])}',\n"
        f"   n:'{esc(ev['n'])}',\n"
        f"   sr:'{esc(ev['sr'])}',url:'{esc(ev.get('url',''))}',oc:'{esc(ev['oc'])}',tcc:'{esc(ev['tcc'])}'}},"
    )

def inject_events(html_content, new_events):
    """Append new events just before the closing ]; of the E array."""
    # Match: const E=[ ... ]; or var E=[ ... ]; — the events array block
    m = re.search(r'((?:const|var|let)\s+E\s*=\s*\[[\s\S]*?)\];', html_content)
    if not m:
        # Debug: show what patterns exist
        has_const = 'const E=' in html_content
        has_var = 'var E=' in html_content
        has_bracket = 'E=[' in html_content
        print(f"  ✗ Could not locate events array — injection skipped")
        print(f"    Debug: 'const E=' found: {has_const}, 'var E=' found: {has_var}, 'E=[' found: {has_bracket}")
        return html_content

    new_js = '\n' + '\n'.join(format_event_js(e) for e in new_events)
    return (
        html_content[:m.start()]
        + m.group(1)
        + new_js
        + '\n];'
        + html_content[m.end():]
    )

# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("West-Asia Strike Tracker — Auto-Updater")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    print(f"Lookback window: {LOOKBACK_HOURS}h (since {cutoff.strftime('%Y-%m-%d %H:%M UTC')})\n")

    with open('index.html', 'r', encoding='utf-8') as f:
        html_content = f.read()

    known_fps = existing_fingerprints(html_content)
    next_id   = max_event_id(html_content) + 1
    print(f"Loaded index.html — existing events: {next_id - 1}, fingerprints: {len(known_fps)}\n")

    # ── Fetch all feeds ──
    all_articles = []
    for name, url in RSS_FEEDS:
        print(f"Fetching {name} ...", end=' ', flush=True)
        arts = fetch_feed(name, url, cutoff)
        print(f"{len(arts)} relevant")
        all_articles.extend(arts)
        time.sleep(0.8)

    print(f"\nTotal candidate articles: {len(all_articles)}\n")

    # ── Build new events ──
    new_events = []
    seen_fps   = set(known_fps)

    for article in all_articles:
        fp = fingerprint(article['title'], article['date'])
        if fp in seen_fps:
            print(f"  [SKIP-DUP]  {article['title'][:70]}")
            continue

        event = build_event(article, next_id)
        if not event:
            print(f"  [SKIP-GEO]  {article['title'][:70]}")
            continue

        print(f"  [ADD] id={next_id} {event['d']}  {event['oc']}→{event['tcc']}  {event['t'][:55]}")
        new_events.append(event)
        seen_fps.add(fp)
        next_id += 1

    # ── Write ──
    if not new_events:
        print("\n✓ No new events — index.html unchanged.")
        return

    print(f"\nInjecting {len(new_events)} new events ...")
    updated = inject_events(html_content, new_events)
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(updated)
    print(f"✓ index.html updated ({len(new_events)} events added, new max id={next_id - 1})")

if __name__ == '__main__':
    main()
