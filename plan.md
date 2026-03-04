# Feed Description 追加計画

## 現状の問題

現在の RSS feed の `<description>` は以下のように最小限の情報しか含まない：

- **号レベル (`feed.xml`)**: 種別名のみ（例: `本紙`）
- **記事レベル (`feed-articles.xml`)**: `{号タイトル} — {セクション}` （例: `2026-03-03 本紙 第1657号 — その他告示 / 国土交通省`）

RSSリーダーで一覧した際に、その号に何が掲載されているかが分からない。

## 利用可能なデータソース

### ソース1: トップページHTML（追加フェッチ不要）
各号の `<li class="articleBox">` には PDF リンクが併記されており、以下が抽出可能：
- **ページ数**: `1-32頁` → 32
- **ファイルサイズ**: `[5MB]` → `5MB`

### ソース2: 号の目次ページ（既存の記事取得で取得済み）
`--no-articles` でない限り、各号の目次ページを既にフェッチしている。記事データから以下を構成可能：
- **トップレベルのセクション一覧**: `告示, 国会事項, 人事異動, ...`
- **記事件数**: 全N件
- **セクション別件数**: `告示(5件), 国会事項(1件), ...`

### ソース3: 外部処理（Phase 2 で検討）
- AI要約（CLAUDE.md に記載あり）
- キーワード抽出

## 提案: 3段階の description

### Step 1: トップページからページ数・サイズを抽出（追加フェッチ不要）

**変更対象**: `models.py`, `parser.py`, `storage.py`, `feed_generator.py` + テスト

`GazetteIssue` にフィールド追加：
```python
page_count: int | None = None      # e.g. 32
pdf_size: str | None = None        # e.g. "5MB"
```

パーサーで `<a class="pdfDlb">` の兄弟要素から抽出。

フィード description 例:
```
本紙 (32頁, 5MB)
```

**メリット**: 追加HTTPリクエスト不要。号のボリューム感がRSSリーダーで分かる。

### Step 2: 記事データからセクション要約を構成（既にフェッチ済みのデータを活用）

**変更対象**: `feed_generator.py`

既に取得された `articles` リストから、ユニークなトップレベルセクション（h2相当）を集約して description に追記。

フィード description 例:
```
本紙 (32頁, 5MB)
告示, 国会事項, 人事異動, 叙位・叙勲 ほか（全28件）
```

**メリット**: 追加HTTPリクエスト不要（既に記事取得パイプラインで取得済み）。何が掲載されているかが一目で分かる。

### Step 3 (将来): AI要約

CLAUDE.md Phase 2 に記載されている `description` 生成の差し替え設計を活用。
本計画のスコープ外。

## 実装計画

### 1. `models.py` — GazetteIssue にフィールド追加
- `page_count: int | None = None`
- `pdf_size: str | None = None`

### 2. `parser.py` — トップページパーサーの拡張
- `_parse_article_link()` で、対象の `<a class="articleTop">` と同じ `<li class="articleBox">` 内にある `<a class="pdfDlb">` のテキストを解析
- 正規表現 `r"(\d+)-(\d+)頁\[(\d+MB)\]"` 等でページ数・サイズを抽出
- `GazetteIssue` に `page_count`, `pdf_size` を設定

### 3. `storage.py` — JSON永続化の対応
- `page_count`, `pdf_size` のシリアライズ/デシリアライズ追加
- 既存データとの後方互換性を維持（フィールドがない場合は None）

### 4. `feed_generator.py` — description 生成ロジック
- `_build_issue_description(issue)` メソッドを新設
- Step 1: `{種別} ({ページ数}頁, {サイズ})` を基本行とする
- Step 2: `articles` がある場合、トップレベルセクションを集約して2行目に追加
- `_add_entry()` で `entry.description()` にこの結果を設定

### 5. テストの更新
- `test_parser.py`: page_count, pdf_size の抽出テスト追加
- `test_feed_generator.py`: description 内容のアサーション更新
- `test_storage.py`: 新フィールドのシリアライズ/デシリアライズテスト追加

## description の最終フォーマット例

### 記事データあり（通常運用時）
```
本紙 (32頁, 5MB)
告示, 国会事項, 人事異動, 叙位・叙勲, 皇室事項（全28件）
```

### 記事データなし（--no-articles 時、または古い蓄積データ）
```
本紙 (32頁, 5MB)
```

### ページ数・サイズも不明（古い蓄積データ）
```
本紙
```
（現状と同じフォールバック）

## 影響範囲
- 既存のissues.jsonとの後方互換性あり（新フィールドはOptional）
- feed.xmlの出力が変わる（descriptionが豊かになる）
- 追加のHTTPリクエストは発生しない
- feed-articles.xmlの記事レベル description は変更しない（既に十分）
