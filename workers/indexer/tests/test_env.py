import os

from athena_indexer.env import load_dotenv


def test_load_dotenv_finds_parent_file_and_keeps_existing(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text('# comment\nA_TEST_KEY=abc\nB_TEST_MODEL="gpt x"\nexport C_TEST=1\nC_EXISTING=new\n')
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    for k in ["A_TEST_KEY", "B_TEST_MODEL", "C_TEST"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("C_EXISTING", "old")
    assert load_dotenv(sub) == tmp_path / ".env"
    assert os.environ["A_TEST_KEY"] == "abc"
    assert os.environ["B_TEST_MODEL"] == "gpt x"
    assert os.environ["C_TEST"] == "1"
    assert os.environ["C_EXISTING"] == "old"
