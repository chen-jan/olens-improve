# Public research dashboard

URL: https://olens-improve-research.jan618.chatgpt.site

Anyone with the link can visit. The first publication is a reviewed validation and development snapshot; held-out evaluation is still underway. Publication succeeded and an unauthenticated HTTP request returned the dashboard. No claim is made about the user's own browser session.

The dashboard's timestamp identifies its content snapshot. It is updated at research milestones, not connected directly to a live judge or database. All 12,978 numeric values in the public data were checked against the local report; all eight exported charts are byte-identical. An independent reviewer checked the exported files and links. Internal filesystem paths and job/process identifiers are removed; no credentials, model files, activation caches or private ledgers are published.

Regenerate the public copy with:

```bash
python scripts/build_public_dashboard.py --output .state/public-dashboard/dist
```

The isolated Site checkout and its hosting manifest are under `.state/public-dashboard`. Reuse the project ID recorded in `configs/public_dashboard.json`; obtain a fresh short-lived source credential through Sites and follow its source-packaging/save/deploy workflow. Pass credentials only through the helper's hidden standard input. Preserve public access. Record each successful version and deployment in the config. Do not create another Site or repurpose the main repository's Git remote.

This publication uses the dedicated Sites source repository. The research repository remains locally committed; the user handles GitHub pushes.
