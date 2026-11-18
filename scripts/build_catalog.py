#!/usr/bin/env python3
"""青空文庫の作品リストから、パブリックドメイン作品だけの検索用カタログを作る。

使い方:
    python scripts/build_catalog.py                 # 公式サイトから取得して public/ に出力
    python scripts/build_catalog.py --csv local.csv # ローカルCSVから生成（テスト用）

出力:
    public/catalog.json     作品一覧（アプリが検索に使う本体）
    public/meta.json        バージョン情報（アプリはまずこれだけ見て、変化があれば本体を取り直す）
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://www.aozora.gr.jp/index_pages/list_person_all_extended_utf8.zip"
SCHEMA_VERSION = 1
# 前回より作品数がこの割合以上減ったら異常とみなして公開しない
MAX_DROP_RATIO = 0.10

REQUIRED_COLUMNS = [
    "作品ID", "作品名", "作品名読み", "ソート用読み", "副題", "副題読み", "原題",
    "分類番号", "文字遣い種別", "作品著作権フラグ", "公開日", "最終更新日",
    "図書カードURL", "人物ID", "姓", "名", "姓読み", "名読み", "姓ローマ字", "名ローマ字",
    "役割フラグ", "没年月日", "人物著作権フラグ",
    "テキストファイルURL", "XHTML/HTMLファイルURL",
]


def fetch_csv_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "aozora-catalog-builder/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".csv"))
        return zf.read(name).decode("utf-8-sig")


def clean(s: str | None) -> str:
    return (s or "").strip()


def build(rows: list[dict]) -> list[dict]:
    if rows:
        missing = [c for c in REQUIRED_COLUMNS if c not in rows[0]]
        if missing:
            raise SystemExit(f"CSVの列が想定と違います（青空文庫側の仕様変更？）: {missing}")

    works: dict[str, dict] = {}
    blocked: set[str] = set()  # 著作権ありの人物が関わる作品

    for r in rows:
        wid = clean(r["作品ID"])
        if not wid:
            continue
        # 作品・人物（翻訳者含む）のどちらかに著作権があれば除外
        if clean(r["作品著作権フラグ"]) != "なし" or clean(r["人物著作権フラグ"]) != "なし":
            blocked.add(wid)
            continue

        w = works.get(wid)
        if w is None:
            w = works[wid] = {
                "id": wid,
                "title": clean(r["作品名"]),
                "titleReading": clean(r["作品名読み"]),
                "sortKey": clean(r["ソート用読み"]),
                "subtitle": clean(r["副題"]),
                "subtitleReading": clean(r["副題読み"]),
                "originalTitle": clean(r["原題"]),
                "ndc": clean(r["分類番号"]),
                "orthography": clean(r["文字遣い種別"]),
                "published": clean(r["公開日"]),
                "updated": clean(r["最終更新日"]),
                "cardURL": clean(r["図書カードURL"]),
                "textURL": clean(r["テキストファイルURL"]),
                "htmlURL": clean(r["XHTML/HTMLファイルURL"]),
                "people": [],
            }
        pid = clean(r["人物ID"])
        if any(p["id"] == pid and p["role"] == clean(r["役割フラグ"]) for p in w["people"]):
            continue
        w["people"].append({
            "id": pid,
            "name": " ".join(x for x in (clean(r["姓"]), clean(r["名"])) if x),
            "reading": " ".join(x for x in (clean(r["姓読み"]), clean(r["名読み"])) if x),
            "romaji": " ".join(x for x in (clean(r["名ローマ字"]), clean(r["姓ローマ字"])) if x),
            "role": clean(r["役割フラグ"]),
            "died": clean(r["没年月日"]),
        })

    for wid in blocked:
        works.pop(wid, None)

    result = sorted(works.values(), key=lambda w: (w["sortKey"] or w["titleReading"], w["id"]))
    for w in result:
        # 著者を先頭に
        w["people"].sort(key=lambda p: (p["role"] != "著者", p["id"]))
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="ローカルのCSVファイル（指定がなければ公式サイトから取得）")
    ap.add_argument("--out", default="public", help="出力ディレクトリ")
    ap.add_argument("--previous-meta", help="前回のmeta.json（作品数の急減チェック用）")
    args = ap.parse_args()

    text = Path(args.csv).read_text(encoding="utf-8-sig") if args.csv else fetch_csv_text(SOURCE_URL)
    rows = list(csv.DictReader(io.StringIO(text)))
    works = build(rows)
    if not works:
        print("作品が0件でした。公開を中止します。", file=sys.stderr)
        return 1

    if args.previous_meta and Path(args.previous_meta).exists():
        prev = json.loads(Path(args.previous_meta).read_text(encoding="utf-8"))
        prev_count = prev.get("count", 0)
        if prev_count and len(works) < prev_count * (1 - MAX_DROP_RATIO):
            print(f"作品数が {prev_count} → {len(works)} に急減。公開を中止します。", file=sys.stderr)
            return 1

    catalog = {"schema": SCHEMA_VERSION, "works": works}
    body = json.dumps(catalog, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    version = hashlib.sha256(body).hexdigest()[:16]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "catalog.json").write_bytes(body)
    meta = {
        "schema": SCHEMA_VERSION,
        "version": version,
        "count": len(works),
        "bytes": len(body),
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": SOURCE_URL,
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(works)} 作品 / {len(body):,} bytes / version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
