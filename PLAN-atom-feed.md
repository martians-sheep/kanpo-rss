# Atom フィード対応 実装計画

## 概要

既存の RSS 2.0 フィードに加えて、Atom 1.0 フィードを同時出力する機能を追加する。
`feedgen` ライブラリが両フォーマットをネイティブサポートしているため、
主な変更は出力メソッドの追加と Atom 固有メタデータの補完。

## 方針

- **既存の RSS 出力はそのまま維持**（後方互換性）
- 各 `rss_file()` 呼び出し箇所で、同時に `atom_file()` も出力
- CLI に `--format` オプションは追加しない（常に両方出力でシンプルに保つ）
- ファイル名規則: `feed.xml` → `feed-atom.xml`, `feed-archive.xml` → `feed-archive-atom.xml` 等

## 出力ファイルマッピング

| 既存 RSS ファイル | 新規 Atom ファイル |
|---|---|
| `docs/feed.xml` | `docs/feed-atom.xml` |
| `docs/feed-archive.xml` | `docs/feed-archive-atom.xml` |
| `docs/feed-articles.xml` | `docs/feed-articles-atom.xml` |
| `docs/articles/feed-YYYYMMDD.xml` | `docs/articles/feed-YYYYMMDD-atom.xml` |

## フェーズ

### Phase 1: feed_generator.py — Atom 対応のコア実装

#### タスク 1.1: `_build_feed()` に Atom 必須メタデータ追加
- `fg.id()` の設定（KANPO_URL を使用）
- `fg.author({"name": "kanpo-rss"})` の追加（Atom 必須）
- これらは RSS 出力には影響しない（feedgen が形式ごとに適切に処理）

#### タスク 1.2: `_add_entry()` に `entry.updated()` 追加
- Atom ではエントリに `<updated>` が必須
- `pubDate` と同じ日時を `entry.updated()` にも設定
- RSS 出力には影響なし

#### タスク 1.3: `_add_article_entry()` にも同様に `entry.updated()` 追加
- 記事エントリにも `updated` を設定

#### タスク 1.4: `generate()` メソッドで Atom ファイルも出力
- `rss_file()` の直後に `atom_file()` を呼び出す
- Atom ファイルのパスは `.xml` の拡張子前に `-atom` を挿入
  - 例: `feed.xml` → `feed-atom.xml`
- ヘルパー関数 `_atom_path(rss_path)` を追加して命名規則を統一

#### タスク 1.5: `generate_article_feed()` でも Atom 出力追加
- 同様に `atom_file()` 呼び出しを追加

#### タスク 1.6: `generate_article_feeds_by_date()` でも Atom 出力追加
- 日付別フィードでも Atom を同時出力
- `feed-articles.xml` のコピー処理で Atom 版もコピー

### Phase 2: テスト追加

#### タスク 2.1: `test_feed_generator.py` に Atom テストクラス追加
- `TestAtomFeedGenerator` クラスを新設
- テスト項目:
  - 有効な Atom XML が生成される（ルート要素が `{http://www.w3.org/2005/Atom}feed`）
  - フィードメタデータ（title, id, updated, author）の存在
  - エントリ構造（title, link, id, updated, summary）の検証
  - アイテム順序の維持
  - max_items による切り詰め
  - 空リストでも有効な Atom が生成される
  - Atom ファイルが RSS と同時に生成される

#### タスク 2.2: 記事フィードの Atom テスト追加
- `TestAtomArticleFeedGenerator` クラスを新設
- 記事レベルのフィードが Atom でも正しく生成されることを検証

#### タスク 2.3: 日付別フィードの Atom テスト追加
- `TestAtomArticleFeedsByDate` に追加テスト
- 日付別 Atom ファイルの存在確認
- `feed-articles-atom.xml` のコピー確認

### Phase 3: CLI・HTML・ドキュメント更新

#### タスク 3.1: `cli.py` の archive フィード出力箇所を対応
- `cli.py` 内で `generate()` を呼ぶ箇所は feed_generator 内部で
  自動的に Atom も出力されるため、CLI 側の変更は最小限
- ログメッセージに Atom ファイル生成を反映

#### タスク 3.2: `docs/index.html` に Atom フィード URL を追加
- RSS フィード URL の下に Atom フィード URL を並記
- `<head>` に Atom の `<link rel="alternate">` タグを追加（任意）

#### タスク 3.3: 記事フィードインデックス HTML に Atom リンク追加
- `generate_article_index()` で生成する HTML テーブルに Atom 列を追加

#### タスク 3.4: `CLAUDE.md` のドキュメント更新
- 出力ファイル一覧に Atom ファイルを追記
- 技術スタックの説明に Atom 対応を反映

### Phase 4: CI/テスト実行・最終確認

#### タスク 4.1: 全テスト実行・パス確認
- `pytest --cov=kanpo_rss` で全テスト通過を確認
- 既存テストが壊れていないことを確認（RSS 出力の後方互換性）

#### タスク 4.2: コミット・プッシュ
