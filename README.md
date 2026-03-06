# West Asia Conflict Tracker

A live, interactive tracker of missile, drone, and airstrike events across West Asia (2024–2026), with color-coded arc trajectories on a dark map, 12-hour auto-refreshing RSS news feed, and timeline controls.

## Live Demo

Once deployed, visit: `https://YOUR-USERNAME.github.io/conflict-tracker/`

## Deploy to GitHub Pages (step by step)

### 1. Create a new GitHub repository

- Go to [github.com/new](https://github.com/new)
- Name it `conflict-tracker` (or whatever you like)
- Set it to **Public**
- Click **Create repository**

### 2. Upload the file

- Click **"uploading an existing file"** on the new repo page
- Drag and drop `index.html` into the upload area
- Click **Commit changes**

### 3. Enable GitHub Pages

- Go to your repo's **Settings** tab
- In the left sidebar, click **Pages**
- Under "Source", select **Deploy from a branch**
- Under "Branch", select **main** and **/ (root)**
- Click **Save**
- Wait 1–2 minutes, then your site will be live at the URL shown

That's it. Three steps, no terminal needed.

---

## What's in the tracker

### 61 curated conflict events including:

- **Iran → Israel**: Operation True Promise I (Apr 2024), True Promise II (Oct 2024)
- **Israel → Iran**: Days of Repentance (Oct 2024), Twelve-Day War strikes (Jun 2025), Roaring Lion (Feb 2026)
- **US → Iran**: Nuclear facility strikes (Jun 2025), Epic Fury (Feb 2026)
- **Iran → Israel/Gulf**: True Promise IV regional salvo (Feb 2026)
- **Houthis → Israel**: 10+ ballistic and drone attacks including Ben Gurion airport hit (May 2025)
- **Houthis → Red Sea**: Ship sinkings (Rubymar, True Confidence, Magic Seas)
- **US/UK → Yemen**: Operation Poseidon Archer (2024), Operation Rough Rider (2025)
- **Israel → Yemen**: 15+ strikes on Hodeidah, Sanaa, leadership kills
- **Israel → Lebanon**: Hezbollah campaign, Nasrallah assassination
- **Hezbollah → Israel**: 320+ rocket barrage, Yakhont anti-ship missile
- **Iraq militia → US**: Tower 22 drone attack
- **Iran → Iraq/Pakistan**: IRGC ballistic strikes on Erbil, Balochistan
- **Israel → Qatar**: Hamas leadership strike in Doha
- **Israel → Syria**: Iranian consulate strike in Damascus

### Map features

- **Red arcs** = direct hits
- **Green arcs** = intercepted
- **Orange dashed arcs** = partial interception
- **Pulsing red circles** = confirmed impact sites
- **Dashed green circles** = successful intercept zones
- **Bézier curves** show smooth launch-to-target trajectories
- **English labels** on all countries and cities (CartoDB Dark Matter tiles)

### Auto-updating RSS news

Fetches from 10 sources every 12 hours:
- Reuters, BBC, Al Jazeera, Times of Israel, Arab News
- Defense One, Jerusalem Post, Middle East Eye, The Guardian, NPR

With countdown timer showing next refresh.

### Timeline controls

- Date picker (FROM / TO)
- Quick buttons: ALL, 2026, 2025 H2, 2025 H1, 2024, LAST 90D
- Filter by type: BALLISTIC, CRUISE, DRONE, MISSILE
- Filter by status: HITS, INTERCEPTS

---

## Adding new events

Edit `index.html` and add to the `E` array:

```javascript
{
  id: '62',               // unique
  d: '2026-03-10',        // YYYY-MM-DD
  t: 'Event title',
  c: 'ballistic',         // ballistic, cruise, drone, missile
  ty: 'Asset type name',
  dt: 'Specific model',
  q: '~10',
  fr: 'Launch origin',
  fc: [lat, lng],
  to: 'Target description',
  tc: [lat, lng],
  tt: 'Target type',
  s: 'hit',               // hit, intercepted, partial
  n: 'Detailed notes...',
  sr: 'Source attribution'
}
```

Then commit and push — GitHub Pages updates automatically.

## No API keys needed

Everything runs client-side in the browser:
- Map tiles: CARTO Dark Matter (free, English labels)
- RSS proxy: allorigins.win (free, no auth)
- Zero server dependencies
