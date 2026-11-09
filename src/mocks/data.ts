import type { ChatMessage, Concept, LectureClip, Mastery, Material, QuizItem, ReviewState, Topic } from '../types'

export const concepts: Concept[] = [
  { id: 'arrays', name: 'Arrays', prerequisiteIds: [] },
  { id: 'loops', name: 'Loops', prerequisiteIds: [] },
  { id: 'big-o', name: 'Big-O notation', prerequisiteIds: ['loops'] },
  { id: 'bubble-sort', name: 'Bubble sort', prerequisiteIds: ['arrays', 'loops'] },
  { id: 'probability', name: 'Probability basics', prerequisiteIds: [] },
  { id: 'linear-regression', name: 'Linear regression', prerequisiteIds: ['probability'] },
  { id: 'overfitting', name: 'Overfitting', prerequisiteIds: ['linear-regression'] },
  { id: 'cross-validation', name: 'k-fold cross-validation', prerequisiteIds: ['overfitting'] },
]

export const topics: Topic[] = [
  {
    id: 'bubble-sort',
    title: 'Bubble sort',
    description: 'How bubble sort works, why it is O(n²), and when it stops early.',
    scope: 'small',
    conceptIds: ['arrays', 'loops', 'big-o', 'bubble-sort'],
    materialIds: [],
    lastStudiedAt: '2026-11-08T10:00:00Z',
  },
  {
    id: 'machine-learning',
    title: 'Machine learning',
    description: 'From regression to model evaluation, guided by what you already know.',
    scope: 'broad',
    conceptIds: ['probability', 'linear-regression', 'overfitting', 'cross-validation'],
    materialIds: ['ml-slides', 'ml-lecture-3'],
    lastStudiedAt: '2026-11-07T15:30:00Z',
  },
]

export const mastery: Mastery[] = [
  { conceptId: 'arrays', estimate: 0.92, uncertainty: 0.1, evidenceCount: 12, updatedAt: '2026-11-08T10:00:00Z' },
  { conceptId: 'loops', estimate: 0.85, uncertainty: 0.15, evidenceCount: 9, updatedAt: '2026-11-08T10:00:00Z' },
  { conceptId: 'big-o', estimate: 0.48, uncertainty: 0.35, evidenceCount: 4, updatedAt: '2026-11-08T10:00:00Z' },
  { conceptId: 'bubble-sort', estimate: 0.7, uncertainty: 0.25, evidenceCount: 6, updatedAt: '2026-11-08T10:00:00Z' },
  { conceptId: 'probability', estimate: 0.62, uncertainty: 0.3, evidenceCount: 5, updatedAt: '2026-11-07T15:30:00Z' },
  { conceptId: 'linear-regression', estimate: 0.35, uncertainty: 0.4, evidenceCount: 3, updatedAt: '2026-11-07T15:30:00Z' },
  { conceptId: 'overfitting', estimate: 0.15, uncertainty: 0.6, evidenceCount: 1, updatedAt: '2026-11-07T15:30:00Z' },
]

export const quizItems: QuizItem[] = [
  {
    id: 'q1',
    topicId: 'bubble-sort',
    conceptIds: ['bubble-sort'],
    format: 'mcq',
    stem: 'After the first full pass of bubble sort on [5, 1, 4, 2], which element is guaranteed to be in its final position?',
    options: ['1', '2', '4', '5'],
    answer: 3,
    difficulty: 2,
    bloom: 'apply',
  },
  {
    id: 'q2',
    topicId: 'bubble-sort',
    conceptIds: ['big-o'],
    format: 'mcq',
    stem: 'What is the worst-case time complexity of bubble sort?',
    options: ['O(n)', 'O(n log n)', 'O(n²)', 'O(2ⁿ)'],
    answer: 2,
    difficulty: 1,
    bloom: 'recall',
  },
  {
    id: 'q3',
    topicId: 'machine-learning',
    conceptIds: ['cross-validation'],
    format: 'numeric',
    stem: 'With 5-fold cross-validation on 1,000 samples, how many samples are in each validation fold?',
    answer: 200,
    difficulty: 2,
    bloom: 'apply',
  },
  {
    id: 'q4',
    topicId: 'machine-learning',
    conceptIds: ['overfitting'],
    format: 'short',
    stem: 'Your model scores 99% on training data and 62% on test data. What is likely happening, and name one fix.',
    answer: 'Overfitting. Fixes: more data, regularisation, simpler model, early stopping, or cross-validation for tuning.',
    difficulty: 3,
    bloom: 'analyse',
  },
]

/** ISO date offset from now, so "due today" works whenever the mock is loaded. */
const daysFromNow = (days: number) => new Date(Date.now() + days * 86_400_000).toISOString()

export const reviewStates: ReviewState[] = [
  { itemId: 'q1', dueAt: daysFromNow(-1), stability: 2.1, difficulty: 4.2 },
  { itemId: 'q2', dueAt: daysFromNow(3), stability: 6.5, difficulty: 2.8 },
  { itemId: 'q3', dueAt: daysFromNow(-0.5), stability: 1.2, difficulty: 5.1 },
  { itemId: 'q4', dueAt: daysFromNow(-2), stability: 0.8, difficulty: 6.0 },
]

export const materials: Material[] = [
  {
    id: 'ml-slides',
    title: 'Intro to ML — lecture slides.pdf',
    kind: 'slides',
    status: 'ready',
    uploadedAt: '2026-11-05T12:00:00Z',
    topicIds: ['machine-learning'],
  },
  {
    id: 'ml-lecture-3',
    title: 'Lecture 3 — Model evaluation.mp4',
    kind: 'recording',
    status: 'ready',
    uploadedAt: '2026-11-06T12:00:00Z',
    topicIds: ['machine-learning'],
  },
  {
    id: 'algo-textbook',
    title: 'Algorithms textbook ch. 2.pdf',
    kind: 'pdf',
    status: 'processing',
    uploadedAt: '2026-11-09T08:00:00Z',
    topicIds: [],
  },
]

export const lectureClips: LectureClip[] = [
  {
    id: 'clip1',
    materialId: 'ml-lecture-3',
    topicId: 'machine-learning',
    title: 'Why training accuracy lies',
    summary: 'Overfitting explained with a polynomial fit example.',
    startS: 312,
    endS: 545,
  },
  {
    id: 'clip2',
    materialId: 'ml-lecture-3',
    topicId: 'machine-learning',
    title: 'k-fold cross-validation walkthrough',
    summary: 'Splitting data into k folds and averaging the scores.',
    startS: 1210,
    endS: 1580,
  },
]

export const sampleSession: ChatMessage[] = [
  {
    id: 'm1',
    role: 'tutor',
    content: 'Before we start: if a model does great on training data but poorly on new data, what do you think went wrong?',
    createdAt: '2026-11-09T10:00:00Z',
  },
  {
    id: 'm2',
    role: 'learner',
    content: 'It memorised the training data?',
    createdAt: '2026-11-09T10:00:30Z',
  },
  {
    id: 'm3',
    role: 'tutor',
    content: 'Exactly — that is overfitting. The model learned noise, not the pattern. Let’s see how k-fold cross-validation catches it.',
    citations: [{ materialId: 'ml-lecture-3', label: '05:12' }, { materialId: 'ml-slides', label: 'Slide 14' }],
    createdAt: '2026-11-09T10:00:45Z',
  },
]
