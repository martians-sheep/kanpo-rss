# kanpo-rss プロジェクトコンテキスト

## プロジェクト概要

官報（https://www.kanpo.go.jp/）の発刊情報をスクレイピングし、RSS 2.0 および Atom 1.0 フィードを自動生成するPythonツール。
GitHub Actionsで毎朝実行し、GitHub Pagesで `feed.xml`（RSS）/ `feed-atom.xml`（Atom）を公開する。

## 技術スタック

- Python 3.11+
- requests + BeautifulSoup4（スクレイピング）
- feedgen（RSS / Atom生成）
- pytest + requests-mock（テスト）
- GitHub Actions（CI/CD）+ GitHub Pages（公開）

## ディレクトリ構成

```
src/kanpo_rss/
├── models.py          # GazetteType(Enum), GazetteIssue(dataclass)
├── scraper.py         # KanpoScraper: HTTP取得（リトライ・レート制限）
├── parser.py          # KanpoParser: トップページHTML解析
├── feed_generator.py  # KanpoFeedGenerator: RSS/Atom XML生成
├── storage.py         # IssueStorage: JSON永続化・マージ・重複排除
├── cli.py             # main(): パイプライン制御・CLIエントリーポイント
└── __main__.py        # python -m kanpo_rss サポート
data/
└── issues.json        # 蓄積データ（GitHub Actionsが自動コミット）
tests/
├── fixtures/top_page.html  # 実サイトから保存したHTMLフィクスチャ
├── test_parser.py     # パーサーテスト（フィクスチャベース）
├── test_scraper.py    # スクレイパーテスト（requests-mock）
├── test_feed_generator.py  # フィード生成テスト
├── test_storage.py    # ストレージテスト
└── test_cli.py        # CLI統合テスト
```

## データフロー

```
1. IssueStorage.load(data/issues.json) → 既存 list[GazetteIssue]
2. kanpo.go.jp トップページ
   → KanpoScraper.fetch_top_page() → HTML文字列
   → KanpoParser.parse_top_page()  → 新規 list[GazetteIssue]
3. IssueStorage.merge(既存, 新規)   → マージ済み list[GazetteIssue]
4. IssueStorage.save(data/issues.json) → 蓄積データ更新
5. KanpoFeedGenerator.generate()      → docs/feed.xml + docs/feed-atom.xml
```

`--data-dir ""` で蓄積を無効化し、従来の1回完結方式で動作する。

## 核となるデータモデル

### GazetteType (Enum)
官報の種別。値はURLプレフィックス文字。

| メンバー | 値 | ラベル |
|---|---|---|
| HONSHI | "h" | 本紙 |
| GOUGAI | "g" | 号外 |
| SEIFU_CHOUTATSU | "c" | 政府調達 |
| TOKUBETSU_GOUGAI | "t" | 特別号外 |

### GazetteIssue (frozen dataclass)
1号分の官報情報。`issue_id`（例: `20260303h01657`）がRSSのGUID / AtomのIDとなる。

## 官報サイトの構造

- トップページ（`/`）に直近90日分の全号が掲載
- 各号は `<a class="articleTop">` タグ内にリンクされている
- hrefパターン: `./YYYYMMDD/YYYYMMDD{type}{issue_number_5digit}/...html`
- パーサーはこのhrefを正規表現で解析し `GazetteIssue` を生成
- `m`（目録）は Phase 1 対象外、WARNINGログで無視

## 実行方法

```bash
# インストール
pip install -e ".[dev]"

# フィード生成
python -m kanpo_rss --output-dir docs -v

# テスト
pytest --cov=kanpo_rss
```

## 設計上の制約・注意点

- **1リクエスト方式**: Phase 1ではトップページのみ取得（fullcontentsは未使用）
- **レート制限**: リクエスト間隔1秒以上、逐次実行（並列なし）
- **データ蓄積**: `data/issues.json` にissue_idをキーとして重複排除・マージし蓄積。GitHub Actionsが毎回自動コミット
- **冪等性**: 同じデータで何度実行しても結果が変わらない
- **最大件数**: デフォルト100件（`--max-items`で変更可）
- **feedgen の add_entry**: `order="append"` を指定しないとアイテム順が逆になる

## Phase 2 拡張ポイント

- 種別ごとのフィード分割 → `cli.py` でフィルタして `generate()` を複数回呼ぶ
- 目次レベル詳細分割 → `GazetteIssue` に `entries: list` フィールド追加
- キーワードフィルタ → パイプライン中間にフィルタステップ挿入
- AI要約 → `description` 生成を差し替え可能な設計

## CI/CD

- `.github/workflows/test.yml`: push/PR時にpytest実行
- `.github/workflows/generate-feed.yml`: 平日09:00 JST（UTC 00:00）にフィード生成→data/issues.jsonコミット→GitHub Pagesデプロイ
  - `contents: write` で data/ へのコミットを許可
  - `[skip ci]` でデータコミットによるCI再起動を防止
