"""Algorithms that compute answers for data-driven question variants.

Variants that change the input (a different array, different keys) get their
answers from these functions, never from a person or an LLM. Each also returns
a short trace used as the explanation.
"""


def insertion_sort_passes(values: list[int], passes: int) -> tuple[list[int], list[str]]:
    """The array after `passes` outer-loop passes of insertion sort (pass 1 inserts element 1)."""
    a = list(values)
    trace = []
    for i in range(1, min(passes, len(a) - 1) + 1):
        key, j = a[i], i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
        trace.append(f"pass {i}: insert {key} → {a}")
    return a, trace


def merge_comparisons(left: list[int], right: list[int]) -> tuple[int, list[int]]:
    """Comparisons made when merging two sorted lists (the standard merge), and the result."""
    i = j = comparisons = 0
    out = []
    while i < len(left) and j < len(right):
        comparisons += 1
        if left[i] <= right[j]:
            out.append(left[i])
            i += 1
        else:
            out.append(right[j])
            j += 1
    out += left[i:] + right[j:]
    return comparisons, out


def binary_search_probes(values: list[int], target: int) -> tuple[int, list[int]]:
    """How many elements binary search inspects to find `target` (mid = (lo + hi) // 2)."""
    lo, hi = 0, len(values) - 1
    probed = []
    while lo <= hi:
        mid = (lo + hi) // 2
        probed.append(values[mid])
        if values[mid] == target:
            return len(probed), probed
        if values[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return len(probed), probed


def radix_pass(values: list[int], digit: int = 0) -> list[int]:
    """One stable LSD radix sort pass on the given decimal digit (0 = ones)."""
    return sorted(values, key=lambda v: (v // 10**digit) % 10)  # sorted() is stable


def linear_probe_slot(existing: list[int], key: int, size: int) -> tuple[int, list[int]]:
    """Slot `key` lands in after inserting `existing` (in order) with h(k) = k mod size and linear probing."""
    table: list[int | None] = [None] * size

    def insert(k: int) -> tuple[int, list[int]]:
        slot = k % size
        tried = [slot]
        while table[slot] is not None:
            slot = (slot + 1) % size
            tried.append(slot)
        table[slot] = k
        return slot, tried

    for k in existing:
        insert(k)
    return insert(key)


def heap_parent(index: int) -> int:
    """Parent of `index` in a 0-based array heap."""
    return (index - 1) // 2


def rows_per_fold(rows: int, k: int) -> float:
    return rows / k


def precision(tp: int, fp: int) -> float:
    return tp / (tp + fp)
