# Tradecorp Sales CRM - IT Hand-over Pack

Prepared 12 Nov 2026 for the IT team. Owner: Gilang Gumilar, Regional Head (SBY).

## 1. What this pack is

A working model of the sales CRM, built as a single web page with dummy data. Sales, regional managers and management have clicked through it and agreed the screens and rules. The request to IT is to rebuild it in Power Apps on Dataverse.

The source code is a reference, not something Power Apps can import. What transfers is the data model, the business rules, the role matrix and the screens.

| File | Use |
|---|---|
| `index.html` | The model. All screens and all rules in one file (HTML, CSS, plain JavaScript, no framework). |
| `seed.json` | Dummy data: 22 enquiries, 18 requests, 9 catalog items, 1 config record. No real customers. |
| `IT_Handover.md` | This document. |
| `README.md` | Build notes and checks. |
| PRD | https://claude.ai/artifact/6vFfLMbBdrMWjGpdcN1vG9 |
| Mock-up PDF v0.3 | Static screens plus the architecture diagram. |

In `index.html`, the rules are in the block marked `rules`, the constants are at the top (`SLA`, `KYC`, `DEPTS`), and each screen is one function (`vDesk`, `vRegion`, `vHub`, `vWork`, `vInter`, `vQuote`, `vMgmt`, `vDetail`).

## 2. Data model (map to Dataverse tables)

### Enquiry
| Field | Type | Notes |
|---|---|---|
| enqNo | Text, unique | `ENQ-{Region}-{FirstOwner}-{YYMMDD}-{####}`. Never changes. |
| received, lastUpdate, contactedAt | DateTime | Drive every SLA calculation. |
| source | Choice | Central, Direct email, WhatsApp |
| customer, contact, phone, email | Text | Used by the duplicate check. |
| line | Choice | Container, Modular, Modification |
| type | Choice | Retail, Project |
| product, location, qty, dateNeeded, pricingDeadline | Text | |
| region | Choice | SBY, BPN, JKT |
| seller | Lookup (User) | Current owner. |
| firstOwner | Lookup (User) | The seller code inside enqNo. |
| status | Choice | New, Contacted, Ongoing, No response, Won, Lost, Not prospectable |
| stage | Choice | New, KYC, Drafter, Estimator, Quote sent, Price-check, PO received, WO approval, WO / Kickoff, Production, Delivered, BAST signed, Handed to Finance |
| kyc (8 flags) | Yes/No x 8 | identity, repeat, need, layout, qty, timeline, location, budget |
| redFlags | Whole number | Minus 10 points each. |
| priceCheck | Yes/No | Separate track: catalog price range only. |
| score, intakeScore, tier | Number, Number, Choice | Calculated. intakeScore is frozen at creation. |
| lossReason | Choice | Price, Lead time, Specification, Competitor, Budget cancelled, No response. Required when Lost. |
| po (6 flags) | Yes/No x 6 | drawing, quote, match, terms, timeline, payment |
| quote | Child table | template (Sale/Rental), revision, lines (item, qty, price), total |
| log | Child table (Activity) | timestamp, actor, text |

### Request (hand-off to another team)
| Field | Type | Notes |
|---|---|---|
| enquiry | Lookup (Enquiry) | |
| dept | Choice | Drafter, Estimator, Purchasing, Trucking, Depo, Branch, Sales Support |
| seller, region | Lookup, Choice | Copied from the enquiry; follows a reassignment. |
| title | Text | What sales needs. |
| urgent, rmApproved | Yes/No | Urgent needs RM approval before it reaches the team. |
| status | Choice | pending (urgent, waiting for RM), sent, accepted, returned, rejected, redirected |
| sentAt, acceptedAt, due, returnedAt | DateTime | |
| reason | Text | For rejections. |
| nudges | Whole number | |
| log | Child table | timestamp, actor, text |

### Catalog item
item, category, mode (Sale, Rental, Service), price (IDR), unit. Owned by the regional managers. Custom items priced by estimators are added afterwards.

### Reference tables
Sellers (code, name, region, role), Regions, Team settings (target days, daily capacity).

## 3. Business rules

All times are business hours: Monday to Friday, 08:00 to 17:00 WIB.

| Rule | Value | Where in the code |
|---|---|---|
| First contact | Within 4 h, else breach | `SLA.contact` |
| Reassign | RM may reassign after 8 h with no contact | `SLA.reassign` |
| Status update | Every 3 business days (27 h) on open enquiries | `SLA.update` |
| Quote follow-up | Daily comment after a quote is sent (9 h) | `SLA.follow` |
| No response | Auto-lost after 7 calendar days, reopenable under the same number | `SLA.lost` |
| Request reminder | No accept, reject or comment after 4 h | `SLA.nofb` |
| Request RM flag | No feedback after 1 business day (9 h) | `SLA.rmflag` |
| Duplicate window | 60 days, match on email, phone or company | `SLA.dup`, `sameCust()` |
| KYC weights | identity 20, repeat 15, clear need 15, layout 15, qty 10, timeline 10, location 5, budget 10 | `KYC` |
| Tiers | A is 70+, B is 40 to 69, C is under 40 | `tier()` |
| Identity gate | No drafter or estimator request without identity | `A.sendReq` |
| Catalog first | Drafter request requires a catalog check; Tier C and price-check use the catalog only | `A.sendReq` |
| Team targets | Drafter 3 d (10 slots/day), Estimator 2 d (8 slots/day, to confirm), Purchasing 3 d, Trucking 2 d, Depo 1 d, Branch 2 d, Sales Support 2 d | `DEPTS` |
| Loss reason | Mandatory on Lost | `A.status` |
| PO handover | 6-item checklist, then RM approval, then work order request to Sales Support | `A.poSend`, `A.apprPO` |

## 4. Role matrix

| Action | Sales | Regional Manager | Management | Support team |
|---|---|---|---|---|
| See enquiries | Own | Own region | All | Linked to own queue |
| Create and update enquiries | Own | Own region | No | No |
| Send requests, nudge | Yes | Yes | No | No |
| Accept, hand back, reject, redirect a request | No | Yes | No | Own team |
| Reassign, approve urgent requests, approve PO packages | No | Yes | No | No |
| Workload and interactions dashboards | Own row | Own region | All regions | No |
| Edit price list | No | Yes | No | No |

In Dataverse this maps to business units per region plus security roles. Management has no control over regional managers; it reads only.

## 5. Where the model is simpler than production

| Topic | Model | Production needs |
|---|---|---|
| Login | A "view as" switcher | Company login (Entra ID) and Dataverse security roles |
| Row security | Rows are filtered on screen, not locked | Real row-level security |
| Index number | Next number computed from existing rows | A counter table with a lock, per region per year |
| SLA timers | Calculated when a screen is opened | Scheduled flows that send reminders and flags (Slack for the SBY pilot) |
| Email intake | Enquiries are typed in | Power Automate on the shared enquiry mailbox; emails with an ENQ number auto-logged |
| AI steps | Not included | KYC pre-fill, follow-up drafts, PO summary |
| Quotation PDF | Totals only | Sale and Rental templates on company letterhead |
| Attachments | Proof is a text reference | File uploads (screenshots, drawings, PO, BAST) |
| Clock | A fixed demo clock (12 Nov 2026 10:00 WIB) so the sample data stays meaningful | Live clock |

## 6. Licences and cost

Current plan: Microsoft 365 Business Premium. It has no full Dataverse and no premium connectors, and Power BI is the free tier.

Dataverse needs Power Apps Premium: USD 20 per user per month, paid yearly, per Microsoft's pricing page (https://www.microsoft.com/en-us/power-platform/products/power-apps/pricing). Every person who uses the app needs one, support teams included. Headcount to confirm.

## 7. Questions for IT

1. Can IT build this as a model-driven or canvas Power App on Dataverse, and in what time frame?
2. Which licences does the company need to buy, and for how many users?
3. Can IT create the shared enquiry mailbox flow and the scheduled reminder flows?
4. Is Slack approved for notifications, or should alerts go to Teams?
5. Who owns the app after go-live (changes, new sellers, price list access)?
