# GitHub Integration Setup for RetroVault Cloud

This document explains how to prepare GitHub integration checks used by the worker endpoints:

- `GET /github-integration-status`
- `GET /changelog`
- `GET /release-notes`

## 1) Create a GitHub token

Create a Personal Access Token (classic or fine-grained) with at least:

- `repo`
- `workflow`
- `read:org`

If you only need read checks, reduce scopes accordingly.

## 2) Test integration status endpoint

Without token:

```bash
curl "https://retrovault.zombi3king24.workers.dev/github-integration-status"
```

With token:

```bash
curl "https://retrovault.zombi3king24.workers.dev/github-integration-status" \
  -H "X-GitHub-Token: YOUR_GITHUB_TOKEN"
```

Expected: JSON response with `github.configured = true` when header is present.

## 3) Optional: expose token as Worker secret

If you later add server-side GitHub API calls in `worker.js`, set a secret:

```bash
npx wrangler secret put GITHUB_TOKEN
```

Then read it from `env.GITHUB_TOKEN` in request handlers.

## 4) Add a GitHub Actions workflow (optional)

Suggested workflow features:

- Lint/syntax check `worker.js`
- Deploy preview branch
- Post deployment URL to PR comment

## 5) Security notes

- Never commit tokens into the repository.
- Rotate leaked tokens immediately.
- Restrict scopes to the minimum required for your automation.

