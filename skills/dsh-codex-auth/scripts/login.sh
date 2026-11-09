#!/usr/bin/env bash
# Run interactively in the user's own terminal; never capture the OAuth output in chat.
set -euo pipefail
umask 077

version="${1:-1.3.0}"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  printf 'Expected an exact stable pi-ai version, e.g. 1.3.0.\n' >&2
  exit 1
fi
command -v npx >/dev/null || { printf 'Node.js and npx are required.\n' >&2; exit 1; }
[[ -t 0 && -t 1 ]] || { printf 'Run login in an interactive local terminal.\n' >&2; exit 1; }

# mktemp creates a new private directory, separate from the repository.
dir="$(mktemp -d "${TMPDIR:-/tmp}/dsh-codex-login.XXXXXXXX")"
printf 'Private login directory: %s\n' "$dir"
printf 'Will run @earendil-works/pi-ai@%s; npx may download it.\n' "$version"
printf 'Continue? [y/N] '
read -r answer
[[ "$answer" == y || "$answer" == Y ]] || exit 1
cd "$dir"
npx --package="@earendil-works/pi-ai@$version" pi-ai login openai-codex
[[ -f auth.json && ! -L auth.json ]] || { printf 'No regular auth.json was produced.\n' >&2; exit 1; }
chmod 600 auth.json
printf '\nLogin file: %s/auth.json\n' "$dir"
printf 'Import it locally; do not paste its contents or callback URL into chat.\n'
printf 'Remove this temporary copy after verifying the DSH import.\n'
