"""Upload, durable extraction, lecturer review, failure/retry and source isolation."""
import io
import zipfile
from pathlib import Path

from athena_api.materials.extract import extract
from athena_api.materials.store import Materials
from athena_api.materials.worker import process_one
from athena_api.spaces.service import StudySpaces
from .test_study_spaces import BODY, clients


def setup(tmp_path):
    spaces, _, owner, student = clients(tmp_path)
    id = owner.post('/offerings', json=BODY).json()['id']
    materials = Materials(spaces, tmp_path / 'materials')
    return spaces, materials, owner, student, id


def upload(client, id, name, content, replace=None):
    return client.post(f'/units/{id}/materials', params={'filename': name, **({'replace': replace} if replace else {})},
                       content=content, headers={'Content-Type': 'application/octet-stream'})


def test_text_upload_publication_attribution_and_source_scope(tmp_path):
    spaces, materials, owner, student, id = setup(tmp_path)
    base = f'/units/{id}/materials'
    result = upload(owner, id, '../../week 1.txt', b'Cross-validation estimates generalisation on held-out data.')
    assert result.status_code == 202
    material = result.json()
    assert material['filename'] == 'week 1.txt' and material['status'] == 'queued'
    assert 'storage_path' not in result.text
    assert owner.post(f"{base}/{material['id']}/publish").status_code == 409
    assert process_one(materials, None)
    passages = owner.get(f"{base}/{material['id']}/passages").json()
    assert passages[0]['section'] == 'Text' and 'held-out' in passages[0]['text']
    owner.post(f'/offerings/{id}/publish')
    assert student.get(base).json() == []
    assert student.get(f"{base}/{material['id']}/file").status_code == 404
    assert owner.post(f"{base}/{material['id']}/publish").status_code == 200
    assert student.get(base).json()[0]['id'] == material['id']
    assert student.get(f"{base}/{material['id']}/file").content.startswith(b'Cross-validation')
    assert student.post(f"{base}/{material['id']}/publish").status_code == 403
    other = owner.post('/offerings', json={**BODY, 'code': 'CSE5ALG', 'title': 'Algorithms'}).json()['id']
    owner.post(f'/offerings/{other}/publish')
    assert student.get(f"/units/{other}/materials/{material['id']}/passages").status_code == 404


def test_upload_validation_and_size_limits_leave_no_partial_material(tmp_path, monkeypatch):
    spaces, materials, owner, _, id = setup(tmp_path)
    monkeypatch.setenv('ATHENA_DOCUMENT_MAX_BYTES', '32')
    assert upload(owner, id, 'huge.txt', b'x' * 33).status_code == 413
    assert upload(owner, id, 'fake.pdf', b'not a PDF').status_code == 422
    assert upload(owner, id, 'macro.exe', b'executable').status_code == 415
    assert upload(owner, id, 'broken.docx', b'broken zip').status_code == 422
    assert upload(owner, id, 'fake.mp4', b'https://untrusted.test/media').status_code == 422
    assert materials.list(id, True) == []
    assert list(materials.root.glob('*')) == []


def test_durable_processing_reclaims_expired_jobs_and_fences_stale_workers(tmp_path):
    spaces, materials, owner, _, id = setup(tmp_path)
    material = upload(owner, id, 'topic.txt', b'A small course passage.').json()
    old = materials.claim()
    assert materials.claim() is None
    with spaces.lock, spaces.db:
        spaces.db.execute('UPDATE material_jobs SET lease_until=0')
    restarted = StudySpaces(tmp_path / 'host.db')
    recovered = Materials(restarted, materials.root)
    new = recovered.claim()
    assert new['id'] == material['id'] and new['lease_token'] != old['lease_token']
    assert not materials.heartbeat(old)
    assert materials.finish(old, error='stale result') is False
    recovered.finish(new, passages=[(3, 'Section A', 'Recovered passage.')])
    assert materials.get(id, material['id'])['status'] == 'ready'
    assert materials.passages(id, material['id'])[0]['page'] == 3
    restarted.close()


def office(kind, parts):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('word/document.xml' if kind == '.docx' else 'ppt/presentation.xml',
                         '<w:document xmlns:w="urn:w"><w:p><w:r><w:t>Overfitting</w:t></w:r></w:p></w:document>' if kind == '.docx' else '<presentation/>')
        for name, text in parts:
            archive.writestr(name, text)
    return stream.getvalue()


def test_docx_paragraphs_and_pptx_slide_numbers_are_real_locations(tmp_path):
    _, materials, owner, _, id = setup(tmp_path)
    doc = upload(owner, id, 'notes.docx', office('.docx', [])).json()
    process_one(materials, None)
    passage = materials.passages(id, doc['id'])[0]
    assert passage['page'] is None and passage['section'] == 'Paragraph 1' and passage['text'] == 'Overfitting'
    slide = lambda text: f'<a:sld xmlns:a="urn:a"><a:t>{text}</a:t></a:sld>'
    deck = upload(owner, id, 'slides.pptx', office('.pptx', [('ppt/slides/slide10.xml', slide('Tenth')), ('ppt/slides/slide2.xml', slide('Second'))])).json()
    process_one(materials, None)
    passages = materials.passages(id, deck['id'])
    assert [p['page'] for p in passages] == [2, 10]
    assert [p['text'] for p in passages] == ['Second', 'Tenth']


def pdf(text):
    contents = f'BT /F1 12 Tf 40 100 Td ({text}) Tj ET'.encode()
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               f'<< /Length {len(contents)} >>\nstream\n'.encode() + contents + b'\nendstream']
    data = b'%PDF-1.4\n'
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n'
    xref = len(data)
    data += b'xref\n0 6\n0000000000 65535 f \n' + b''.join(f'{o:010d} 00000 n \n'.encode() for o in offsets)
    return data + f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


def test_pdf_pages_and_scanned_pdf_failure_are_visible_and_retryable(tmp_path):
    _, materials, owner, _, id = setup(tmp_path)
    document = upload(owner, id, 'lecture.pdf', pdf('Cross validation')).json()
    process_one(materials, None)
    assert materials.passages(id, document['id'])[0]['page'] == 1
    scanned = upload(owner, id, 'scan.pdf', pdf('')).json()
    process_one(materials, None)
    failed = materials.get(id, scanned['id'])
    assert failed['status'] == 'failed' and 'OCR' in failed['error']
    result = owner.post(f"/units/{id}/materials/{scanned['id']}/retry")
    assert result.status_code == 202 and result.json()['status'] == 'queued'


def test_replacement_retains_immutable_original_passages(tmp_path):
    _, materials, owner, _, id = setup(tmp_path)
    first = upload(owner, id, 'notes.txt', b'Original source.').json()
    process_one(materials, None)
    second = upload(owner, id, 'notes.txt', b'Revised source.', replace=first['id']).json()
    process_one(materials, None)
    assert first['source_id'] == second['source_id'] and second['version'] == 2
    assert materials.passages(id, first['id'])[0]['text'] == 'Original source.'
    assert materials.passages(id, second['id'])[0]['text'] == 'Revised source.'


def test_recording_processing_produces_pending_clips_and_approved_playback(tmp_path):
    from athena_api.lectures.service import LectureService
    from athena_api.lectures.store import SqliteLectureStore
    spaces, materials, owner, student, id = setup(tmp_path)
    # Generated test container signature; fake indexer exercises durable integration without model calls.
    recording = upload(owner, id, 'lecture.wav', b'RIFF' + bytes(40)).json()
    lectures = LectureService(SqliteLectureStore(tmp_path / 'host.db'))
    def index(row, material_store, service):
        service.import_indexer_file(dict(recordingId=row['id'], offeringId=id, title='Lecture', durationS=30., status='ready',
            media=row['storage_path'], clips=[dict(id='clip', recordingId=row['id'], startS=0., endS=30., topicId='topic', topic='Topic',
            title='Validation', summary='Held-out evaluation.', transcript='Estimate generalisation on held-out observations.')]), base_dir=tmp_path)
    assert process_one(materials, lectures, recording_indexer=index)
    assert materials.get(id, recording['id'])['status'] == 'ready'
    assert lectures.for_students(id)[0].clips == []
    assert lectures.approved_material(id) == []
    owner.post(f'/offerings/{id}/publish')
    assert student.get(f'/units/{id}/lectures').json()[0]['clips'] == []
    assert owner.post(f"/units/{id}/lectures/{recording['id']}/clips/clip/status", json={'status': 'approved'}).status_code == 204
    assert len(student.get(f'/units/{id}/lectures').json()[0]['clips']) == 1
    assert len(lectures.for_students(id)[0].clips) == 1
    assert lectures.media(id, recording['id'], for_students=True).is_file()


def test_recording_worker_invokes_indexer_contract_with_real_local_media(tmp_path, monkeypatch):
    import sys
    import wave
    from athena_api.lectures.service import LectureService
    from athena_api.lectures.store import SqliteLectureStore
    spaces, materials, owner, _, id = setup(tmp_path)
    sound = io.BytesIO()
    with wave.open(sound, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(bytes(32000))
    recording = upload(owner, id, 'lecture.wav', sound.getvalue()).json()
    script = tmp_path / 'offline_indexer.py'
    script.write_text("""
import json, pathlib, sys
args = sys.argv[1:]
value = lambda key: args[args.index(key) + 1]
topics = json.loads(pathlib.Path(value('--topics')).read_text())['topics']
assert topics and set(topics[0]) == {'id', 'name'}
recording = value('--recording-id')
result = dict(recordingId=recording, offeringId=value('--offering'), title='Local test', durationS=1., status='ready', clips=[dict(id='test-clip', recordingId=recording, startS=0., endS=1., topicId=topics[0]['id'], topic=topics[0]['name'], title='Validation', summary='Evaluate held-out data.', transcript='Evaluate held-out data.')])
pathlib.Path(value('--out'), 'clips.json').write_text(json.dumps(result))
""")
    monkeypatch.setenv('ATHENA_INDEXER_COMMAND', f'{sys.executable} {script}')
    lectures = LectureService(SqliteLectureStore(tmp_path / 'host.db'))
    assert process_one(materials, lectures)
    assert materials.get(id, recording['id'])['status'] == 'ready'
    stored = lectures.store.get(id, recording['id'])
    assert stored.clips[0].status == 'pending'
    assert stored.clips[0].proposed.transcript == 'Evaluate held-out data.'
    assert Path(stored.media_path).read_bytes() == sound.getvalue()
