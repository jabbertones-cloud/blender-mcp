from pathlib import Path


def test_bench_alias_and_default_port_match_runner():
    source = (Path(__file__).resolve().parents[1] / "eval" / "run.py").read_text()
    assert "'--bench'" in source
    assert "default=9876" in source
    assert "29500" not in source
    assert "Offline evaluation is forbidden" in source
