# Landing redesign: new home page and site-wide look

Date: 2026-10-11
Status: approved in conversation, awaiting written review

## Goal

Replace the Blik home page with a shorter, clearer page that sells, in this
order: honest anonymous 360° feedback for small teams, the €19 Single Round
with no subscription, data control and GDPR tooling, and pluggability
(self-hosting, REST API, webhooks, JSON export). Give the whole public site a
cleaner look at the same time by rewriting the shared design tokens and
components that all landing pages use.

Reference point: effy.ai. What to borrow: a light, product-first hero with a
real screenshot, short sections with one job each, large plain facts, a
compact comparison table and a short "your data" block. What not to borrow:
gradient text, gradient backgrounds, invented customer counts.

## Decisions already made

- Hero angle: outcome-led, "Honest 360° feedback for small teams". Pricing and
  open source appear in the sub-heading and the next sections, not the H1.
- Scope: new tokens and shared components in the landing stylesheet; only the
  home page gets new content. The other 31 landing templates keep their class
  names and inherit the new look. They are checked for breakage, not
  redesigned.
- Theme: light and dark both stay, following the system preference as today.
  The toggle stays.
- Hero visual: the existing report overview screenshot in a thin browser
  frame, light or dark image by theme. No new assets.
- Pricing cards and prices do not change. `landing/includes/pricing_plans.html`
  is reused as is.

## Visual language

Rules that apply to every public page, in both themes:

- One accent colour: the existing indigo scale from `main.css`. No gradients
  anywhere on public pages. The `--primary-gradient` custom property and its
  uses in the landing stylesheet are replaced with flat `--primary-600`.
- Surfaces: page background, card background, 1px `--border`. Cards carry no
  drop shadow. The only shadow left is on the hero screenshot frame.
- The hero sits on the page background. The flat indigo hero banner and the
  indigo closing-CTA band are gone. Closing CTA is a bordered card.
- Type: system font stack unchanged. Headings use a four-step scale: H1
  3.5rem on desktop (2.25rem on phones), section H2 `--text-4xl`, card H3
  `--text-xl`, eyebrow labels `--text-sm` uppercase with `0.06em` tracking.
  H1 and H2 get `letter-spacing: -0.02em` and `line-height: 1.1`. Body copy
  is capped at 65ch.
- Rhythm: sections are `--space-20` tall on desktop and `--space-12` on
  phones. Section titles are left-aligned inside two-column sections and
  centred only above grids.
- Container: 1120px max, 16px side gutter on phones, 32px from 768px.
- Buttons: `.btn` stays; primary is solid indigo, secondary is bordered. The
  hero-specific white button override is removed because the hero is no longer
  indigo.

## Shared template changes

`templates/landing/base.html`:

- Header: logo, the page's `nav_links` block, theme toggle, and one new
  primary button "Run a review round" linking to `signup?plan=single`. The
  button sits outside the `nav_links` block so every page gets it, including
  the 26 pages that override the block with their own anchor links. The
  default `nav_links` become Product (home page `#product` anchor, as an absolute link so it works from any page), Pricing,
  Developers, Compare (alternatives), FAQ.
- Footer: same five columns and links, minus the embedded "Get Started"
  button. Tighter spacing, smaller type.
- Mobile menu, theme script and the expandable helpers are unchanged.

## Home page (`templates/landing/index.html`)

Rewritten from scratch. Meta, Open Graph, SoftwareApplication and Article
structured data are kept with updated titles; the FAQ structured data lists
only the six questions below. Sections in order:

1. **Hero.** Two columns from 960px, stacked below. Left: eyebrow "360°
   feedback", H1 "Honest 360° feedback for small teams", one sentence
   ("Anonymous reviews from peers, managers and reports, turned into one
   clear report. Run a single round for €19, subscribe, or self-host the
   open source version."), primary button "Run a review round, €19"
   (`signup?plan=single`), secondary link "See how it works" (`#how`). Under
   the buttons one muted line: "No subscription · EU hosted · Open source".
   Right: `report_professional_skills_overview_{light,dark}.webp` in a
   browser frame with three dots, light/dark chosen by theme with the same
   CSS pattern the carousel used (`[data-theme="dark"]` swaps the image).
2. **Fact strip.** Four items in a row, each a large figure and a short
   label: "4 questionnaires", "€19 per round", "EU hosted", "AGPL-3.0". When
   `rating_data` is present a fifth item shows the rating value and count.
   Nothing is invented.
3. **How it works** (`#how`). Three numbered steps, each with a short title,
   two sentences and a screenshot: add people and pick a questionnaire
   (`invitations_desktop_light`), reviewers answer through a link with no
   account (`feedback_mobile_{light,dark}`), you read the report
   (`report_charts_desktop_{light,dark}`).
4. **What you get** (`#product`). Two text-beside-image blocks. "Reports
   people actually read": radar chart screenshot; copy names per-category
   scores, self-versus-others gaps, and Dreyfus skill and agency levels, with
   links to the Dreyfus and agency pages. "A questionnaire for every role":
   one compact list of the four questionnaires with their audience, plus one
   line that every questionnaire is editable and custom questionnaires stay
   private.
5. **Pricing** (`#pricing`). H2 "Pay once, subscribe, or self-host", one
   intro line, then `{% include "landing/includes/pricing_plans.html" %}`.
6. **Your data.** Three bordered items in a row: EU hosting (Hetzner,
   Germany; self-hosting keeps data on your servers), GDPR tooling (account
   and organisation JSON export, deletion tools, 30-day retention after
   cancellation) with the existing honest sentence that the organisation
   stays responsible for lawful processing, and anonymity (token links, no
   reviewer accounts, aggregation thresholds) with the existing caveat that
   a database administrator could in principle link tokens to invitations.
7. **Plug it in.** Three short items: self-host with Docker Compose (one
   code block: `docker compose up`), REST API and HMAC-signed webhooks, JSON
   export of everything. Links to the developers page and `api_swagger_url`.
8. **Compare.** The existing 50-person cost table (Blik hosted €588, Lattice,
   Culture Amp, 15Five) with its caption and scope note, and one link to the
   alternatives page. The row of four comparison buttons is dropped.
9. **FAQ.** Six `<details>` items: Can I pay for one review round without a
   subscription? How does Blik ensure reviewer anonymity? Is Blik GDPR
   compliant? Can I customize the questionnaires? Can I export my data? How
   is Blik different from Lattice, Culture Amp, and 15Five? Answers are the
   existing ones. One link to the full FAQ page.
10. **Closing CTA.** Bordered card: H2 "Start your first review round
    today", the hero's two buttons.

Removed from the home page: the "Why Blik" etymology, the screenshot
carousel and phone mockup, the nine feature cards, the use-case grid, the
Dreyfus framework section and the developer assessment promo. All of it
still exists on its own pages, linked from the footer or from the sections
above.

## Stylesheet changes (`static/css/landing.css`)

Replace, not add. The following blocks are deleted and rewritten in one
"Shared components" block at the top of the file, right after the utility
classes:

- Header, Hero, Sections, Features Grid base (lines 176-330 today).
- CTA Section and Footer (654-740).
- Homepage block (5134-5331): the story, questionnaire grid, framework
  diagram and showcase styles go; whatever the new sections need is written
  fresh.
- Screenshot carousels, the screenshot light/dark swap rules and the Phone
  Mockup (4830-5133) are kept: hr_managers, people_analytics, eu_tech,
  privacy, open_source, dreyfus_model and dreyfus_results_preview still use
  them. Only selectors whose last consumer was the old home page are
  removed, decided by grepping `templates/landing` for each class before
  deleting it.
- The mobile hero overrides inside the two responsive blocks (around 1263
  and 1573) are folded into the new hero rules.
- Later rules that would override the new shared block are consolidated
  into it, not left to fight: the `.landing-page .container` rule at 1558
  (1400px) and its 640px variant, and the two mobile `.landing-page
  .section` padding rules at 1279 and 1594. After the change there is one
  container rule and one section rule, each with its own breakpoints.
- White-on-indigo colours that assumed the old hero and CTA band are
  replaced with theme tokens: `.faq-hero-link` (white) becomes
  `--primary-600` underlined; `.cta-section .cta-box` and its `h3` and `p`
  (translucent white) become a bordered card with `--text-primary` and
  `--text-secondary`. Any other `white` or `rgba(255,255,255,…)` colour in
  the landing stylesheet is audited the same way: keep it only where the
  element still sits on a solid `--primary-700` surface in both themes.

New component classes, all prefixed to avoid collisions with the 31 other
pages: `.home-hero`, `.home-hero-media`, `.browser-frame`, `.fact-strip`,
`.steps`, `.step`, `.split` (text-beside-image), `.data-grid`, `.plug-grid`,
`.cta-card`. Existing shared classes keep their names (`.section`,
`.section-title`, `.section-intro`, `.features-grid`, `.feature-card`,
`.pricing-*`, `.faq-*`, `.comparison-table`, `.footer-*`, `.header*`,
`.nav`) so other pages keep working; only their values change.

Gradient removal: every `linear-gradient` and `--primary-gradient` use in
the landing stylesheet becomes a flat colour. Tinted card variants become
`--primary-50`-style flat tints. Solid indigo surfaces that carry white text
(the Dreyfus assessment hero, question numbers, progress bar and submit
button, and any other surface the white audit keeps) use `--primary-700`
(#4338ca), not `--primary-600`: `main.css` remaps `--primary-600` to #818cf8
in dark mode, where white text reaches only about 3:1, while `--primary-700`
is the same in both themes and gives white text over 8:1. Primary buttons
keep `--primary` from `main.css`, which already passes in both themes.

Expected net size: the file shrinks. Nothing page-specific below the shared
block is restyled unless a visual check shows it broke.

## Pages checked, not redesigned

After the change, these pages are screenshotted in both themes at 1440px and
at phone width and compared with before: home, pricing, hr_managers,
developers, vs_lattice, dreyfus_model, one_time_360_review, faq,
people_analytics. Fixes are limited
to breakage caused by the shared changes (a hero that lost its contrast, a
grid that overflowed). No copy or structure changes on those pages.

## Testing

The landing app has no unit tests and this change adds none: it is templates
and CSS, with no logic unit to test. Verification is:

1. `.venv/bin/python manage.py test` still passes (template errors surface
   here through the pages that render in other apps' tests).
2. The standalone landing server answers every GET page in
   `landing/urls.py` with status 200, and the two POST-only endpoints
   (`dreyfus-assessment/submit/`, `dreyfus-assessment/capture-email/`) with
   302 on GET, which is their designed behaviour. One shell loop with an
   expected-status table, not a blanket 200 check.
3. The visual comparison above, light and dark, desktop and phone. The two
   templates only reachable through the assessment POST flow
   (`dreyfus_results_preview.html`, `dreyfus_email_captured.html`) are
   rendered with `render_to_string` and a small fixed context from a
   throwaway script, then screenshotted the same way. The assessment form
   (`dreyfus_assessment.html`) is rendered the same way with a fixed
   questionnaire dict of two sections and three questions, so the check
   exercises the form and not the "unavailable" fallback that the live view
   shows when the questionnaire API is unreachable. Both themes, both
   widths, as for the other pages.
4. The home page's FAQ JSON-LD contains exactly the six visible questions.

## Out of scope

Pricing changes, new copy on other pages, a new font, removing dark mode,
customer logos or testimonials (none exist), and any change to the main app
UI under `templates/admin_dashboard` or `static/css/main.css` beyond what the
landing stylesheet overrides for itself.
