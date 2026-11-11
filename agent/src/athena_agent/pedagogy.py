"""Shared tutoring instructions: meaningful evidence rather than vocabulary drills."""

QUESTION_DESIGN = '''Design a short learning opportunity for a university student.
Test the requested concept itself, not a trivial prerequisite or a phrase copied
from the scenario. A beginner question can be accessible and still require thought.
Prefer choosing between approaches, predicting a consequence, explaining a boundary
case, interpreting a result, or correcting a plausible misconception. One question,
one reasoning target; avoid unrelated multi-part chores. Use realistic but brief
scenarios. Do not put the answer in the question or require specialist background
unrelated to the learning objective.

Example of a weak question for regression versus classification:
"A model predicts rent. What does it predict?" This only tests reading the prompt.
A better diagnostic asks which task changes when the same outcome is represented
as a numerical amount versus a category, with plausible reasons as the choices.
A better follow-up asks why an integer-valued label is not necessarily regression,
or how binning a numerical target changes the modelling task. Use these as design
patterns, not a script to repeat for other subjects.

Multiple-choice distractors must represent distinct, plausible misconceptions,
not obviously irrelevant statements. Avoid yes/no, copied nouns, and giveaway
options that are much longer or more precise than the others.
For an open answer, ask for a brief explanation or application, and put observable
reasoning requirements in the private rubric. Credit sound reasoning in different
words. After a correct answer, increase the demand or use a genuinely different
case; do not ask the same identification question with rent changed to a loan.
After difficulty, scaffold the specific gap with a smaller step, not more jargon.
Use recent questions and recorded evidence to avoid repetition. Do not assume
mastery from a click or inflate proficiency without independent reasoning.'''
