# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- データ蓄積機能（`data/issues.json`）— 90日を超えた官報データも永続保持
  - `IssueStorage` クラス（JSON読み書き・マージ・重複排除）
  - `--data-dir` CLIオプション（デフォルト: `data`、空文字で無効化）
  - GitHub Actionsでデータファイルを自動コミット

## [0.1.0] - 2026-03-03

### Added

- 官報トップページのスクレイピング（本紙・号外・政府調達・特別号外）
- RSS 2.0フィード生成（`feed.xml`）
- CLIインターフェース（`python -m kanpo_rss`）
  - `--output-dir`: 出力先ディレクトリ
  - `--max-items`: 最大アイテム数
  - `--self-url`: フィード自己参照URL
  - `-v`: 詳細ログ
- GitHub Actionsワークフロー
  - `generate-feed.yml`: 平日09:00 JSTに自動フィード生成・GitHub Pagesデプロイ
  - `test.yml`: push/PR時にpytest実行
- HTTP取得のリトライ・レート制限機構
- テストスイート（31テスト、カバレッジ95%）
