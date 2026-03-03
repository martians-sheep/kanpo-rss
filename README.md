# kanpo-rss

日本の[官報](https://www.kanpo.go.jp/)（Government Gazette）の新着情報をRSSフィードとして配信するツール。

官報サイトは公式RSSを提供していないため、本ツールがサイトをスクレイピングしてRSS 2.0フィードを自動生成します。

## 機能

- 官報サイトから本紙・号外・政府調達・特別号外の発刊情報を取得
- 全種別をまとめた単一のRSSフィード（`feed.xml`）を生成
- 日付別の記事レベルRSSフィード（`articles/feed-YYYYMMDD.xml`）— 個別記事ごとのRSS（キーワードフィルタ向き）
- アーカイブRSSフィード（`feed-archive.xml`）— 全件を含むRSS
- データ蓄積機能：`data/issues.json` に過去データを永続保存（90日超のデータも保持）
- 全件JSONデータ（`issues.json`）をGitHub Pagesで公開
- GitHub Actionsで毎朝自動実行、GitHub Pagesで公開

## 公開エンドポイント

GitHub Pages で配信中: <https://martians-sheep.github.io/kanpo-rss/>

| URL | 内容 |
|---|---|
| [`feed.xml`](https://martians-sheep.github.io/kanpo-rss/feed.xml) | 最新100件のRSSフィード（号レベル） |
| [`feed-articles.xml`](https://martians-sheep.github.io/kanpo-rss/feed-articles.xml) | 最新日の記事フィード |
| [`articles/`](https://martians-sheep.github.io/kanpo-rss/articles/) | 日付別の記事フィード一覧 |
| [`feed-archive.xml`](https://martians-sheep.github.io/kanpo-rss/feed-archive.xml) | 全件RSSフィード（アーカイブ） |
| [`issues.json`](https://martians-sheep.github.io/kanpo-rss/issues.json) | 全件JSONデータ |

## セットアップ

```bash
# インストール
pip install .

# 開発用（テスト含む）
pip install -e ".[dev]"
```

## 使い方

```bash
# フィード生成（docs/feed.xml に出力）
python -m kanpo_rss

# オプション指定
python -m kanpo_rss --output-dir docs --max-items 100 -v

# 蓄積なしで実行（従来動作）
python -m kanpo_rss --data-dir ""
```

### CLI オプション

| オプション | デフォルト | 説明 |
|---|---|---|
| `--output-dir` | `docs` | feed.xml の出力先ディレクトリ |
| `--max-items` | `100` | RSSアイテムの最大件数 |
| `--self-url` | なし | フィードの自己参照URL（rel=self） |
| `--data-dir` | `data` | 蓄積データの保存先。空文字で蓄積無効 |
| `--no-articles` | off | 記事レベルフィードの生成をスキップ |
| `-v, --verbose` | off | 詳細ログ出力 |

## テスト

```bash
pytest
pytest --cov=kanpo_rss --cov-report=term-missing
```

## アーキテクチャ

```
src/kanpo_rss/
├── models.py          # データクラス（GazetteType, GazetteIssue, GazetteArticle）
├── scraper.py         # HTTP取得（リトライ・レート制限付き）
├── parser.py          # HTML解析（トップページ・号ページ）
├── feed_generator.py  # RSS生成（feedgen）
├── storage.py         # データ蓄積（JSON永続化・マージ）
└── cli.py             # エントリーポイント
```

## ライセンス

MIT
