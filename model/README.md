# HTML model (Node)

The single-file working model of the Tradecorp CRM: `index.html` (all screens and rules, plain JavaScript) with dummy data in `seed.json`. It is the reference the Flask app in the repo root was built from, and it still runs on its own.

## Run it on a PC
Needs Node.js 18 or newer (check with `node -v`). No `npm install` needed: the server uses no extra packages. From the repo root:

```powershell
node server.js
```

- Open http://localhost:8080. Other PCs on the office network open `http://<server IP>:8080` (find the IP with `ipconfig`). Windows Firewall may ask to allow Node.js: allow it on **private** networks only.
- First time: click **Load sample data**.
- Data is saved in `model/writes.json` (not in git). Back up that file; delete it to start empty.
- Other port: `$env:PORT=9000; node server.js`. Other data file: `$env:CRM_DATA="C:\path\copy.json"; node server.js` (handy for testing without touching `writes.json`).
- Test: `node --test test`.

**No login.** Anyone who can reach the port can read and change data. Keep it on the office network, dummy data only.

## Changelog

### 13 Nov 2026: UI cleanup, theme and language
- **Theme and language:** a light/dark toggle (moon/sun icon) and an EN/ID select at the bottom of the left rail, both remembered per browser. With no theme chosen, the page follows the computer's setting.
- **Fewer tabs:** "Workload" and "Interactions" merged into one **Team** tab. Sales has 4 tabs, the RM 5, Management 4. Sales lost "My workload", which repeated the desk.
- **Fewer numbers:** at most 3 KPI cards per screen. Things that need action come first; on Region control, Approvals, Reassignment and No response are at the top.
- **Enquiry screen:** one main button for the next step (New: Mark contacted; open: Log follow-up; Lost: Reopen). The other actions are under **More**. Empty cards (no requests, no same-customer match) are hidden.
- **Demo tools:** the "view as" role, person and demo clock are grouped in one dashed **Demo** box.
- **Rule explanations:** long notes (tier scores, escalation, quotation validity, who sees what) moved behind a small ⓘ icon next to the heading.
- **Fixes:**
  - Cancel and Save in dialogs did not close the dialog (CSS bug).
  - Text contrast on tier chips, the red Open button and light-mode amber.
  - The page now has a mobile viewport tag, so the phone layout works.

**Tested:**
- `node --test` passes.
- All four roles and all their tabs render, with no screen showing more than 3 KPIs.
- The enquiry screen is correct for New, Contacted, Ongoing, No response, Won and Lost.
- The More menu and the ⓘ help work with mouse and keyboard (Enter, Escape).
- Text contrast passes WCAG AA in light and dark, EN and ID, on 8 screens.
- At 375 px phone width the page has no sideways scroll.

**Not tested / known gaps:**
- A full save of a new enquiry (skipped so no test data went into `writes.json`).
- The Indonesian text has not been reviewed by a native speaker.
- Activity-log entries and some dialog notes are English only.
- Some labels are 11 px.
- Long dialogs need scrolling on short screens.

### 13 Nov 2026: roadmap step 1
Added `server.js` (serves the model, saves data to `model/writes.json`) and a server adapter in `model/index.html`. Tested: `node --test` (save, read back, bad input rejected), and in a browser: sample data loaded through the page (22 enquiries, 18 requests, 9 catalog items), and it was still there after a reload. Not tested: two PCs at once, opening from another PC on the network, a long-running server.
