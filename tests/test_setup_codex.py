"""Run with: python3 -m unittest discover -s tests -v."""

import json
import random
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = '''
import runpy, sys
from pathlib import Path
from unittest.mock import patch
isolated_home, script, *args = sys.argv[1:]
sys.argv = [script, *args]
with patch('pathlib.Path.home', return_value=Path(isolated_home)):
    runpy.run_path(script, run_name='__main__')
'''


class CodexSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='executor-tests-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.repo = self.base / 'executor'
        self.user_dir = self.base / 'user'
        self.user_dir.mkdir()
        self.repo.mkdir()
        shutil.copy2(ROOT / 'setup', self.repo / 'setup')
        shutil.copytree(ROOT / 'config' / 'codex', self.repo / 'config' / 'codex')
        for name in ('mcp', 'prompts', 'context', 'skills/example'):
            (self.repo / name).mkdir(parents=True)
        (self.repo / 'context/example.md').write_text('Standing instructions\n')
        (self.repo / 'prompts/example.md').write_text('Example prompt\n')
        (self.repo / 'skills/example/SKILL.md').write_text('Example skill\n')
        self.servers = {
            'carrier': {'url': 'http://example.invalid/mcp'},
            'nexus': {'command': 'example-server', 'args': ['stdio']},
        }
        self.save_json('servers.json', self.servers)
        self.save_json('codex.servers.json', {'carrier': {'enabled': True}, 'nexus': {'enabled': False}})
        self.save_json('secrets.json', {
            'carrier': {'headers': {'Authorization': 'Bearer TEST_ONLY', 'X.Header': 'test'}},
            'nexus': {'env': {'TEST_TOKEN': 'TEST_ONLY'}},
        })
        self.api = runpy.run_path(str(self.repo / 'setup'), run_name='test_setup')
        self.config = self.user_dir / '.codex/config.toml'

    def save_json(self, name, data):
        (self.repo / 'mcp' / name).write_text(json.dumps(data))

    def write_config(self, doc):
        self.api['write_toml'](self.config, doc)

    def read_config(self):
        return tomllib.loads(self.config.read_text())

    def run_setup(self, *args, answers='', success=True):
        result = subprocess.run(
            [sys.executable, '-c', BOOTSTRAP, str(self.user_dir), str(self.repo / 'setup'), *args],
            input=answers, text=True, capture_output=True, timeout=15, cwd=self.base,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_fresh_normal_install(self):
        self.run_setup('codex')
        doc = self.read_config()
        self.assertNotIn('sandbox_mode', doc)
        self.assertNotIn('approval_policy', doc)
        self.assertTrue(doc['mcp_servers']['carrier']['enabled'])
        self.assertFalse(doc['mcp_servers']['nexus']['enabled'])
        self.assertEqual(doc['mcp_servers']['carrier']['http_headers']['X.Header'], 'test')
        self.assertEqual(doc['mcp_servers']['nexus']['env']['TEST_TOKEN'], 'TEST_ONLY')
        self.assertTrue((self.user_dir / '.codex/commands/example.md').is_symlink())
        self.assertEqual((self.user_dir / '.codex/AGENTS.md').read_text(), 'Standing instructions\n')
        self.assertEqual(doc['skills']['config'][0]['path'], str(self.repo / 'skills/example'))
        before = self.config.read_bytes()
        self.run_setup('codex')
        self.assertEqual(self.config.read_bytes(), before)

    def test_yolo_and_normal_replay_preserve_plugin_and_tool_settings(self):
        names = ['files/read', 'files.read', 'tool name', 'tool"quote', 'tool\\path', '🛠', 'tool]end']
        tools = {name: {'approval_mode': 'prompt', 'output_token_limit': 1234} for name in names}
        self.write_config({
            'model': 'test-model',
            'projects': {'/tmp/project.with spaces': {'trust_level': 'trusted'}},
            'mcp_servers': {'carrier': {'url': self.servers['carrier']['url'], 'tools': tools}},
            'plugins': {'sample@test': {'enabled': True, 'mcp_servers': {
                'example.server': {'enabled': False, 'tools': tools},
            }}},
        })
        self.run_setup('--yolo', 'codex', answers='y\ny\n')
        doc = self.read_config()
        self.assertEqual(doc['approval_policy'], 'never')
        self.assertEqual(doc['sandbox_mode'], 'danger-full-access')
        self.assertEqual(doc['model'], 'test-model')
        self.assertEqual(doc['projects']['/tmp/project.with spaces']['trust_level'], 'trusted')
        plugin = doc['plugins']['sample@test']['mcp_servers']['example.server']
        self.assertFalse(plugin['enabled'])
        for server in [*doc['mcp_servers'].values(), plugin]:
            self.assertEqual(server['default_tools_approval_mode'], 'approve')
            for tool in server.get('tools', {}).values():
                self.assertEqual(tool, {'approval_mode': 'approve', 'output_token_limit': 1234})
        before = self.read_config()
        self.run_setup('--yolo', 'codex', answers='y\ny\n')
        self.assertEqual(self.read_config(), before)
        self.run_setup('codex')
        self.assertEqual(self.read_config(), before)

    def test_confirmation_cancellation(self):
        for answers in ('n\n', 'y\nn\n', '', 'y\n'):
            with self.subTest(answers=answers):
                self.write_config({'model': 'unchanged'})
                before = self.config.read_bytes()
                result = self.run_setup('--yolo', 'codex', answers=answers, success=answers in ('n\n', 'y\nn\n'))
                self.assertIn('Aborted.', result.stdout)
                self.assertEqual(self.config.read_bytes(), before)
                self.assertFalse((self.user_dir / '.agents').exists())

    def test_legacy_project_paths_and_valid_quoted_keys(self):
        self.config.parent.mkdir(parents=True)
        self.config.write_text('[projects./tmp/legacy.with spaces] # old format\ntrust_level = "trusted"\n\n[mcp_servers.carrier.tools."files/read"]\napproval_mode = "prompt"\n')
        self.run_setup('--yolo', 'codex', answers='y\ny\n')
        doc = self.read_config()
        self.assertEqual(doc['projects']['/tmp/legacy.with spaces']['trust_level'], 'trusted')
        self.assertEqual(doc['mcp_servers']['carrier']['tools']['files/read']['approval_mode'], 'approve')
        self.assertEqual(self.config.read_text().count('trust_level'), 1)
        before = self.read_config()
        self.run_setup('codex')
        self.assertEqual(self.read_config(), before)

    def test_explicit_policy_overrides_and_new_servers(self):
        self.write_config({'mcp_servers': {'carrier': {
            'enabled': False, 'default_tools_approval_mode': 'approve',
            'tools': {'files/read': {'approval_mode': 'approve'}},
        }}})
        self.save_json('codex.servers.json', {'carrier': {
            'enabled': True, 'default_tools_approval_mode': 'writes',
            'tools': {'files/read': {'approval_mode': 'prompt'}},
        }})
        self.run_setup('codex')
        doc = self.read_config()
        self.assertTrue(doc['mcp_servers']['carrier']['enabled'])
        self.assertEqual(doc['mcp_servers']['carrier']['default_tools_approval_mode'], 'writes')
        self.assertEqual(doc['mcp_servers']['carrier']['tools']['files/read']['approval_mode'], 'prompt')
        self.assertFalse(doc['mcp_servers']['nexus']['enabled'])

    def test_yolo_without_mcp_servers(self):
        self.save_json('servers.json', {})
        self.save_json('secrets.json', {})
        self.save_json('codex.servers.json', {})
        self.run_setup('--yolo', 'codex', answers='y\ny\n')
        doc = self.read_config()
        self.assertEqual(doc['mcp_servers'], {})
        self.assertEqual(doc['sandbox_mode'], 'danger-full-access')
        self.assertEqual(doc['approval_policy'], 'never')

    def test_malformed_config_is_not_overwritten(self):
        self.config.parent.mkdir(parents=True)
        for text in ('[broken\n', 'model = "a"\nmodel = "b"\n', '[mcp_servers.x.tools.files/read]\napproval_mode="prompt"\n'):
            with self.subTest(text=text):
                self.config.write_text(text)
                self.run_setup('codex', success=False)
                self.assertEqual(self.config.read_text(), text)

    def test_missing_and_empty_config(self):
        self.assertEqual(self.api['read_toml'](self.config), {})
        self.config.parent.mkdir(parents=True)
        self.config.touch()
        self.assertEqual(self.api['read_toml'](self.config), {})

    def test_randomized_key_round_trips(self):
        rng = random.Random(42)
        alphabet = 'abcXYZ09_-/ ."\\[]#\t\né🛠'
        keys = ['', *[''.join(rng.choice(alphabet) for _ in range(rng.randrange(1, 24))) for _ in range(250)]]
        for key in keys:
            with self.subTest(key=key):
                doc = {'nested': {key: {key: key}}, 'rows': [{key: key}], key: key}
                self.write_config(doc)
                self.assertEqual(self.read_config(), doc)
                self.assertEqual(self.api['read_toml'](self.config), doc)


if __name__ == '__main__':
    unittest.main()
