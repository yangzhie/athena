import type { LectureClip, LectureRecording } from '../types'

const clip = (recordingId: string, id: string, startS: number, endS: number, topic: string, title: string, summary: string): LectureClip =>
  ({ id: `${recordingId}-${id}`, recordingId, startS, endS, topic, title, summary })

/** m:ss → seconds, to keep the mock readable. */
const t = (mmss: string) => {
  const [m, s] = mmss.split(':').map(Number)
  return m * 60 + s
}

export const lectureRecordings: LectureRecording[] = [
  // CSE5DMI Data Mining
  {
    id: 'dmi-w3',
    offeringId: 'cse5dmi-2026-s2',
    title: 'Model evaluation',
    week: 3,
    durationS: t('52:10'),
    status: 'ready',
    clips: [
      clip('dmi-w3', 'a', t('5:12'), t('9:05'), 'Overfitting', 'Why training accuracy lies', 'A polynomial fit that scores perfectly on training data and badly on new data.'),
      clip('dmi-w3', 'b', t('20:10'), t('26:20'), 'Cross-validation', 'k-fold cross-validation walkthrough', 'Splitting data into k folds, training k times and averaging the scores.'),
      clip('dmi-w3', 'c', t('26:20'), t('31:45'), 'Cross-validation', 'Choosing k', 'Trade-offs between 5, 10 and leave-one-out.'),
    ],
  },
  {
    id: 'dmi-w5',
    offeringId: 'cse5dmi-2026-s2',
    title: 'Clustering',
    week: 5,
    durationS: t('48:30'),
    status: 'ready',
    clips: [
      clip('dmi-w5', 'a', t('3:30'), t('14:10'), 'k-means', 'k-means step by step', 'Assign points to the nearest centroid, move centroids, repeat until stable.'),
      clip('dmi-w5', 'b', t('14:10'), t('21:00'), 'k-means', 'Picking the number of clusters', 'The elbow method and silhouette scores.'),
      clip('dmi-w5', 'c', t('25:40'), t('38:05'), 'Density-based clustering', 'DBSCAN and density', 'Finding clusters of any shape, and what counts as noise.'),
    ],
  },
  {
    id: 'dmi-w6',
    offeringId: 'cse5dmi-2026-s2',
    title: 'Association rules',
    week: 6,
    durationS: t('50:00'),
    status: 'processing',
    clips: [],
  },

  // CSE5ALG Data Structures and Algorithms
  {
    id: 'alg-w2',
    offeringId: 'cse5alg-2026-s2',
    title: 'Sorting basics',
    week: 2,
    durationS: t('45:20'),
    status: 'ready',
    clips: [
      clip('alg-w2', 'a', t('2:15'), t('10:40'), 'Bubble sort', 'Bubble sort, pass by pass', 'Adjacent swaps push the largest value to the end on each pass.'),
      clip('alg-w2', 'b', t('10:40'), t('16:30'), 'Big-O notation', 'Why bubble sort is O(n²)', 'Counting comparisons across nested passes.'),
      clip('alg-w2', 'c', t('16:30'), t('19:10'), 'Bubble sort', 'Stopping early when sorted', 'A pass with no swaps means the array is already sorted.'),
    ],
  },
  {
    id: 'alg-w4',
    offeringId: 'cse5alg-2026-s2',
    title: 'Hash tables',
    week: 4,
    durationS: t('51:05'),
    status: 'ready',
    // Pending lecturer review, to demo the review screen.
    clips: [
      clip('alg-w4', 'a', t('4:00'), t('15:20'), 'Hashing', 'Hashing and collisions', 'Hash functions, buckets, chaining and open addressing.'),
      clip('alg-w4', 'b', t('15:20'), t('24:00'), 'Hashing', 'Hash map vs balanced tree', 'O(1) average lookups against ordered keys and O(log n) guarantees.'),
    ].map((c) => ({ ...c, approved: false })),
  },
]
