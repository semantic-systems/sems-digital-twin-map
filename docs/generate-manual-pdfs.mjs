// Regenerates user-manual-{en,de}.pdf from the .md files in this directory.
// The .md files are the source of truth — always edit those, then rerun this.
//
// Usage:
//   cd docs && npm install --no-save playwright marked && node generate-manual-pdfs.mjs
//
// (playwright's bundled Chromium must be installed once via `npx playwright install chromium`
// if it isn't already cached locally.)

import { chromium } from 'playwright';
import { marked } from 'marked';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const DOCS = path.dirname(fileURLToPath(import.meta.url));

const CONFIGS = [
  {
    lang: 'en',
    src: path.join(DOCS, 'user-manual-en.md'),
    out: path.join(DOCS, 'user-manual-en.pdf'),
    title: 'SEMS Situational Map',
    subtitle: 'User Manual',
    tagline: 'For city staff and emergency personnel who use the map occasionally. No technical background required.',
    footer: 'SEMS Situational Map — User Manual',
    generated: 'Generated',
  },
  {
    lang: 'de',
    src: path.join(DOCS, 'user-manual-de.md'),
    out: path.join(DOCS, 'user-manual-de.pdf'),
    title: 'SEMS Lagekarte',
    subtitle: 'Benutzerhandbuch',
    tagline: 'Für Mitarbeitende in Stadtverwaltung und Einsatzkräften, die die Karte gelegentlich nutzen. Keine technischen Vorkenntnisse nötig.',
    footer: 'SEMS Lagekarte — Benutzerhandbuch',
    generated: 'Erstellt am',
  },
];

function stripCoverLines(md) {
  // Drop the top H1, the italic tagline, the cross-language link line, and the
  // leading "---" divider — all of that is re-rendered on the cover page instead.
  const lines = md.split('\n');
  let i = 0;
  while (i < lines.length && lines[i].trim() !== '---') i++;
  i++; // skip the '---' itself
  return lines.slice(i).join('\n').trim();
}

function css() {
  return `
  @page { size: A4; margin: 0; }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: #1f2937;
    font-size: 13px;
    line-height: 1.6;
  }
  .cover {
    width: 210mm;
    height: 297mm;
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 45%, #1e40af 100%);
    color: #fff;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 40mm 28mm;
    page-break-after: always;
    position: relative;
  }
  .cover .eyebrow {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #93c5fd;
    margin-bottom: 18px;
  }
  .cover h1 {
    font-size: 42px;
    font-weight: 800;
    margin: 0 0 6px;
    line-height: 1.15;
  }
  .cover h2 {
    font-size: 22px;
    font-weight: 500;
    color: #bfdbfe;
    margin: 0 0 28px;
  }
  .cover .tagline {
    font-size: 14px;
    color: #cbd5e1;
    max-width: 320px;
    line-height: 1.6;
    border-left: 3px solid #3b82f6;
    padding-left: 14px;
  }
  .cover .dots {
    position: absolute;
    left: 28mm;
    bottom: 24mm;
    display: flex;
    gap: 8px;
  }
  .cover .dots span {
    width: 9px; height: 9px; border-radius: 50%; display: inline-block;
  }
  .cover .meta {
    position: absolute;
    left: 28mm;
    bottom: 16mm;
    font-size: 10px;
    color: #64748b;
    letter-spacing: 0.04em;
  }
  .content {
    padding: 16mm 20mm 20mm;
  }
  h1 { display: none; } /* title lives on the cover only */
  h2 {
    font-size: 17px;
    font-weight: 700;
    color: #0f172a;
    margin: 26px 0 10px;
    padding-bottom: 6px;
    border-bottom: 2px solid #2563eb;
    page-break-after: avoid;
  }
  .content > h2:first-of-type { margin-top: 0; }
  h3 { font-size: 14px; font-weight: 700; margin: 16px 0 6px; }
  p { margin: 0 0 10px; }
  ul, ol { margin: 0 0 10px; padding-left: 20px; }
  li { margin-bottom: 5px; }
  strong { color: #0f172a; }
  a { color: #2563eb; text-decoration: none; }
  hr { border: none; border-top: 1px solid #e5e7eb; margin: 18px 0; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0 14px;
    font-size: 12px;
    page-break-inside: avoid;
  }
  th, td {
    text-align: left;
    padding: 7px 10px;
    border-bottom: 1px solid #e5e7eb;
  }
  thead th {
    background: #f1f5f9;
    color: #0f172a;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  em { color: #4b5563; }
  code { background: #f1f5f9; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
  section.block { page-break-inside: avoid; }
  `;
}

function splitIntoSections(bodyHtml) {
  // Wrap each h2..(next h2) run in a page-break-avoid section so headings
  // don't strand at the bottom of a page.
  const parts = bodyHtml.split(/(?=<h2)/g).filter(Boolean);
  return parts.map((p) => `<section class="block">${p}</section>`).join('\n');
}

async function build(cfg) {
  const raw = fs.readFileSync(cfg.src, 'utf8');
  const body = stripCoverLines(raw);
  const bodyHtml = marked.parse(body);
  const sectioned = splitIntoSections(bodyHtml);

  const html = `<!doctype html>
<html lang="${cfg.lang}">
<head>
<meta charset="utf-8" />
<title>${cfg.title}</title>
<style>${css()}</style>
</head>
<body>
  <div class="cover">
    <div class="eyebrow">${cfg.lang === 'de' ? 'Handbuch' : 'Documentation'}</div>
    <h1>${cfg.title}</h1>
    <h2>${cfg.subtitle}</h2>
    <div class="tagline">${cfg.tagline}</div>
    <div class="dots">
      <span style="background:#ef4444"></span>
      <span style="background:#f97316"></span>
      <span style="background:#ca8a04"></span>
      <span style="background:#6b7280"></span>
    </div>
    <div class="meta">${cfg.generated} ${new Date().toISOString().slice(0, 10)}</div>
  </div>
  <div class="content">
    ${sectioned}
  </div>
</body>
</html>`;

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: 'networkidle' });
  await page.pdf({
    path: cfg.out,
    format: 'A4',
    printBackground: true,
    margin: { top: '0mm', bottom: '14mm', left: '0mm', right: '0mm' },
    displayHeaderFooter: true,
    headerTemplate: '<div></div>',
    footerTemplate: `
      <div style="width:100%; font-size:8px; color:#9ca3af; font-family: 'Inter', sans-serif; padding: 0 20mm; display:flex; justify-content:space-between;">
        <span>${cfg.footer}</span>
        <span><span class="pageNumber"></span> / <span class="totalPages"></span></span>
      </div>`,
  });
  await browser.close();
  console.log('wrote', cfg.out);
}

for (const cfg of CONFIGS) {
  await build(cfg);
}
