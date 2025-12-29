# エラーハンドリングガイド

MD Review MCP スキル使用時に発生しうるエラーと対応方法。

## ファイルが見つからない

### エラーメッセージ
```
Error: File not found: /path/to/file.md
```

### 原因
- ファイルパスが不正
- ファイルがまだ生成されていない
- 相対パスが誤っている

### 対応方法

1. **ファイルパスを確認**
   ```
   ファイルが存在するか確認:
   - ls /path/to/file.md
   - find . -name "file.md"
   ```

2. **絶対パス / 相対パスを修正**
   ```
   project_root: "/Users/user/project"
   files: ["docs/API.md"]  # relative to project_root
   ```

3. **実在するファイルのリストを表示**
   ```
   プロジェクト配下のファイル一覧を表示してから再度実行
   ```

4. **再度 review.request を実行**

## アプリが起動しない

### エラーメッセージ
```
Error: Failed to open Electron app
Failed to launch mdreview://session/...
```

### 原因
- Electron アプリがインストールされていない
- URL Scheme が登録されていない
- アプリのプロセスがハング している

### 対応方法

1. **アプリがインストールされているか確認**
   ```bash
   ls -la /Applications/MD\ Review.app
   ```

2. **URL Scheme が Info.plist に登録されているか確認**
   ```bash
   plutil -p "/Applications/MD Review.app/Contents/Info.plist" | grep -A 5 CFBundleURLTypes
   ```

   登録されていない場合：
   ```bash
   plutil -insert CFBundleURLTypes -json '[{"CFBundleURLName":"MD Review Session","CFBundleURLSchemes":["mdreview"]}]' "/Applications/MD Review.app/Contents/Info.plist"
   ```

3. **Launch Services を再登録**
   ```bash
   /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -kill -r -domain local -domain system -domain user "/Applications/MD Review.app"
   ```

4. **手動でアプリを起動**
   ```bash
   # 直接起動
   open -a "MD Review"

   # URL Scheme で直接起動
   open "mdreview://session/550e8400-e29b-41d4-a716-446655440000"
   ```

5. **再度 review.request を実行**

## セッションが重複している

### エラーメッセージ
```
Error: Session already exists
Cannot create new session with resume_key: ...
```

### 原因
- 同じ resume_key で既に review.request が実行中
- 前のセッションがまだ finalize されていない

### 対応方法

1. **既存セッションを確認**
   ```
   Electron アプリを開いて、当該セッションが存在するか確認
   ```

2. **セッションを復旧 (冪等性)**
   ```
   同じ resume_key で再度 review.request を実行
   → 既存セッションが復旧される
   ```

3. **または新しい resume_key で実行**
   ```
   session.new-id で新しい UUID を生成
   → 新規セッションで review.request を実行
   ```

## Markdown がレンダリングされない

### エラーメッセージ
```
Warning: Failed to render markdown
Markdown content may not display correctly
```

### 原因
- Markdown 記法が無効
- ファイルが破損している
- 文字エンコーディングが不正

### 対応方法

1. **Markdown ファイルを確認**
   ```bash
   file /path/to/file.md   # ファイル形式確認
   od -c /path/to/file.md | head  # バイナリ確認
   ```

2. **Markdown 記法を確認**
   - リスト（`-`, `*`）が正しく書かれているか
   - コードブロック（\`\`\`）のペアが正しいか
   - 見出し（`#`）の フォーマットが正しいか

3. **ファイルエンコーディングを確認**
   ```bash
   # UTF-8 に統一
   iconv -f ISO-8859-1 -t UTF-8 /path/to/file.md > /tmp/file.md
   mv /tmp/file.md /path/to/file.md
   ```

4. **Markdown を生成し直す**

## コメントが保存されない

### エラーメッセージ
```
Error: Failed to save comment
Comment data may be lost
```

### 原因
- データベースがロック中
- ディスク容量不足
- ファイル権限エラー

### 対応方法

1. **DB をリセット**
   ```bash
   rm ~/Library/Application\ Support/MDReview/sessions.sqlite
   ```

2. **セッションデータをリセット**
   ```bash
   rm -rf ~/Library/Application\ Support/MDReview/session_data/
   ```

3. **再度セッションを開く**
   ```
   新しい resume_key で review.request を実行
   ```

## ファイル権限エラー

### エラーメッセージ
```
Error: Permission denied: /path/to/file
```

### 原因
- ファイルが読み取り専用
- ディレクトリのパーミッションが不正
- ユーザーが不適切

### 対応方法

1. **ファイル権限を確認**
   ```bash
   ls -l /path/to/file.md
   ```

2. **読み取り権限を付与**
   ```bash
   chmod 644 /path/to/file.md
   chmod 755 /path/to/directory
   ```

3. **ディレクトリの所有権を確認**
   ```bash
   ls -ld /path/to/directory
   sudo chown $USER /path/to/directory  # 必要に応じて
   ```

## タイムアウトエラー

### エラーメッセージ
```
Error: Timeout waiting for review finalization
Session did not complete within expected time
```

### 原因
- ユーザーがレビューを実施中
- Electron アプリがハング している
- ネットワーク遅延

### 対応方法

1. **Electron アプリをチェック**
   ```
   MD Review アプリが起動しているか確認
   ```

2. **レビューが進行中か確認**
   ```
   アプリで当該セッションを確認
   コメント作成中の場合は待機
   ```

3. **強制終了＆リトライ**
   ```bash
   # アプリを終了
   pkill "MD Review"

   # 新しい resume_key で再実行
   session.new-id → review.request
   ```

## インストール関連

### CLI サーバが起動しない

```
Error: CLI server failed to start
```

**対応:**
```bash
# TypeScript ビルドを確認
npm run build

# ノードモジュールをリセット
rm -rf node_modules
npm install

# 再度起動
node dist/index.js
```

### MCP Tool が見つからない

```
Error: Tool not found: review.request
```

**対応:**
```bash
# CLI が正しく起動しているか確認
ps aux | grep "dist/index.js"

# Claude Code のモードを確認
/mcp を再度実行
```

## デバッグ情報の取得

### ログを確認

```bash
# CLI ログ
# terminal に出力された stderr をコピー

# Electron アプリログ
open ~/Library/Application\ Support/MDReview/

# DB ファイル
ls -la ~/Library/Application\ Support/MDReview/sessions.sqlite
```

### 診断スクリプト実行

```bash
# ファイル構造確認
find ~/Library/Application\ Support/MDReview -type f

# DB 確認
sqlite3 ~/Library/Application\ Support/MDReview/sessions.sqlite ".tables"

# セッション確認
sqlite3 ~/Library/Application\ Support/MDReview/sessions.sqlite "SELECT resume_key, state FROM sessions LIMIT 5;"
```
