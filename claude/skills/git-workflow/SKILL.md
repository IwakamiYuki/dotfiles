---
name: git-workflow
description: |-
  Git 操作の汎用ガイドライン。コミット、PR 作成、ブランチ操作のルールを定義。
  以下の場面で **プロアクティブに** 適用：
  - git add, git commit を実行する場面
  - PR を作成・更新する場面
  - ブランチを作成・切り替える場面
  - GitHub Issues / PR を操作する場面
  - 「コミットして」「push して」「PR 作って」等の依頼
---

# Git Workflow ガイドライン

## コミット操作

### git add と git commit は必ず分離実行

`&&` や `;` での連結は **禁止**。必ず別々のツールコールで実行する。

```
# OK: 別々のツールコール
[Tool Call 1] git add src/foo.ts src/bar.ts
[Tool Call 2] git commit -m "feat: add foo feature"

# NG: 連結実行
git add src/foo.ts && git commit -m "feat: add foo feature"
```

理由: settings.json で `git add` は allow（確認不要）、`git commit` は ask（確認必要）に設定されている。連結すると add の段階でも確認が必要になる。

### Conventional Commits

- 形式: `type: description`
- type: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- 1 行目 50 文字以内
- コミットメッセージは HEREDOC で渡す:

```bash
git commit -m "$(cat <<'EOF'
feat: add user authentication
EOF
)"
```

### コミットの分割

変更内容が複数の論理単位にまたがる場合、コミットを分割する。

- **構造変更**（配置・整理・フォーマット）と **動作変更**（機能追加・修正）は別コミット
- 各コミットは独立して意味を持つ単位にする
- `git diff` や `git status` で変更内容を確認し、関連するファイルごとにグルーピングして add → commit を繰り返す

```
# 例: リファクタリング + 新機能を同時に行った場合
[Tool Call 1] git add src/utils.ts          # リファクタリング対象
[Tool Call 2] git commit -m "refactor: extract helper function"
[Tool Call 3] git add src/feature.ts src/feature.test.ts  # 新機能
[Tool Call 4] git commit -m "feat: add user notification"
```

### git add のルール

- `git add -A`, `git add .`, `git add --all` は禁止（hook でブロック済み）
- ファイルを個別に指定する
- 機密ファイル（.env, credentials 等）は add しない

## GitHub 操作

### gh コマンドを使用

PR 作成・Issue 操作は GitHub CLI (`gh`) を使う。

```bash
# PR 作成（必ず --draft）
gh pr create --draft --title "feat: add feature" --body "$(cat <<'EOF'
## Summary
- ...

## Test plan
- [ ] ...
EOF
)"

# PR 一覧
gh pr list

# Issue 確認
gh issue view 123
```

### PR は必ず draft で作成

- `gh pr create --draft` を常に使用
- ユーザーが明示的に「draft 不要」「ready で」と指示した場合のみ通常 PR

## ブランチ操作

### 命名規則

- `feature/xxx` — 新機能
- `fix/xxx` — バグ修正
- `refactor/xxx` — リファクタリング
- `docs/xxx` — ドキュメント
- `chore/xxx` — 雑務

### ブランチ作成

```bash
git checkout -b feature/add-user-auth
```
