# HTML Reporting — Reference Notes

This directory contains reference material for the abp-html-reporting skill.

## Design System

### CSS Variables
```css
:root {
  --accent: #CE0F69;           /* Aker BP Magenta */
  --dark-magenta: #7D2248;     /* Headers, titles */
  --green: #00B373;            /* OK / positive */
  --orange: #F68D2E;           /* Warning */
  --red: #D14F4E;              /* Danger / negative */
  --blue: #4993B4;             /* Info / neutral */
  --bg-card: #f1f1f1;          /* Card backgrounds */
}
```

### Font
Lato (Google Fonts): `<link href="https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700;900&display=swap" rel="stylesheet">`

### Page Structure
```
<aside class="sidebar">   ← Fixed left sidebar with logo + nav
<div class="main">
  <div class="hero">      ← Gradient banner with title
  <section id="...">      ← Content sections
  <div class="footer">    ← Footer with timestamp
</div>
```

### Components

**Callouts:**
```html
<div class="callout success"><strong>Summary:</strong> All wells stable.</div>
<div class="callout warning"><strong>Watch:</strong> Well A04 WHP declining.</div>
<div class="callout danger"><strong>Action needed:</strong> Well B03 shut in.</div>
```

**KPI Cards:**
```html
<div class="kpi-grid">
  <div class="kpi">
    <div class="label">Oil Export</div>
    <div class="value v-green">12,480</div>
    <div class="delta">Sm³/d • +2.1%</div>
  </div>
</div>
```

**Tables:**
- Cell classes: `up` (green), `down` (red), `flat` (gray), `event` (orange)

**Timeline:**
```html
<div class="timeline">
  <div class="tl-item event"><div class="tl-time">Fri 22:30</div><div class="tl-text">PCVs closed</div></div>
</div>
```

### Interactive Charts (Plotly.js)
- Load: `<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>`
- Use IntersectionObserver for lazy-loading per-episode charts
- Adaptive resolution by episode duration

### Output Convention
`OutputDataFiles/{Asset}_{Type}_{DDMmmYYYY}.html`
