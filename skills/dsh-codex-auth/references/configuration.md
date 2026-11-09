# Configuration reference

## Version scope

The initial procedure was exercised with DSH Desktop `0.2.2-rc.1` and pi-ai `1.3.0`. Reinspect the installed implementation for other versions. OAuth endpoints, catalogs, authorization surfaces, and credential schemas may change.

## Typical locations

These are defaults, not guaranteed paths:

- DSH home: `~/.dsh`, possibly overridden by `DSH_HOME`.
- Desktop patch: `<DSH_HOME>/profiles/desktop/cordis.patch.yml`.
- Web patch: `<DSH_HOME>/profiles/web/cordis.patch.yml`.
- Credential store: `<DSH_HOME>/.credentials.yaml`, possibly overridden by the credential provider configuration.

Desktop and Web are different profiles. Modify the one used by the actual application. Some desktop releases do not support operating the managed Desktop profile through the standalone CLI.

## Route fragment

Merge this into an existing provider dictionary; do not replace other providers:

```yaml
- id: llm-pi-ai
  name: "@deepseek-ai/dsh-llm-pi-ai"
  config:
    providers:
      openai-codex:
        displayName: ChatGPT (Codex)
```

The route ID is `openai-codex`. The credential record key is `llm-pi-ai/openai-codex`. An empty route inherits the installed pi-ai provider's models, endpoint, and protocol.

## Credential document shape

The following is **illustrative only**. Do not paste placeholders into a live credential store. Obtain real values locally from the supported OAuth implementation.

```yaml
version: 1
records:
  llm-pi-ai/openai-codex:
    kind: grant
    payload:
      type: oauth
      access: "<access token — secret>"
      refresh: "<refresh token — secret>"
      expires: 0 # actual epoch milliseconds, not zero
      accountId: "<account identifier>"
```

Preserve other top-level sections, references, records, and comments whenever supported by the editing library. Never use a regular-expression insertion as a general-purpose YAML editor. Avoid direct writes while DSH may be refreshing tokens; use its credential service or stop competing writers.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No ChatGPT login button | Older DSH clients may not expose the host's authorization flow. This does not imply that the provider is absent. |
| Route missing | Active profile, patch composition, YAML validity, settings overrides, and whether a restart is required. |
| Missing credential | Correct credential store and record key; remove an unintended `apiKeyEnv` override. |
| `INVALID_CREDENTIAL` | Credential shape, issuer, account ID, expiry, and whether another client rotated the refresh token. Never log the payload. |
| `model_not_found` / model not supported | Catalog/account entitlement mismatch. Use account discovery when available, then a minimal request. |
| 401 / refresh failure | Reauthenticate if the grant is expired, revoked, or rotated elsewhere; preserve unrelated records. |
| 403 / region refusal | Provider policy or network restrictions. A working proxy is not evidence of permission to use the service. |
| Callback cannot connect | Browser and listener on the same host, port 1455 available for the tested flow, IPv4/localhost reachability. Use the implementation's local manual-entry prompt if available. |
| Quota error | Account plan and provider usage limits; Plus is not unlimited inference. |

Do not hardcode model IDs or claim that every model in the installed catalog is available to a particular subscription.

## Refresh and logout

The tested built-in provider can refresh stored OAuth grants using DSH's credential-store lock. Initial inference success does not prove that refresh will succeed in the future.

Removing the route does not remove the credential. Removing a local credential does not revoke it at the issuer. Document these as separate actions.

## Upstream pointers

Verify these against the installed version rather than assuming upstream HEAD matches the user's installation:

- [DSH repository](https://github.com/deepseek-ai/deepseek-harness)
- [pi-ai package](https://www.npmjs.com/package/@earendil-works/pi-ai)
- [OpenAI Codex authentication](https://developers.openai.com/codex/auth)

Do not confuse Codex OAuth with OpenAI API-key billing or a different Sign in with ChatGPT integration. They can have different client registrations, scopes, endpoints, and supported models.
