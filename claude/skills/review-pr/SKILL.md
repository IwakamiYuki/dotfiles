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
  2. Verify comment accuracy by checking current code state
  3. Analyze valid comments and generate fix proposals
  4. Apply fixes after user approval
  5. Commit and push changes
  6. Generate reply messages for each comment
  7. Post replies after user approval

  ⚠️ IMPORTANT: Comments may contain incorrect or misleading information.
  Claude MUST verify each comment against the actual code before proceeding.

  IMPORTANT: Before starting this workflow, Claude MUST:
  - Check current context usage (you have access to this information)
  - If usage is 70% or higher, strongly recommend user to run `/compact` first
  - Warn that this workflow requires significant context (50K+ tokens)
  - Ask user if they want to proceed or compact first
allowed-tools: Read, Edit, Write
model: opus
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
3. **コメント検証**: Claude が実際のコード状態を確認し、各コメント内容の正確さをチェック
   - 指摘されている内容が現在のコードに当てはまるか確認
   - 既に修正済みの指摘を識別
   - 不正確または誤解を招くコメントを検出
   - 検証結果をユーザーに報告
4. **有効な修正案生成**: Claude が検証済みの有効な指摘に対する修正案を生成
5. **ユーザー承認**: 修正案を一覧表示し、一括承認を求める
6. **修正適用**: 承認された修正を適用
7. **コミット & プッシュ**: 修正をコミットして PR にプッシュ
8. **返信生成**: 各コメントへの返信文を生成（検証結果に基づいて対応）
9. **返信承認**: 返信文を一覧表示し、一括承認を求める
10. **一括投稿**: 承認された返信を GitHub に投稿

**処理フロー**:
```
fetch comments → verify accuracy → [REPORT VALIDATION] →
analyze valid comments → generate fixes → [USER APPROVAL] →
apply fixes → commit & push → generate replies → [USER APPROVAL] →
post replies
```

**重要な注意事項**:
- Claude がこのスクリプトを実行すると、JSON データが出力されます
- **Claude はコメントを分析する前に、実際のコード状態を確認**します
- 各コメントについて以下を検証:
  - 指摘内容が現在のコード状態に当てはまるか
  - 既に修正済みの内容でないか
  - 不正確な情報でないか
- 検証結果をユーザーに報告し、有効なコメントに対してのみ修正案を生成
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
- ✅ **コンテキスト使用率チェック**: Claude が作業開始前に自分のコンテキスト使用率をチェックし、70% 以上の場合は `/compact` を推奨
- ✅ **コメント内容の検証**: Claude が実際のコード状態を確認し、コメント内容が正確かどうかをチェック
  - 間違った指摘や時代遅れのコメントを識別
  - 既に修正済みの指摘をフィルタリング
  - ユーザーに検証結果を報告
- ✅ **有効なコメントのみで修正案生成**: 検証済みの指摘に対してのみ修正案を生成
- ✅ **テスト環境自動検出**: プロジェクトのテスト充実度を判定
  - テストランナーの検出 (jest, pytest, vitest など)
  - テストファイルの存在確認
  - テスト成功率の確認
- ✅ **TDD ワークフロー対応** (テスト充実プロジェクト):
  - **Red フェーズ**: 修正前にテストを作成し、失敗を確認
  - **Green フェーズ**: 最小限のコードでテスト成功
  - **Refactor フェーズ**: テスト通過後にリファクタリング
- ✅ **テスト不足プロジェクト対応**: 従来の修正案生成フロー
- ✅ **修正案の自動生成**: Claude が有効なすべての指摘に対する修正案を一括生成
- ✅ **コード修正の自動適用**: ユーザー承認後、Claude が修正を適用して commit & push
- ✅ **テスト実行確認**: TDD 実行時に各フェーズでテスト実行を確認
- ✅ **返信文の自動生成**: 各コメントへの返信文を Claude が生成（無効なコメントには説明的な返信）
- ✅ **一括返信投稿**: ユーザー承認後、すべての返信を GitHub に投稿
- ✅ **AI レビュー待機**: push 後に AI レビューを待機し、新しいコメントを自動検出（オプション）
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

**ステップ 0**: コンテキストチェック（Claude が実施）

Claude は作業開始前に、自分のコンテキスト使用率を確認：
- **70% 以上**: ユーザーに `/compact` の実行を強く推奨し、続行の可否を確認
- **70% 未満**: そのまま作業を続行

**重要**: このワークフローは 50K+ トークンを使用するため、コンテキストに余裕がないと途中で中断される可能性があります。

**ステップ 1**: コメント取得
```bash
~/.claude/scripts/auto_reply_pr_comments.sh
```

このスクリプトが JSON 形式でコメントデータを出力します。

**ステップ 2**: Claude がコメント内容を検証

JSON データを読み取り、各コメントについて以下を確認：
- 指摘されているファイルと行番号を確認
- **実際のコード状態を読み込んで検証**
- 指摘内容が現在のコードに当てはまるか判定
- 既に修正済みでないか確認
- 不正確な情報でないか確認

**検証結果をユーザーに報告**:
```
検証結果:

✅ 有効なコメント (修正対象):
- コメント #1 [src/example.js:42]: 変数名が不明瞭 → 修正対象
- コメント #3 [src/utils.js:15]: エラーハンドリング不足 → 修正対象

⚠️ 既に修正済みのコメント:
- コメント #2 [src/styles.css:8]: このスタイル定義は既に削除されています

❌ 不正確なコメント:
- コメント #4 [src/config.js:20]: このファイルには設定が見当たりません

次のステップに進みますか？ (y/n)
```

**ステップ 3**: テスト環境の判定と TDD サイクル開始（テスト充実プロジェクト）

Claude がプロジェクトにテストが存在するか確認：
- テストファイルの存在 (`.test.js`, `.spec.ts`, `test_*.py` など)
- テストランナーの設定 (`jest`, `pytest`, `vitest` など)
- テスト成功率の確認

**テスト充実プロジェクト** の場合:
1. **Red フェーズ**: 修正を適用する前に、**テストを先に作成**
   - 指摘内容に基づいて失敗するテストケースを作成
   - テストが失敗することを確認
2. **Green フェーズ**: 最小限のコードで テストを通す修正を実装
3. **Refactor フェーズ**: テスト通過後、必要に応じてリファクタリング

**テスト不足プロジェクト** の場合:
- 従来の修正案生成フローに進む

**例 (TDD 実行)**:
```
テスト環境を検出しました：pytest を使用しているプロジェクトです。
TDD サイクルで対応します。

【Red フェーズ】
失敗するテストを作成中...
tests/test_utils.py を作成
def test_validate_email_with_special_chars():
    assert validate_email("user+tag@example.com") == True

テストを実行: 失敗 ❌ (期待通り)

【Green フェーズ】
修正案を生成・実装中...
src/utils.py の validate_email 関数を修正

テストを実行: 成功 ✅

【Refactor フェーズ】
リファクタリングが必要か判定...
不要（既に最適な実装）

修正完了 ✅
```

**テスト不足プロジェクト**:
```
テスト環境が見つかりません。
従来の修正案生成フローで対応します。

修正案 #1: src/example.js:42
指摘: 変数名が不明瞭
修正内容: result → validationResult に変更
...
```

**ステップ 4**: ユーザー承認（修正案確認）

Claude が生成した修正案（またはテストコード）をユーザーに表示して承認を求めます。

**テスト充実プロジェクト**:
- 作成したテストコード
- 実装予定のコード修正

**テスト不足プロジェクト**:
- 従来の修正案一覧

**ステップ 5**: 修正を適用 + commit & push

**テスト充実プロジェクト（TDD）**:
ユーザーが承認すると、Claude が TDD サイクルを実行：
1. テストコードを追加 → `git add` でステージング
2. テスト実行 → **失敗することを確認** (Red フェーズ)
3. 修正コードを実装 → `git add` でステージング
4. テスト実行 → **成功することを確認** (Green フェーズ)
5. 必要に応じてリファクタリング (Refactor フェーズ)
6. `git commit -m "test: <テストの説明>\n\nfix: <修正内容の説明>"` でコミット
7. `git push` でリモートに反映

**テスト不足プロジェクト**:
- すべての修正を適用
- `git add` でステージング
- `git commit -m "fix: レビュー指摘事項を修正"` でコミット
- `git push` でリモートに反映

**ステップ 5**: 返信文を一括生成

Claude が各コメントへの返信文を生成し、一覧表示して承認を求めます。
**重要**: 有効なコメントには修正内容の説明を、検証結果の異なるコメントには適切な説明を返信します。

**例**:
```
返信 #1: [123456] src/example.js:42 ✅ 有効
「ご指摘ありがとうございます。result を validationResult に変更しました。」

返信 #2: [discussion_r789012] src/utils.js:15 ✅ 有効
「エラーハンドリングを追加しました。try-catch で例外を捕捉するようにしています。」

返信 #3: [inline_c456] src/styles.css:8 ⚠️ 既に修正済み
「ご指摘の該当コードは既に削除されています。ご確認ください。」

返信 #4: [inline_c789] src/config.js:20 ❌ 不正確
「当該行の確認ができませんでした。詳細をご確認いただき、コメントをご修正ください。」

承認しますか？ (y/n)
```

**注意**: Claude は返信文に AI 署名を含めません。`post_pr_reply.sh` が自動的に追加します。

**ステップ 6**: 返信を一括投稿

ユーザーが承認すると、Claude が `post_pr_reply.sh` を使ってすべての返信を GitHub に投稿します。

**重要**: 返信文に AI 署名を含めないでください。`post_pr_reply.sh` が自動的に AI 署名を追加します。

**ステップ 7**: AI レビュー待機（オプション）

`--wait-for-ai-review` オプションを指定した場合、push 後に AI レビューを待機：

```bash
~/.claude/scripts/wait_and_recheck_pr_comments.sh <pr_number> <repo>
```

- 30 秒 × 20 回（合計 10 分）待機
- 各チェックで新しいコメントがあるか確認
- 新しいコメントを検出したら通知して終了
- ユーザーが「レビューコメントに対応」と再度依頼すると、新しいコメントに対応

## 技術詳細

### 返信投稿の実装

`post_pr_reply.sh` の使い方：

```bash
post_pr_reply.sh <comment_type> <comment_id> <message> [thread_id]
```

**引数**:
- `comment_type`: "inline" または "discussion"
- `comment_id`: コメント ID (inline) または databaseId (discussion)
- `message`: 返信メッセージ（AI 署名を含めないこと）
- `thread_id`: (オプション) discussion の場合、pullRequestReviewThreadId

**重要**: `message` に AI 署名を含めないでください。スクリプトが自動的に以下の署名を追加します：
```
---
🤖 _This reply was generated with AI assistance_
```

**対応コメントタイプ**:
- **インラインコメント**: REST API または GraphQL API
- **Discussion コメント**: GraphQL API (`addPullRequestReviewThreadReply`)
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

- **コメント検証が必須**: Claude がコメント内容を検証してからのみ修正案を生成します
- **手動承認が必須**: Claude が生成した修正案と返信は、ユーザーの承認後に適用・投稿されます
- **AI 署名はデフォルトで追加**: 透明性のため、AI による返信であることを明示します
- **GraphQL API 使用**: Discussion コメントへの返信には GraphQL API が必要です

### 検証時の注意事項

Claude はコメント検証時に以下を確認します：

- **ファイルの存在確認**: 指摘されたファイルが実際に存在するか
- **コード内容確認**: 指摘されている行番号のコード内容が指摘内容と合致するか
- **既修正検出**: 指摘内容が既に修正済みでないか
- **不正確性検出**: コメントの情報が時代遅れまたは誤解を招いていないか
- **修正可能性判定**: 指摘に基づいて実際に修正が可能か

不正確なコメントに対しては、Claude が丁寧な説明とともに返信し、
レビュアーに確認を促します。

### TDD ワークフロー時の注意事項

**テスト環境検出時**:
- テストランナー (jest, pytest, vitest 等) の存在確認
- テストファイルの命名規則検出 (`.test.js`, `.spec.ts`, `test_*.py` 等)
- 既存テストの実行確認（全テストが通過していることを前提）

**TDD サイクルの実行ルール**:
1. **Red フェーズ**:
   - テストを作成してステージング
   - テスト実行 → **失敗を確認**（継続条件）
   - 失敗が確認できない場合は修正案を見直す

2. **Green フェーズ**:
   - 最小限のコードで修正
   - テスト実行 → **成功を確認**（継続条件）
   - テストが通らない場合は修正を繰り返す

3. **Refactor フェーズ**:
   - テスト成功後、必要に応じてリファクタリング
   - リファクタリング後もテスト実行で成功を確認

**重要**:
- 修正を適用する **前に** テストを作成する（TDD の原則）
- 各フェーズでテスト実行を確認してから次に進む
- テスト失敗時は修正案を見直す

## 参考資料

- [GitHub CLI ドキュメント](https://cli.github.com/manual/)
- [GitHub REST API](https://docs.github.com/en/rest)
