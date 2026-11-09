import type { DocumentReference } from '../types'

type MockPassage = Omit<DocumentReference, 'kind'> & { offeringId: string; keywords: string[] }

/** A few slide passages per offering, so the mock tutor can cite documents. */
export const documentPassages: MockPassage[] = [
  {
    offeringId: 'cse5dmi-2026-s2',
    sourceId: 'dmi-slides-w3',
    passageId: 'dmi-slides-w3-p14',
    title: 'Week 3 slides: Model evaluation',
    page: 14,
    section: 'k-fold cross-validation',
    quote: 'Split the data into k folds. Train on k−1 folds, validate on the remaining fold, repeat k times and average the k scores.',
    keywords: ['cross', 'validation', 'k-fold', 'fold', 'folds'],
  },
  {
    offeringId: 'cse5dmi-2026-s2',
    sourceId: 'dmi-slides-w3',
    passageId: 'dmi-slides-w3-p9',
    title: 'Week 3 slides: Model evaluation',
    page: 9,
    section: 'Overfitting',
    quote: 'A model that fits noise in the training set will score well on training data but generalise poorly to unseen data.',
    keywords: ['overfitting', 'overfit', 'generalise', 'training'],
  },
  {
    offeringId: 'cse5dmi-2026-s2',
    sourceId: 'dmi-slides-w5',
    passageId: 'dmi-slides-w5-p6',
    title: 'Week 5 slides: Clustering',
    page: 6,
    section: 'k-means',
    quote: 'Repeat until assignments stop changing: assign each point to its nearest centroid, then move each centroid to the mean of its points.',
    keywords: ['clustering', 'cluster', 'clusters', 'k-means', 'kmeans', 'centroid'],
  },
  {
    offeringId: 'cse5alg-2026-s2',
    sourceId: 'alg-slides-w2',
    passageId: 'alg-slides-w2-p11',
    title: 'Week 2 slides: Sorting basics',
    page: 11,
    section: 'Bubble sort complexity',
    quote: 'In the worst case bubble sort makes n−1 passes with up to n−1 comparisons each, giving O(n²) comparisons.',
    keywords: ['bubble', 'sort', 'o(n²)', 'complexity', 'big-o', 'passes'],
  },
  {
    offeringId: 'cse5alg-2026-s2',
    sourceId: 'alg-slides-w4',
    passageId: 'alg-slides-w4-p8',
    title: 'Week 4 slides: Hash tables',
    page: 8,
    section: 'Hash map vs tree',
    quote: 'Hash maps give O(1) average lookups but no ordering; balanced trees give O(log n) lookups and keep keys sorted.',
    keywords: ['hash', 'map', 'tree', 'hashing', 'lookup'],
  },
]
