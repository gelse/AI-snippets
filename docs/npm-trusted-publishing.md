# npm Trusted Publishing (OIDC)

This document describes the one-time setup for OIDC-based trusted publishing
so the GitHub Actions workflow can publish `@gelse/ai-snippets` to npm without
storing an npm access token as a repository secret.

## How it works

The workflow (`.github/workflows/npm-publish.yml`) declares
`id-token: write` permission and uses `actions/setup-node` with
`registry-url: https://registry.npmjs.org`. When npm sees a publish request
from a trusted OIDC identity, it authenticates using the short-lived token
issued by GitHub Actions — no `NODE_AUTH_TOKEN` secret is required.

## One-time npmjs.com setup

1. Sign in to [npmjs.com](https://www.npmjs.com/) and open the
   **Settings** page for the `@gelse/ai-snippets` package.

2. Under **Publishing access**, find **Configure trusted publishers** (or
   **Linked publishers** / **OIDC publishers** depending on the current UI).

3. Click **Add a new trusted publisher** and fill in:

   | Field | Value |
   |-------|-------|
   | **Repository owner** | `gelse` |
   | **Repository name** | `AI-snippets` |
   | **Workflow filename** | `.github/workflows/npm-publish.yml` |
   | **Environment** | _(leave empty)_ |

   The workflow does not declare a GitHub Actions environment, so the
   environment field must be left blank. If a mismatch is present the OIDC
   token will be rejected.

4. Save the configuration.

> **Note:** Provenance attestation (`--provenance`) requires the repository
> to be public on GitHub, or the **Require provenance** option must be
> enabled in the package's npm settings. Since `gelse/AI-snippets` is a
> public repository this is already satisfied.

## First-publish runbook

1. **Sanity-check locally** — run the full packaging target to confirm
   everything builds correctly:

   ```sh
   make package-npx
   ```

   This generates tool artifacts, builds the TypeScript bundle, stages
   embedded assets, and creates a tarball in `dist/`.

2. **Verify the version** — ensure `package.json` version matches the tag
   you intend to push. The CI workflow will fail on a mismatch.

   ```sh
   # Example: tag v0.1.0 ↔ package.json "0.1.0"
   node -p "require('./package.json').version"
   ```

3. **Create and push the tag**:

   ```sh
   git tag v0.1.0
   git push origin v0.1.0
   ```

4. **Watch the workflow** — go to the repository's **Actions** tab and
   monitor the _Publish to npm_ workflow run. On success the version will be
   live on [npmjs.com](https://www.npmjs.com/package/@gelse/ai-snippets).

> **Expected failure on first run:** The CI publish job will fail until the
> npm-side trusted-publishing configuration (steps above) is completed.
> This is normal — complete the one-time setup, then re-run the workflow or
> push the tag again.
