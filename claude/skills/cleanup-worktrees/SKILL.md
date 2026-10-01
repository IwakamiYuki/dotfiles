---
name: cleanup-worktrees
description: |-
  merge 済みブランチの worktree を検知し、承認後に worktree とブランチをまとめて削除する。
  以下の場面で使用：
  - 「merge 済みの worktree を消して」「worktree を掃除して」「不要な worktree を削除して」等の依頼
  - PR が merge された後の後片付けを依頼された場合
  - "/cleanup-worktrees" を手動で実行した場合
---

# Cleanup Worktrees

merge 済みの worktree を検知 → 一覧提示 → 一括承認 → 削除、を行う。`start-worktree` と対になるスキル。

## 前提

- 検知は worktree の **HEAD SHA** で行い、ブランチ名・ディレクトリ名（命名規則）には依存しない。手動作成の worktree や、後からリネームしたブランチも対象になる
  - `gh`: HEAD を含む PR が merged かつ `head.sha == HEAD`。squash / rebase merge も検知できる
  - `git`（`gh` が使えない場合のフォールバック）: HEAD が既定ブランチの merge commit の第 2 親。squash / rebase merge は検知できない
- どちらも「HEAD の内容は merge 済み」なので、未 push コミットの確認は不要
- 未コミットの変更があってもスキップしない。`create-worktree` が untracked / ignored ファイルをコピーするため、ほぼ全 worktree に何かしら残っている。代わりに承認時に件数を見せる
- スクリプトは `~/.claude/skills/cleanup-worktrees/bin/` にある

## 手順

### 1. 検知

```bash
~/.claude/skills/cleanup-worktrees/bin/scan-worktrees
```

- 削除はしない。stdout は JSON、stderr は進捗・警告
- `candidates`: 削除候補 / `excluded`: merge 済みだが除外したもの（保護ブランチ・現在のセッションの worktree・locked）
- stderr に「gh が使えない」警告が出た場合は、squash merge を検知できないことをユーザーに伝える
- `candidates` が空なら、その旨を伝えて終了する

### 2. 一覧提示と承認

表で提示し、一括で承認を取る。除外したいものがあれば指定してもらう。

```
削除対象(2)
  branch              worktree                    PR            未コミット
  feature/add-login   ../app_worktree_feature_…   #123 merged   tracked 2 / untracked 5
  fix/typo            ../app_worktree_fix_typo    #130 merged   なし

除外(1)
  master   保護ブランチ
```

- `tracked_changes` は merge 後に手を入れた本物の作業の可能性があるため、目立たせる。0 でなければ削除前に patch を退避する旨も伝える
- `untracked_files` はコピー由来が大半なので、件数のみ
- `origin` が `manual` のもの（`create-worktree` 由来でない）は、その旨を併記する
- `branch` が null（detached HEAD）のものは、worktree のみ削除しブランチは消さない旨を併記する

### 3. 削除

承認された worktree ごとに実行する。1 件が失敗しても残りは続ける。

```bash
~/.claude/skills/cleanup-worktrees/bin/remove-worktree <path> <branch|-> <merged_via>
```

- `branch` が null の場合は `-` を渡す
- `merged_via` は候補の `merged_via`（`gh` / `git`）をそのまま渡す
- スクリプトが行うこと:
  1. tracked の変更があれば `git diff HEAD` を `<メインの repo>/.claude/tmp/worktree-patches/` に退避
  2. `git worktree remove --force`（未コミット変更は承認済みのため）→ `git worktree prune`
  3. `git branch -d`。拒否された場合のみ、`merged_via` が `gh` なら `-D`（squash merge では `-d` が拒否されるため）。`git` 判定では `-D` にせず失敗として報告する
- stdout は 1 行 JSON。`error` が null でなければ失敗として扱う

### 4. 報告

- 削除したもの: `branch → 削除時の HEAD SHA`（誤削除時に `git branch <name> <sha>` で復元できるよう必ず載せる）
- 退避した patch のパス
- 失敗したものと理由

## 注意

- メインの worktree、保護ブランチ（master / main / develop 等）、現在のセッションが入っている worktree は削除しない
- 現在のセッションの worktree を消したい場合は、`ExitWorktree` でメインに戻ってから再実行するよう伝える
- `--force` を付けるのは承認後の `remove-worktree` の中だけ。それ以外の場面で使わない
- リモートブランチは削除しない（GitHub の "Automatically delete head branches" に任せる）
