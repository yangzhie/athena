import sqlite3
import subprocess
from pathlib import Path


def test_stopped_volume_backup_and_restore_preserve_databases_and_material(tmp_path):
    root = Path(__file__).parents[3]
    volume = tmp_path / 'data'; volume.mkdir()
    for name in ('athena.db', 'agent.db'):
        with sqlite3.connect(volume / name) as db:
            db.execute('CREATE TABLE synthetic (value TEXT)')
            db.execute("INSERT INTO synthetic VALUES ('synthetic acceptance')")
    (volume / 'materials').mkdir()
    (volume / 'materials' / 'synthetic.txt').write_text('Synthetic material')
    backup, restored = tmp_path / 'backup', tmp_path / 'restored'
    for action, source, destination in [('backup', volume, backup), ('restore', backup, restored)]:
        subprocess.run(['python3', str(root / 'scripts/backup.py'), action, str(source), str(destination)], check=True, capture_output=True)
        assert (destination / 'materials/synthetic.txt').read_text() == 'Synthetic material'
        with sqlite3.connect(destination / 'athena.db') as db:
            assert db.execute('SELECT value FROM synthetic').fetchone()[0] == 'synthetic acceptance'
    assert subprocess.run(['python3', str(root / 'scripts/backup.py'), 'restore', str(backup), str(restored)], capture_output=True).returncode != 0
