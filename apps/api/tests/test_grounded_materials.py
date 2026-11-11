"""Unified retrieval, immutable citations and explicit grounding failures."""
import asyncio
from datetime import UTC, datetime

import pytest

from athena_agent.conversation import InMemoryConversationStore, TopicContext
from athena_agent.contracts import RequestContext
from athena_agent.learning import LearningState
from athena_agent.retrieval import reference_for
from athena_agent.roadmap import Roadmap
from athena_api.lectures.service import LectureService
from athena_api.lectures.store import SqliteLectureStore
from athena_api.materials.worker import process_one
from athena_api.sessions.agent_tutor import AgentTutor
from athena_api.sessions.material import LectureMaterial, OfferingMaterial
from athena_api.sessions.models import LearningSession
from athena_api.sessions.operations import Operation
from athena_api.sessions.tutor import TutorError, TutorReply
from .test_material_lifecycle import setup, upload
from .test_material import lectures as fixture_lectures, OFF


def test_unified_retrieval_selects_only_published_offering_versions(tmp_path):
    _, materials, owner, _, id = setup(tmp_path)
    lectures = LectureService(SqliteLectureStore(tmp_path / 'host.db'))
    provider = OfferingMaterial(materials, lectures)
    first = upload(owner, id, 'validation.txt', b'Cross validation tests generalisation. Original.').json()
    process_one(materials, lectures)
    assert provider.for_goal(id, 'cross validation') == []
    owner.post(f"/units/{id}/materials/{first['id']}/publish")
    selected = provider.for_goal(id, 'cross validation')
    assert selected[0]['source_id'] == first['id'] and selected[0]['kind'] == 'document'
    replacement = upload(owner, id, 'validation.txt', b'Cross validation uses held-out data. Revised.', replace=first['id']).json()
    process_one(materials, lectures)
    assert provider.for_goal(id, 'cross validation')[0]['source_id'] == first['id']
    owner.post(f"/units/{id}/materials/{replacement['id']}/publish")
    selected = provider.for_goal(id, 'cross validation')
    assert [item['source_id'] for item in selected] == [replacement['id']]
    assert provider.for_goal('other-offering', 'cross validation') == []
    assert provider.for_goal(id, 'bubble sort') == []
    assert 'Original' in materials.passages(id, first['id'])[0]['text']


def test_comparison_retrieval_prefers_both_subjects_over_repetition():
    class Material:
        def list(self, offering, manager=False):
            return [dict(id='slides', source_id='slides', version=1, kind='document', status='ready',
                         published=True, filename='Lecture slides')]
        def passages(self, offering, id):
            return [dict(id='comparison', page=28, section=None,
                         text='Regression predicts numerical values; classification predicts discrete labels.'),
                    *[dict(id=f'repeated-{i}', page=i, section=None, text='Regression ' * 50) for i in range(8)]]
    from types import SimpleNamespace
    selected = OfferingMaterial(Material(), SimpleNamespace(approved_material=lambda _: [])).for_goal(
        'offering', 'What is the difference between regression and classification?')
    assert selected[0]['passage_id'] == 'comparison'
    assert len(selected) == 5


def test_cited_passages_resolve_original_version_with_scope_authorisation(tmp_path):
    _, materials, owner, student, id = setup(tmp_path)
    material = upload(owner, id, 'lecture.txt', b'Exact attributable passage.').json()
    process_one(materials, None)
    passage = materials.passages(id, material['id'])[0]
    owner.post(f'/offerings/{id}/publish')
    url = f"/units/{id}/materials/{material['id']}/passages/{passage['id']}"
    assert student.get(url).status_code == 404
    owner.post(f"/units/{id}/materials/{material['id']}/publish")
    source = student.get(url).json()
    assert source['text'] == 'Exact attributable passage.' and source['version'] == 1
    assert source['filename'] == 'lecture.txt' and 'storage_path' not in source
    assert student.get(url.replace(passage['id'], 'invented-passage')).status_code == 404


def test_video_and_document_ranking_keeps_approved_clips_and_bounds_context(tmp_path):
    _, materials, owner, _, id = setup(tmp_path)
    lectures = LectureService(SqliteLectureStore(tmp_path / 'host.db'))
    lectures.import_indexer_file(dict(recordingId='lecture', offeringId=id, title='Lecture', durationS=300., status='ready',
        clips=[dict(id='clip', recordingId='lecture', startS=0., endS=300., topicId='validation', topic='Validation',
                    title='Cross validation', summary='Generalisation', transcript='Cross validation generalisation. ' * 2000)]))
    material = upload(owner, id, 'notes.txt', b'Cross validation generalisation.').json()
    process_one(materials, lectures)
    owner.post(f"/units/{id}/materials/{material['id']}/publish")
    provider = OfferingMaterial(materials, lectures)
    assert {i['kind'] for i in provider.for_goal(id, 'cross validation')} == {'document'}
    lectures.approve_pending(id, 'lecture')
    selected = provider.for_goal(id, 'cross validation')
    assert {i['kind'] for i in selected} == {'document', 'video'}
    assert len(next(i for i in selected if i['kind'] == 'video')['transcript']) <= 6000


def test_conflicting_sources_never_retry_without_materials():
    calls = []
    class Rejecting:
        async def start(self, context, goal, *, materials=None, capabilities=None):
            calls.append(materials)
            error = RuntimeError('conflict')
            error.code = 'conflicting_sources'
            raise error
    tutor = AgentTutor(None, None, material=LectureMaterial(fixture_lectures()))
    tutor._orchestrator = lambda _session: Rejecting()
    now = datetime.now(UTC)
    session = LearningSession(id='s', student_id='student', offering_id=OFF, goal='insertion sort', title='Goal', created_at=now, updated_at=now)
    with pytest.raises(TutorError) as error:
        asyncio.run(tutor.start(session))
    assert error.value.status == 409 and error.value.code == 'conflicting_sources'
    assert 'conflict' in str(error.value)
    assert len(calls) == 1 and calls[0].items


def test_material_refresh_uses_current_concept_and_retries_preserve_original_evidence():
    context = RequestContext(request_id='test', learner_id='student', session_id='session')
    store = InMemoryConversationStore()
    snapshot = store.create(context)
    roadmap = Roadmap.model_validate(dict(goal='Machine learning', scope=dict(scope='narrow', rationale='A focused test'),
        graph=dict(partial_coverage=False, concepts=[dict(concept_id='overfit', title='Overfitting', description='Generalisation error',
                                                        objectives=['Compare training and validation'], difficulty='beginner')])))
    snapshot.active_topic = TopicContext(learning_state=LearningState(goal='Machine learning', current_concept_id='overfit'), roadmap=roadmap)
    store._save(context, snapshot)
    class Provider:
        version = 1
        queries = []
        def for_goal(self, offering, query):
            self.queries.append((offering, query))
            return [dict(kind='document', source_id=f'version-{self.version}', passage_id=f'passage-{self.version}',
                         title='Overfitting', text='Validation estimates generalisation.')]
    provider = Provider()
    class ReadingTutor(AgentTutor):
        async def message(self, session, text):
            knowledge = self.store.read(context).active_topic.knowledge
            item = knowledge.items[0]
            return [TutorReply('Consider held-out data.', sources=[reference_for(item, item.text).model_dump()], knowledge_origin='materials')]
    tutor = ReadingTutor(store, None, material=provider)
    now = datetime.now(UTC)
    session = LearningSession(id='session', student_id='student', offering_id='offering', goal='Machine learning', title='Learning', created_at=now, updated_at=now)
    first = Operation(id='message:one', kind='message', session=session, payload={'text': 'Explain validation.'})
    replies = asyncio.run(tutor.operation(first))
    assert provider.queries[0] == ('offering', 'Explain validation.')
    assert replies[0].sources[0]['source_id'] == 'version-1'
    provider.version = 2
    replay = asyncio.run(tutor.operation(first))
    assert replay[0].sources == replies[0].sources and len(provider.queries) == 1
    second = first.model_copy(update={'id': 'message:two'})
    assert asyncio.run(tutor.operation(second))[0].sources[0]['source_id'] == 'version-2'
