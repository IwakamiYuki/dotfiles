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
  5. Commit changes (do NOT push yet)
  6. Record skipped findings in the PR description BEFORE pushing
     (AI reviewers start reviewing the moment you push, so the note must land first)
  7. Push
  8. Generate reply messages for each comment
  9. Post replies after user approval

  ⚠️ IMPORTANT: Comments may contain incorrect or misleading information.
  Claude MUST verify each comment against the actual code before proceeding.

  ⚠️ IMPORTANT: AI reviewers often over-report. A correct comment is not automatically
  worth fixing. Claude MUST judge whether each comment is worth acting on in THIS PR
  (out-of-scope / nitpick / YAGNI findings are skipped with an explanatory reply),
  and MUST NOT reply to non-actionable auto-generated summary comments.
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
5. **ユーザー承認**: 修正案を一覧表示し、AskUserQuestion で 1 件ずつ承認を求める
6. **修正適用**: 承認された修正を適用
7. **コミット**: 修正をコミット（この時点では push しない）
8. **PR 本文更新**: 対応を見送った指摘とその理由を PR 説明に追記（再指摘の抑止）
9. **プッシュ**: PR 本文の更新後に push（AI レビューが新しい本文を読める状態にする）
10. **返信生成**: 各コメントへの返信文を生成（検証結果に基づいて対応）
11. **返信承認**: 返信文を一覧表示し、AskUserQuestion で一括承認を求める
12. **一括投稿**: 承認された返信を GitHub に投稿

**処理フロー**:
```
fetch comments → verify accuracy → [REPORT VALIDATION] →
analyze valid comments → generate fixes → [USER APPROVAL] →
apply fixes → commit → update PR description with skipped findings → push →
generate replies → [USER APPROVAL] → post replies
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

**ステップ 1**: コメント取得
```bash
~/.claude/scripts/auto_reply_pr_comments.sh
```

このスクリプトが JSON 形式でコメントデータを出力します。

**CRITICAL: スクリプト出力の完全取得ルール**

Bash ツールの出力は途中で切れる（truncated）ことがあります。**出力が切れた場合、切れた状態のまま次のステップに進むことは禁止**です。

**対処方法**: 出力が truncated された場合は、`--output` オプションでファイルに出力し、Read ツールで全文を取得してください：
```bash
~/.claude/scripts/auto_reply_pr_comments.sh --output .claude/tmp/pr-comments-output.txt
```
その後、Read ツールでファイルを読み取ります。出力が大きい場合は offset/limit で分割読み込みしてください。

**通常時**: 出力が完全に取得できた場合（truncated でない場合）は、そのまま使用して問題ありません。リダイレクトは不要です。

**ステップ 2**: Claude がコメント内容を検証

JSON データを読み取り、各コメントについて以下を確認：
- 指摘されているファイルと行番号を確認
- **実際のコード状態を読み込んで検証**
- 指摘内容が現在のコードに当てはまるか判定
- 既に修正済みでないか確認
- 不正確な情報でないか確認

**検証結果をユーザーに報告**（全コメントを漏れなく分類すること）:
```
検証結果:

✅ 有効なコメント (修正対象):
- コメント #1 [src/example.js:42]: 変数名が不明瞭 → 修正対象
- コメント #3 [src/utils.js:15]: エラーハンドリング不足 → 修正対象

⚠️ 既に修正済みのコメント:
- コメント #2 [src/styles.css:8]: このスタイル定義は既に削除されています

❌ 不正確なコメント:
- コメント #4 [src/config.js:20]: このファイルには設定が見当たりません

💬 修正不要のコメント (返信のみ):
- コメント #5 [General]: 設計方針についての質問 → 返信で回答
- コメント #6 [src/app.js:10]: LGTM → 返信でお礼
- コメント #7 [src/legacy.js:88]: 既存コードへの nitpick → スコープ外のため見送り

🔇 返信対象外 (サマリ等):
- コメント #8 [General]: CodeRabbit の PR サマリ → 指摘なしのため返信しない

次のステップに進みますか？ (y/n)
```

**CRITICAL**: 取得した全コメントがいずれかのカテゴリに分類されていることを確認してください。分類漏れは返信漏れにつながります。

**⚠️ やりすぎ注意: 「正しい指摘」と「対応すべき指摘」は別物**

AI レビュアー（CodeRabbit、Copilot、Claude review など）は、事実としては正しいが
この PR で対応する価値のない指摘を大量に出す傾向があります。
「指摘が正しい」ことは「修正する」理由になりません。以下は原則として見送り、
返信で理由を伝えるに留めてください（`💬 修正不要のコメント` に分類）:

- **スコープ外**: この PR の変更が引き起こしたものではない、既存コードへの指摘
- **nitpick**: 命名の好み、コメント追加の提案、軽微なスタイル
- **過剰な防御**: 実際には起こり得ない入力への null チェック、想定されない例外処理
- **YAGNI**: 現時点で必要のない抽象化・汎用化・設定値の外出し提案
- **過剰なテスト要求**: 些細なロジックや自明なコードへのテスト追加要求
- **プロジェクト規約との衝突**: 既存コードベースの慣習に反する一般論的な提案

逆に、以下は指摘の粒度に関わらず必ず対応します:

- バグ・不具合（誤ったロジック、境界値の取りこぼし）
- セキュリティ上の問題
- データ破壊・不可逆な操作のリスク
- この PR の変更が直接生んだ設計上の破綻

**判断基準**: 迷ったら「この PR の変更が引き起こした問題か？」を第一に問うこと。
対応数が多いほど良いレビュー対応ではありません。PR を肥大化させ、
レビュアーの再確認コストを増やすことのほうが害になります。

**MUST**: 見送る場合も、ユーザーへの報告時に見送り対象と理由を明示してください。
ユーザーが「これは直して」と指示した場合は、その判断に従います。

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

Claude が生成した修正案（またはテストコード）をユーザーに表示し、**AskUserQuestion ツールで 1 件ずつ**承認を求めます。

**CRITICAL: 自由入力で承認を待たない**
「承認しますか？ (y/n)」のようにテキストで問いかけて待つと、Claude Code の状態が DONE（完了）になり、
tmux sidebar などの通知で「入力待ち」を検知できません。承認は必ず AskUserQuestion で取ってください
（質問中は WAITING として検知されます）。

**手順**:
1. 修正案の全体像（件数と各指摘の要約）をテキストで先に表示する
2. 各修正案を **1 質問 = 1 修正案** にして AskUserQuestion で確認する
   - 1 回の呼び出しに入れられるのは最大 4 問。5 件以上あるときは 4 件ずつ複数回に分ける
   - `header`: 指摘の識別（例: `#1 example.js`。12 文字以内）
   - `question`: ファイル:行、指摘の要旨、修正内容を 1〜2 文で書く（詳細な diff は事前にテキストで表示しておく）
   - `options`（推奨案を先頭にして `(Recommended)` を付ける）:
     - `修正を適用` — 修正案どおりに対応する
     - `見送る` — 対応せず、理由を添えて返信する（PR 本文の「対応方針の補足」に追記）
     - `別案で対応` — 方針を変えたい。選択後に自由入力（Other）で内容を受け取る
   - 見送りが妥当と判断した指摘は `見送る` を推奨にする
3. 「その他（自由入力）」で返ってきた内容は、その指摘の修正方針の指示として扱う
4. 全件の回答が出揃ってから、ステップ 5 に進む

**テスト充実プロジェクト**: 質問の前に、作成したテストコードと実装予定のコード修正をテキストで表示する
**テスト不足プロジェクト**: 質問の前に、従来の修正案一覧をテキストで表示する

**あわせて確認するもの**: 対応を見送る指摘がある場合、PR 本文に追記する
「対応方針の補足」の文面を、最後の質問として AskUserQuestion で確認してください
（`この文面で追記` / `修正したい`。文面は質問の前にテキストで表示しておく）。
push 前に本文を更新する必要があるため、承認をここで済ませておきます。

**ステップ 5**: 修正を適用してコミット（push はまだしない）

**CRITICAL**: このステップでは push しません。
push すると AI レビューが即座に走るため、先にステップ 6 で PR 本文を更新します。

**テスト充実プロジェクト（TDD）**:
ユーザーが承認すると、Claude が TDD サイクルを実行：
1. テストコードを追加 → `git add` でステージング
2. テスト実行 → **失敗することを確認** (Red フェーズ)
3. 修正コードを実装 → `git add` でステージング
4. テスト実行 → **成功することを確認** (Green フェーズ)
5. 必要に応じてリファクタリング (Refactor フェーズ)
6. `git commit -m "test: <テストの説明>\n\nfix: <修正内容の説明>"` でコミット

**テスト不足プロジェクト**:
- すべての修正を適用
- `git add` でステージング
- `git commit -m "fix: レビュー指摘事項を修正"` でコミット

**ステップ 6**: 見送り事項を PR 本文に追記（push 前）

**なぜ必要か**: スレッドへの返信は AI レビュアーの次回レビュー時のコンテキストに
含まれないことが多く、**同じ指摘が何度も繰り返されます**。
PR 本文は毎回のレビュー入力に含まれるため、ここに方針を書くことで再指摘を抑止します。

**CRITICAL: 必ず push の前に実施すること**

現在の AI レビュアーは push を検知して**即座に**レビューを開始します。
push 後に本文を更新しても、そのレビューは古い本文を読んでいるため抑止が効かず、
見送ると決めた指摘がもう一度上がってきます。
**本文を先に更新し、レビュアーが新しい本文を読める状態にしてから push** してください。

**実施条件**: 対応を見送ったコメントが 1 件以上ある場合に実施します。
見送りが 0 件の場合はこの手順を飛ばして push に進みます。

**CRITICAL: PR 本文を上書きしないこと**

`gh pr edit --body` は本文を**全文置換**します。既存の説明を消さないため、
必ず現在の本文を取得し、管理セクションのみを差し替えてください。

```bash
# 1. 現在の本文を取得（ファイル経由で扱う。直接埋め込むと引用符や改行で壊れる）
gh pr view <pr_number> --json body -q .body > .claude/tmp/pr-body.md

# 2. 管理セクションを追記または更新（下記マーカー方式）

# 3. 本文を更新
gh pr edit <pr_number> --body-file .claude/tmp/pr-body.md
```

**管理セクションの形式**（HTML コメントのマーカーで囲む）:

```markdown
<!-- review-scope:start -->
## 対応方針の補足

以下のレビュー指摘は内容を確認したうえで、本 PR では意図的に対応を見送っています。
再度の指摘は不要です。

- **`src/legacy.js` の命名規則**: 本 PR の変更範囲外の既存実装のため、別途対応します
- **`validateInput` への null チェック追加**: 呼び出し元が限定されており該当ケースは発生しません
- **`formatDate` のテスト追加**: 自明な処理のため本 PR では追加しません

<!-- review-scope:end -->
```

**運用ルール**:
- マーカーが**既にある場合**: その区間を新しい内容で置き換える（項目は累積させる）
- マーカーが**ない場合**: 本文の末尾に追記する
- マーカー外の既存本文は**一切変更しない**
- 見送り理由は 1 行で簡潔に。レビュアーが読んで納得できる粒度にする
- ユーザーへの報告時に、PR 本文へ追記した旨と内容を伝える

**注意**: この追記は AI レビュアーへの申し送りであると同時に、
人間のレビュアーや将来の自分への記録にもなります。
「なぜ直さなかったか」が PR に残ることに価値があります。

**ステップ 7**: push

PR 本文の更新が完了してから、リモートに反映します。

```bash
git push
```

これにより、push を検知して走る AI レビューは、更新後の PR 本文
（見送り方針を含む）を読んだ状態でレビューを開始します。

**ステップ 8**: 返信文を一括生成

Claude が**取得した全コメント**に対して返信文を生成し、一覧表示したうえで、**AskUserQuestion ツールで**承認を求めます
（テキストで「承認しますか？」と聞いて待たない。理由はステップ 4 の CRITICAL を参照）。

**CRITICAL: 指摘コメントへの返信は必須**
- コード修正を行ったコメントだけでなく、**すべての指摘コメントに返信**してください
- 修正対象外のコメント（質問、感想、称賛、情報提供など）にも適切な返信を生成してください
- 返信が不要に見えるコメントでも、最低限「ご確認ありがとうございます」等の応答を返してください
- 対応を見送ったコメントも、理由を添えて返信してください（無言でスルーしない）

**例外: 指摘ではない自動生成コメントには返信しない**

AI レビュアーが投稿する「サマリ」系のコメントは、レビュー指摘ではなく PR の説明です。
これらに返信してもレビュアーにとって価値がなく、PR のノイズを増やすだけなので **返信しません**。

返信対象外の例:
- PR サマリ / Summary / 変更内容の要約コメント
- Walkthrough / 変更ファイル一覧 / 変更点の解説
- シーケンス図・アーキテクチャ図などの自動生成図表
- レビュー開始・完了の通知（"Review in progress"、"Actionable comments posted: 0" など）
- ボットの設定案内・チップス・広告的な定型文

**判定基準**: そのコメントに「対応すべき指摘」が 1 つも含まれていなければ返信不要です。
サマリ本文の中に具体的な指摘が混ざっている場合は、その指摘部分にのみ返信してください。

**MUST**: 返信しないと判断したコメントは、ユーザーへの報告時に
「返信対象外（サマリコメント）」として明示し、分類漏れと区別できるようにしてください。

**コメント種別ごとの返信方針**:
- **修正対応したコメント**: 修正内容の説明
- **既に修正済みのコメント**: 修正済みであることの説明
- **不正確なコメント**: 丁寧な説明と確認の依頼
- **質問・議論コメント**: 質問への回答や議論への参加
- **称賛・感想コメント**: お礼や同意の返信
- **情報提供コメント**: 情報への感謝と対応方針の説明
- **対応を見送ったコメント**: 見送る理由を添えて返信（無言でスルーしない）

**対応を見送ったコメントへの返信ルール**:

指摘そのものを否定せず、「この PR では対応しない」理由を具体的に伝えます。
「妥当な指摘だが今回の PR のスコープ外」という形が基本です。

```
（スコープ外）
「ご指摘ありがとうございます。こちらは本 PR の変更範囲外の既存実装のため、
今回は見送らせてください。別途対応を検討します。」

（nitpick）
「ご提案ありがとうございます。現状の記述でも可読性に問題はないと判断し、
今回は変更を見送ります。」

（過剰な防御 / YAGNI）
「ご指摘ありがとうございます。この関数の呼び出し元は限定されており
該当ケースは発生しないため、今回はチェックを追加せず進めます。」
```

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

返信 #5: [issue_c101] (General comment) 💬 修正不要
「ご質問ありがとうございます。この設計方針は〇〇の理由で採用しています。」

返信 #6: [inline_c102] src/app.js:10 💬 修正不要
「ご確認ありがとうございます！」

```

**返信の承認方法**（返信は件数が多くなりがちなので、修正案と違い 1 問にまとめる）:

返信一覧を上記の形式でテキスト表示した直後に、AskUserQuestion を 1 問だけ呼びます。
- `header`: `返信投稿`
- `question`: `上記 N 件の返信を GitHub に投稿しますか？`
- `options`:
  - `すべて投稿 (Recommended)` — 一覧のまま投稿する
  - `一部を修正` — 修正したい返信を選び直す。選択後に自由入力（Other）で対象番号と修正内容を受け取る
  - `投稿しない` — 投稿せず終了する

「一部を修正」の場合は、該当の返信だけ直して一覧を再表示し、もう一度 AskUserQuestion で確認します。

**注意**: Claude は返信文に AI 署名を含めません。`post_pr_reply.sh` が自動的に追加します。

**ステップ 9**: 返信を一括投稿

ユーザーが承認すると、Claude が各コメントに対して以下のコマンドを実行して GitHub に投稿します。

**MUST**: 返信投稿には必ず `~/.claude/scripts/post_pr_reply.sh` を使用してください。
**MUST NOT**: `gh api`、`gh pr comment`、その他の直接 API コールは使用禁止です。

```bash
# インラインコメントへの返信
~/.claude/scripts/post_pr_reply.sh inline <comment_id> "<返信メッセージ>"

# Discussion コメントへの返信
~/.claude/scripts/post_pr_reply.sh discussion <databaseId> "<返信メッセージ>" <threadId>
```

**重要**: 返信文に AI 署名を含めないでください。`post_pr_reply.sh` が自動的に AI 署名を追加します。

**ステップ 10**: AI レビュー待機（オプション）

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
- **承認は AskUserQuestion で取る**: 自由入力で待つと状態が DONE になり、入力待ちを検知できません。修正案は 1 件ずつ、返信は一括で確認します
- **AI 署名はデフォルトで追加**: 透明性のため、AI による返信であることを明示します
- **GraphQL API 使用**: Discussion コメントへの返信には GraphQL API が必要です

### スクリプト出力の完全取得（全ステップ共通）

**すべてのスクリプト実行**において、Bash ツールの出力が途中で切れる（truncated）リスクがあります。

**出力が truncated された場合の対処**:
1. `--output` オプション付きでスクリプトを再実行し、ファイルに出力を保存する
   ```bash
   ~/.claude/scripts/auto_reply_pr_comments.sh --output .claude/tmp/pr-comments-output.txt
   ```
2. Read ツールでファイル全体を読み取る（offset/limit で分割読み込み可能）

**禁止事項**: 出力の一部だけ見て判断しない。特に JSON データは完全な形でパースする必要がある

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
