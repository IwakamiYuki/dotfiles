#!/usr/bin/env bash
set -eo pipefail  # -u を削除（SIGPIPE 対策）

# ステージされているかチェック
if git diff --staged --quiet 2>/dev/null; then
  echo "❌ ステージされている変更がありません。"
  exit 1
fi

echo "🤖 コミットメッセージを考え中..."
echo

# AI で候補生成（codex が git diff を直接取得）
RAW_RESPONSE="$(
  PATH=/opt/homebrew/bin:$PATH codex exec \
    "現在のリポジトリで git diff --staged を実行して、ステージされた変更を確認してください。その変更に基づいて適切なコミットメッセージを日本語で3つ提案してください。Conventional Commitsの形式（feat:, fix:, refactor: など）で、スコープは含めず type: description の形式で出力してください。各提案は1行ずつ、番号や説明なしで出力してください。" \
    2>/dev/null || true
)"

# Conventional Commits 形式でフィルタリング
CANDIDATES="$(echo "$RAW_RESPONSE" | grep -E '^(feat|fix|refactor|docs|test|chore|style|perf):' | head -3 || true)"

# フィルタリング後に候補がない場合、最初の3行を使用（形式チェックを緩和）
if [ -z "$CANDIDATES" ]; then
  CANDIDATES="$(echo "$RAW_RESPONSE" | grep -v '^$' | head -3 || true)"
fi

if [ -z "$CANDIDATES" ]; then
  echo "❌ コミットメッセージを考えられませんでした。"
  echo "📋 AI の応答: $RAW_RESPONSE"
  exit 1
fi

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
