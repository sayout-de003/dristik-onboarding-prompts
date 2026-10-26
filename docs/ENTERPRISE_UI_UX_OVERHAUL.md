# Dristik Enterprise UI/UX Overhaul

## Objective

Redesign the full Dristik application into a coherent, accessible, evidence-first enterprise SaaS product. This is a page-by-page product redesign, not a theme-only change. Preserve existing API contracts, routes, authentication, audit capabilities, and report/export behavior unless a separate approved implementation explicitly changes them.

## Non-negotiable product principles

1. **Explain the result in plain language.** Every analysis should answer: What did we check? What did we find? What does it mean? Why does it matter? What should I do next?
2. **Evidence before assertion.** Findings must identify affected URL(s), evidence/scope, observation date where available, confidence, severity, and a practical fix. Do not invent evidence or imply a fix was verified when it was not.
3. **Honest measurement states.** Visually distinguish measured, calculated, inferred, simulated, unavailable, and not connected. An unconnected source is not a score of zero. Simulated AI-search evaluation is not live AI visibility.
4. **One source of truth.** The frontend presents canonical backend scores, severity, confidence, and measurement state; it must not silently recalculate or blend competing scores.
5. **Progressive disclosure.** Put the summary and next action first. Put definitions, methodology, raw evidence, and advanced settings behind clear expandable details.
6. **Preserve capabilities.** No page or workflow is removed merely to simplify navigation. Consolidate entry points only when the underlying capability remains accessible.
7. **Accessible by default.** Keyboard navigation, visible focus, semantic headings, labeled controls, reduced motion, readable contrast, useful error messages, and responsive layouts are acceptance requirements.

## Shared application shell

- Persistent primary navigation grouped by user task: Overview; Audits; Findings; Remediation; Reports; Data sources; Workspace and settings.
- Keep all existing destinations accessible, including analytics, continuous intelligence, public grader, pricing, account/team, connectors, external authority, agency workspace, scoring rubric, and contact where applicable.
- Add clear active-navigation state, page title, one-sentence description, breadcrumb where hierarchy helps, and a single primary action per page.
- Global search/command menu must use human-readable labels and keyboard instructions.
- Audit/workspace selection must be visible and unambiguous. Do not show workspace-only controls to users who lack permission.
- All pages need designed loading, empty, error, permission-denied, partial-data, and success states.
- Mobile layouts must preserve key actions and allow wide tables to scroll without breaking the viewport.

## Page-by-page redesign contract

### 1. Public entry and onboarding
**Pages:** Intro/landing, sign-up, login, password reset, forgot password, contact, pricing.

- Explain what Dristik does in plain language before product terminology.
- State which audit domains are included and distinguish product capabilities from data sources that require connection.
- Use labeled fields, inline validation, accessible error recovery, password visibility where available, and clear submission/loading states.
- Pricing must not promise unsupported features or imply a connector is active by default.

### 2. Audit creation and configuration
**Pages:** New audit form, site/URL setup, audit data sources, connectors.

- Group fields into Site, Scope, Audit areas, Data sources, and Run settings.
- Explain each advanced option inline; provide examples only when accurate.
- Show what will be inspected and what is excluded before starting.
- Show provider connection state, required permissions, last successful sync if known, and the effect of missing data.
- Prevent accidental duplicate submissions and explain validation errors beside the field.

### 3. Audit execution and pipeline
**Pages:** Pipeline, progress, telemetry, continuous intelligence.

- Show the current stage, completed stages, pending stages, retries/failures, and last update.
- Explain progress in user terms; do not present an arbitrary percentage as meaningful completion when the backend cannot support it.
- Keep logs/technical details available in a diagnostic view, separate from the default user summary.
- Make retry/cancel behavior explicit and preserve the audit identifier and results across refreshes.

### 4. Overview and executive summary
**Pages:** Overview, analysis overview, delta analytics dashboard.

- Lead with site/audit identity, audit status, date, pages checked, scope limitations, and the most important next actions.
- Present SEO, GEO, AEO, and CRO as distinct domains; do not imply they share the same methodology.
- For each score, explain the scale, meaning, coverage, and data limitations. Include methodology access nearby.
- Distinguish current measured performance from readiness, estimates, and unavailable measurements.
- Prioritize a short action list by severity, impact rationale, confidence, and effort where the source supports those fields.

### 5. Findings and evidence
**Pages:** Findings, finding detail/drawer, audit tabs, external authority panels.

Every finding should answer:
- **What we observed:** a specific, verifiable observation.
- **Where:** affected URL(s) and page scope.
- **Why it matters:** practical search, usability, trust, or conversion consequence, without guaranteed outcome claims.
- **Recommended fix:** clear action, with implementation detail where available.
- **How to verify:** observable pass condition.
- **Evidence and confidence:** source, scope, timestamp/snapshot where available, and known limitations.

Use filters with visible active state, result counts, sorting, severity, domain, scope, status, and confidence only where those values exist. Keep raw payloads and technical details available without making them the default reading experience.

### 6. Remediation and prioritization
**Pages:** Roadmap, remediation flow, task/implementation views.

- Explain priority using source-backed severity, impact, confidence, and effort; do not invent revenue estimates or business impact.
- Group related work into understandable steps and show dependencies.
- Make status explicit: suggested, planned, in progress, implemented, and verified are different states.
- Never label a fix as verified solely because a user marked it complete.
- Provide a clear verification step and show evidence of the before/after change when available.

### 7. Reports and exports
**Pages:** Executive report, full audit report, PDF report, report preview/export.

- Preserve premium editorial report layouts and print-specific CSS.
- Use consistent titles, definitions, severity legends, evidence references, scope statements, page numbers, and methodology notes.
- Explain each chart and score in plain language and label missing/partial data honestly.
- Ensure exports match the canonical on-screen report data and include a generated-at timestamp where available.
- Keep report styles isolated from app-shell styles so UI changes cannot damage PDFs.

### 8. Integrations and external data
**Pages:** Connectors modal, audit data sources, external authority, settings.

- Show connected, not connected, authorization required, sync failed, stale, and unavailable states distinctly.
- Explain what data a connector contributes and what it does not measure.
- Provide a test/reconnect action where supported and surface actionable failure messages.
- Never substitute zeros or fabricated metrics when an external provider fails.

### 9. Workspace, account and team
**Pages:** Account panel, team panel, agency workspace, notifications, command palette.

- Make workspace context, role/permissions, member actions, and account settings clear.
- Hide or disable restricted actions with a concise explanation; enforce permissions in the backend as well.
- Notifications need meaningful titles, concise descriptions, and a route to the relevant task.
- Use consistent modal/drawer behavior, close controls, focus handling, and unsaved-change protection where needed.

### 10. Public grader and auxiliary screens
**Pages:** Public grader, scoring rubric, pricing modal, plans, contact, telemetry.

- State what the tool checks, its limitations, and whether the result is a quick sample or a full audit.
- Show definitions and scoring methodology next to rubric-based results.
- Separate technical diagnostics from customer-facing recommendations.
- Ensure public forms and result pages work on small screens and provide clear retry/error states.

## Plain-language writing standard

Prefer:
- “Pages checked” instead of “crawl coverage” when first introducing the metric.
- “Pages with missing title tags” instead of “title-tag deficiency incidence.”
- “We could not measure AI visibility because no live provider result was available” instead of implying zero visibility.
- “This change has been applied but not rechecked” instead of “fixed” when verification is absent.

For each score, metric, chart, or analysis block, provide a short explanation with:
- **What it measures**
- **What this result means**
- **Why it matters**
- **What to do next**
- **Data source and limitations**

Do not turn every paragraph into a tooltip. Keep the main explanation visible and use expandable methodology details for deeper context.

## Visual system

- Neutral, high-contrast canvas; white/light surfaces in light mode; carefully tuned dark mode.
- Restrained teal accent reserved for primary actions and selected states; semantic colors reserved for success, warning, and error.
- Consistent spacing, type scale, borders, radii, buttons, inputs, tabs, tables, cards, banners, empty states, and modals.
- Avoid oversized decorative cards, excessive gradients, unexplained abbreviations, all-caps labels, and charts without a clear takeaway.
- Use stable layouts and skeletons; avoid layout shift while loading.
- Responsive breakpoints must be tested on narrow mobile, tablet, laptop, and wide desktop screens.

## Implementation phases and exit criteria

### Phase 1 — Foundation (started)
- Establish shared visual tokens and common responsive/accessibility refinements.
- Record page inventory and UX contracts.
- **Exit:** app builds, no routes removed, global styles do not leak into report/print rendering.

### Phase 2 — Navigation and shared components
- Review AppShell, navigation labels/grouping, breadcrumbs, page headers, buttons, form fields, cards, tables, banners, drawers, dialogs, and empty/error/loading states.
- **Exit:** all routes are reachable, navigation works by keyboard and touch, shared components behave consistently.

### Phase 3 — Audit journey
- Redesign audit creation, source setup, pipeline, overview, findings, evidence, and remediation.
- **Exit:** a tester can start or open an audit, understand scope and status, find evidence, and identify a verifiable next action without developer assistance.

### Phase 4 — Reports, integrations, and workspace
- Redesign report preview/export, connectors, external data, account/team, agency workspace, grader, and auxiliary pages.
- **Exit:** existing capabilities remain accessible and partial/unavailable data is explained honestly.

### Phase 5 — Verification and release
- Run frontend typecheck/build and automated tests; add/repair tests for routes, permissions, empty/error/loading states, and core workflows.
- Manually test all routes in light/dark themes and at mobile/tablet/desktop widths.
- Check keyboard-only use, focus visibility, contrast, reduced motion, console errors, broken links, overflow, and PDF/print output.
- Run Lighthouse and accessibility checks on representative routes; target 90+ performance where realistic and 95+ accessibility, while documenting route-specific exceptions.
- **Exit:** no known blocker in core journeys, no fabricated measurements, and test evidence is recorded.

## Important status note

This document defines the complete redesign target and acceptance criteria. It does not claim every page has already been redesigned or that tests have passed. The initial shared-style refinement is a foundation only; each page still requires inspection, implementation, and verification against the live application and backend contracts.
