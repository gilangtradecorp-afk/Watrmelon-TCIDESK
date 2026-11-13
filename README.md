# Tradecorp Sales CRM

Starter project for continuing the CRM build in Claude Code.

## Contents
| Path | What |
|---|---|
| `CLAUDE.md` | Project memory: context, agreed decisions, working rules, roadmap. Claude Code reads it automatically. |
| `KICKOFF_PROMPT.md` | The first message to paste into Claude Code |
| `model/index.html` | Working model: all screens and rules, plain JavaScript |
| `model/seed.json` | Dummy data (22 enquiries, 18 requests, 9 catalog items) |
| `tools/gen_seed.py` | Regenerates the dummy data |
| `docs/IT_Handover.md` | Data model, rules, role matrix, gaps versus production |
| `docs/Tradecorp_CRM_Mockup_v0.3.pdf` | Static mock-up and architecture diagram |
| `docs/LINKS.md` | Links to the live model, PRD and guides |

## How to start
1. Unzip to a folder you keep projects in.
2. Open that folder in Claude Code.
3. Paste the text from `KICKOFF_PROMPT.md`.

## Status
- Works today: the model as a Claude artifact (shared database).
- Not yet: running standalone on a PC with saved data (first Claude Code task).
- Blocked on IT: Entra app registration for real login and SharePoint data.

## Tools used
Claude (chat) for the PRD, model and guides; Playwright for the click-through test; Python for seed data.

## 4D self-check
- Delegation: Claude packaged the project and wrote CLAUDE.md from the agreed decisions. G chooses where it lives and what Claude Code builds first.
- Description: decisions copied from the PRD (sections 9a to 9l) as of 12 Nov 2026.
- Discernment: only dummy data is included. Real staff first names and codes are in the model. The PRD text itself is not in the pack, only linked.
- Diligence: verify CLAUDE.md matches your understanding before the first Claude Code session; it will be treated as the source of truth.
