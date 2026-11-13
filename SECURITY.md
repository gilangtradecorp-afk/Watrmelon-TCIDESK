# Security Policy

This is a private repository for the PT Tradecorp Indonesia Sales CRM. It is not open source. Do not fork it to a personal account or copy it outside the company.

## Supported versions

| Version | Supported |
|---|---|
| `main` branch | Yes |
| Anything else (old branches, local copies, the published Claude artifact) | No |

## Reporting a problem

If you find a security issue (a leaked secret, real customer data in the repo, a way to see or change data you should not have access to):

1. **Do not** open a normal GitHub issue or post it in a shared Slack channel.
2. Contact the repo owner, Gilang (Regional Head SBY), directly by Teams or company email.
3. Say what you found, where (file and line, or screen and steps), and whether it has already been shared anywhere.

You should get a reply within 2 business days (Mon-Fri, 08:00-17:00 WIB). A confirmed leaked secret is revoked first and cleaned from the history after.

## Rules for everyone who works in this repo

- **No secrets in git.** Client secrets, tokens, API keys and passwords go in `.env`, which is git-ignored. If you commit one by mistake, tell the owner straight away: deleting the file is not enough, because the secret stays in the history and must be revoked.
- **Dummy data only.** No real customer names, prices, emails or phone numbers. Seed customers end with "(sample)".
- **Staff data.** The model contains real staff first names and short codes. Keep the repo private and do not paste these into outside tools.
- **Least access.** Collaborators get the lowest role they need: Read to view, Write to push. Only the owner has Admin.
- **Leaving the team.** The owner removes your access on your last day.
- **Microsoft 365.** Any code that writes to SharePoint or uses the Entra app is reviewed by the owner before it is merged, and the IT team is told before it runs against real data.
- **Outside services.** Ask the owner before adding a service that sends company data outside Microsoft 365.
