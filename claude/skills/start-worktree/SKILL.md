---
name: start-worktree
description: |-
  作業内容からブランチ名（worktree 名）を決めて worktree を作成し、セッションをその worktree へ移してプランモードで作業を始める。
  以下の場面で使用：
  - 「worktree で作業を始めて」「worktree 切って〇〇して」等、worktree での作業開始を依頼された場合
  - 「ブランチ名を考えて worktree を作って」等、命名を任された場合
  - "/start-worktree <作業内容>" を手動で実行した場合
---

# Start Worktree

作業内容 → ブランチ名の決定 → worktree 作成 → セッション移動 → プランモード開始、を一気通貫で行う。
ユーザーがブランチ名を考える手間を省くのが目的なので、命名で確認の往復はしない。

## 前提

- worktree の作成は必ず `~/dotfiles/bin/create-worktree` を使う（lazygit と共通の処理）
  - 出力先: `../<repo>_worktree_<ブランチ名の / を _ に置換>`
  - 分岐元: 現在の HEAD
  - 未コミットのファイル・gitignore 対象（`.env` 等）を、ビルド成果物などを除外してコピーする
  - stdout: 作成した worktree の絶対パスのみ / 失敗時は非 0 で終了
- `EnterWorktree` に `name` を渡して作成してはいけない。`.claude/worktrees/` に作られ、命名規則とファイルコピーが適用されないため。必ず `path` で既存 worktree に入る

## 手順

### 1. 作業内容の把握

- 引数やメッセージから作業内容を読み取る。作業内容が空、または命名できないほど曖昧な場合のみ、何をするか質問する
- `git rev-parse --show-toplevel` で git リポジトリ内であることを確認する
- `git rev-parse --path-format=absolute --git-dir --git-common-dir` の 2 行が異なる場合は、すでに worktree の中にいる（`--path-format=absolute` がないとサブディレクトリで相対パスが返り、誤判定する）。そこから作ると名前が入れ子（`repo_worktree_a_worktree_b`）になるため、メインのリポジトリで実行し直すよう伝えて中断する

### 2. ブランチ名の決定

- 形式: `<type>/<kebab-case の英語>`
  - type: `feature` / `fix` / `refactor` / `docs` / `chore`（git-workflow スキルの命名規則）
  - 説明部分は 2〜5 語程度、全体で 40 文字以内を目安にする
  - 例: 「lazygit の除外パターンにテストを追加」→ `feature/lazygit-exclude-pattern-test`
- `git branch -a --format='%(refname:short)'` で既存ブランチを確認し、
  - 既存の命名傾向（チケット番号のプレフィックス等）があれば合わせる
  - 同名ブランチがあれば末尾に `-2` などを付けて衝突を避ける
- `git check-ref-format --branch <name>` で有効な名前か確認する

### 3. worktree の作成

```bash
~/dotfiles/bin/create-worktree <branch>
```

- stdout の最終行を worktree のパスとして扱う
- 失敗した場合は stderr の内容をユーザーに伝えて中断する（勝手に別名でリトライしない）

### 4. セッションの移動

- `EnterWorktree` を `path: <手順 3 のパス>` で呼ぶ
- Bash の `cd` だけではセッションの作業ディレクトリは移らないので、必ずこのツールを使う

### 5. プランモードで作業開始

- 作成結果を簡潔に報告する（ブランチ名、worktree のパス、分岐元のブランチ）
- `EnterPlanMode` を呼ぶ
- プランモードでは、手順 1 の作業内容を前提として調査・計画を進める。作業内容をユーザーに再度聞き直さない

## 後片付け

- 作業終了時に元のディレクトリへ戻る場合は `ExitWorktree` を `action: "keep"` で呼ぶ（`path` で入った worktree は ExitWorktree では削除されない）
- worktree の削除はユーザーが lazygit 等で行う
