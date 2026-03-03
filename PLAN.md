# kanpo-rss 設計計画

## 背景

日本の官報（https://www.kanpo.go.jp/）は公式RSSを提供していない。
本プロジェクトは官報サイトをスクレイピングしてRSSフィードを自動生成・公開する。

## Phase 1（現在） - 基本フィード生成

### スコープ

- 官報トップページから本紙・号外・政府調達・特別号外の発刊情報を取得
- 全種別をまとめた単一の `feed.xml` を生成
- GitHub Actions で毎朝自動実行
- GitHub Pages で公開

### アーキテクチャ

```
kanpo.go.jp トップページ（1リクエスト）
  → scraper.py  HTTP取得（リトライ・レート制限）
  → parser.py   HTML解析 → list[GazetteIssue]
  → feed_generator.py  RSS 2.0 XML生成
  → docs/feed.xml
```

### 設計判断

| 判断事項 | 選択 | 理由 |
|---|---|---|
| 取得対象 | トップページのみ | 1リクエストで90日分の全号情報が取得可能 |
| 状態管理 | なし（毎回フル再生成） | 冪等性が保証され、実装がシンプル |
| RSSアイテム粒度 | 号単位 | Phase 1では十分。目次レベルはPhase 2で |
| デプロイ方式 | actions/deploy-pages | コミット履歴を汚さない |
| scraper/parser分離 | あり | テスタビリティと責務の明確化 |

## Phase 2（予定） - フィード拡充

### 種別ごとのフィード分割

- `feed.xml`（全種別）に加え、`feed_honshi.xml`, `feed_gougai.xml` 等を生成
- 実装: `cli.py` で `GazetteType` ごとにフィルタし `generate()` を複数回呼ぶ
- 影響範囲: `cli.py` のみ。他モジュールの変更不要

### 目次レベルの詳細分割

- 各号内の個別記事（告示、府令など）をRSSアイテムとして出力
- 実装:
  - `models.py` に `GazetteEntry` dataclass を追加
  - `GazetteIssue` に `entries: list[GazetteEntry]` フィールドを追加
  - `parser.py` に `parse_fullcontents()` メソッドを追加
  - fullcontentsページの取得が必要（日数分の追加リクエスト）
- 影響範囲: `models.py`, `parser.py`, `scraper.py`（既存の `fetch_fullcontents` を活用）, `feed_generator.py`, `cli.py`

### キーワードフィルタリング・通知

- 設定ファイル（`config.yaml`）でキーワードルールを定義
- パイプラインの「解析→生成」の間にフィルタステップを挿入
- Slack/メール通知は別モジュールとして追加

### AI要約

- 個別記事ページの取得が前提（Phase 2の目次分割に依存）
- `description` 生成をプラグイン的に差し替え可能な設計
- LLM APIの呼び出しコスト・レート制限を考慮した設計が必要

## 官報サイト構造メモ

### URL構造

```
トップページ: https://www.kanpo.go.jp/
全文目次:     https://www.kanpo.go.jp/{YYYYMMDD}/{YYYYMMDD}.fullcontents.html
号の第1頁:    https://www.kanpo.go.jp/{YYYYMMDD}/{YYYYMMDD}{type}{issue5}/{YYYYMMDD}{type}{issue5}0001f.html
```

### 種別プレフィックス

| プレフィックス | 種別 | 備考 |
|---|---|---|
| h | 本紙 | 毎日発行 |
| g | 号外 | 毎日発行、同日複数号あり |
| c | 政府調達 | 毎日発行 |
| t | 特別号外 | 不定期 |
| m | 目録 | 月次、Phase 1対象外 |

### トップページHTML構造

- 各号: `<li class="articleBox">` 内の `<a class="articleTop">`
- href例: `./20260303/20260303h01657/20260303h016570000f.html`
- テキスト: `本紙\n(第1657号)`
