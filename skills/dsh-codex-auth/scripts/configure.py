#!/usr/bin/env python3
"""Offline DSH configuration helper. Requires PyYAML; never logs secret values.

POSIX only: Windows requires a separate ACL-aware implementation.
DSH must be stopped; this helper does not share DSH's credential writer lock.
YAML comments/formatting are normalized. Original bytes are backed up.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import uuid

try:
    import yaml
except ImportError:
    sys.exit('Install PyYAML into a virtual environment; see scripts/README.md.')


class Refused(Exception):
    pass


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise Refused('Duplicate YAML key; nothing changed.')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def private_file(path, secret=False):
    if path.is_symlink():
        raise Refused('Symlink refused; nothing changed.')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise Refused('Expected a regular file owned by the current user.')
    if secret and info.st_mode & 0o077:
        raise Refused('Secret file permissions must be owner-only (chmod 600).')
    if info.st_nlink != 1:
        raise Refused('Hard-linked file refused.')


def read_yaml(path, secret=False):
    private_file(path, secret)
    raw = path.read_bytes()
    try:
        return raw, yaml.load(raw, Loader=UniqueLoader)
    except (yaml.YAMLError, ValueError, TypeError):
        raise Refused('Unsupported or malformed YAML; nothing changed.') from None


def mapping(value):
    if not isinstance(value, dict):
        raise Refused('Expected a YAML mapping; nothing changed.')
    return value


def save(path, before, document):
    """Atomic replacement with backup and a best-effort concurrent-write check."""
    if path.read_bytes() != before:
        raise Refused('File changed during preparation; nothing changed.')
    encoded = yaml.safe_dump(document, sort_keys=False, allow_unicode=True).encode()
    # Parse the generated file before touching the target.
    yaml.load(encoded, Loader=UniqueLoader)
    backup = path.with_name(path.name + '.bak-' + uuid.uuid4().hex)
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(before)
        stream.flush()
        os.fsync(stream.fileno())
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        private_file(path)
        if path.read_bytes() != before:
            raise Refused('Concurrent edit detected; original preserved; backup retained.')
        # Both absolute paths are checked here before replacement/removal.
        if temporary.parent != path.parent or not temporary.name.startswith('.' + path.name + '.'):
            raise Refused('Unexpected temporary path.')
        os.replace(temporary, path)
    finally:
        if temporary.exists() and temporary.parent == path.parent and temporary.name.startswith('.' + path.name + '.'):
            temporary.unlink()
    print('Updated:', path)
    print('Owner-only backup:', backup)


def import_grant(args):
    source = Path(os.path.abspath(Path(args.auth_file).expanduser()))
    target = Path(os.path.abspath(Path(args.credentials).expanduser()))
    if source == target:
        raise Refused('Source and destination must differ.')
    private_file(source, secret=True)
    try:
        grant = json.loads(source.read_bytes())['openai-codex']
    except (ValueError, KeyError, TypeError):
        raise Refused('Invalid pi-ai credential JSON; values redacted.') from None
    mapping(grant)
    required = {'type', 'access', 'refresh', 'expires', 'accountId'}
    if set(grant) != required or grant['type'] != 'oauth':
        raise Refused('Unsupported grant schema; check the installed pi-ai version.')
    if any(not isinstance(grant[k], str) or not grant[k].strip() for k in ('access', 'refresh', 'accountId')):
        raise Refused('Missing required credential strings.')
    if type(grant['expires']) not in (int, float) or not time.time() * 1000 < grant['expires'] < 1e16:
        raise Refused('Credential expiry must be future epoch milliseconds.')
    raw, document = read_yaml(target, secret=True)
    mapping(document)
    if document.get('version') != 1:
        raise Refused('Unsupported credential document version.')
    records = mapping(document.setdefault('records', {}))
    key = 'llm-pi-ai/openai-codex'
    if key in records:
        raise Refused('Codex credential already exists; refusing replacement.')
    records[key] = {'kind': 'grant', 'payload': grant}
    if args.apply:
        save(target, raw, document)
    else:
        print('Dry run OK: would add the Codex grant. No secret values shown.')


def configure_route(args):
    target = Path(os.path.abspath(Path(args.patch).expanduser()))
    raw, document = read_yaml(target)
    if not isinstance(document, list) or any(not isinstance(x, dict) for x in document):
        raise Refused('Expected a patch entry list.')
    ids = [x['id'] for x in document if 'id' in x]
    if len(ids) != len(set(ids)):
        raise Refused('Duplicate patch IDs; refusing to guess.')
    entries = [x for x in document if x.get('id') == 'llm-pi-ai']
    if len(entries) != 1:
        raise Refused('Expected one existing llm-pi-ai entry; inspect the active profile.')
    entry = entries[0]
    if entry.get('name', '@deepseek-ai/dsh-llm-pi-ai') != '@deepseek-ai/dsh-llm-pi-ai' or entry.get('disabled'):
        raise Refused('Unexpected or disabled llm-pi-ai entry.')
    providers = mapping(mapping(entry.setdefault('config', {})).setdefault('providers', {}))
    if 'openai-codex' in providers:
        raise Refused('Codex route already exists; refusing replacement.')
    providers['openai-codex'] = {'displayName': 'ChatGPT (Codex)'}
    if args.apply:
        save(target, raw, document)
    else:
        print('Dry run OK: would add openai-codex; other providers remain unchanged.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    imp = sub.add_parser('import-grant', help='Import a separate pi-ai grant into an existing DSH store')
    imp.add_argument('--auth-file', required=True)
    imp.add_argument('--credentials', required=True)
    route = sub.add_parser('configure-route', help='Add a route to an existing active-profile patch')
    route.add_argument('--patch', required=True)
    for child in (imp, route):
        child.add_argument('--apply', action='store_true', help='Write changes; otherwise dry-run only')
        child.add_argument('--dsh-stopped', action='store_true', help='Confirm all DSH credential/config writers are stopped')
    args = parser.parse_args()
    if os.name != 'posix':
        raise Refused('POSIX only; Windows requires ACL-aware handling.')
    if args.apply and not args.dsh_stopped:
        raise Refused('Stop DSH and pass --dsh-stopped before applying changes.')
    (import_grant if args.operation == 'import-grant' else configure_route)(args)


if __name__ == '__main__':
    try:
        main()
    except Refused as error:
        print('ERROR:', error, file=sys.stderr)
        sys.exit(1)
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError):
        # Parser/OS exceptions may include a credential source line: never print them.
        print('ERROR: operation refused or failed. Check schema, permissions, existing entries, and --dsh-stopped. No secret values logged.', file=sys.stderr)
        sys.exit(1)
