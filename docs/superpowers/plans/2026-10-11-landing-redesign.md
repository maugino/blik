# Landing Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Blik home page with a ten-section, product-first page and restyle the shared landing components so all 32 landing pages get a flatter, cleaner look with no gradients.

**Architecture:** One Django app (`landing`) serves 32 templates that extend `templates/landing/base.html` and share `static/css/landing.css` (loaded after `static/css/main.css`, which owns the colour tokens). The work is template plus CSS only: a rewritten `base.html` header and footer, a rewritten `index.html`, and a rewritten "shared components" block at the top of `landing.css` that replaces the old header, hero, section, CTA and footer rules. Page-specific CSS further down the file stays, except for consolidated overrides and a mechanical white-on-indigo contrast pass.

**Tech Stack:** Django 5 templates, plain CSS with custom properties, headless Chrome for screenshots. No build step, no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-11-landing-redesign-design.md`

## Global Constraints

- No `linear-gradient` and no `--primary-gradient` anywhere in `static/css/landing.css` after this plan.
- Solid indigo surfaces that carry white text use `--primary-700` (#4338ca, identical in both themes), never `--primary-600` (remapped to #818cf8 in dark mode).
- Hard-coded `white` or `rgba(255,255,255,…)` text survives only on a `--primary-700` surface.
- Existing shared class names stay (`.section`, `.section-title`, `.section-intro`, `.features-grid`, `.feature-card`, `.pricing-*`, `.faq-*`, `.comparison-table`, `.footer-*`, `.header*`, `.nav`, `.hero*`, `.cta-section`, `.cta-content`, `.cta-box`). Only their values change.
- Carousel, phone mockup and `[data-theme] .screenshot-light/.screenshot-dark` rules stay: seven other pages use them.
- New home-only classes are prefixed: `.home-hero`, `.home-hero-media`, `.browser-frame`, `.fact-strip`, `.steps`, `.step`, `.split`, `.data-grid`, `.plug-grid`, `.cta-card`.
- Prices come from `landing/context_processors.py:PRICING` (`plan_single_price`, `plan_single_max`, `plan_saas_price`, `plan_saas_max`, `plan_saas_annual`, `trial_days`). Never hard-code a price.
- Light and dark themes both stay, following the system preference. No theme-related JS changes.
- Python for every command is `.venv/bin/python`. The standalone landing server is `DJANGO_SETTINGS_MODULE=landing_settings .venv/bin/python manage.py runserver 8777`. Port 8765 is taken by another process; never use it.
- Headless Chrome: `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --screenshot=<png> --window-size=<W>,<H> --user-data-dir=<fresh dir> <url>` run in the background, wait for the PNG, then `pkill -f "headless=new"`. Widths under 500px are ignored, so phone checks use a wrapper page with a 375px iframe.
- Commit after each task. Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- No unit tests are added: the change is templates and CSS with no logic unit (project rule: real units or none).

## Review Focus

1. **Dark mode on a page nobody touched.** A comparison or framework page with a `--primary-600` panel and white text must still be readable after the contrast pass; Task 5 covers this with the dark-mode screenshots of `vs_lattice`, `dreyfus_model` and `performance_matrix`.
2. **`rating_data` absent.** The landing container cannot always reach the main app API, so the fact strip and both structured-data blocks must render cleanly with `rating_data = None`; Task 3 renders the home page with and without it.
3. **Nav button on pages that override `nav_links`.** 26 templates override the block; the header button must appear on all of them and must not break the mobile menu; Task 2 checks `pricing` (overrides) and `signup` (does not).
4. **Phone width.** Two-column sections (`.home-hero`, `.split`, `.steps`) must stack with no horizontal scroll at 375px; Task 4's wrapper-page screenshots cover it.
5. **Assessment pages behind the POST flow.** `dreyfus_assessment.html`, `dreyfus_results_preview.html` and `dreyfus_email_captured.html` are not reachable by GET; Task 5 renders them with `render_to_string` and fixed contexts.

---

### Task 1: Shared components block in `landing.css`

**Files:**
- Modify: `static/css/landing.css` (delete lines 176-330 "Header" through "Sections" and the start of "Features Grid"; delete lines 654-740 "CTA Section" and "Footer"; delete the hero/section/container overrides inside the two responsive blocks at 1215-1313 and 1557-1615; delete lines 5134-5331 homepage block; add one new block after the utility classes)

**Interfaces:**
- Produces: CSS classes used by Task 2 (`.header`, `.header-content`, `.header-cta`, `.nav`, `.footer*`) and Task 3 (`.home-hero`, `.home-hero-media`, `.browser-frame`, `.fact-strip`, `.steps`, `.step`, `.split`, `.split--reverse`, `.data-grid`, `.plug-grid`, `.cta-card`, `.eyebrow`, `.section-link`).

- [ ] **Step 1: Record the before state for comparison**

```bash
mkdir -p /tmp/landing-before
cd /Users/tdz/projects/blik
DJANGO_SETTINGS_MODULE=landing_settings .venv/bin/python manage.py runserver 8777 > /tmp/landing-before/server.log 2>&1 &
sleep 4
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
for p in "" pricing hr-managers developers vs-lattice dreyfus-model one-time-360-review faq people-analytics performance-matrix about open-source; do
  n=${p:-home}
  "$C" --headless=new --screenshot=/tmp/landing-before/$n.png --window-size=1440,5000 --user-data-dir=/tmp/landing-before/ud-$n "http://127.0.0.1:8777/$p" >/dev/null 2>&1 &
done
sleep 20; pkill -f "headless=new"; ls /tmp/landing-before/*.png | wc -l
```

Expected: `12`. Leave the server running for later tasks.

- [ ] **Step 2: Delete the old shared blocks**

Delete these ranges from `static/css/landing.css`, highest first so line numbers stay valid. Verify each range's first and last line before deleting.

| Range | First line | Last line |
|---|---|---|
| 5134-5331 | `/* ==================== Homepage ==================== */` | blank line before `/* ==================== Pricing ==================== */` |
| 1557-1614 | `/* Better spacing and readability */` | blank line after the `640px` media block's closing `}` |
| 1263-1281 | `    .landing-page .hero-title {` (inside the 768px block) | `    }` closing `.landing-page .section { padding: var(--space-16) 0; }` |
| 1001-1013 | `/* CTA box inside CTA section - use transparent styling */` | `}` closing `.landing-page .cta-section .cta-box p` |
| 654-738 | `/* CTA Section */` | blank line before `/* Special Feature Cards with Color Variants */` |
| 176-318 | `/* Header */` | `}` closing `.landing-page .section-title` |

```bash
cd /Users/tdz/projects/blik
for r in 5134 5331 1557 1614 1263 1281 1001 1013 654 738 176 318; do printf '%5d: ' $r; sed -n "${r}p" static/css/landing.css; done
```

Expected: each printed line matches the table above (blank lines print as empty). Then, in one sed call so all addresses use the original numbering:

```bash
sed -i '' -e '5134,5331d' -e '1557,1614d' -e '1263,1281d' -e '1001,1013d' -e '654,738d' -e '176,318d' static/css/landing.css
grep -c 'Homepage ====\|/\* Header \*/\|/\* CTA Section \*/\|Better spacing and readability\|CTA box inside CTA section' static/css/landing.css
```

Expected: `0`.

- [ ] **Step 2b: Edit the card and FAQ rules in place**

These rules sit below the new block with the same specificity, so a top-of-file override would lose. Edit them where they are:

```bash
cd /Users/tdz/projects/blik
.venv/bin/python - <<'EOF'
p = 'static/css/landing.css'
s = open(p).read()
edits = [
(""".landing-page .feature-card {
    background: var(--bg-card);
    padding: var(--space-12);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--border);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.landing-page .section-alt .feature-card {
    box-shadow: var(--shadow-xs);
}

.landing-page .feature-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}""",
""".landing-page .feature-card {
    background: var(--bg-card);
    padding: var(--space-8);
    border-radius: var(--radius-xl);
    border: 1px solid var(--border);
    transition: border-color 0.15s ease;
}

.landing-page .feature-card:hover {
    border-color: var(--text-tertiary);
}"""),
("""    border-radius: 12px;
    box-shadow: var(--shadow-sm);
    border: 2px solid var(--border);
    position: relative;""",
"""    border-radius: 12px;
    border: 1px solid var(--border);
    position: relative;"""),
(""".landing-page .pricing-featured {
    border-color: var(--primary);
    box-shadow: 0 8px 20px rgba(79, 70, 229, 0.15);
}""",
""".landing-page .pricing-featured {
    border-color: var(--primary);
}"""),
(""".landing-page .faq-grid {
    max-width: 1200px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
}

@media (min-width: 768px) {
    .landing-page .faq-grid {
        grid-template-columns: repeat(2, 1fr);
        gap: 1.5rem;
    }
}
""",
""".landing-page .faq-grid {
    max-width: 800px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.75rem;
}
"""),
(""".landing-page .faq-item {
    background: var(--bg-card);
    padding: 0;
    border-radius: 12px;
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--border);
}

.landing-page .section-alt .faq-item {
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
""",
""".landing-page .faq-item {
    background: var(--bg-card);
    padding: 0;
    border-radius: 12px;
    border: 1px solid var(--border);
}
"""),
]
for old, new in edits:
    assert s.count(old) == 1, old.splitlines()[0]
    s = s.replace(old, new)
open(p, 'w').write(s)
print('ok')
EOF
```

Expected: `ok`. An assertion prints the first line of the rule whose text drifted; open the file at that selector and apply the same change by hand.

- [ ] **Step 3: Insert the new shared components block**

Insert immediately after the `.p-12 { padding: var(--space-12); }` utility line (originally line 59):

```css
/* ==================== Shared components ====================
   One accent colour, flat surfaces, 1px borders, no gradients.
   Every landing page inherits these. Page blocks further down
   only add page-specific layout. */

.landing-page {
    background: var(--bg-body);
    color: var(--text-primary);
}

.landing-page .container {
    max-width: 1120px;
    margin: 0 auto;
    padding-left: 1rem;
    padding-right: 1rem;
}

@media (min-width: 768px) {
    .landing-page .container {
        padding-left: 2rem;
        padding-right: 2rem;
    }
}

/* Header */
.landing-page .header {
    background: var(--bg-body);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 100;
}

.landing-page .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    height: 60px;
}

.landing-page .logo {
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--text-primary);
    text-decoration: none;
}

.landing-page .nav {
    display: flex;
    gap: 1.5rem;
    align-items: center;
}

.landing-page .nav a {
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 0.9375rem;
    font-weight: 500;
}

.landing-page .nav a:hover {
    color: var(--text-primary);
}

/* The header button is an <a> inside .nav, so it needs more specificity
   than `.landing-page .nav a` (colour, padding, mobile border). */
.landing-page .nav a.header-cta {
    margin-left: 0.5rem;
    white-space: nowrap;
    color: white;
    padding: 0.625rem 1rem;
    border-bottom: none;
}

.landing-page .nav a.header-cta:hover {
    color: white;
}

.landing-page .theme-toggle {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0.5rem;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
}

.landing-page .theme-toggle:hover {
    color: var(--text-primary);
}

.landing-page .theme-toggle svg {
    width: 20px;
    height: 20px;
}

/* Hero (shared by every page; the home page adds .home-hero on top) */
.landing-page .hero {
    padding: var(--space-16) 0 var(--space-12);
    text-align: center;
}

.landing-page .hero-content {
    max-width: 760px;
    margin: 0 auto;
}

.landing-page .hero-title {
    font-size: 2.75rem;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: -0.02em;
    margin-bottom: var(--space-6);
    color: var(--text-primary);
}

.landing-page .hero-subtitle {
    font-size: var(--text-lg);
    line-height: 1.6;
    color: var(--text-secondary);
    max-width: 65ch;
    margin: 0 auto var(--space-8);
}

.landing-page .hero-cta {
    display: flex;
    gap: 0.75rem;
    justify-content: center;
    flex-wrap: wrap;
}

/* Sections */
.landing-page .section {
    padding: var(--space-20) 0;
}

.landing-page .section-alt {
    background: var(--bg-card);
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
}

.landing-page .section-title {
    font-size: var(--text-4xl);
    font-weight: 700;
    line-height: 1.15;
    letter-spacing: -0.02em;
    text-align: center;
    margin-bottom: var(--space-12);
    color: var(--text-primary);
}

.landing-page .eyebrow {
    display: block;
    font-size: var(--text-sm);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--primary);
    margin-bottom: var(--space-3);
}

/* Buttons: flat, one accent */
.landing-page .btn {
    border-radius: var(--radius-md);
    font-weight: 600;
    padding: 0.75rem 1.25rem;
    font-size: 0.9375rem;
    line-height: 1.2;
    transition: background-color 0.15s ease, border-color 0.15s ease;
}

.landing-page .btn-primary {
    background: var(--primary);
    color: white;
    border: 1px solid var(--primary);
}

.landing-page .btn-primary:hover {
    background: var(--primary-dark);
    border-color: var(--primary-dark);
}

.landing-page .btn-secondary {
    background: var(--bg-card);
    color: var(--text-primary);
    border: 1px solid var(--border);
}

.landing-page .btn-secondary:hover {
    border-color: var(--text-tertiary);
    background: var(--bg-card);
}

/* Cards keep their own rules further down the file (edited in Step 2b
   to drop shadows and hover lifts). Nothing to override here. */

/* Closing call to action: bordered card instead of an indigo band */
.landing-page .cta-section {
    background: transparent;
    color: var(--text-primary);
    border: none;
}

.landing-page .cta-card,
.landing-page .cta-content {
    max-width: 720px;
    margin: 0 auto;
    text-align: center;
    padding: var(--space-12) var(--space-8);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    background: var(--bg-card);
}

.landing-page .cta-content h2,
.landing-page .cta-card h2 {
    font-size: var(--text-3xl);
    font-weight: 700;
    letter-spacing: -0.02em;
    margin-bottom: var(--space-4);
}

.landing-page .cta-content p,
.landing-page .cta-card p {
    font-size: var(--text-lg);
    color: var(--text-secondary);
    margin-bottom: var(--space-8);
}

.landing-page .cta-buttons {
    display: flex;
    gap: 0.75rem;
    justify-content: center;
    flex-wrap: wrap;
}

.landing-page .cta-section .cta-box {
    background: var(--bg-card);
    border: 1px solid var(--border);
}

.landing-page .cta-section .cta-box h3 {
    color: var(--text-primary);
}

.landing-page .cta-section .cta-box p {
    color: var(--text-secondary);
}

/* Footer */
.landing-page .footer {
    background: var(--bg-card);
    color: var(--text-primary);
    padding: var(--space-12) 0 var(--space-6);
    border-top: 1px solid var(--border);
    font-size: var(--text-sm);
}

.landing-page .footer-content {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: var(--space-8);
    margin-bottom: var(--space-8);
}

.landing-page .footer-section h4 {
    font-weight: 600;
    font-size: var(--text-sm);
    margin-bottom: var(--space-3);
    color: var(--text-primary);
}

.landing-page .footer-section p {
    color: var(--text-secondary);
    max-width: 32ch;
}

.landing-page .footer-section ul {
    list-style: none;
}

.landing-page .footer-section ul li {
    margin-bottom: 0.375rem;
}

.landing-page .footer-section a {
    color: var(--text-secondary);
    text-decoration: none;
}

.landing-page .footer-section a:hover {
    color: var(--text-primary);
}

.landing-page .footer-bottom {
    border-top: 1px solid var(--border);
    padding-top: var(--space-6);
    text-align: center;
    color: var(--text-tertiary);
}

/* ---------- Home page components ---------- */

.landing-page .home-hero {
    text-align: left;
    padding: var(--space-16) 0 var(--space-12);
}

.landing-page .home-hero .container {
    display: grid;
    grid-template-columns: minmax(0, 5fr) minmax(0, 6fr);
    gap: var(--space-12);
    align-items: center;
}

.landing-page .home-hero .hero-content {
    max-width: none;
    margin: 0;
}

.landing-page .home-hero .hero-title {
    font-size: 3.5rem;
}

.landing-page .home-hero .hero-subtitle {
    margin-left: 0;
}

.landing-page .home-hero .hero-cta {
    justify-content: flex-start;
}

.landing-page .hero-note {
    margin-top: var(--space-4);
    font-size: var(--text-sm);
    color: var(--text-tertiary);
}

.landing-page .browser-frame {
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    background: var(--bg-card);
    box-shadow: var(--shadow-md);
}

.landing-page .browser-frame-bar {
    display: flex;
    gap: 6px;
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
}

.landing-page .browser-frame-bar span {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--border);
}

.landing-page .browser-frame img {
    display: block;
    width: 100%;
    height: auto;
}

/* Theme-dependent screenshot: show one <img> per theme */
.landing-page .img-dark { display: none; }
[data-theme="dark"] .landing-page .img-light { display: none; }
[data-theme="dark"] .landing-page .img-dark { display: block; }

.landing-page .fact-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: var(--space-6);
    padding: var(--space-8) 0;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
}

.landing-page .fact {
    text-align: center;
}

.landing-page .fact-value {
    display: block;
    font-size: var(--text-3xl);
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--text-primary);
    line-height: 1.1;
}

.landing-page .fact-label {
    display: block;
    margin-top: var(--space-1);
    font-size: var(--text-sm);
    color: var(--text-secondary);
}

.landing-page .steps {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-8);
    counter-reset: step;
}

.landing-page .step {
    counter-increment: step;
}

.landing-page .step-media {
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    background: var(--bg-card);
    aspect-ratio: 4 / 3;
    margin-bottom: var(--space-4);
}

.landing-page .step-media img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: top center;
}

.landing-page .step h3 {
    font-size: var(--text-xl);
    font-weight: 600;
    margin-bottom: var(--space-2);
}

.landing-page .step h3::before {
    content: counter(step) ". ";
    color: var(--primary);
}

.landing-page .step p {
    color: var(--text-secondary);
    line-height: 1.6;
}

.landing-page .split {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-12);
    align-items: center;
}

.landing-page .split + .split {
    margin-top: var(--space-20);
}

.landing-page .split--reverse .split-text {
    order: 2;
}

.landing-page .split-text h2 {
    font-size: var(--text-3xl);
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.15;
    margin-bottom: var(--space-4);
}

.landing-page .split-text p {
    color: var(--text-secondary);
    line-height: 1.6;
    margin-bottom: var(--space-4);
}

.landing-page .split-text ul {
    list-style: none;
    margin: 0 0 var(--space-4);
}

.landing-page .split-text li {
    padding-left: 1.5rem;
    position: relative;
    margin-bottom: var(--space-2);
    color: var(--text-primary);
}

.landing-page .split-text li::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0.55em;
    width: 0.6rem;
    height: 0.6rem;
    border-radius: 50%;
    background: var(--primary);
}

.landing-page .split-text a:not(.btn) {
    color: var(--primary);
}

.landing-page .data-grid,
.landing-page .plug-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-6);
}

.landing-page .data-grid .feature-card h3,
.landing-page .plug-grid .feature-card h3 {
    font-size: var(--text-xl);
}

.landing-page .plug-grid .code-block {
    margin: var(--space-4) 0 0;
    font-size: var(--text-sm);
}

.landing-page .section-link {
    display: block;
    text-align: center;
    margin-top: var(--space-8);
    color: var(--primary);
    font-weight: 500;
}

/* Responsive: one place for every shared breakpoint */
@media (max-width: 960px) {
    .landing-page .home-hero .container,
    .landing-page .split,
    .landing-page .steps,
    .landing-page .data-grid,
    .landing-page .plug-grid {
        grid-template-columns: 1fr;
    }

    .landing-page .split--reverse .split-text {
        order: 0;
    }

    .landing-page .home-hero .hero-title {
        font-size: 2.75rem;
    }
}

@media (max-width: 768px) {
    .landing-page .section {
        padding: var(--space-12) 0;
    }

    .landing-page .hero {
        padding: var(--space-12) 0 var(--space-8);
    }

    .landing-page .hero-title,
    .landing-page .home-hero .hero-title {
        font-size: 2.25rem;
    }

    .landing-page .section-title {
        font-size: var(--text-3xl);
        margin-bottom: var(--space-8);
    }

    .landing-page .hero-cta .btn,
    .landing-page .cta-buttons .btn {
        width: 100%;
        text-align: center;
    }

    /* Inside the open mobile menu the button is a list child */
    .landing-page .nav a.header-cta {
        margin: 0.75rem 1rem;
        align-self: flex-start;
    }
}
```

- [ ] **Step 4: Confirm the mobile-nav rules survived and the file parses**

The 768px block that starts with `.landing-page .header-content { position: relative; }` must still exist (it holds the mobile menu), and the stylesheet must have no unbalanced braces.

```bash
cd /Users/tdz/projects/blik
grep -n 'mobile-menu-toggle {' static/css/landing.css | head -2
.venv/bin/python - <<'EOF'
s = open('static/css/landing.css').read()
assert s.count('{') == s.count('}'), (s.count('{'), s.count('}'))
print('braces balanced', s.count('{'))
EOF
```

Expected: one `.landing-page .mobile-menu-toggle {` hit inside the 768px block, and `braces balanced N`.

- [ ] **Step 5: Reload the home page and confirm it still renders**

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8777/
```

Expected: `200`. The old home template still renders against the new shared rules; Task 3 replaces it.

- [ ] **Step 6: Commit**

```bash
cd /Users/tdz/projects/blik
git add static/css/landing.css
git commit -m "Rewrite the shared landing components: flat surfaces, one container rule, one section rule

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Header and footer in `base.html`

**Files:**
- Modify: `templates/landing/base.html:64-96` (header) and `:98-152` (footer)

**Interfaces:**
- Consumes: `.header-cta` from Task 1.
- Produces: the default `nav_links` block (Product, Pricing, Developers, Compare, FAQ) and a header button outside the block that every page shows.

- [ ] **Step 1: Replace the header markup**

In `templates/landing/base.html`, replace the `<header>…</header>` element with:

```html
    <header class="header">
        <div class="container">
            <div class="header-content">
                <a href="{% landing_url 'index' %}" class="logo">{{ site_name|default:"Blik" }}</a>
                <button class="mobile-menu-toggle" aria-label="Toggle menu" aria-expanded="false">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                </button>
                <nav class="nav">
                    {% block nav_links %}
                    <a href="{% landing_url 'index' %}#product">Product</a>
                    <a href="{% landing_url 'pricing' %}">Pricing</a>
                    <a href="{% landing_url 'developers' %}">Developers</a>
                    <a href="{% landing_url 'alternatives' %}">Compare</a>
                    <a href="{% landing_url 'faq' %}">FAQ</a>
                    {% endblock %}
                    <button class="theme-toggle" aria-label="Toggle theme">
                        <svg class="sun-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                        </svg>
                        <svg class="moon-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                        </svg>
                    </button>
                    <a href="{% landing_url 'signup' %}?plan=single" class="btn btn-primary header-cta">Run a review round</a>
                </nav>
            </div>
        </div>
    </header>
```

The button is inside `<nav>` so the existing mobile menu JS shows it in the dropdown, and outside `{% block nav_links %}` so the 26 overriding pages keep it. On phones the nav is hidden until the menu button opens it, and the `.nav a.header-cta` rules from Task 1 keep the button white-on-indigo and give it a margin inside the list.

- [ ] **Step 2: Replace the footer's first column**

Replace the first `<div class="footer-section">` in the footer with:

```html
                <div class="footer-section">
                    <h4>{{ site_name|default:"Blik" }}</h4>
                    <p>Anonymous 360° feedback. Pay once per round, subscribe, or self-host the open source version.</p>
                </div>
```

The other four columns and the `footer-bottom` line stay exactly as they are.

- [ ] **Step 3: Check the button is present on an overriding page and a non-overriding page**

```bash
cd /Users/tdz/projects/blik
for p in pricing/ signup/ ; do printf '%s ' $p; curl -s http://127.0.0.1:8777/$p | grep -c 'header-cta'; done
curl -s http://127.0.0.1:8777/pricing/ | grep -c 'footer-signup'
```

Expected: `pricing/ 1`, `signup/ 1`, then `0`.

- [ ] **Step 4: Commit**

```bash
git add templates/landing/base.html
git commit -m "Slim the landing header and footer and add a site-wide review-round button

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: New home page template

**Files:**
- Rewrite: `templates/landing/index.html`

**Interfaces:**
- Consumes: every `.home-*`, `.browser-frame`, `.fact-*`, `.steps`, `.split*`, `.data-grid`, `.plug-grid`, `.cta-card`, `.img-light/.img-dark`, `.eyebrow`, `.section-link` class from Task 1; context keys `rating_data`, `site_name`, `site_protocol`, `site_domain`, `api_swagger_url`, the `PRICING` keys; tags `landing_url`, `article_schema`, `static`.
- Produces: anchors `#product`, `#how`, `#pricing`, `#faq` used by the header and the hero.

- [ ] **Step 1: Keep the head blocks, replace the body**

Keep lines 1-3 (`extends`, `load`) and the entire `{% block meta %}`, `{% block structured_data %}` and `{% block extra_head %}` blocks from the current file, with these edits inside them:

1. Every `<title>`, `og:title` and `twitter:title` becomes `Honest 360° feedback for small teams | Blik360`.
2. Every `description` / `og:description` / `twitter:description` becomes `Anonymous 360° feedback from peers, managers and reports, turned into one clear report. Run a single round for €{{ plan_single_price }}, subscribe from €{{ plan_saas_price }}/mo, or self-host the open source version.`
3. The two `og:image` / `twitter:image` query strings become `?title=Honest%20360%C2%B0%20feedback&subtitle=For%20small%20teams`.
4. In `{% article_schema %}` set `headline="Honest 360° feedback for small teams"` and `description="Anonymous 360° feedback for small teams: one hosted round for a one-time price, a subscription, or self-hosting under AGPL-3.0."`.
5. Delete the `MobileApplication` JSON-LD block (the phone mockup it described is gone). Keep `SoftwareApplication`, `Product` and `Organization`.

Then replace everything from `{% block nav_links %}` to the end of the file with the markup in Steps 2 and 3.

- [ ] **Step 2: Nav and content blocks**

```html
{% block nav_links %}
    <a href="#product">Product</a>
    <a href="#how">How it works</a>
    <a href="#pricing">Pricing</a>
    <a href="{% landing_url 'developers' %}">Developers</a>
    <a href="{% landing_url 'alternatives' %}">Compare</a>
    <a href="#faq">FAQ</a>
{% endblock %}

{% block content %}
    <section class="hero home-hero">
        <div class="container">
            <div class="hero-content">
                <span class="eyebrow">360° feedback</span>
                <h1 class="hero-title">Honest 360° feedback for small teams</h1>
                <p class="hero-subtitle">Anonymous reviews from peers, managers and reports, turned into one clear report. Run a single round for €{{ plan_single_price }}, subscribe, or self-host the open source version.</p>
                <div class="hero-cta">
                    <a href="{% landing_url 'signup' %}?plan=single" class="btn btn-primary">Run a review round, €{{ plan_single_price }}</a>
                    <a href="#how" class="btn btn-secondary">See how it works</a>
                </div>
                <p class="hero-note">No subscription · EU hosted · Open source</p>
            </div>
            <div class="home-hero-media">
                <div class="browser-frame">
                    <div class="browser-frame-bar"><span></span><span></span><span></span></div>
                    <img class="img-light" src="{% static 'img/screenshots/report_professional_skills_overview_light.webp' %}" alt="A Blik 360 feedback report: overall score, self-assessment gap and skill level" width="1920" height="1080" loading="eager">
                    <img class="img-dark" src="{% static 'img/screenshots/report_professional_skills_overview_dark.webp' %}" alt="" width="1920" height="1080" loading="eager">
                </div>
            </div>
        </div>
    </section>

    <section class="section" style="padding-top: 0;">
        <div class="container">
            <div class="fact-strip">
                <div class="fact"><span class="fact-value">4</span><span class="fact-label">questionnaires included</span></div>
                <div class="fact"><span class="fact-value">€{{ plan_single_price }}</span><span class="fact-label">per round, no subscription</span></div>
                <div class="fact"><span class="fact-value">EU</span><span class="fact-label">hosted in Germany</span></div>
                <div class="fact"><span class="fact-value">AGPL</span><span class="fact-label">open source, self-host free</span></div>
                {% if rating_data %}<div class="fact"><span class="fact-value">{{ rating_data.aggregateRating.ratingValue }}/5</span><span class="fact-label">from {{ rating_data.aggregateRating.ratingCount }} reviews</span></div>{% endif %}
            </div>
        </div>
    </section>

    <section id="how" class="section">
        <div class="container">
            <h2 class="section-title">How it works</h2>
            <div class="steps">
                <div class="step">
                    <div class="step-media"><img src="{% static 'img/screenshots/invitations_desktop_light.webp' %}" alt="Inviting reviewers for a review cycle" loading="lazy"></div>
                    <h3>Add people, pick a questionnaire</h3>
                    <p>Add the person being reviewed, choose one of four questionnaires or your own, and list who should give feedback.</p>
                </div>
                <div class="step">
                    <div class="step-media">
                        <img class="img-light" src="{% static 'img/screenshots/feedback_mobile_light.webp' %}" alt="A reviewer answering questions on a phone" loading="lazy">
                        <img class="img-dark" src="{% static 'img/screenshots/feedback_mobile_dark.webp' %}" alt="" loading="lazy">
                    </div>
                    <h3>Reviewers answer through a link</h3>
                    <p>Each reviewer gets a private link by email. No account, no app, works on a phone. Reminders go out automatically.</p>
                </div>
                <div class="step">
                    <div class="step-media">
                        <img class="img-light" src="{% static 'img/screenshots/report_charts_desktop_light.webp' %}" alt="A radar chart comparing self, peer, manager and direct report ratings" loading="lazy">
                        <img class="img-dark" src="{% static 'img/screenshots/report_charts_desktop_dark.webp' %}" alt="" loading="lazy">
                    </div>
                    <h3>Read the report</h3>
                    <p>Scores per category, self versus others, and a skill and initiative level with concrete next steps. Share it with the person or keep it for the conversation.</p>
                </div>
            </div>
        </div>
    </section>

    <section id="product" class="section section-alt">
        <div class="container">
            <div class="split">
                <div class="split-text">
                    <span class="eyebrow">Reports</span>
                    <h2>Reports people actually read</h2>
                    <p>One page per person, with the numbers that matter and the gaps that start a useful conversation.</p>
                    <ul>
                        <li>Scores per competency, from every reviewer group</li>
                        <li>Self-assessment next to what others said, sorted by gap</li>
                        <li>A skill level on the <a href="{% landing_url 'dreyfus_model' %}">Dreyfus model</a> and an initiative level on the <a href="{% landing_url 'agency_levels' %}">five levels of agency</a></li>
                        <li>Strengths, development areas and written comments</li>
                    </ul>
                </div>
                <div class="browser-frame">
                    <div class="browser-frame-bar"><span></span><span></span><span></span></div>
                    <img class="img-light" src="{% static 'img/screenshots/report_charts_desktop_light.webp' %}" alt="Performance overview radar chart in a Blik report" loading="lazy">
                    <img class="img-dark" src="{% static 'img/screenshots/report_charts_desktop_dark.webp' %}" alt="" loading="lazy">
                </div>
            </div>

            <div class="split split--reverse">
                <div class="split-text">
                    <span class="eyebrow">Questionnaires</span>
                    <h2>A questionnaire for every role</h2>
                    <p>Four research-backed questionnaires come with Blik. Use them as they are, edit them, or write your own.</p>
                    <ul>
                        <li><strong>Professional Skills 360</strong>, for any role</li>
                        <li><strong>Software Engineering 360</strong>, for engineers</li>
                        <li><strong>Manager 360</strong>, for people leads</li>
                        <li><strong>360 Degree Feedback</strong>, twelve questions for a quick round</li>
                    </ul>
                    <p>Likert scales, multiple choice and free text. Your own questionnaires stay private to your organisation.</p>
                </div>
                <div class="browser-frame">
                    <div class="browser-frame-bar"><span></span><span></span><span></span></div>
                    <img class="img-light" src="{% static 'img/screenshots/feedback_desktop_light.webp' %}" alt="A questionnaire section as a reviewer sees it" loading="lazy">
                    <img class="img-dark" src="{% static 'img/screenshots/feedback_desktop_dark.webp' %}" alt="" loading="lazy">
                </div>
            </div>
        </div>
    </section>

    <section id="pricing" class="section">
        <div class="container">
            <h2 class="section-title">Pay once, subscribe, or self-host</h2>
            <p class="section-intro">Flat prices, no per-seat fees, reviewers are always free.</p>
            {% include "landing/includes/pricing_plans.html" %}
        </div>
    </section>

    <section class="section section-alt">
        <div class="container">
            <h2 class="section-title">Your data</h2>
            <div class="data-grid">
                <div class="feature-card">
                    <h3>Hosted in the EU</h3>
                    <p>The hosted service runs at Hetzner in Germany with daily backups. Self-host and the data never leaves your servers.</p>
                </div>
                <div class="feature-card">
                    <h3>Tools for GDPR obligations</h3>
                    <p>Export your whole organisation as JSON, delete people and their data, and keep reports only as long as you need them. Your organisation remains responsible for lawful processing, access and retention.</p>
                </div>
                <div class="feature-card">
                    <h3>How anonymity works</h3>
                    <p>Reviewers answer through token links, never accounts, and reports aggregate by category with a minimum response threshold. A database administrator could in principle link a token to an invitation; nothing in the interface does.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="section">
        <div class="container">
            <h2 class="section-title">Plug it in</h2>
            <div class="plug-grid">
                <div class="feature-card">
                    <h3>Self-host in minutes</h3>
                    <p>One Docker Compose file with PostgreSQL and a setup wizard. Runs on a small VPS.</p>
                    <pre class="code-block"><code>docker compose up</code></pre>
                </div>
                <div class="feature-card">
                    <h3>REST API and webhooks</h3>
                    <p>Bearer-token API for people, cycles and reports, plus HMAC-signed webhooks for cycle events. <a href="{{ api_swagger_url }}" target="_blank" rel="noopener">API docs</a>.</p>
                </div>
                <div class="feature-card">
                    <h3>Your data, in plain JSON</h3>
                    <p>Full export of every account and organisation. Move to another tool without asking us. <a href="{% landing_url 'developers' %}">For developers</a>.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="section section-alt">
        <div class="container">
            <h2 class="section-title">How Blik compares</h2>
            <div class="table-container">
                <table class="comparison-table">
                    <caption>50-person comparison, as of October 2026. USD and EUR are shown separately.</caption>
                    <thead>
                        <tr><th>Platform</th><th>Annual cost</th><th>Scope</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>Blik hosted</td><td>€{{ plan_saas_annual }}</td><td>Up to {{ plan_saas_max }} employees; 360° feedback</td></tr>
                        <tr><td><a href="https://lattice.com/pricing">Lattice</a></td><td>$6,000–19,200</td><td>Performance alone to all five modules; annual billing, $4,000 minimum</td></tr>
                        <tr><td><a href="https://www.cultureamp.com/platform/plans-and-pricing">Culture Amp</a></td><td>Quote required</td><td>No public prices; engagement and performance suite</td></tr>
                        <tr><td><a href="https://www.15five.com/pricing">15Five</a></td><td>$2,400 / $6,600 / $9,600</td><td>Engage / Perform / Total Platform; 360° feedback in Perform and Total Platform</td></tr>
                    </tbody>
                </table>
            </div>
            <p class="section-intro">Compare the feature scope as well as the subscription: Blik has no SSO, native HRIS connectors, or native mobile app.</p>
            <a class="section-link" href="{% landing_url 'alternatives' %}">All alternatives, with dated vendor prices</a>
        </div>
    </section>

    <section id="faq" class="section">
        <div class="container">
            <h2 class="section-title">Questions</h2>
            <div class="faq-grid">
                <details class="faq-item">
                    <summary>Can I pay for one review round without a subscription?</summary>
                    <p>Yes. The Single Round is €{{ plan_single_price }} once and covers a hosted feedback round for up to {{ plan_single_max }} employees, with no subscription and no charge for reviewers. <a href="{% landing_url 'one_time_360_review' %}">See what's included.</a></p>
                </details>
                <details class="faq-item">
                    <summary>How does Blik ensure reviewer anonymity?</summary>
                    <p>Reviewers use token-based links, and reports aggregate feedback by category with configurable thresholds. Responses retain a token reference, which may link to an invitation email. Confidentiality depends on invitation method, permissions, thresholds, and feedback content; it is not guaranteed against administrators with database access.</p>
                </details>
                <details class="faq-item">
                    <summary>Is Blik GDPR compliant?</summary>
                    <p>EU hosting and self-hosting do not automatically establish GDPR compliance. Blik provides export and deletion tools to support your obligations. Your organization remains responsible for lawful processing, configuration, access controls, retention, and compliance processes.</p>
                </details>
                <details class="faq-item">
                    <summary>Can I customize the questionnaires?</summary>
                    <p>Yes! The application comes with 4 default questionnaires for different roles and needs, and you can create your own with no restrictions. We have multiple types of answer modes like Likert scales, multiple choice, and free text. The questionnaires can contain multiple segments which work well on mobile devices too.</p>
                </details>
                <details class="faq-item">
                    <summary>Can I export my data?</summary>
                    <p>Yes. You get a full account and organization JSON export. This makes it easy to back up your data or migrate to another system if you need to.</p>
                </details>
                <details class="faq-item">
                    <summary>How is Blik different from Lattice, Culture Amp, and 15Five?</summary>
                    <p>Blik is AGPL-3.0 software you can self-host free, with a one-time hosted review round for €{{ plan_single_price }} or managed EU hosting subscriptions from €{{ plan_saas_price }}/month for up to {{ plan_saas_max }} employees. Lattice, Culture Amp, and 15Five offer broader hosted performance-management suites with different modules and pricing. <a href="{% landing_url 'alternatives' %}">Compare features, deployment, and dated vendor prices.</a></p>
                </details>
            </div>
            <a class="section-link" href="{% landing_url 'faq' %}">All questions and answers</a>
        </div>
    </section>

    <section class="section cta-section">
        <div class="container">
            <div class="cta-card">
                <h2>Start your first review round today</h2>
                <p>Self-host for free, run a single hosted round for €{{ plan_single_price }}, or let us handle the infrastructure with an EU-hosted subscription.</p>
                <div class="cta-buttons">
                    <a href="{% landing_url 'signup' %}?plan=single" class="btn btn-primary">Run a review round, €{{ plan_single_price }}</a>
                    <a href="#how" class="btn btn-secondary">See how it works</a>
                </div>
            </div>
        </div>
    </section>

    {% include "landing/includes/pricing_sources.html" %}

    {% include "landing/includes/article_metadata.html" with template_path="landing/index.html" author="Thijs de Zoete" %}
{% endblock %}
```

- [ ] **Step 3: FAQ structured data, trimmed to the six visible questions**

```html
{% block extra_scripts %}
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "Can I pay for one review round without a subscription?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Yes. The Single Round is €{{ plan_single_price }} once and covers a hosted feedback round for up to {{ plan_single_max }} employees, with no subscription and no charge for reviewers."
                }
            },
            {
                "@type": "Question",
                "name": "How does Blik ensure reviewer anonymity?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Reviewers use token-based links, and reports aggregate feedback by category with configurable thresholds. Responses retain a token reference, which may link to an invitation email. Confidentiality depends on invitation method, permissions, thresholds, and feedback content; it is not guaranteed against administrators with database access."
                }
            },
            {
                "@type": "Question",
                "name": "Is Blik GDPR compliant?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "EU hosting and self-hosting do not automatically establish GDPR compliance. Blik provides export and deletion tools to support your obligations. Your organization remains responsible for lawful processing, configuration, access controls, retention, and compliance processes."
                }
            },
            {
                "@type": "Question",
                "name": "Can I customize the questionnaires?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Yes! The application comes with 4 default questionnaires for different roles and needs, and you can create your own with no restrictions. We have multiple types of answer modes like Likert scales, multiple choice, and free text. The questionnaires can contain multiple segments which work well on mobile devices too."
                }
            },
            {
                "@type": "Question",
                "name": "Can I export my data?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Yes. You get a full account and organization JSON export. This makes it easy to back up your data or migrate to another system if you need to."
                }
            },
            {
                "@type": "Question",
                "name": "How is Blik different from Lattice, Culture Amp, and 15Five?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Blik is AGPL-3.0 software you can self-host free, with a one-time hosted review round for €{{ plan_single_price }} or managed EU hosting subscriptions from €{{ plan_saas_price }}/month for up to {{ plan_saas_max }} employees. Lattice, Culture Amp, and 15Five offer broader hosted performance-management suites with different modules and pricing."
                }
            }
        ]
    }
    </script>
{% endblock %}
```

- [ ] **Step 4: Render with and without `rating_data` and check the FAQ schema matches the visible questions**

```bash
cd /Users/tdz/projects/blik
DJANGO_SETTINGS_MODULE=landing_settings .venv/bin/python - <<'EOF'
import django, json, re
django.setup()
from django.test import RequestFactory
from django.template.loader import render_to_string
from django.conf import settings
rf = RequestFactory()
for rating in (None, {"aggregateRating": {"ratingValue": "4.8", "ratingCount": "12"}, "reviews": []}):
    html = render_to_string('landing/index.html', {'rating_data': rating, 'site_description': settings.SITE_DESCRIPTION, 'site_keywords': settings.SITE_KEYWORDS}, request=rf.get('/'))
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        json.loads(block)
    faq = [b for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S) if '"FAQPage"' in b][0]
    schema_q = [q['name'] for q in json.loads(faq)['mainEntity']]
    visible_q = re.findall(r'<summary>(.*?)</summary>', html)
    assert schema_q == visible_q, (schema_q, visible_q)
    assert ('4.8/5' in html) == bool(rating)
    assert 'linear-gradient' not in html
    print('ok', 'with rating' if rating else 'without rating', len(visible_q), 'questions')
EOF
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8777/
```

Expected: `ok without rating 6 questions`, `ok with rating 6 questions`, `200`. If a JSON block fails to parse, the usual cause is a trailing comma left by the `{% if rating_data %}` branches; fix the template, not the check.

- [ ] **Step 5: Commit**

```bash
git add templates/landing/index.html
git commit -m "Rewrite the home page: product-first hero, ten short sections, six FAQs

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Gradient removal and white-on-indigo contrast pass

**Files:**
- Modify: `static/css/landing.css` (page-specific blocks below the shared block)

**Interfaces:**
- Consumes: nothing new.
- Produces: a stylesheet with zero gradients and every white-text surface on `--primary-700`.

- [ ] **Step 1: Replace every gradient with a flat colour**

```bash
cd /Users/tdz/projects/blik
grep -n 'gradient' static/css/landing.css
```

Apply these replacements (the line numbers are from before Task 1; find each by its text):

| Rule (find by text) | Replace the `background:` with |
|---|---|
| `--primary-gradient: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);` (the `.assessment-page` variable) | delete the line |
| `.feature-card-success`, `-warning`, `-danger`, `-primary` tinted variants (`rgba(16,185,129,0.05)` style gradients, four rules) | `var(--success-50)`, `var(--warning-50)`, `var(--danger-50)`, `var(--primary-50)` |
| `.landing-page .comparison-cta-box` (`var(--primary-gradient)`) | `var(--primary-700)` |
| `linear-gradient(135deg, var(--primary-600) 0%, var(--success-600) 100%)` (around old line 2067, audience assessment banner) | `var(--primary-700)` |
| `.savings-highlight` (`var(--primary-600)` to `var(--primary-700)`) | `var(--primary-700)` |
| `.landing-page .dreyfus-stages-banner` and the about-page banner (`primary-600` to `primary-700`, old lines 6262 and 6329) | `var(--primary-700)` |
| `.assessment-page .hero-section`, `.section-icon`, `.question-number`, `.assessment-progress::-webkit-progress-value`, `::-moz-progress-bar`, `.submit-button` and any other `var(--primary-gradient)` use | `var(--primary-700)` |
| `.landing-page .assessment-email-card`, `.landing-page .confirmation-cta` (`var(--color-primary)` to `var(--color-primary-dark)`) | `var(--primary-700)` |

```bash
sed -i '' -E \
  -e '/--primary-gradient: linear-gradient/d' \
  -e 's/background: var\(--primary-gradient\);/background: var(--primary-700);/' \
  -e 's/background: linear-gradient\(135deg, var\(--primary-600\) 0%, var\(--primary-700\) 100%\);/background: var(--primary-700);/' \
  -e 's/background: linear-gradient\(135deg, var\(--primary-600\) 0%, var\(--success-600\) 100%\);/background: var(--primary-700);/' \
  -e 's/background: linear-gradient\(135deg, var\(--color-primary\) 0%, var\(--color-primary-dark\) 100%\);/background: var(--primary-700);/' \
  -e 's/background: linear-gradient\(135deg, rgba\(16, 185, 129, 0\.05\) 0%, rgba\(16, 185, 129, 0\.02\) 100%\);/background: var(--success-50);/' \
  -e 's/background: linear-gradient\(135deg, rgba\(245, 158, 11, 0\.05\) 0%, rgba\(245, 158, 11, 0\.02\) 100%\);/background: var(--warning-50);/' \
  -e 's/background: linear-gradient\(135deg, rgba\(239, 68, 68, 0\.05\) 0%, rgba\(239, 68, 68, 0\.02\) 100%\);/background: var(--danger-50);/' \
  -e 's/background: linear-gradient\(135deg, rgba\(79, 70, 229, 0\.05\) 0%, rgba\(79, 70, 229, 0\.02\) 100%\);/background: var(--primary-50);/' \
  static/css/landing.css
grep -c 'gradient' static/css/landing.css
```

Expected: `0`. If not zero, print the remaining lines and replace each by hand with the flat colour from the table.

- [ ] **Step 2: Move white-text surfaces from `--primary-600` to `--primary-700`**

These rules set `color: white` (or near-white) and `background: var(--primary-600)`. Change each background to `var(--primary-700)`:

`.landing-page .feature-card-gradient`, `.landing-page .audience-highlight`, `.landing-page .framework-page .framework-principle-card--wide`, `.landing-page .framework-page .framework-principle-panel`, `.landing-page .framework-page .framework-research-banner`, `.landing-page .framework-page .matrix-scenario-prompt`, `.landing-page .framework-page .dreyfus-agency-link`, `.landing-page .dreyfus-stages-banner`, `.checkout-btn.primary`.

```bash
cd /Users/tdz/projects/blik
.venv/bin/python - <<'EOF'
import re
p = 'static/css/landing.css'
s = open(p).read()
targets = ['.landing-page .feature-card-gradient', '.landing-page .audience-highlight',
  '.landing-page .framework-page .framework-principle-card--wide',
  '.landing-page .framework-page .framework-principle-panel',
  '.landing-page .framework-page .framework-research-banner',
  '.landing-page .framework-page .matrix-scenario-prompt',
  '.landing-page .framework-page .dreyfus-agency-link',
  '.landing-page .dreyfus-stages-banner', '.checkout-btn.primary']
for sel in targets:
    pat = re.compile(re.escape(sel) + r' \{([^}]*)\}')
    m = pat.search(s)
    assert m, sel
    body = m.group(1)
    assert 'white' in body or 'rgba(255' in body, sel
    new = body.replace('var(--primary-600)', 'var(--primary-700)')
    assert new != body, (sel, 'no primary-600 found')
    s = s[:m.start(1)] + new + s[m.end(1):]
open(p, 'w').write(s)
print('ok')
EOF
```

Expected: `ok`. An assertion names the selector whose text drifted; fix that one by hand.

- [ ] **Step 3: Retire whites that no longer sit on indigo**

The shared hero and CTA band were indigo; now they are the page background. Every remaining white-text rule was checked against its parent surface:

| Selector | Parent surface after Step 1 | Change |
|---|---|---|
| `.landing-page .faq-hero-link` | shared `.hero`, now page background | `color: var(--primary); text-decoration: underline;` |
| `.landing-page .hero-subtitle.about-hero-subtitle`, `.landing-page .hero-title.product-on-primary-title` (about page) | `.hero.about-hero`, now `--primary-700` | leave white |
| `.landing-page .feature-card .product-on-primary-title`, `.product-on-primary-copy` (open-source page, lines 348 and 458) | line 458 is inside `.feature-card-gradient`, now `--primary-700`: leave white. Line 348: open `templates/landing/open_source.html:340-350`; if its card has no indigo class, remove `product-on-primary-*` from that markup so the card reads with the default text colours | see left |
| `.landing-page .feature-card .about-join-title` / `.about-join-copy`, `.landing-page .btn.about-hosting-button` | `.about-join-card`, now `--primary-700` | leave white |
| `.landing-page h2.audience-assessment-title`, `p.audience-assessment-description`, `p.audience-assessment-note` | audience assessment banner, now `--primary-700` | leave white |
| `.landing-page .home-framework*`, `.home-assessment*`, `.role-badge` | deleted in Task 1 | confirm with grep |

```bash
cd /Users/tdz/projects/blik
grep -n 'home-framework\|home-assessment\|role-badge' static/css/landing.css | wc -l
sed -n 340,350p templates/landing/open_source.html
```

Expected: first command `0`. The second shows the card around line 348; apply the table row.

- [ ] **Step 4: Verify no white text is left on a `--primary-600` or `--primary` surface, except buttons and badges**

```bash
cd /Users/tdz/projects/blik
awk '
/{[[:space:]]*$/ { sel=$0; sub(/[[:space:]]*{[[:space:]]*$/,"",sel); bg="" }
/background:/ { bg=$0 }
/color: *white|color: *rgba\(255/ { if (bg ~ /primary-600\)|var\(--primary\)/) { gsub(/^[ \t]+/,"",bg); printf "%5d %s | %s\n", NR, sel, bg } }
' static/css/landing.css
```

Expected: only button-like or badge-like selectors remain (`.featured-badge`, `.read-more-toggle`, `.card-expand-toggle:hover`, `.slider-scenario-btn.active`, `.portfolio-strategy-number`, `.carousel-nav:hover`, `.questionnaire-badge`). Those are small bold UI elements on `--primary` (#6366f1 in dark mode, 4.4:1 against white), which meets the 3:1 UI-component floor. Any text-bearing panel in the output is a miss: move it to `--primary-700`.

- [ ] **Step 5: Commit**

```bash
git add static/css/landing.css
git commit -m "Replace every landing gradient with a flat colour and put white text on primary-700 only

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Route check, visual comparison, and fixes to inherited pages

**Files:**
- Create (throwaway, in the scratchpad, not committed): `render_assessment.py`, `phone.html`
- Modify as needed: `static/css/landing.css` (only breakage caused by Tasks 1-4)

**Interfaces:**
- Consumes: everything above.
- Produces: the before/after screenshot set and any fixes.

- [ ] **Step 1: Status check for every landing URL**

```bash
cd /Users/tdz/projects/blik
.venv/bin/python - <<'EOF'
import re, subprocess
src = open('landing/urls.py').read()
paths = re.findall(r"path\('([^']*)'", src)
expected = {'dreyfus-assessment/submit/': '302', 'dreyfus-assessment/capture-email/': '302'}
bad = []
for p in paths:
    code = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', f'http://127.0.0.1:8777/{p}'], capture_output=True, text=True).stdout
    want = expected.get(p, '200')
    if code != want:
        bad.append((p, code, want))
print('checked', len(paths))
print('bad', bad)
EOF
```

Expected: `checked 35`, `bad []`. Note `dreyfus-assessment/` itself returns 200 with the "unavailable" template when the main app API is down; that is designed behaviour, and Step 3 covers the real form.

- [ ] **Step 2: Run the Django test suite**

```bash
cd /Users/tdz/projects/blik
.venv/bin/python manage.py test 2>&1 | tail -5
```

Expected: `OK` (PostgreSQL-only tests skip on SQLite). A `TemplateSyntaxError` here points at the rewritten template.

- [ ] **Step 3: Render the three assessment templates with fixed contexts**

Save to the scratchpad as `render_assessment.py` and run it from the project directory:

```python
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'landing_settings'
django.setup()
from django.template.loader import render_to_string
from django.test import RequestFactory

req = RequestFactory().get('/')
q = {'sections': [
    {'title': 'Problem solving', 'description': 'How you approach unfamiliar work.', 'questions': [
        {'uuid': 'q1', 'question_text': 'When given a vague task, I clarify the goal before starting.', 'required': True, 'config': {'labels': {'1': 'Rarely', '5': 'Always'}}},
        {'uuid': 'q2', 'question_text': 'I can debug a problem I have never seen before.', 'required': True, 'config': {'labels': {'1': 'Rarely', '5': 'Always'}}},
    ]},
    {'title': 'Initiative', 'description': 'What you do when nobody asks.', 'questions': [
        {'uuid': 'q3', 'question_text': 'I propose improvements without being asked.', 'required': True, 'config': {'labels': {'1': 'Rarely', '5': 'Always'}}},
    ]},
]}
preview = {'skill_level': 3.4, 'skill_stage': 'Competent', 'agency_level': 3.8, 'agency_stage': 'Self-Driven',
           'quadrant': {'name': 'Rising Star', 'description': 'Growing skills with strong initiative.'}}
pages = {
    'assessment_form': ('landing/dreyfus_assessment.html', {'questionnaire': q, 'total_questions': 3}),
    'assessment_results': ('landing/dreyfus_results_preview.html', {'preview': preview}),
    'assessment_captured': ('landing/dreyfus_email_captured.html', {'preview': preview, 'email': 'you@example.com', 'report_url': 'https://example.com/report'}),
}
out = os.environ['OUT']
for name, (tpl, ctx) in pages.items():
    html = render_to_string(tpl, ctx, request=req)
    html = html.replace('<head>', '<head><base href="http://127.0.0.1:8777/">', 1)
    for theme in ('light', 'dark'):
        themed = html.replace('<head>', f"<head><script>localStorage.setItem('theme','{theme}')</script>", 1)
        open(f'{out}/{name}_{theme}.html', 'w').write(themed)
        print('wrote', f'{name}_{theme}.html')
```

```bash
cd /Users/tdz/projects/blik
S=/private/tmp/claude-501/-Users-tdz-projects-blik/5c232ab0-18df-4f88-8a0d-8015cf083fb7/scratchpad
mkdir -p $S/after
OUT=$S/after .venv/bin/python $S/render_assessment.py
```

Expected: six `wrote …` lines.

- [ ] **Step 4: Screenshot every page in both themes at desktop width**

For the live pages, force a theme the same way: save each page with `curl`, inject the `localStorage` line and a `<base href>`, and screenshot the `file://` copy.

```bash
cd /Users/tdz/projects/blik
S=/private/tmp/claude-501/-Users-tdz-projects-blik/5c232ab0-18df-4f88-8a0d-8015cf083fb7/scratchpad
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
for p in "" pricing hr-managers developers vs-lattice dreyfus-model one-time-360-review faq people-analytics performance-matrix about open-source; do
  n=${p:-home}
  curl -s "http://127.0.0.1:8777/$p" | sed "s#<head>#<head><base href=\"http://127.0.0.1:8777/\">#" > $S/after/$n.html
  for t in light dark; do
    sed "s#<head>#<head><script>localStorage.setItem('theme','$t')</script>#" $S/after/$n.html > $S/after/${n}_$t.html
  done
done
for f in $S/after/*_light.html $S/after/*_dark.html; do
  n=$(basename $f .html)
  "$C" --headless=new --screenshot=$S/after/$n.png --window-size=1440,5000 --user-data-dir=$S/after/ud-$n "file://$f" >/dev/null 2>&1 &
done
sleep 30; pkill -f "headless=new"; ls $S/after/*.png | wc -l
```

Expected: `30` (12 live pages plus 3 assessment templates, × 2 themes). Open each PNG with the Read tool and compare with `/tmp/landing-before/<name>.png`. Record, per page, one line: fine, or what broke.

- [ ] **Step 5: Phone-width screenshots**

Save to the scratchpad as `phone.html`:

```html
<!doctype html><meta charset="utf-8">
<style>body{margin:0;display:flex;gap:16px;padding:16px;background:#888}iframe{width:375px;height:2600px;border:0;background:#fff}</style>
<iframe src="after/home_light.html"></iframe>
<iframe src="after/home_dark.html"></iframe>
<iframe src="after/pricing_light.html"></iframe>
<iframe src="after/hr-managers_light.html"></iframe>
<iframe src="after/assessment_form_light.html"></iframe>
```

```bash
S=/private/tmp/claude-501/-Users-tdz-projects-blik/5c232ab0-18df-4f88-8a0d-8015cf083fb7/scratchpad
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$C" --headless=new --screenshot=$S/phone.png --window-size=2000,2700 --user-data-dir=$S/ud-phone "file://$S/phone.html" >/dev/null 2>&1 &
sleep 10; pkill -f "headless=new"; ls -la $S/phone.png
```

Open `phone.png`. Expected: every column stacks to one column, no horizontal scrollbar inside any iframe, the header shows the logo and the menu button only.

- [ ] **Step 6: Fix breakage found in Steps 4 and 5**

Fix only what the shared changes broke, in `static/css/landing.css`, below the shared block, next to the page's own rules. Typical findings and their fixes:

- A page hero with text that is now invisible (white on page background) → that rule is in the Task 4 Step 3 table; apply the same `--text-primary` / `--text-secondary` swap.
- A grid that overflows at phone width → add the grid's selector to the `@media (max-width: 960px)` list in the shared block.
- A `.cta-box` inside `.cta-section` with a stray white heading → `color: var(--text-primary)`.

Re-run Step 4 for the affected page only and look again.

- [ ] **Step 7: Commit**

```bash
cd /Users/tdz/projects/blik
git add static/css/landing.css
git commit -m "Fix inherited landing pages after the shared restyle

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
pkill -f "runserver 8777"
```

If Step 6 changed nothing, skip the commit and just stop the server.

---

### Task 6: Dreyfus framework block on the home page

Added after the user reviewed the Task 3 home page: the Dreyfus graphic and explanation were missing. It becomes a third text-beside-image block in the "What you get" section (`#product`), after the questionnaires block and before Pricing, using the existing `.split` component and the existing SVG component.

**Files:**
- Modify: `templates/landing/index.html` (inside `<section id="product">`, after the `split split--reverse` questionnaires block)
- Modify: `static/css/landing.css` (one small rule pair in the shared block, after `.browser-frame img`)

**Interfaces:**
- Consumes: `.split`, `.split-text`, `.eyebrow` from Task 1; `templates/components/dreyfus_model_svg.html` (a 912×516 SVG that uses `--text-primary` and other theme tokens, so it renders in both themes); `landing_url` names `dreyfus_model`, `agency_levels`, `performance_matrix`, `dreyfus_assessment_start`.
- Produces: `.diagram-frame` class.

- [ ] **Step 1: Add the frame rule to the shared block**

In `static/css/landing.css`, directly after the `.landing-page .browser-frame img { … }` rule in the shared components block, add:

```css
/* Bordered surface for an inline SVG diagram (the Dreyfus model on the home page) */
.landing-page .diagram-frame {
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--bg-card);
    padding: var(--space-6);
}

.landing-page .diagram-frame svg {
    display: block;
    width: 100%;
    height: auto;
}
```

- [ ] **Step 2: Add the block to the home page**

In `templates/landing/index.html`, inside `<section id="product" class="section section-alt">`, immediately after the closing `</div>` of the `<div class="split split--reverse">` questionnaires block and before the section's closing `</div></section>`, insert:

```html
            <div class="split">
                <div class="split-text">
                    <span class="eyebrow">The framework</span>
                    <h2>A shared language for skill</h2>
                    <p>Every report places the person on the five stages of the <a href="{% landing_url 'dreyfus_model' %}">Dreyfus model of skill acquisition</a>, from Novice to Expert, and on the <a href="{% landing_url 'agency_levels' %}">five levels of agency</a>. Growth becomes a concrete next stage instead of a vague rating.</p>
                    <ul>
                        <li>Skill level, derived from the competency scores</li>
                        <li>Initiative level, derived from the agency questions</li>
                        <li>One <a href="{% landing_url 'performance_matrix' %}">performance matrix</a> quadrant that combines the two</li>
                        <li>Concrete next steps for the stage the person is at</li>
                    </ul>
                    <p>Try it on yourself: a <a href="{% landing_url 'dreyfus_assessment_start' %}">free five-minute developer skills assessment</a>, no signup.</p>
                </div>
                <div class="diagram-frame" aria-label="The five stages of the Dreyfus model: Novice, Advanced Beginner, Competent, Proficient, Expert" role="img">
                    {% include 'components/dreyfus_model_svg.html' %}
                </div>
            </div>
```

- [ ] **Step 3: Render check**

```bash
cd /Users/tdz/projects/blik
DJANGO_SETTINGS_MODULE=landing_settings .venv/bin/python - <<'EOF'
import django, re
django.setup()
from django.test import RequestFactory
from django.template.loader import render_to_string
from django.conf import settings
html = render_to_string('landing/index.html', {'rating_data': None, 'site_description': settings.SITE_DESCRIPTION, 'site_keywords': settings.SITE_KEYWORDS}, request=RequestFactory().get('/'))
product = html.split('id="product"')[1].split('id="pricing"')[0]
assert product.count('class="split') == 3, product.count('class="split')
assert 'diagram-frame' in product and '<svg class="dreyfus-model' in product
assert product.index('A shared language for skill') > product.index('A questionnaire for every role')
print('ok: 3 split blocks, SVG present, framework block last')
EOF
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8777/
```

Expected: `ok: 3 split blocks, SVG present, framework block last`, `200`.

- [ ] **Step 4: Screenshot the home page in both themes and check the block**

```bash
cd /Users/tdz/projects/blik
S=/private/tmp/claude-501/-Users-tdz-projects-blik/5c232ab0-18df-4f88-8a0d-8015cf083fb7/scratchpad
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
mkdir -p $S/task6
curl -s http://127.0.0.1:8777/ | sed "s#<head>#<head><base href=\"http://127.0.0.1:8777/\">#" > $S/task6/home.html
for t in light dark; do sed "s#<head>#<head><script>localStorage.setItem('theme','$t')</script>#" $S/task6/home.html > $S/task6/home_$t.html; done
```

Then screenshot `file://$S/task6/home_light.html` and `file://$S/task6/home_dark.html` at 1440×5000, and a 375px iframe wrapper of both, the way Task 5 did. Open the PNGs: the SVG must be fully visible inside its frame, text in the SVG legible in both themes, and the block stacked to one column at phone width.

- [ ] **Step 5: Commit**

```bash
git add templates/landing/index.html static/css/landing.css
git commit -m "Add the Dreyfus framework block to the home page

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
