# Contributing

kanpo-rss への貢献に感謝します。

## 開発環境のセットアップ

```bash
# リポジトリのクローン
git clone https://github.com/<owner>/kanpo-rss.git
cd kanpo-rss

# 仮想環境の作成・有効化
python3 -m venv .venv
source .venv/bin/activate

# 開発用依存関係のインストール
pip install -e ".[dev]"
```

## テストの実行

```bash
# 全テスト
pytest

# カバレッジ付き
pytest --cov=kanpo_rss --cov-report=term-missing

# 特定のテストファイル
pytest tests/test_parser.py -v
```

## ローカルでのフィード生成

```bash
# 実際の官報サイトからフィード生成（docs/feed.xmlに出力）
python -m kanpo_rss --output-dir docs -v
```

## プロジェクト構成

```
src/kanpo_rss/
├── models.py          # データクラス定義
├── scraper.py         # HTTP取得
├── parser.py          # HTML解析
├── feed_generator.py  # RSS生成
├── storage.py         # データ蓄積（JSON永続化）
└── cli.py             # CLIエントリーポイント
data/
└── issues.json        # 蓄積データ
tests/
├── fixtures/          # テスト用HTMLフィクスチャ
├── test_parser.py
├── test_scraper.py
├── test_feed_generator.py
├── test_storage.py
└── test_cli.py
```

## コーディング規約

- Python 3.11+ の機能を利用可
- 型ヒントを記述する
- テストは `pytest` で記述
- HTTPモックには `requests-mock` を使用

## Pull Request

1. フィーチャーブランチを作成: `git checkout -b feature/your-feature`
2. テストを追加・更新
3. `pytest` が全て通過することを確認
4. PRを作成

## テスト用HTMLフィクスチャの更新

パーサーのテストは `tests/fixtures/top_page.html` を使用しています。
官報サイトのHTML構造が変わった場合は、フィクスチャを更新してください:

```bash
curl -s -L 'https://www.kanpo.go.jp/' > tests/fixtures/top_page.html
```
