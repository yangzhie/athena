import type { Offering } from '../types'

/**
 * Offerings the signed-in student is enrolled in. Hardcoded for the PoC;
 * in the real app these are the spaces a lecturer added the student to.
 */
export const enrolledOfferings: Offering[] = [
  {
    id: 'cse5dmi-2026-s2',
    unit: { code: 'CSE5DMI', title: 'Data Mining' },
    year: 2026,
    semester: 'Semester 2',
    suggestions: [
      'Explain k-fold cross-validation',
      'How do I know if my model is overfitting?',
      'Quiz me on clustering',
    ],
  },
  {
    id: 'cse5alg-2026-s2',
    unit: { code: 'CSE5ALG', title: 'Data Structures and Algorithms' },
    year: 2026,
    semester: 'Semester 2',
    suggestions: [
      'Why is bubble sort O(n²)?',
      'When should I use a hash map over a tree?',
      'Quiz me on Big-O notation',
    ],
  },
]
