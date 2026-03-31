#!/usr/bin/env python3
"""
ACLED Corroboration Tool for West Asia Strike Tracker
Runs automatically via GitHub Actions when a new ACLED file is uploaded to data/.
Can also be run manually: python corroborate_acled.py [acled_file.xlsx]

If no file is specified, it auto-finds the latest .xlsx in data/.
Always updates index.html in the same directory.
"""
import re, sys, json, glob, os
import pandas as pd
from datetime import datetime

# ─── CONFIGURATION ──────────────────────────────────────────────────────────
IRAN_WAR_START = '2026-02-28'

# Only these countries — excludes Palestine/Gaza (separate conflict)
IRAN_WAR_COUNTRIES = [
    'Iran','Israel','Lebanon','Bahrain','Kuwait','Qatar',
    'United Arab Emirates','Saudi Arabia','Oman','Iraq','Jordan','Syria','Yemen'
]

# Map ACLED names → tracker codes
COUNTRY_MAP = {'United Arab Emirates': 'UAE'}

# Only count actual strikes, not protests/riots/strategic developments
STRIKE_TYPES = ['Explosions/Remote violence']

def load_acled(path):
    df = pd.read_excel(path)
    war = df[df['WEEK'] >= IRAN_WAR_START].copy()
    war = war[war['COUNTRY'].isin(IRAN_WAR_COUNTRIES)]
    strikes = war[war['EVENT_TYPE'].isin(STRIKE_TYPES)]
    return strikes

def load_tracker(path='index.html'):
    with open(path, 'r') as f:
        html = f.read()
    events = []
    for m in re.finditer(
        r"\{id:'[^']*',d:'([^']*)',t:'([^']*)'.*?oc:'([^']*)',tcc:'([^']*)'",
        html, re.DOTALL
    ):
        events.append({
            'date': m.group(1), 'title': m.group(2),
            'oc': m.group(3), 'tcc': m.group(4)
        })
    return events, html

def country_normalize(c):
    return COUNTRY_MAP.get(c, c)

def compare(acled, tracker_events):
    """Compare ACLED aggregates against tracker event counts."""
    # ACLED: events by country
    acled_by_country = acled.groupby('COUNTRY').agg(
        events=('EVENTS','sum'), fatalities=('FATALITIES','sum')
    ).reset_index()
    acled_by_country['country'] = acled_by_country['COUNTRY'].apply(country_normalize)

    # Tracker: events by target country
    from collections import Counter
    tracker_tcc = Counter(e['tcc'] for e in tracker_events if e['date'] >= IRAN_WAR_START)
    tracker_oc = Counter(e['oc'] for e in tracker_events if e['date'] >= IRAN_WAR_START)

    # ACLED: by week
    acled_by_week = acled.groupby('WEEK').agg(
        events=('EVENTS','sum'), fatalities=('FATALITIES','sum')
    ).reset_index()

    # Build comparison table
    rows = []
    for _, r in acled_by_country.iterrows():
        c = r['country']
        rows.append({
            'country': c,
            'acled_events': int(r['events']),
            'acled_fatalities': int(r['fatalities']),
            'tracker_targeted': tracker_tcc.get(c, 0),
            'tracker_origin': tracker_oc.get(c, 0),
            'coverage_ratio': round(tracker_tcc.get(c, 0) / max(r['events'], 1) * 100, 1)
        })
    rows.sort(key=lambda x: x['acled_events'], reverse=True)

    # Weekly breakdown
    weeks = []
    for _, r in acled_by_week.iterrows():
        weeks.append({
            'week': r['WEEK'].strftime('%Y-%m-%d'),
            'events': int(r['events']),
            'fatalities': int(r['fatalities'])
        })

    # ACLED totals
    totals = {
        'total_events': int(acled['EVENTS'].sum()),
        'total_fatalities': int(acled['FATALITIES'].sum()),
        'countries': len(acled['COUNTRY'].unique()),
        'weeks': len(acled['WEEK'].unique()),
        'last_week': acled['WEEK'].max().strftime('%Y-%m-%d'),
        'tracker_events': len([e for e in tracker_events if e['date'] >= IRAN_WAR_START]),
    }

    return rows, weeks, totals

def print_report(rows, weeks, totals):
    print("\n" + "=" * 70)
    print("ACLED vs TRACKER — CORROBORATION REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"ACLED data through: {totals['last_week']}")
    print("=" * 70)

    print(f"\n  ACLED total strike events: {totals['total_events']:,}")
    print(f"  ACLED total fatalities:    {totals['total_fatalities']:,}")
    print(f"  Tracker curated events:    {totals['tracker_events']}")
    print(f"  Coverage ratio:            {totals['tracker_events']/max(totals['total_events'],1)*100:.1f}%")
    print(f"  (Each tracker event may represent dozens/hundreds of ACLED events)")

    print(f"\n{'Country':<20} {'ACLED Events':>12} {'ACLED Dead':>10} {'Tracker→':>10} {'Tracker←':>10} {'Coverage':>8}")
    print("-" * 70)
    for r in rows:
        print(f"{r['country']:<20} {r['acled_events']:>12,} {r['acled_fatalities']:>10,} {r['tracker_targeted']:>10} {r['tracker_origin']:>10} {r['coverage_ratio']:>7.1f}%")

    print(f"\nWeekly breakdown:")
    print(f"  {'Week':<12} {'Events':>8} {'Fatalities':>10}")
    print("  " + "-" * 30)
    for w in weeks:
        print(f"  {w['week']:<12} {w['events']:>8,} {w['fatalities']:>10,}")

    # Identify gaps
    print(f"\n⚠ GAPS (countries where ACLED has 50+ events but tracker has <3):")
    for r in rows:
        if r['acled_events'] >= 50 and r['tracker_targeted'] < 3:
            print(f"  → {r['country']}: {r['acled_events']} ACLED events, only {r['tracker_targeted']} in tracker")

def inject_acled_stats(html, totals, rows):
    """Inject ACLED comparison data into the analytics panel."""
    # Build the ACLED stats JS snippet
    acled_data = json.dumps({
        'total': totals['total_events'],
        'fatalities': totals['total_fatalities'],
        'lastWeek': totals['last_week'],
        'byCountry': {r['country']: r['acled_events'] for r in rows}
    })

    # Find existing ACLED data block or inject new one
    marker = '// ACLED_DATA_START'
    end_marker = '// ACLED_DATA_END'

    if marker in html:
        # Replace existing
        pattern = re.escape(marker) + r'[\s\S]*?' + re.escape(end_marker)
        replacement = f"{marker}\nvar ACLED={acled_data};\n{end_marker}"
        html = re.sub(pattern, replacement, html)
    else:
        # Insert before INIT block
        init_marker = '// INIT'
        if init_marker in html:
            html = html.replace(
                init_marker,
                f"{marker}\nvar ACLED={acled_data};\n{end_marker}\n\n{init_marker}"
            )

    # Update the methodology footnote with ACLED comparison
    acled_note = (
        f'ACLED documents {totals["total_events"]:,} strike events and {totals["total_fatalities"]:,} '
        f'fatalities across {totals["countries"]} countries (data through {totals["last_week"]}). '
        f'This tracker covers {totals["tracker_events"]} curated incidents — each may represent '
        f'dozens of individual ACLED events.'
    )

    # Find and update the methodology text
    old_acled_pattern = r'ACLED documents [\d,]+ strike events.*?individual ACLED events\.'
    if re.search(old_acled_pattern, html):
        html = re.sub(old_acled_pattern, acled_note, html)
    else:
        # Insert before "This tracker is not a comprehensive record"
        html = html.replace(
            'This tracker is not a comprehensive record',
            acled_note + ' This tracker is not a comprehensive record'
        )

    return html

def main():
    # Auto-find ACLED file
    if len(sys.argv) >= 2:
        acled_path = sys.argv[1]
    else:
        # Find latest .xlsx in data/ folder
        files = sorted(glob.glob('data/*.xlsx'), key=os.path.getmtime, reverse=True)
        if not files:
            print("No ACLED .xlsx files found in data/ folder.")
            print("Usage: python corroborate_acled.py [acled_file.xlsx]")
            sys.exit(1)
        acled_path = files[0]
        print(f"Auto-detected latest ACLED file: {acled_path}")

    html_path = 'index.html'

    print(f"Loading ACLED data from: {acled_path}")
    acled = load_acled(acled_path)
    print(f"  {len(acled)} rows, {acled['EVENTS'].sum():,} strike events (Feb 28+ only, Iran war countries only)")

    print(f"Loading tracker from: {html_path}")
    tracker_events, html = load_tracker(html_path)
    print(f"  {len(tracker_events)} tracker events")

    rows, weeks, totals = compare(acled, tracker_events)
    print_report(rows, weeks, totals)

    updated = inject_acled_stats(html, totals, rows)
    with open(html_path, 'w') as f:
        f.write(updated)
    print(f"\n✓ ACLED stats injected into {html_path}")

if __name__ == '__main__':
    main()
