import json

from athena_api.srs import generators as g
from athena_api.srs.cli import main
from athena_api.srs.models import Bank, McqVariant, NumericVariant
from athena_api.srs.starter_banks import cse5alg_bank, starter_banks
from athena_api.srs.store import SqliteStore

# --- generators ---------------------------------------------------------------------------


def test_insertion_sort_passes():
    assert g.insertion_sort_passes([5, 2, 4, 6, 1, 3], 1)[0] == [2, 5, 4, 6, 1, 3]
    assert g.insertion_sort_passes([5, 2, 4, 6, 1, 3], 2)[0] == [2, 4, 5, 6, 1, 3]
    assert g.insertion_sort_passes([3, 1, 2], 99)[0] == [1, 2, 3]


def test_merge_comparisons():
    assert g.merge_comparisons([1, 4, 9], [2, 3, 10]) == (5, [1, 2, 3, 4, 9, 10])
    assert g.merge_comparisons([1, 2, 3], [7, 8, 9])[0] == 3


def test_binary_search_probes():
    assert g.binary_search_probes([3, 8, 12, 17, 21, 25, 30], 17) == (1, [17])
    assert g.binary_search_probes([3, 8, 12, 17, 21, 25, 30], 25) == (2, [17, 25])


def test_radix_pass_is_stable():
    assert g.radix_pass([170, 45, 75, 90, 802, 24, 2, 66]) == [170, 90, 802, 2, 24, 45, 75, 66]


def test_linear_probe_and_heap_parent():
    assert g.linear_probe_slot([12, 22, 32], 42, 10) == (5, [2, 3, 4, 5])
    assert [g.heap_parent(i) for i in (1, 2, 9, 14)] == [0, 0, 4, 6]


# --- banks ------------------------------------------------------------------------------------


def test_starter_banks_are_valid_with_several_wordings():
    for bank in starter_banks():
        Bank.model_validate_json(bank.model_dump_json())
        for item in bank.items:
            assert len(item.variants) >= 3, item.id
            stems = [v.stem for v in item.variants]
            assert len(set(stems)) == len(stems), f"{item.id} repeats a wording"


def test_ids_are_stable_across_builds():
    a, b = cse5alg_bank(), cse5alg_bank()
    assert a == b  # same ids, same option order


def test_computed_answers_match_generators():
    item = next(i for i in cse5alg_bank().items if i.id == "insertion-pass")
    first = item.variants[0]
    assert isinstance(first, McqVariant)
    assert first.options[first.answer_index] == "[2, 4, 5, 6, 1, 3]"
    probe = next(i for i in cse5alg_bank().items if i.id == "linear-probing").variants[0]
    assert isinstance(probe, NumericVariant) and probe.answer == 5.0


def test_mcq_options_have_one_correct_answer():
    for bank in starter_banks():
        for item in bank.items:
            for v in item.variants:
                if isinstance(v, McqVariant):
                    assert v.options.count(v.options[v.answer_index]) == 1
                    assert 2 <= len(v.options) <= 4


# --- cli ------------------------------------------------------------------------------------


def test_cli_loads_and_exports(tmp_path, capsys):
    db = tmp_path / "srs.db"
    main(["--db", str(db), "load-starter"])
    assert "cse5alg-2026-s2" in capsys.readouterr().out
    store = SqliteStore(db)
    assert len(store.get_bank("cse5alg-2026-s2").items) == 10
    store.close()

    main(["export-starter", str(tmp_path / "out")])
    exported = tmp_path / "out" / "cse5dmi-2026-s2.json"
    assert json.loads(exported.read_text())["offering_id"] == "cse5dmi-2026-s2"
    main(["--db", str(db), "load", str(exported)])
