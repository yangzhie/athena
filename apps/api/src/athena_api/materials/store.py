import time
import uuid
from pathlib import Path

from fastapi import HTTPException

from ..spaces.service import StudySpaces

DOCUMENTS = {'.pdf', '.txt', '.md', '.docx', '.pptx'}
RECORDINGS = {'.mp4', '.mkv', '.mov', '.webm', '.m4a', '.mp3', '.wav', '.flac', '.ogg'}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS materials (
 id TEXT PRIMARY KEY, offering_id TEXT NOT NULL REFERENCES offerings(id), source_id TEXT NOT NULL,
 version INTEGER NOT NULL, filename TEXT NOT NULL, kind TEXT NOT NULL, suffix TEXT NOT NULL,
 storage_path TEXT NOT NULL, size INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
 published INTEGER NOT NULL DEFAULT 0, error TEXT, created_at REAL NOT NULL,
 UNIQUE(source_id, version)
);
CREATE TABLE IF NOT EXISTS material_jobs (
 material_id TEXT PRIMARY KEY REFERENCES materials(id), status TEXT NOT NULL DEFAULT 'queued',
 lease_until REAL NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, lease_token TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS document_passages (
 id TEXT PRIMARY KEY, material_id TEXT NOT NULL REFERENCES materials(id),
 page INTEGER, section TEXT, text TEXT NOT NULL
);
'''


class Materials:
    def __init__(self, spaces: StudySpaces, root: str | Path):
        self.spaces = spaces
        self.db, self.lock = spaces.db, spaces.lock
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock, self.db:
            self.db.executescript(SCHEMA)
            if 'lease_token' not in {r[1] for r in self.db.execute('PRAGMA table_info(material_jobs)')}:
                self.db.execute("ALTER TABLE material_jobs ADD COLUMN lease_token TEXT NOT NULL DEFAULT ''")

    def get(self, offering, id):
        with self.lock:
            cursor = self.db.execute('SELECT * FROM materials WHERE offering_id=? AND id=?', (offering, id))
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(404, 'Material not found.')
            return dict(zip([col[0] for col in cursor.description], row, strict=True))

    def view(self, row):
        result = {key: row[key] for key in ['id', 'source_id', 'version', 'offering_id', 'filename', 'kind', 'size', 'status', 'published', 'error', 'created_at']}
        result['published'] = bool(result['published'])
        return result

    def list(self, offering, manager=False):
        with self.lock:
            cursor = self.db.execute('SELECT * FROM materials WHERE offering_id=? ORDER BY created_at, id', (offering,))
            rows = [dict(zip([c[0] for c in cursor.description], row, strict=True)) for row in cursor.fetchall()]
        return [self.view(row) for row in rows if manager or (row['published'] and row['status'] == 'ready')]

    def reserve_upload(self, offering, filename, replace=None):
        filename = filename.replace('\\', '/').rsplit('/', 1)[-1]
        suffix = Path(filename).suffix.lower()
        if suffix not in DOCUMENTS | RECORDINGS or not filename or len(filename) > 240:
            raise HTTPException(415, 'Supported formats: PDF, text, DOCX, PPTX, audio and video recordings.')
        id = uuid.uuid4().hex
        source, version = id, 1
        if replace:
            old = self.get(offering, replace)
            source = old['source_id']
            with self.lock:
                version = self.db.execute('SELECT MAX(version)+1 FROM materials WHERE source_id=?', (source,)).fetchone()[0]
        return dict(id=id, offering_id=offering, source_id=source, version=version, filename=filename,
                    kind='document' if suffix in DOCUMENTS else 'recording', suffix=suffix,
                    storage_path=str(self.root / (id + suffix)))

    def finish_upload(self, row, size):
        with self.lock, self.db:
            self.db.execute('INSERT INTO materials (id,offering_id,source_id,version,filename,kind,suffix,storage_path,size,created_at) '
                            'VALUES (?,?,?,?,?,?,?,?,?,?)', (*[row[k] for k in ['id','offering_id','source_id','version','filename','kind','suffix','storage_path']], size, time.time()))
            self.db.execute('INSERT INTO material_jobs (material_id) VALUES (?)', (row['id'],))
        return self.view(self.get(row['offering_id'], row['id']))

    def publish(self, offering, id):
        row = self.get(offering, id)
        if row['status'] != 'ready':
            raise HTTPException(409, 'Material must finish processing before publication.')
        with self.lock, self.db:
            self.db.execute('UPDATE materials SET published=1 WHERE id=?', (id,))
        return self.view(self.get(offering, id))

    def retry(self, offering, id):
        row = self.get(offering, id)
        if row['status'] != 'failed':
            raise HTTPException(409, 'Only failed material can be retried.')
        with self.lock, self.db:
            self.db.execute('UPDATE materials SET status="queued",error=NULL WHERE id=?', (id,))
            self.db.execute('UPDATE material_jobs SET status="queued",attempts=0,lease_until=0 WHERE material_id=?', (id,))
        return self.view(self.get(offering, id))

    def claim(self):
        now = time.time()
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            interrupted = self.db.execute('SELECT material_id FROM material_jobs WHERE status="processing" AND lease_until<? AND attempts>=3', (now,)).fetchall()
            for (id,) in interrupted:
                self.db.execute('UPDATE material_jobs SET status="failed" WHERE material_id=?', (id,))
                self.db.execute('UPDATE materials SET status="failed",error=? WHERE id=?', ('Processing was interrupted repeatedly. Retry after checking the worker.', id))
            row = self.db.execute('SELECT j.material_id,m.offering_id FROM material_jobs j JOIN materials m ON m.id=j.material_id '
                                  'JOIN offerings o ON o.id=m.offering_id WHERE o.status!="deleted" AND j.attempts<3 AND '
                                  '(j.status="queued" OR (j.status="processing" AND j.lease_until<?)) ORDER BY m.created_at LIMIT 1', (now,)).fetchone()
            if row is None:
                return None
            token = uuid.uuid4().hex
            self.db.execute('UPDATE material_jobs SET status="processing",lease_until=?,attempts=attempts+1,lease_token=? WHERE material_id=?', (now + 120, token, row[0]))
            self.db.execute('UPDATE materials SET status="processing",error=NULL WHERE id=?', (row[0],))
        return {**self.get(row[1], row[0]), 'lease_token': token}

    def heartbeat(self, row):
        with self.lock, self.db:
            return self.db.execute('UPDATE material_jobs SET lease_until=? WHERE material_id=? AND lease_token=? AND status="processing"', (time.time() + 120, row["id"], row["lease_token"])).rowcount == 1

    def finish(self, row, passages=None, error=None):
        status = 'failed' if error else 'ready'
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            owner = self.db.execute('SELECT lease_token,status FROM material_jobs WHERE material_id=?', (row['id'],)).fetchone()
            if not owner or owner != (row['lease_token'], 'processing'):
                return False
            if passages is not None:
                self.db.execute('DELETE FROM document_passages WHERE material_id=?', (row['id'],))
                self.db.executemany('INSERT INTO document_passages VALUES (?,?,?,?,?)',
                                    [(f"{row['id']}-{i}", row['id'], page, section, text) for i, (page, section, text) in enumerate(passages)])
            self.db.execute('UPDATE materials SET status=?,error=? WHERE id=?', (status, error, row['id']))
            self.db.execute('UPDATE material_jobs SET status=?,lease_until=0 WHERE material_id=?', (status, row['id']))

    def passages(self, offering, id):
        self.get(offering, id)
        with self.lock:
            return [dict(id=r[0], page=r[1], section=r[2], text=r[3]) for r in self.db.execute(
                'SELECT id,page,section,text FROM document_passages WHERE material_id=? ORDER BY rowid', (id,))]

    def passage(self, offering, material, passage):
        row = self.get(offering, material)
        with self.lock:
            result = self.db.execute('SELECT id,page,section,text FROM document_passages WHERE material_id=? AND id=?',
                                     (material, passage)).fetchone()
        if not result:
            raise HTTPException(404, 'Source passage not found.')
        return dict(id=result[0], page=result[1], section=result[2], text=result[3], filename=row['filename'], version=row['version'])
