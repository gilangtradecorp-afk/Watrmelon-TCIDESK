# Tradecorp Sales CRM

Project memory for Claude Code. Read this first, then `README.md` and `docs/IT_Handover.md`.

## What this is
A sales CRM for PT Tradecorp Indonesia (containers, modular buildings, container modifications). One index number follows an enquiry from first contact to BAST (handover document); every step is logged so service level can be measured. Owner: Gilang (G), Regional Head SBY.

## Where we are
- The CRM runs as a Python Flask app (`crm/`) on a local Windows PC in Surabaya: SQLite database in `instance/crm.db`, served by waitress (`serve.py`, port 8000) as a Windows service (NSSM), reached from outside through Tailscale Funnel on G's own Tailscale account. Development server: `run.py` on http://127.0.0.1:5100.
- Login uses the app's own accounts (username + password, hashed). No Microsoft 365, Entra ID or SharePoint dependency, so there is no licence cost and nothing is blocked on IT.
- `model/index.html` (single-file HTML + JavaScript model) is the reference for flows and rules. `seed_data.json` is a copy of `model/seed.json` loaded by `flask --app run.py seed`.
- The Power Apps pilot on SharePoint lists is no longer the target; Microsoft 365 is only a possible later integration (Outlook intake).

## Agreed decisions (do not re-open without asking G)
1. Index number: `ENQ-{Region}-{FirstOwnerCode}-{YYMMDD}-{####}`. Fixed for life. Running number per region, resets yearly. Assign the seller first, then mint.
2. KYC score weights: identity 20, repeat 15, clear need 15, layout 15, qty 10, timeline 10, location 5, budget or decision maker 10. Red flag minus 10. Tier A >= 70, B 40-69, C < 40. Price-check is a separate track.
3. SLA, business hours Mon-Fri 08:00-17:00 WIB: first contact 4 h; RM may reassign after 8 h; status update every 3 business days; daily comment after a quote is sent; no response auto-lost after 7 calendar days, reopenable under the same number.
4. Hand-offs: Drafter, Estimator, Purchasing, Trucking, Depo, Branch, Sales Support. Identity gate before Drafter/Estimator. Catalog-first before Drafter. Tier C and price-check use the catalog only. Urgent needs RM approval. No feedback after 4 h = reminder, after 1 business day = RM flag.
5. Roles: Sales sees own; RM sees and controls own region; Management sees all, read only, no control over RMs; support teams see their own queue.
6. Regions and codes: SBY (GIL rm, ADI, AND), BPN (HEN rm, NOV, REV, YUL), JKT (DIN rm, END, EVI, IVA, YOP, WEL).
7. Quotations: two templates only, Sale and Rental. Project quotes with a BOQ stay with estimators. Price list is owned by RMs.
8. Sales scope ends at delivery plus signed BAST; Finance invoices.
9. Alerts: the app's own team chat (region, team, per-enquiry and direct channels, @mentions, attachments) plus in-app notifications, instead of Slack. SLA reminders are posted by a background check every 5 minutes, once per event. Duplicate window 60 days (email, phone, company).
10. Login: app accounts, not Microsoft. Hosting: G's own PC, GitHub repo and Tailscale account.

Still to confirm with G: estimator capacity per day (app uses 8), what Depo and Branch requests cover, "Tracking" was read as "Trucking".

## Working rules
- Dummy data only. No real customer names, prices, emails or phone numbers in the repo. Seed customers end with "(sample)".
- Never commit secrets (client IDs with secrets, tokens, API keys). Use `.env`, which is git-ignored.
- G is learning to code. Explain jargon the first time it appears, prefer small readable steps, and say what to verify.
- G's machine is Windows with PowerShell 5.1. Give PowerShell commands, and write files as UTF-8 without BOM.
- Every build gets an update to `README.md` (what changed, how to run, what was tested, what was not).
- Flag data issues; do not silently fix them.
- Ask before: deleting files, anything that costs money, anything that sends data outside the company, and any write to Microsoft 365.
- Run the tests before every push: `.venv\Scripts\python -m pytest -q tests`.
- Never commit `.env`, `instance/` (database, uploads) or `.venv/`; they are git-ignored.

## Done
Standalone app with all model screens, business-hours SLA per region time zone and holidays, scheduled reminders, quotation PDF (Sale and Rental) with PPN, discount approval and WhatsApp text, file attachments and contact proof, team chat, mock-up v0.3 features, Order (PO) page, Excel export, smoke tests.

## Suggested roadmap
1. Deploy on the Surabaya PC (NSSM service + Tailscale Funnel), change all demo passwords, set a new `SECRET_KEY`, remove `CRM_DEMO_NOW` from `.env`.
2. Scheduled database backup (copy `instance/` daily).
3. Database migrations (Alembic) before the schema changes with real data in it.
4. Push notifications to phones; Outlook email intake (needs M365 admin approval).

## Map of the code
- `config.py`: settings, read from `.env`.
- `crm/rules.py`: pure rules (constants, business hours, KYC score, tier, SLA state, duplicate keys). Start here for any rule change.
- `crm/models.py`: database tables. `crm/services.py`: shared helpers (time, scoping per role, logging, numbering, chat posting).
- `crm/views/`: one blueprint per area: `auth`, `enquiries`, `dash` (desk, region, workload, management), `hub`, `sales` (quotes, orders, export, price list), `chat`, `admin`.
- `crm/sla_job.py`: background SLA check. `crm/templates/`, `crm/static/`: pages and styling.
- `seed.py`: demo accounts and data. `tests/test_smoke.py`: smoke tests per role and main flow.

The old JavaScript model in `model/index.html` keeps its own layout: constants at the top, `rules`, one function per screen (`vDesk` ... `vMgmt`), actions in `A`.
