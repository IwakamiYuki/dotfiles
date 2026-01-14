---
name: review-pr
description: |-
  Automatically handle Pull Request review comments from GitHub. Use this skill when:
  - User says "レビューコメントに対応" / "respond to review comments"
  - User says "レビューコメントを確認して修正" / "check and fix review comments"
  - User says "PR のフィードバックに対応" / "address PR feedback"
  - User mentions fixing review feedback on a PR

  Workflow:
  1. Fetch review comments (inline, discussion, general)
  2. Analyze all comments and generate fix proposals
  3. Apply fixes after user approval
  4. Commit and push changes
  5. Generate reply messages for each comment
  6. Post replies after user approval

  This is a fully automated workflow with user approval checkpoints.
allowed-tools: Read, Edit, Write
---

# PR レビューコメント確認スキル

**IMPORTANT**: このスキルは、ユーザーが PR のレビューコメントを確認したい際に使用してください。

GitHub の Pull Request に対するレビューコメントを取得し、見やすく整形して表示します。

## 発動条件

以下のフレーズを含む依頼があった場合、このスキルを使用：

**日本語**:
- レビューコメントに対応
- レビューコメントを確認して修正
- PR のフィードバックに対応
- レビュー指摘を修正して返信
- コメントに対応してください

**英語**:
- respond to review comments
- address review feedback
- fix and reply to comments
- handle PR feedback

## 使用方法

ユーザーが「レビューコメントに対応」と依頼すると、このスキルが自動的に起動します。

### 自動実行フロー

**完全自動化** で修正から返信まで一気に実行：

```bash
~/.claude/scripts/auto_reply_pr_comments.sh
```

このスクリプトは以下を自動で処理します：

1. **コメント取得**: 直前 push 以降のレビューコメントを JSON 形式で取得
2. **Claude 連携**: コメントデータを Claude に渡す
3. **修正案生成**: Claude がすべての指摘に対する修正案を生成
4. **ユーザー承認**: 修正案を一覧表示し、一括承認を求める
5. **修正適用**: 承認された修正を適用
6. **コミット & プッシュ**: 修正をコミットして PR にプッシュ
7. **返信生成**: 各コメントへの返信文を生成
8. **返信承認**: 返信文を一覧表示し、一括承認を求める
9. **一括投稿**: 承認された返信を GitHub に投稿

**処理フロー**:
```
fetch comments → analyze → generate fixes → [USER APPROVAL] →
apply fixes → commit & push → generate replies → [USER APPROVAL] →
post replies
```

**重要な注意事項**:
- Claude がこのスクリプトを実行すると、JSON データが出力されます
- Claude はその JSON を読み取り、修正案と返信文を生成します
- ユーザーは修正案と返信文を確認し、承認します
- 承認後、Claude がコードを修正してコミット・プッシュし、返信を投稿します


## 機能

- ✅ **自動 PR 検出**: 現在のブランチから PR 番号を自動取得
- ✅ **動的リポジトリ検出**: 現在のリポジトリを自動取得（フォークにも対応）
- ✅ **直前 push 以降のコメント自動抽出**: デフォルトで直前 push 時刻以降のコメントのみ表示
- ✅ **複数種類のコメント取得**:
  - インラインコメント (Pull Request Review Comments API)
  - Discussion コメント (GraphQL API)
  - 一般コメント (Issue Comments API)
  - レビューコメント (Pull Request Reviews API)
- ✅ **コンテキスト使用率チェック**: 作業開始前にコンテキスト使用率をチェックし、70% 以上の場合は `/compact` を推奨
- ✅ **修正案の自動生成**: Claude がすべての指摘に対する修正案を一括生成
- ✅ **コード修正の自動適用**: ユーザー承認後、Claude が修正を適用して commit & push
- ✅ **返信文の自動生成**: 各コメントへの返信文を Claude が生成
- ✅ **一括返信投稿**: ユーザー承認後、すべての返信を GitHub に投稿
- ✅ **AI 署名**: 返信に AI による生成であることを明示


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


## Claude による自動対応ワークフロー

ユーザーが「レビューコメントに対応」と依頼すると、Claude が以下を自動実行します：

**ステップ 0**: コンテキストチェック

作業開始前に、コンテキスト使用率を自動チェック：
- **70% 以上**: 警告を表示し、`/compact` の実行を推奨
- **70% 未満**: そのまま作業を続行

これにより、作業中のコンテキスト不足を防止します。

**ステップ 1**: コメント取得
```bash
~/.claude/scripts/auto_reply_pr_comments.sh
```

このスクリプトが JSON 形式でコメントデータを出力します。

**ステップ 2**: Claude がコメントを分析

JSON データを読み取り、すべてのレビュー指摘を分析します。

**ステップ 3**: 修正案を一括生成

Claude がすべての指摘に対する修正案を生成し、ユーザーに一覧表示して承認を求めます。

**例**:
```
修正案 #1: src/example.js:42
指摘: 変数名が不明瞭
修正内容: result → validationResult に変更

修正案 #2: src/utils.js:15
指摘: エラーハンドリングが不足
修正内容: try-catch ブロックを追加

承認しますか？ (y/n)
```

**ステップ 4**: 修正を適用 + commit & push

ユーザーが承認すると、Claude が：
- すべての修正を適用
- `git add` でステージング
- `git commit -m "fix: レビュー指摘事項を修正"` でコミット
- `git push` でリモートに反映

**ステップ 5**: 返信文を一括生成

Claude が各コメントへの返信文を生成し、一覧表示して承認を求めます。

**例**:
```
返信 #1: [123456] src/example.js:42
「ご指摘ありがとうございます。result を validationResult に変更しました。」

返信 #2: [discussion_r789012] src/utils.js:15
「エラーハンドリングを追加しました。try-catch で例外を捕捉するようにしています。」

承認しますか？ (y/n)
```

**ステップ 6**: 返信を一括投稿

ユーザーが承認すると、Claude が `post_pr_reply.sh` を使ってすべての返信を GitHub に投稿します。

## 技術詳細

### 返信投稿の実装

`post_pr_reply.sh` を使用して、インラインコメントと Discussion コメントの両方に対応：

**インラインコメント**: REST API または GraphQL API
**Discussion コメント**: GraphQL API (`addPullRequestReviewThreadReply`)
- `auto_reply_pr_comments.sh` が各コメントの `threadId` (pullRequestReviewThreadId) を取得
- `post_pr_reply.sh` に `threadId` を渡すことで、追加の API コールなしで返信可能
- `threadId` が指定されない場合は、自動的に GraphQL で取得（後方互換性）

### JSON データ構造

`auto_reply_pr_comments.sh` が出力する JSON には以下の情報が含まれます：

**inline_comments**:
- `id`: コメント ID
- `path`: ファイルパス
- `line`: 行番号
- `user.login`: 作成者
- `body`: コメント本文

**discussion_comments**:
- `databaseId`: コメントの database ID
- `threadId`: pullRequestReviewThreadId（返信に必須）
- `path`: ファイルパス
- `position`: 行位置
- `author.login`: 作成者
- `body`: コメント本文

### AI 署名

デフォルトで、返信の末尾に以下の署名が自動追加されます：

```
---
🤖 _This reply was generated with AI assistance_
```

### 制限事項

- **手動承認が必須**: Claude が生成した修正案と返信は、ユーザーの承認後に適用・投稿されます
- **AI 署名はデフォルトで追加**: 透明性のため、AI による返信であることを明示します
- **GraphQL API 使用**: Discussion コメントへの返信には GraphQL API が必要です

## 参考資料

- [GitHub CLI ドキュメント](https://cli.github.com/manual/)
- [GitHub REST API](https://docs.github.com/en/rest)
