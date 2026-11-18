import csv, io, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_catalog import build

def load():
    here = Path(__file__).parent
    subprocess.run([sys.executable, str(here / "make_sample.py"), str(here / "sample.csv")], check=True)
    return list(csv.DictReader(io.StringIO((here / "sample.csv").read_text(encoding="utf-8-sig"))))

def test_filters_and_merges():
    works = {w["id"]: w for w in build(load())}
    assert set(works) == {"000773", "000752", "000127", "001567", "043014"}
    assert "099001" not in works  # 翻訳者に著作権あり
    assert "099002" not in works  # 作品に著作権あり
    assert len(works["000752"]["people"]) == 1  # 重複行は1人に
    roles = [p["role"] for p in works["043014"]["people"]]
    assert roles == ["著者", "翻訳者"]

if __name__ == "__main__":
    test_filters_and_merges(); print("OK")
