"""Offline integration tests for the POSIX installer."""
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/install-skills.sh'


class InstallerTest(unittest.TestCase):
    def test_install_and_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / 'repo'
            repo.mkdir()
            (repo / 'sources.toml').write_text(
                '[[sources]]\nid = "demo"\ndest = "skills/demo"\n'
                '[[sources]]\nid = "new-openspec"\ndest = "skills/new"\n')
            for name in ('demo', 'new'):
                skill = repo / 'skills' / name
                skill.mkdir(parents=True)
                (skill / 'SKILL.md').write_text('new content')
            archive = base / 'fixture.tar.gz'
            with tarfile.open(archive, 'w:gz') as tar:
                tar.add(repo, arcname='fixture')
            bin_dir = base / 'bin'
            bin_dir.mkdir()
            curl = bin_dir / 'curl'
            curl.write_text('#!/bin/sh\nwhile [ "$#" -gt 0 ]; do\n'
                            'if [ "$1" = "-o" ]; then cp "$FIXTURE" "$2"; exit; fi\n'
                            'shift\ndone\nexit 1\n')
            curl.chmod(0o755)
            project = base / 'project'
            project.mkdir()
            env = dict(os.environ, PATH=str(bin_dir) + ':' + os.environ['PATH'],
                       FIXTURE=str(archive))

            def run(*args, ok=True):
                result = subprocess.run(['sh', str(SCRIPT), *args], cwd=project,
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
                return result.stdout

            self.assertIn('0 installation(s) updated', run('--update'))
            self.assertFalse((project / '.gitignore').exists())
            run('--target', 'codex', '--only', 'demo')
            installed = project / '.codex/skills/demo'
            (installed / 'SKILL.md').write_text('old')
            (installed / 'obsolete').write_text('obsolete')
            run('--target', 'codex', '--only', 'demo', ok=False)
            self.assertIn('1 installation(s) updated', run('--update'))
            self.assertEqual((installed / 'SKILL.md').read_text(), 'new content')
            self.assertFalse((installed / 'obsolete').exists())
            self.assertFalse((project / '.claude').exists())
            self.assertFalse((project / '.codex/skills/new-openspec').exists())
            custom = project / 'custom skills'
            custom.mkdir()
            (custom / 'demo').symlink_to(installed, target_is_directory=True)
            run('--update', '--target', 'claude', '--dest-root', str(custom), '--only', 'demo')
            self.assertFalse((custom / 'demo').is_symlink())
            self.assertTrue((installed / 'SKILL.md').exists())
            run('--target', 'codex', '--only', 'demo', '--force')
            run('--update', '--only', 'unknown', ok=False)
            run('--only', 'demo', '--force')
            self.assertTrue((project / '.agents/skills/demo/SKILL.md').exists())
            self.assertFalse((project / '.claude/skills/demo').exists())
            run('--target', 'both', '--only', 'demo', '--force')
            self.assertTrue((project / '.claude/skills/demo/SKILL.md').exists())
            run('--target', 'antigravity,claude', '--only', 'demo', '--force')
            before = (project / '.gitignore').read_text()
            run('--target', 'claude', '--only', 'new-openspec', '--dry-run')
            self.assertFalse((project / '.claude/skills/new-openspec').exists())
            self.assertEqual((project / '.gitignore').read_text(), before)
            run('--target', 'unknown', '--only', 'demo', ok=False)
            run('--target', 'codex,claude', '--dest-root', str(custom), ok=False)



if __name__ == '__main__':
    unittest.main()
