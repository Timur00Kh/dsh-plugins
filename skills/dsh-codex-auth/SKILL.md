---
name: dsh-codex-auth
description: Connect a ChatGPT account with Codex access to DeepSeek Harness (DSH) through its built-in pi-ai openai-codex provider, without installing additional DSH plugins. Use for Codex OAuth login, credential import, cordis.patch.yml configuration, and troubleshooting subscription authentication.
---

# DSH Codex OAuth without additional plugins

Configure DSH's **existing** `dsh-llm-pi-ai` integration, not a new provider plugin. Configuration activates a route; it does not perform OAuth login.

## Safety rules

- Never print, echo, paste into chat, commit, or return access tokens, refresh tokens, authorization codes, callback URLs, or credential-file contents. Redact diagnostics, including token exchange errors.
- Login is performed by the user on OpenAI's authorization page. Never ask for a password, session cookie, or a token copied from the browser.
- Discover paths and installed versions; do not assume a username, OS, installation path, provider catalog, model entitlement, or GitHub account.
- Request permission for writes outside the workspace. If sandbox access is denied, use the supported approval mechanism, not an alternative access path.
- Never put OAuth secrets in `cordis.patch.yml`, environment-variable API-key fields, source repositories, or the skill directory.
- Never reuse the same rotating refresh token in Codex CLI and DSH. Obtain a separate grant for this integration.
- Credential storage is normally plaintext protected by filesystem permissions, not an encrypted vault.

## 1. Inspect the installation

1. Determine the actual current working directory and whether DSH Desktop, Web, or another profile is running.
2. Locate the active profile and effective DSH home. The default is `~/.dsh`, but `DSH_HOME` and installation settings may override it.
3. Read the profile patch before editing it. Locate the existing `llm-pi-ai` entry and preserve its other providers.
4. Check installed DSH and pi-ai versions and their local documentation. Confirm that `openai-codex` exists and supports OAuth. This recipe was exercised against DSH `0.2.2-rc.1` and `@earendil-works/pi-ai` `1.3.0`; it is not a guarantee for other releases.
5. Determine whether the current DSH version already exposes provider authorization in the UI or CLI. Prefer that native flow if available. Older versions may register the host authorization flow without exposing a browser button.
6. Do not start another DSH server or modify a different profile just to obtain a login.

See [the reference](references/configuration.md) for paths, schemas, and troubleshooting.

## Bundled helpers

Read [scripts/README.md](scripts/README.md) before executing anything. The helpers are optional, POSIX-only, and require explicit paths:

- `scripts/login.sh [exact-pi-ai-version]`: user-run interactive wrapper around the upstream pi-ai CLI, in a new private temporary directory; default version `1.3.0`. Do not capture its terminal output into chat.
- `scripts/configure.py import-grant --auth-file ... --credentials ...`: validate/import a separate grant, without displaying it.
- `scripts/configure.py configure-route --patch ...`: preserve other providers and add the built-in route.
- Both configuration operations default to dry-run. Writes require `--apply --dsh-stopped`, make an owner-only backup, and refuse conflicting records/routes. They require existing files. Stop DSH first; they do not share its writer lock.
- PyYAML normalizes comments/formatting. Unknown tags such as `!!js` are refused: do not strip them to force the script through; use a native editor or a carefully reviewed targeted edit instead.
- `scripts/test_configure.py`: offline tests using synthetic credentials only.

Do not apply these helpers to an already configured account just to demonstrate the skill.

## 2. Obtain a separate OAuth grant

Prefer a supported native DSH login if the installed version provides one: it writes directly through DSH's credential service and avoids manual import.

Otherwise, use the installed pi-ai OAuth implementation or its matching, pinned CLI version. Obtain user approval before downloading/executing an external package. For the tested version, the interactive command is:

```bash
npx @earendil-works/pi-ai@1.3.0 login openai-codex
```

Run it in a **new private directory outside the repository**, using `umask 077` on POSIX before creating files. The tested CLI writes `auth.json` to its current directory; check this behavior for the installed version. Do not run it at the workspace root.

The user completes login on OpenAI's page. The tested implementation binds a loopback callback on port 1455; check for a conflicting listener before starting. The browser must reach the same host. If manual callback entry is required, use the local CLI prompt, not chat or a public log.

Use the actual provider implementation rather than writing a new OAuth client with hardcoded endpoints/client IDs. If a custom helper is unavoidable, require state validation, PKCE S256, exact callback validation, bounded timeouts, cancellation, loopback-only binding, restrictive file permissions, and redacted errors.

Track any managed background login job. Collect its outcome; cancel it if abandoned. Do not busy-poll or leave a sleeping pipeline behind.

## 3. Import through the credential store

If native login already committed the grant, skip manual import.

For an external pi-ai login, import the `openai-codex` credential into the **active DSH credential store**, preserving all existing entries. Prefer a supported credential-service transaction. Otherwise:

1. Pause competing credential writers or close DSH before editing its credential file.
2. Validate the credential schema locally, without printing values. For the tested implementation it contains `type: oauth`, `access`, `refresh`, `expires` (epoch milliseconds), and `accountId`.
3. Parse the existing credential YAML with a proper YAML parser. Reject malformed documents or conflicting existing records rather than overwriting blindly.
4. Back up the original outside the repository with equally restrictive permissions. Explain that the backup contains secrets too.
5. Insert `records["llm-pi-ai/openai-codex"] = { kind: "grant", payload: credential }` while preserving all other references and records.
6. Write atomically in the same directory with owner-only permissions on POSIX (`0600`; parent directory preferably `0700`). On Windows, check that ACLs restrict access to the intended user.
7. Validate the resulting document without emitting secret values. If anything fails, stop and preserve the original.

Never set `apiKeyEnv` on this route merely to supply an OAuth token: that can override native OAuth and break refresh.

## 4. Activate the built-in route

Merge into the **existing** `llm-pi-ai` entry in the active profile patch:

```yaml
- id: llm-pi-ai
  name: "@deepseek-ai/dsh-llm-pi-ai"
  config:
    providers:
      openai-codex:
        displayName: ChatGPT (Codex)
```

This is a fragment, not a replacement for the entire patch. Keep other providers and unrelated entries. Do not add duplicate `id: llm-pi-ai` entries or duplicate YAML keys.

Omit `api`, `baseURL`, `apiKeyEnv`, and `models` unless inspection of the installed version establishes a need. An omitted `models` list inherits the built-in catalog; an explicit list replaces it. Do not use a placeholder model ID in a saved default.

Validate the YAML and confirm that only the intended route changed. Restart the existing application if required by that version. Do not automatically switch the default model without the user's request.

## 5. Verify and finish

- Confirm the route appears in the actual running DSH instance after reload/restart.
- Use the installed catalog or an authenticated discovery API to choose a model. A catalog entry is not proof that the account can use it.
- Run **one minimal inference**, warning that it consumes a small amount of subscription allowance. Use the native DSH/pi-ai transport rather than a hand-written HTTP request where possible.
- Require a completed successful response, not merely HTTP 200 or an initial stream event. If a model is refused, distinguish entitlement/catalog issues from invalid authentication. Avoid broad model probing that spends unnecessary quota.
- A successful inference does not test future token refresh. Say refresh is supported by the provider, not that it has been independently verified.
- Once import is verified, remove the temporary credential copy using a verified absolute path. Keep backup-retention decisions explicit. Revoke abandoned grants through the account if appropriate.
- Report only the route, chosen model, validation result, whether a restart is still needed, and rollback steps. Never include secrets.

## Rollback

Remove only the added `openai-codex` route and its owned credential record, preserving other providers/accounts. Deleting the local record is **not** server-side revocation. To revoke access, use the supported OpenAI account/session controls. A backup may contain a still-valid refresh token; treat it as a secret until removed or revoked.
