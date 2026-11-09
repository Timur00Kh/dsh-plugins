"""Offline tests: synthetic tokens only; never touches real DSH files."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import yaml

SCRIPT = Path(__file__).with_name('configure.py')


@unittest.skipUnless(os.name == 'posix', 'POSIX permission model')
class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.auth = self.root / 'auth.json'
        self.creds = self.root / 'credentials.yaml'
        self.patch = self.root / 'patch.yml'
        self.grant = {'type': 'oauth', 'access': 'TEST_ACCESS_NOT_REAL',
                      'refresh': 'TEST_REFRESH_NOT_REAL', 'accountId': 'test-account',
                      'expires': int(time.time() * 1000) + 3600000}
        self.auth.write_text(json.dumps({'openai-codex': self.grant}))
        self.creds.write_text('version: 1\nrefs:\n  EXAMPLE: retained\nrecords: {}\n')
        self.patch.write_text('- id: llm-pi-ai\n  config:\n    providers:\n      example: {}\n')
        for path in (self.auth, self.creds, self.patch):
            path.chmod(0o600)

    def run_helper(self, operation='import-grant', *flags):
        paths = ['--auth-file', str(self.auth), '--credentials', str(self.creds)]
        if operation == 'configure-route':
            paths = ['--patch', str(self.patch)]
        result = subprocess.run([sys.executable, str(SCRIPT), operation, *paths, *flags],
                                text=True, capture_output=True)
        for value in ('TEST_ACCESS_NOT_REAL', 'TEST_REFRESH_NOT_REAL', 'retained'):
            self.assertNotIn(value, result.stdout + result.stderr)
        return result

    def test_dry_run_changes_nothing(self):
        original = self.creds.read_bytes()
        self.assertEqual(self.run_helper().returncode, 0)
        self.assertEqual(self.creds.read_bytes(), original)
        self.assertEqual(list(self.root.glob('*.bak-*')), [])

    def test_import_preserves_refs_and_backup(self):
        original = self.creds.read_bytes()
        self.assertEqual(self.run_helper('import-grant', '--apply', '--dsh-stopped').returncode, 0)
        doc = yaml.safe_load(self.creds.read_text())
        self.assertEqual(doc['refs'], {'EXAMPLE': 'retained'})
        self.assertEqual(doc['records']['llm-pi-ai/openai-codex']['payload'], self.grant)
        backups = list(self.root.glob('credentials.yaml.bak-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.creds.stat().st_mode & 0o777, 0o600)

    def test_requires_stopped_confirmation(self):
        self.assertNotEqual(self.run_helper('import-grant', '--apply').returncode, 0)

    def test_existing_record_not_overwritten(self):
        self.creds.write_text('version: 1\nrecords:\n  llm-pi-ai/openai-codex: {}\n')
        original = self.creds.read_bytes()
        self.assertNotEqual(self.run_helper('import-grant', '--apply', '--dsh-stopped').returncode, 0)
        self.assertEqual(self.creds.read_bytes(), original)

    def test_duplicate_keys_refused(self):
        self.creds.write_text('version: 1\nrecords: {}\nrecords: {}\n')
        self.assertNotEqual(self.run_helper().returncode, 0)

    def test_malformed_yaml_is_redacted(self):
        self.creds.write_text('version: 1\nrecords: [TEST_REFRESH_NOT_REAL\n')
        self.assertNotEqual(self.run_helper().returncode, 0)

    def test_insecure_permissions_refused(self):
        self.auth.chmod(0o644)
        self.assertNotEqual(self.run_helper().returncode, 0)

    def test_symlink_refused(self):
        link = self.root / 'linked.yaml'
        link.symlink_to(self.creds)
        self.creds = link
        self.assertNotEqual(self.run_helper().returncode, 0)

    def test_expired_grant_refused(self):
        self.grant['expires'] = 1
        self.auth.write_text(json.dumps({'openai-codex': self.grant}))
        self.assertNotEqual(self.run_helper().returncode, 0)

    def test_configure_route_preserves_other_providers(self):
        self.assertEqual(self.run_helper('configure-route', '--apply', '--dsh-stopped').returncode, 0)
        providers = yaml.safe_load(self.patch.read_text())[0]['config']['providers']
        self.assertEqual(providers['example'], {})
        self.assertEqual(providers['openai-codex'], {'displayName': 'ChatGPT (Codex)'})
        self.assertNotEqual(self.run_helper('configure-route').returncode, 0)

    def test_unknown_yaml_tag_refused(self):
        self.patch.write_text('- id: llm-pi-ai\n  config: !!js value\n')
        self.assertNotEqual(self.run_helper('configure-route').returncode, 0)

    def test_duplicate_patch_ids_refused(self):
        self.patch.write_text('- id: llm-pi-ai\n- id: llm-pi-ai\n')
        self.assertNotEqual(self.run_helper('configure-route').returncode, 0)


if __name__ == '__main__':
    unittest.main()
