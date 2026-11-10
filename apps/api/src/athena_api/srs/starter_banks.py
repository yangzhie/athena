"""Hand-written starter banks for the PoC units.

Each item is one idea with 3-4 wordings. Data-driven wordings (different arrays,
keys, numbers) get their answers from `generators`. Variant ids are fixed
strings: cards remember wrong wordings by id, so reloading a bank must not
change them.
"""

import random

from . import generators as g
from .models import Bank, Item, McqVariant, NumericVariant, ShortVariant

ALG = "cse5alg-2026-s2"
DMI = "cse5dmi-2026-s2"


def _fmt(a: list[int]) -> str:
    return "[" + ", ".join(map(str, a)) + "]"


def _mcq(id: str, stem: str, correct: str, distractors: list[str], explanation: str) -> McqVariant:
    """Up to 4 options (the answer plus the first 3 distinct distractors), shuffled
    deterministically per variant id so reloads give the same order."""
    options = [correct] + [d for d in dict.fromkeys(distractors) if d != correct][:3]
    rng = random.Random(id)
    rng.shuffle(options)
    return McqVariant(id=id, stem=stem, options=options, answer_index=options.index(correct), explanation=explanation)


def _item(id, offering, topic, concept, difficulty, bloom, variants) -> Item:
    return Item(id=id, offering_id=offering, topic_id=topic, concept=concept,
                difficulty=difficulty, bloom=bloom, variants=variants)


# --- CSE5ALG -----------------------------------------------------------------------------


def _insertion_pass_variant(n: int, values: list[int], passes: int, framing: str) -> McqVariant:
    after, trace = g.insertion_sort_passes(values, passes)
    distractors = [
        _fmt(sorted(values)),  # fully sorted
        _fmt(g.insertion_sort_passes(values, passes + 1)[0]),  # one pass too many
        _fmt(g.insertion_sort_passes(values, max(1, passes - 1))[0]),  # one pass too few
        _fmt(values[1:2] + values[:1] + values[2:]),  # only swapped the first pair
    ]
    stems = {
        "direct": f"What is the array after {passes} pass{'es' if passes > 1 else ''} of insertion sort on {_fmt(values)}?",
        "trace": f"You run insertion sort on {_fmt(values)} and stop after the outer loop has run {passes} time{'s' if passes > 1 else ''}. What does the array look like?",
        "prefix": f"Insertion sort keeps a sorted prefix. Starting from {_fmt(values)}, what is the whole array once the first {passes + 1} elements are sorted?",
    }
    return _mcq(f"pass-{n}", stems[framing], _fmt(after), distractors, "Each pass inserts the next element into the sorted prefix: " + "; ".join(trace))


def _merge_variant(n: int, left: list[int], right: list[int], framing: str) -> NumericVariant:
    count, merged = g.merge_comparisons(left, right)
    stems = {
        "direct": f"How many comparisons does the merge step make when merging {_fmt(left)} and {_fmt(right)}?",
        "scenario": f"Merge sort is combining the sorted halves {_fmt(left)} and {_fmt(right)}. How many element comparisons happen before one half runs out?",
        "count": f"Count the comparisons the standard merge makes on {_fmt(left)} + {_fmt(right)}.",
    }
    return NumericVariant(
        id=f"merge-{n}", stem=stems[framing], answer=float(count),
        explanation=f"Compare the two fronts until one list is empty ({count} comparisons), then copy the rest: {_fmt(merged)}.",
    )


def _binary_variant(n: int, values: list[int], target: int, framing: str) -> NumericVariant:
    count, probed = g.binary_search_probes(values, target)
    stems = {
        "direct": f"Binary search (mid = (lo + hi) // 2) looks for {target} in {_fmt(values)}. How many elements does it inspect?",
        "scenario": f"A sorted array holds {_fmt(values)}. Searching for {target} with binary search, how many probes until it's found?",
        "trace": f"How many middle elements are checked when binary search finds {target} in {_fmt(values)}?",
    }
    return NumericVariant(id=f"bs-{n}", stem=stems[framing], answer=float(count),
                          explanation=f"It inspects {', '.join(map(str, probed))}: {count} probes.")


def _radix_variant(n: int, values: list[int], framing: str) -> McqVariant:
    after = g.radix_pass(values, 0)
    distractors = [_fmt(sorted(values)), _fmt(g.radix_pass(values, 1)), _fmt(sorted(values, key=lambda v: -(v % 10)))]
    stems = {
        "direct": f"After the first pass of LSD radix sort (by the ones digit) on {_fmt(values)}, what is the array?",
        "stable": f"Radix sort starts with the least significant digit and must be stable. What does {_fmt(values)} become after that first pass?",
        "digit": f"Sort {_fmt(values)} stably by the last digit only. What is the result?",
    }
    return _mcq(f"radix-{n}", stems[framing], _fmt(after), distractors,
                f"Group by ones digit, keeping the original order for ties (stable): {_fmt(after)}.")


def _probe_variant(n: int, existing: list[int], key: int, size: int, framing: str) -> NumericVariant:
    slot, tried = g.linear_probe_slot(existing, key, size)
    stems = {
        "direct": f"A hash table of size {size} uses h(k) = k mod {size} and linear probing. After inserting {_fmt(existing)}, which slot does {key} go in?",
        "scenario": f"Keys {_fmt(existing)} are already in a size-{size} table (h(k) = k mod {size}, linear probing). Where does {key} end up?",
        "trace": f"With h(k) = k mod {size} and linear probing, insert {_fmt(existing)} then {key}. Give {key}'s slot index.",
    }
    return NumericVariant(id=f"probe-{n}", stem=stems[framing], answer=float(slot),
                          explanation=f"{key} mod {size} = {tried[0]}; slots tried: {', '.join(map(str, tried))}.")


def cse5alg_bank() -> Bank:
    items = [
        _item("insertion-worst-case", ALG, "insertion-sort",
              "Insertion sort takes O(n²) time in the worst case (reverse-sorted input).", 1, "recall", [
                  _mcq("wc-1", "What is the worst-case time complexity of insertion sort?", "O(n²)", ["O(n)", "O(n log n)", "O(log n)"],
                       "On reversed input every element shifts past all earlier ones: 1 + 2 + … + (n−1) = O(n²)."),
                  _mcq("wc-2", "Insertion sort is given n numbers in descending order. How does its running time grow?", "Quadratically, O(n²)",
                       ["Linearly, O(n)", "As O(n log n)", "Logarithmically"],
                       "Descending input is the worst case: each new element moves to the front."),
                  _mcq("wc-3", "Which input makes insertion sort do the most work?", "A reverse-sorted array",
                       ["An already sorted array", "An array of identical values", "A random array"],
                       "Reverse order maximises shifts; sorted input is the best case, O(n)."),
              ]),
        _item("insertion-best-case", ALG, "insertion-sort",
              "Insertion sort runs in O(n) on already sorted input.", 2, "recall", [
                  _mcq("bc-1", "What is insertion sort's running time on an array that is already sorted?", "O(n)", ["O(1)", "O(n log n)", "O(n²)"],
                       "Each element is compared once with its left neighbour and stays put."),
                  _mcq("bc-2", "Why is insertion sort a good choice for nearly sorted data?", "Few elements need to move, so it's close to linear time",
                       ["It always runs in O(n log n)", "It uses no comparisons", "It skips the first half of the array"],
                       "Work is proportional to n plus the number of inversions."),
                  _mcq("bc-3", "Insertion sort on [1, 2, 3, …, n] makes about how many comparisons?", "n − 1", ["n²/2", "log₂ n", "n log₂ n"],
                       "One comparison per element from the second onward."),
              ]),
        _item("insertion-pass", ALG, "insertion-sort",
              "Each insertion sort pass inserts the next element into the sorted prefix.", 2, "apply", [
                  _insertion_pass_variant(1, [5, 2, 4, 6, 1, 3], 2, "direct"),
                  _insertion_pass_variant(2, [7, 3, 9, 1, 8], 3, "trace"),
                  _insertion_pass_variant(3, [4, 8, 2, 6, 5], 2, "prefix"),
              ]),
        _item("insertion-stable", ALG, "insertion-sort",
              "Insertion sort is stable: equal keys keep their original order.", 3, "analyse", [
                  ShortVariant(id="st-1", stem="Is insertion sort stable? Explain why in one or two sentences.",
                               model_answer="Yes. It only shifts elements that are strictly greater than the key, so equal elements never pass each other.",
                               rubric=["says it is stable", "only strictly greater elements are shifted / equal keys don't swap"],
                               explanation="Stability comes from using > (not ≥) when shifting."),
                  ShortVariant(id="st-2", stem="Two records have the same key. After insertion sort, could their order be reversed? Why or why not?",
                               model_answer="No. Insertion sort stops shifting at an equal element, so the later record stays after the earlier one.",
                               rubric=["says the order is preserved", "shifting stops at equal keys"],
                               explanation="The inner loop condition a[j] > key stops at equal keys."),
                  _mcq("st-3", "Which change would make insertion sort unstable?", "Shifting while a[j] ≥ key instead of a[j] > key",
                       ["Starting the outer loop at index 1", "Using a while loop instead of a for loop", "Sorting in descending order with >"],
                       "With ≥, equal elements get moved past each other."),
              ]),
        _item("merge-sort-complexity", ALG, "merge-sort",
              "Merge sort runs in O(n log n) in every case: T(n) = 2T(n/2) + O(n).", 2, "recall", [
                  _mcq("ms-1", "What is merge sort's worst-case time complexity?", "O(n log n)", ["O(n)", "O(n²)", "O(log n)"],
                       "log n levels of recursion, each doing O(n) merging work."),
                  _mcq("ms-2", "Which recurrence describes merge sort?", "T(n) = 2T(n/2) + O(n)", ["T(n) = T(n−1) + O(n)", "T(n) = 2T(n/2) + O(1)", "T(n) = T(n/2) + O(1)"],
                       "Two half-size subproblems plus a linear merge."),
                  _mcq("ms-3", "Unlike insertion sort, how does merge sort's running time change on already sorted input?", "It stays O(n log n)",
                       ["It drops to O(n)", "It rises to O(n²)", "It drops to O(log n)"],
                       "Merge sort always splits and merges fully, whatever the input order."),
              ]),
        _item("merge-comparisons", ALG, "merge-sort",
              "The merge step compares the fronts of two sorted lists until one runs out.", 3, "apply", [
                  _merge_variant(1, [1, 4, 9], [2, 3, 10], "direct"),
                  _merge_variant(2, [2, 5, 6, 8], [1, 3, 4], "scenario"),
                  _merge_variant(3, [1, 2, 3], [7, 8, 9], "count"),
              ]),
        _item("binary-search-probes", ALG, "complexity-search",
              "Binary search halves the search range each step, so it needs O(log n) probes.", 2, "apply", [
                  _binary_variant(1, [3, 8, 12, 17, 21, 25, 30], 25, "direct"),
                  _binary_variant(2, [2, 4, 7, 9, 11, 14, 19, 23, 28], 4, "scenario"),
                  _binary_variant(3, [1, 5, 9, 13, 17, 21, 25, 29], 29, "trace"),
              ]),
        _item("radix-first-pass", ALG, "radix-sort",
              "LSD radix sort sorts stably by the least significant digit first.", 3, "apply", [
                  _radix_variant(1, [170, 45, 75, 90, 802, 24, 2, 66], "direct"),
                  _radix_variant(2, [33, 21, 54, 13, 40, 22], "stable"),
                  _radix_variant(3, [128, 305, 91, 16, 54, 77], "digit"),
              ]),
        _item("linear-probing", ALG, "hash-tables",
              "Linear probing places a key in the next free slot after its hash position.", 3, "apply", [
                  _probe_variant(1, [12, 22, 32], 42, 10, "direct"),
                  _probe_variant(2, [7, 14, 21], 28, 7, "scenario"),
                  _probe_variant(3, [5, 16, 27], 38, 11, "trace"),
              ]),
        _item("heap-parent", ALG, "heaps",
              "In a 0-based array heap, the parent of index i is (i − 1) // 2.", 2, "apply", [
                  NumericVariant(id="hp-1", stem="In a binary heap stored in a 0-based array, what is the index of the parent of index 9?",
                                 answer=float(g.heap_parent(9)), explanation="(9 − 1) // 2 = 4."),
                  NumericVariant(id="hp-2", stem="A min-heap is stored in an array starting at index 0. Node at index 14: where is its parent?",
                                 answer=float(g.heap_parent(14)), explanation="(14 − 1) // 2 = 6."),
                  NumericVariant(id="hp-3", stem="Sift-up moves the item at index 6 of a 0-based heap array to its parent. Which index is that?",
                                 answer=float(g.heap_parent(6)), explanation="(6 − 1) // 2 = 2."),
              ]),
    ]
    return Bank(offering_id=ALG, items=items)


# --- CSE5DMI -------------------------------------------------------------------------------


def _folds_variant(n: int, rows: int, k: int, framing: str) -> NumericVariant:
    per = g.rows_per_fold(rows, k)
    stems = {
        "direct": f"With {k}-fold cross-validation on {rows} rows, how many rows are in each validation fold?",
        "scenario": f"You split a {rows}-row dataset for {k}-fold cross-validation. How many rows does each model get to validate on?",
        "train": f"In {k}-fold cross-validation over {rows} rows, each fold holds out how many rows?",
    }
    return NumericVariant(id=f"folds-{n}", stem=stems[framing], answer=per, tolerance=0.5,
                          explanation=f"{rows} / {k} = {per:g} rows per fold.")


def _precision_variant(n: int, tp: int, fp: int, framing: str) -> NumericVariant:
    p = g.precision(tp, fp)
    stems = {
        "direct": f"A classifier makes {tp} true positives and {fp} false positives. What is its precision (0–1)?",
        "scenario": f"A spam filter flags {tp + fp} emails; {tp} really are spam. What is its precision (0–1)?",
        "formula": f"Compute TP / (TP + FP) for TP = {tp}, FP = {fp}, to two decimal places.",
    }
    return NumericVariant(id=f"prec-{n}", stem=stems[framing], answer=round(p, 4), tolerance=0.01,
                          explanation=f"{tp} / ({tp} + {fp}) = {p:.2f}.")


def cse5dmi_bank() -> Bank:
    items = [
        _item("overfitting", DMI, "overfitting",
              "Overfitting: a model fits noise in the training data and generalises poorly.", 1, "recall", [
                  _mcq("of-1", "A model scores 99% on training data and 62% on test data. What is most likely happening?", "Overfitting",
                       ["Underfitting", "Data leakage into training", "A balanced fit"], "A large train–test gap is the classic sign of overfitting."),
                  _mcq("of-2", "What does it mean when a model overfits?", "It has learned noise in the training set and generalises poorly",
                       ["It is too simple to capture the pattern", "It trains too slowly", "It uses too little memory"],
                       "Overfitting = memorising training specifics rather than the underlying pattern."),
                  _mcq("of-3", "Which of these usually reduces overfitting?", "Regularisation or a simpler model",
                       ["Training for many more epochs", "Adding more features without more data", "Evaluating on the training set"],
                       "Constraining model complexity (or more data) helps it generalise."),
              ]),
        _item("fold-size", DMI, "cross-validation",
              "In k-fold cross-validation each fold holds 1/k of the data for validation.", 2, "apply", [
                  _folds_variant(1, 1000, 5, "direct"),
                  _folds_variant(2, 600, 10, "scenario"),
                  _folds_variant(3, 1200, 4, "train"),
              ]),
        _item("cv-purpose", DMI, "cross-validation",
              "Cross-validation estimates generalisation by validating on every part of the data once.", 2, "recall", [
                  _mcq("cv-1", "Why use k-fold cross-validation instead of a single train/test split?", "Every row is used for validation once, giving a more reliable estimate",
                       ["It trains a model with no validation data", "It makes training faster", "It removes the need for a test set entirely"],
                       "Averaging k validation scores reduces the luck of one split."),
                  _mcq("cv-2", "In k-fold cross-validation, how many times is each row used for validation?", "Exactly once", ["k times", "Never", "k − 1 times"],
                       "Each fold is held out once, and each row is in exactly one fold."),
                  _mcq("cv-3", "What do you report after k-fold cross-validation?", "The average (and spread) of the k validation scores",
                       ["The best of the k scores", "The training accuracy", "The score of the last fold"],
                       "The mean over folds estimates generalisation; the spread shows its stability."),
              ]),
        _item("kmeans-steps", DMI, "k-means",
              "k-means alternates: assign points to the nearest centroid, then move centroids to their points' mean.", 2, "recall", [
                  _mcq("km-1", "What happens in the assignment step of k-means?", "Each point joins its nearest centroid's cluster",
                       ["Centroids move to the mean of their points", "Points far from all centroids are removed", "k is increased by one"],
                       "Assignment, then update, repeated until assignments stop changing."),
                  _mcq("km-2", "After assigning points, how does k-means update each centroid?", "To the mean of the points assigned to it",
                       ["To the point farthest from it", "To a random data point", "It stays fixed"], "The update step moves centroids to cluster means."),
                  _mcq("km-3", "When does k-means stop?", "When assignments (and so centroids) stop changing",
                       ["After exactly k iterations", "When every cluster has the same size", "When one centroid remains"],
                       "Convergence: no point changes cluster, so centroids don't move."),
              ]),
        _item("precision", DMI, "evaluation",
              "Precision = TP / (TP + FP): the share of predicted positives that are correct.", 2, "apply", [
                  _precision_variant(1, 40, 10, "direct"),
                  _precision_variant(2, 45, 15, "scenario"),
                  _precision_variant(3, 18, 6, "formula"),
              ]),
    ]
    return Bank(offering_id=DMI, items=items)


def starter_banks() -> list[Bank]:
    return [cse5alg_bank(), cse5dmi_bank()]
