import asyncio

from athena_agent.learning import MultipleChoiceAnswer, TextAnswer
from .test_orchestrator import setup, one_concept_responses, OPEN, successful_reasoning


def test_progress_tracks_real_mastery_and_next_actions_without_private_data():
    context, store, _, orchestrator = setup([*one_concept_responses(), OPEN, successful_reasoning()])
    first = asyncio.run(orchestrator.start(context, 'Compare'))
    before = store.read(context)
    summary = orchestrator.progress(context)
    assert summary.mastered_count == 0 and summary.total_count == 1 and summary.next_step == 'answer'
    assert summary.concepts[0].status == 'unknown' and not summary.complete
    assert store.read(context) == before
    followup = asyncio.run(orchestrator.answer(context, MultipleChoiceAnswer(question_id=first.question.question_id, selected_choice_id='a')))
    summary = orchestrator.progress(context)
    assert summary.concepts[0].evidence_count == 1 and summary.mastered_count == 0
    asyncio.run(orchestrator.answer(context, TextAnswer(question_id=followup.question.question_id, text='Compare and swap neighbours.')))
    summary = orchestrator.progress(context)
    assert summary.complete and summary.next_step == 'complete'
    assert summary.mastered_count == 1 and summary.eligible_concept_ids == []
    for field in ['criteria', 'expected_reasoning', 'correct_choice_id', 'question_records', 'assessment_records']:
        assert field not in summary.model_dump_json()


def test_progress_after_gap_requests_continue():
    context, _, _, orchestrator = setup([*one_concept_responses(), {'misconceptions': [], 'prerequisite_gaps': []}, {'text': 'Compare neighbours.'}])
    question = asyncio.run(orchestrator.start(context, 'Compare'))
    asyncio.run(orchestrator.answer(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='b')))
    assert orchestrator.progress(context).next_step == 'continue'
