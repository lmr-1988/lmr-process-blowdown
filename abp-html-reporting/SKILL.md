---
name: abp-html-reporting
description: Generate self-contained, single-file HTML reports with Aker BP branding — magenta gradient hero, sidebar navigation, KPI cards, callouts, timelines, tables, and lazy-loaded Plotly.js charts. Use when the user asks for a "report", "HTML output", branded summary, weekend screening report, PBU report, or slugging history dashboard.
category: reporting
environment: [browser, plotly-cdn, google-fonts-cdn]
---

# Aker BP — HTML Reporting

## Purpose

Generate self-contained, single-file HTML reports with full Aker BP branding. All CSS is inlined — no build step, no server, opens directly in a browser. Lato font from Google Fonts is the only external dependency.

## When to Use

- Weekend / weekly production screening reports
- PBU analysis output
- Slugging-history dashboards
- Investigation summaries with timeline + KPIs

## Requirements

- Modern web browser for viewing the output
- Google Fonts CDN access (Lato font family)
- Plotly.js CDN access for interactive charts (only if using chart components)
- Time-series data already retrieved (this skill does not handle data retrieval)

## Build Order

1. Start from the HTML skeleton (boilerplate `<head>` / sidebar / hero / sections / footer).
2. Paste the CSS template into `<style>`.
3. Drop in components: callouts, KPI cards, timelines, tables, Plotly charts.
4. Output to `OutputDataFiles/{Asset}_{Type}_{DDMmmYYYY}.html`.

## Brand Identity

| Element | Value |
|---------|-------|
| Primary accent | Magenta `#CE0F69` |
| Heading colour | `#7D2248` (dark magenta) |
| Font | Lato (Google Fonts) — weights 300, 400, 700, 900 |
| Card bg | `#f1f1f1` |
| Background | White (no dark mode) |
| Logo | `https://companieslogo.com/img/orig/AKRBP.OL-c65af99e.png?t=1603469381` (sidebar only, 120 px) |

### Platform images (CDN-proxied, CORS-safe)

| Asset | URL |
|-------|-----|
| EG | `https://i0.wp.com/akerbp.com/wp-content/uploads/2023/06/10-edvard-grieg4x.png?ssl=1` |
| IA | `https://i0.wp.com/akerbp.com/wp-content/uploads/2023/06/09-ivar-aasen4x.png?ssl=1` |
| Skarv | `https://i0.wp.com/akerbp.com/wp-content/uploads/2023/06/07-skarv4x.png?ssl=1` |
| Alvheim | `https://i0.wp.com/akerbp.com/wp-content/uploads/2023/06/08-alvheim4x.png?ssl=1` |
| Valhall | `https://i0.wp.com/akerbp.com/wp-content/uploads/2023/06/13-valhall4x-3.png?ssl=1` |

Place as **small thumbnails in the hero header** (right-aligned), NOT as full-width banners.

## Page Structure

```
┌──────────┬─────────────────────────────┐
│ SIDEBAR  │  HERO (magenta gradient)     │
│ (260px)  ├─────────────────────────────┤
│ fixed    │  Sections (KPIs, tables,     │
│ • Logo   │   timelines, charts)         │
│ • Nav    ├─────────────────────────────┤
│          │  Footer                       │
└──────────┴─────────────────────────────┘
```

- **Sidebar** — logo, title, nav links with coloured status dots.
- **Hero** — magenta gradient, title + status badge, platform image thumbnails.
- **Sections** — `id` MUST match sidebar nav `href`.
- **Footer** — `PE Assistant • <description> • <date> • Norway time (CEST)`.

## Critical Rules

1. **Single self-contained file** — all CSS inline in `<style>`. No external CSS, no JS bundles (Plotly is from CDN only).
2. Google Fonts (Lato) is the only external CSS dependency.
3. Use HTML entities: `&sup3;`, `&minus;`, `&rarr;`, `&bull;`, `&mdash;`.
4. Every `<section>` needs an `id` matching its sidebar nav link.
5. **Headings** in dark magenta `#7D2248`.
6. Darken semantic colours on white backgrounds:
   - Green `#22c55e` → `#008a59`
   - Yellow `#eab308` → `#9a8300`
7. Logo in sidebar only; platform images in hero only — never mix.
8. **Rates in Sm³/d** (×24 from CDF Sm³/h hourly data).
9. **Top-down structure** in the report layout (Export → Headers → Wells → Root Cause), mirroring the investigation methodology.
10. Footer says **Norway time / CEST / CET** — never UTC.

## Components Available

- **Hero** — gradient header with title, badge, platform thumbnails
- **KPI cards** — single-value cards with delta indicator
- **Callouts** — coloured notice boxes (info / warning / success / critical)
- **Timeline** — vertical event timeline with magenta markers
- **Tables** — striped rows, magenta header
- **Status badges** — coloured pills
- **Interactive charts** — Plotly.js (CDN), lazy-loaded via IntersectionObserver

## Plotly Charts — Lazy-Loading Pattern

```html
<div class="chart" id="chart-1" data-loaded="false"></div>

<script>
const obs = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting && e.target.dataset.loaded === "false") {
      Plotly.newPlot(e.target.id, /* trace, layout */);
      e.target.dataset.loaded = "true";
    }
  });
}, { rootMargin: "100px" });
document.querySelectorAll(".chart").forEach(el => obs.observe(el));
</script>
```

Use range slider on long-timeline charts. Colours: rate magenta `#CE0F69`, WHP blue `#2563eb`. Episode bands: confirmed green, rate-only yellow, excluded blue.

## Package Contents

- `references/README.md` — Full HTML design system reference: CSS variables, page structure, component snippets (callout, KPI, timeline, table), Plotly.js lazy-loading pattern, and output naming convention.

## Boundaries

This skill intentionally excludes:

- PDF report generation (see `abp-pdf-reporting`)
- Teams / Adaptive Card notifications (see `abp-teams-notifications`)
- CDF data retrieval or Enlight API access
- Investigation methodology or domain logic
- React / TypeScript web applications (see `abp-react-dashboard`)

## Source Notes

- `knowledge/reporting-html-aker-bp.md`
- `knowledge/reporting-html-css-template.md` — full CSS stylesheet
- `knowledge/reporting-html-components.md` — component snippets
- `knowledge/reporting-html-skeleton.md` — boilerplate
- `knowledge/reporting-pdf-pdfpages.md`
- `knowledge/reporting-teams-adaptive-cards.md`
- `OutputDataFiles/AkerBP_HTML_Design_System.md` — visual reference

The original CSS template, full skeleton, and component library are large. Copy them verbatim from the source notes when assembling a report — do not rewrite from memory.
