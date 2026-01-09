---
name: review-pr
description: |-
  Fetch and display Pull Request review comments from GitHub. Use this skill when:
  - User says "レビューコメントを確認" / "check review comments"
  - User says "新しいコメント" / "new comments"
  - User says "PR のコメント" / "PR comments"
  - User mentions getting feedback on a PR
  - After pushing commits to a PR branch

  Automatically fetches inline comments, review comments, and general comments,
  and displays them in an organized format for easy review.
allowed-tools: Bash, Read
---

# PR レビューコメント確認スキル

**IMPORTANT**: このスキルは、ユーザーが PR のレビューコメントを確認したい際に使用してください。

GitHub の Pull Request に対するレビューコメントを取得し、見やすく整形して表示します。

## 発動条件

以下のフレーズを含む依頼があった場合、このスキルを使用：

**日本語**:
- レビューコメントを確認
- 新しいコメントを見せて
- PR のコメント
- レビュー結果を確認
- フィードバックを確認
- レビューコメントに返信してください
- コメントに対応してください
- フィードバックに返信

**英語**:
- check review comments
- show new comments
- PR comments
- review feedback
- check feedback
- reply to review comments
- respond to comments
- reply to feedback

## 使用方法

### 推奨: スクリプトを使用

**最も簡単な方法** は用意されたスクリプトを使用することです：

```bash
# デフォルト: 直前の push 以降のコメントのみ取得（新機能）
~/.claude/scripts/fetch_pr_comments.sh

# 全コメントを取得
~/.claude/scripts/fetch_pr_comments.sh -a

# 特定の日時以降のコメントのみ取得
~/.claude/scripts/fetch_pr_comments.sh -s "2025-01-08T09:00:00Z"

# P1 優先度のコメントのみ取得
~/.claude/scripts/fetch_pr_comments.sh -p P1

# ヘルプを表示
~/.claude/scripts/fetch_pr_comments.sh -h
```

スクリプトは以下を自動で処理します：
- PR 番号とリポジトリの自動検出
- 直前の push 時刻の自動取得（デフォルト動作）
- エラーハンドリング
- 3 種類のコメントの取得と整形
- 色付き表示
- フィルタリング機能

### 基本的な使い方（手動実行）

```bash
# 現在のブランチの PR 番号を自動検出
PR_NUMBER=$(gh pr view --json number --jq '.number' 2>/dev/null)
if [[ -z "$PR_NUMBER" ]]; then
    echo "エラー: 現在のブランチに関連付けられた PR が見つかりません"
    exit 1
fi

# リポジトリを動的に取得
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
if [[ -z "$REPO" ]]; then
    echo "エラー: リポジトリ情報を取得できません"
    exit 1
fi

# インラインコメントを取得
gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments"
```

### 出力形式

コメントは以下の形式で表示されます：

```
File: tools/test/run_unity_tests.sh
Line: 102
Comment: ワイルドカードを使用したファイル削除は予期しない...
---
```

## 機能

- ✅ **自動 PR 検出**: 現在のブランチから PR 番号を自動取得
- ✅ **動的リポジトリ検出**: 現在のリポジトリを自動取得（フォークにも対応）
- ✅ **直前 push 以降のコメント自動抽出**: デフォルトで直前 push 時刻以降のコメントのみ表示（新機能）
- ✅ **3 種類のコメント取得**:
  - インラインコメント (Pull Request Review Comments API)
  - 一般コメント (Issue Comments API)
  - レビューコメント (Pull Request Reviews API)
- ✅ **新規コメントフィルタ**: タイムスタンプでフィルタリング可能
- ✅ **見やすい整形**: ファイルパス、行番号、コメント本文を構造化表示

## 実装例

### PR 番号の取得

```bash
PR_NUMBER=$(gh pr view --json number --jq '.number' 2>/dev/null)
if [[ -z "$PR_NUMBER" ]]; then
    echo "エラー: 現在のブランチに関連付けられた PR が見つかりません"
    exit 1
fi
```

### コメントの取得

```bash
# リポジトリを動的に取得
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
if [[ -z "$REPO" ]]; then
    echo "エラー: リポジトリ情報を取得できません"
    exit 1
fi

# 1. インラインコメント (Pull Request Review Comments API)
# Note: .line は現在の行番号、.original_line は元の行番号（コードが変更された場合に異なる）
gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments" \
  --jq '.[] | "File: \(.path)\nLine: \(.line // .original_line)\nComment: \(.body)\n---"'

# 2. 一般コメント (Issue Comments API)
gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" \
  --jq '.[] | "Comment: \(.body)\nAuthor: \(.user.login)\n---"'

# 3. レビューコメント (Pull Request Reviews API)
gh api "repos/${REPO}/pulls/${PR_NUMBER}/reviews" \
  --jq '.[] | select(.body and (.body | length) > 0) | "Review by \(.user.login)\nState: \(.state)\nComment: \(.body)\n---"'
```

### 新規コメントのみ取得

```bash
# リポジトリを動的に取得
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
if [[ -z "$REPO" ]]; then
    echo "エラー: リポジトリ情報を取得できません"
    exit 1
fi

# 特定の日時以降のコメントのみ取得（jq の --arg で安全に変数を渡す）
SINCE="2025-01-08T09:57:00Z"
gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments" | \
  jq --arg since "$SINCE" '.[] | select(.created_at > $since) | "File: \(.path)\nLine: \(.line // .original_line)\nComment: \(.body)\n---"'
```

## トラブルシューティング

### PR が見つからない

**エラー**: `no pull requests found for branch "xxx"`

**原因**: 現在のブランチが PR に紐付いていない

**対処**:
1. ブランチ名を確認: `git branch --show-current`
2. PR 一覧を確認: `gh pr list`
3. 手動で PR 番号を指定: `gh pr view 66`

### GitHub CLI が認証されていない

**エラー**: `authentication required`

**対処**:
```bash
gh auth login
```

### コメントが取得できない

**原因**: PR にコメントがまだ付いていない、または API レート制限

**対処**:
1. ブラウザで PR を確認
2. レート制限を確認: `gh api rate_limit`

## ベストプラクティス

### コミット後に自動確認

コミットを push した後、自動的にレビューコメントを確認：

```bash
git push && gh pr view --comments
```

### 優先度の高いコメントを識別

P1 や P2 などの優先度タグ付きコメントを抽出：

```bash
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
if [[ -z "$REPO" ]]; then
    echo "エラー: リポジトリ情報を取得できません"
    exit 1
fi

gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments" \
  --jq '.[] | select(.body | contains("P1")) | "File: \(.path)\nLine: \(.line // .original_line)\nComment: \(.body)\n---"'
```

## レビューコメントへの返信

### 自動返信ワークフロー

Claude がレビューコメントに対して返信を生成・投稿できます。

**ステップ 1**: コメントを確認
```bash
~/.claude/scripts/fetch_pr_comments.sh
```

**ステップ 2**: Claude に返信を依頼
```
「このレビューコメントに返信してください」
```

**ステップ 3**: Claude が返信内容を生成し、確認を求める

**ステップ 4**: 承認後、自動的に GitHub に返信を投稿

### 手動返信

特定のコメントに直接返信:
```bash
~/.claude/scripts/reply_pr_comments.sh \
  -c <comment_id> \
  -m "返信メッセージ"
```

### ドライラン

実際には投稿せず、返信内容のみプレビュー:
```bash
~/.claude/scripts/reply_pr_comments.sh \
  --dry-run \
  -c <comment_id> \
  -m "返信メッセージ"
```

### 返信機能の制限事項

- **トップレベルコメントのみ対応**: REST API の制限により、返信への返信はできません
- **手動承認が必須**: Claude が生成した返信は、ユーザーの承認後に投稿されます

## 参考資料

- [GitHub CLI ドキュメント](https://cli.github.com/manual/)
- [GitHub REST API](https://docs.github.com/en/rest)
