# Tradecorp Sales CRM

Project memory for Claude Code. Read this first, then `docs/IT_Handover.md`.

## What this is
A sales CRM for PT Tradecorp Indonesia (containers, modular buildings, container modifications). One index number follows an enquiry from first contact to BAST (handover document); every step is logged so service level can be measured. Owner: Gilang (G), Regional Head SBY.

## Where we are
- `model/index.html` is a working single-file model (HTML + plain JavaScript, no framework) with dummy data in `model/seed.json`. It was published as a Claude artifact and uses the artifact database (`window.claude.use("db")`). Outside an artifact that call is absent, so the page falls back to in-memory mode.
- A Power Apps pilot (4 screens on SharePoint lists) is being built by hand in parallel. Do not change SharePoint column names without checking the guide links in `docs/LINKS.md`.
- Target: a real web app on Microsoft 365 data (SharePoint lists via Microsoft Graph, company login via Entra ID). Blocked until IT registers an Entra app. Until then, build against a local storage adapter.

## Agreed decisions (do not re-open without asking G)
1. Index number: `ENQ-{Region}-{FirstOwnerCode}-{YYMMDD}-{####}`. Fixed for life. Running number per region, resets yearly. Assign the seller first, then mint.
2. KYC score weights: identity 20, repeat 15, clear need 15, layout 15, qty 10, timeline 10, location 5, budget or decision maker 10. Red flag minus 10. Tier A >= 70, B 40-69, C < 40. Price-check is a separate track.
3. SLA, business hours Mon-Fri 08:00-17:00 WIB: first contact 4 h; RM may reassign after 8 h; status update every 3 business days; daily comment after a quote is sent; no response auto-lost after 7 calendar days, reopenable under the same number.
4. Hand-offs: Drafter, Estimator, Purchasing, Trucking, Depo, Branch, Sales Support. Identity gate before Drafter/Estimator. Catalog-first before Drafter. Tier C and price-check use the catalog only. Urgent needs RM approval. No feedback after 4 h = reminder, after 1 business day = RM flag.
5. Roles: Sales sees own; RM sees and controls own region; Management sees all, read only, no control over RMs; support teams see their own queue.
6. Regions and codes: SBY (GIL rm, ADI, AND), BPN (HEN rm, NOV, REV, YUL), JKT (DIN rm, END, EVI, IVA, YOP, WEL).
7. Quotations: two templates only, Sale and Rental. Project quotes with a BOQ stay with estimators. Price list is owned by RMs.
8. Sales scope ends at delivery plus signed BAST; Finance invoices.
9. Alerts: Slack for the SBY pilot. Duplicate window 60 days (email, phone, company).

Still to confirm with G: estimator capacity per day (model uses 8), what Depo and Branch requests cover, "Tracking" was read as "Trucking".

## Working rules
- Dummy data only. No real customer names, prices, emails or phone numbers in the repo. Seed customers end with "(sample)".
- Never commit secrets (client IDs with secrets, tokens, API keys). Use `.env`, which is git-ignored.
- G is learning to code. Explain jargon the first time it appears, prefer small readable steps, and say what to verify.
- G's machine is Windows with PowerShell 5.1. Give PowerShell commands, and write files as UTF-8 without BOM.
- Every build gets an update to `README.md` (what changed, how to run, what was tested, what was not).
- Flag data issues; do not silently fix them.
- Ask before: deleting files, anything that costs money, anything that sends data outside the company, and any write to Microsoft 365.

## Suggested roadmap
1. Make the model run standalone: add a storage adapter (interface: subscribe to a collection, set a document) with two implementations, artifact db and localStorage, plus a tiny local server so `seed.json` loads.
2. Split `index.html` into modules (rules, storage, views) and add unit tests for the rules: `biz()`, `score()`, `tier()`, `sla()`, `rst()`, `mint()`, `sameCust()`.
3. Add what the model lacks: business-hours reminders as a scheduled job, quotation PDF (Sale and Rental), file attachments, Outlook intake.
4. When IT delivers the Entra app: add a Microsoft Graph storage adapter for the SharePoint lists and real login.

## Map of the model code
Constants at the top (`PEOPLE`, `DEPTS`, `KYC`, `SLA`), then `rules`, then one function per screen: `vDesk`, `vEnq`, `vDetail`, `vRegion`, `vHub`, `vWork`, `vInter`, `vQuote`, `vMgmt`. Actions are in the `A` object, change handlers in `C`. Writes go through `put()`, `upE()` and `upR()`.
