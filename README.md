# aozora-catalog

青空文庫のパブリックドメイン作品（著作権なし）だけを集めた検索用カタログを、毎日自動で更新・公開する仕組みと、iOSアプリ側の検索コードです。

```
青空文庫 公式CSV（毎日更新）
   │  GitHub Actions（毎日 04:17 JST）
   ▼
scripts/build_catalog.py
   ├─ 作品・人物（翻訳者含む）どちらかに著作権があれば除外
   ├─ 作品IDごとに著者・翻訳者をまとめる
   └─ 作品数が前回より10%以上減ったら公開しない（データ異常の防止）
   ▼
GitHub Pages
   ├─ meta.json      … 数百バイト。version（catalog.jsonのハッシュ）と件数
   └─ catalog.json   … 作品一覧（約1万7千件、gzip転送で1MB前後の見込み）
   ▼
iOSアプリ（CatalogStore）
   ├─ まず meta.json だけ確認 → version が変わったときだけ catalog.json を取得
   ├─ ハッシュと件数を検証してから保存（壊れたデータで上書きしない）
   └─ 端末内で検索（オフラインでも動く）
```

## セットアップ

1. GitHub に新しいリポジトリ（例: `aozora-catalog`）を作り、このフォルダの中身を push
2. リポジトリの **Settings → Pages → Build and deployment → Source** を **GitHub Actions** にする
3. **Actions** タブで「Update Aozora catalog」を開き、**Run workflow** で初回実行
4. `https://torunen.github.io/aozora-catalog/meta.json` が開けたら成功

以後は毎日自動で更新されます。

> 注意: 公開リポジトリでは、60日間コミットがないとスケジュール実行が自動で止まります。Actions タブから再有効化するか、たまにコミットしてください。

## iOS への組み込み

`ios/BookCatalog/` の4ファイルを Xcode プロジェクトに追加します（iOS 16 以降）。

| ファイル | 役割 |
|---|---|
| `AozoraModels.swift` | 作品・人物・メタ情報のモデル。小説判定（NDC 9x3）など |
| `BookSearchEngine.swift` | かな/カナ・全角/半角・空白を吸収する検索。空白区切りでAND検索 |
| `CatalogStore.swift` | ダウンロード・検証・キャッシュ・更新確認（6時間おき） |
| `BookSearchView.swift` | 検索画面と詳細画面のサンプル |

リポジトリ名を変えた場合は `CatalogStore(baseURL:)` のURLを合わせてください。

初回起動を速くしたい場合は、生成した `catalog.json` をアプリに同梱すると、ネットに繋がる前から検索できます（以後は自動で最新に差し替わります）。

テストは `ios/BookCatalogTests/BookSearchEngineTests.swift` をテストターゲットに追加し、`@testable import` をアプリ名に変えて実行します。

## ローカルで試す

```bash
python3 scripts/build_catalog.py              # 公式サイトから取得して public/ に出力
python3 tests/test_build.py                   # サンプルCSVでのテスト
```

## 検索の仕様

- 「らしょうもん」「ラショウモン」「ﾗｼｮｳﾓﾝ」「羅生門」どれでもヒット
- 作家名は漢字・読み・ローマ字（`soseki`）で検索可
- 「漱石 こころ」のように空白区切りでAND検索
- 並び順: 作品名の完全一致 > 前方一致 > 部分一致 > 作家名 > 副題・原題
- 絞り込み: 小説・物語のみ（NDC 913/933/983 など）、日本の小説のみ（913）、新字新仮名のみ

## 今後の拡張メモ

- 旧字と新字の揺れ（龍/竜、澤/沢）への対応
- 本文の文字数（要約対象として長さが十分か）の付与
- 「主人公になれる」候補作品のタグ付け
