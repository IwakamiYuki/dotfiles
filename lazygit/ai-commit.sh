#!/usr/bin/env bash
set -eo pipefail  # -u を削除（SIGPIPE 対策）

# ステージされているかチェック
if git diff --staged --quiet 2>/dev/null; then
  echo "❌ ステージされている変更がありません。"
  exit 1
fi

echo "🤖 コミットメッセージを考え中..."
echo

# diff を取得して codex に標準入力で渡す（codex 内の git 実行に依存しない）
STAGED_DIFF="$(git diff --staged)"

PROMPT='以下は git diff --staged の出力です。この変更に基づいて、適切なコミットメッセージを日本語で3つ提案してください。Conventional Commits の形式（feat:, fix:, refactor:, docs:, test:, chore:, style:, perf: のいずれか）で、スコープは含めず "type: description" の形式で出力してください。各提案は 1 行ずつ、番号や前置き・説明・コードブロックなしで、純粋に 3 行だけ出力してください。'

# stderr も取り込み、ログとして残す（デバッグ用）
LOG_FILE="$(mktemp -t ai-commit.XXXXXX.log)"
RAW_RESPONSE="$(
  printf '%s\n\n--- git diff --staged ---\n%s\n' "$PROMPT" "$STAGED_DIFF" \
    | PATH=/opt/homebrew/bin:$PATH codex exec - 2>"$LOG_FILE" || true
)"

# ANSI エスケープシーケンスと CR を除去
CLEAN_RESPONSE="$(printf '%s' "$RAW_RESPONSE" | sed -E $'s/\x1B\\[[0-9;]*[A-Za-z]//g; s/\r//g')"

# Conventional Commits 形式でフィルタリング（先頭空白を許容）
CANDIDATES="$(printf '%s\n' "$CLEAN_RESPONSE" | grep -E '^[[:space:]]*(feat|fix|refactor|docs|test|chore|style|perf):' | sed -E 's/^[[:space:]]+//' | head -3 || true)"

if [ -z "$CANDIDATES" ]; then
  echo "❌ コミットメッセージを考えられませんでした。"
  echo
  echo "📋 codex の応答（先頭 30 行）:"
  printf '%s\n' "$CLEAN_RESPONSE" | head -30
  echo
  if [ -s "$LOG_FILE" ]; then
    echo "📋 codex stderr（先頭 20 行）:"
    head -20 "$LOG_FILE"
  fi
  echo
  echo "ログ全文: $LOG_FILE"
  exit 1
fi
rm -f "$LOG_FILE"

echo "✨ 🤖 候補を用意しました！"
echo

# fzf で候補を選択
base_msg="$(echo "$CANDIDATES" | fzf \
  --prompt="💬 コミットメッセージを選択 (Esc でキャンセル)> " \
  --height=40% \
  --border=rounded \
  --color="fg:#ebdbb2,bg:#282828,hl:#fe8019,fg+:#fbf1c7,bg+:#3c3836,hl+:#fe8019" \
  --color="info:#83a598,prompt:#fe8019,pointer:#fe8019,marker:#fe8019,spinner:#fe8019" \
  --header="↑↓ or jk: 選択 | Enter: 決定 | Esc: キャンセル" \
  --reverse \
  --pointer="▶" \
  --marker="✓" \
  --bind="j:down,k:up"
)" || {
  echo "キャンセルしました。"
  exit 0
}

if [ -z "$base_msg" ]; then
  echo "キャンセルしました。"
  exit 0
fi

# コミットメッセージファイルを作成
tmpfile="$(mktemp)"
echo "$base_msg" > "$tmpfile"

# コメント行は落としてクリーンなメッセージファイルを作る
cleanfile="${tmpfile}.clean"
grep -vE '^\s*#' "$tmpfile" >"$cleanfile"

# 空チェック
if ! grep -q '[^[:space:]]' "$cleanfile"; then
  echo "❌ コミットメッセージが空のため中止します。"
  rm -f "$tmpfile" "$cleanfile"
  exit 1
fi

echo
echo "📝 git commit を実行します..."
git commit -F "$cleanfile"

status=$?
rm -f "$tmpfile" "$cleanfile"

echo
if [ "$status" -eq 0 ]; then
  echo "✅ コミット完了！"
else
  echo "❌ コミット失敗（終了コード: $status）"
fi
exit "$status"
