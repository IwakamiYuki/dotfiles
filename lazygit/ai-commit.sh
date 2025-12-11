#!/usr/bin/env bash
set -euo pipefail

# ステージされているかチェック
if git diff --staged --quiet; then
  echo "❌ ステージされている変更がありません。"
  exit 1
fi

echo "🤖 Codex (gpt-5.1-codex) でコミットメッセージを生成中..."
echo

DIFF="$(git diff --staged 2>/dev/null | head -c 10000)"

# Codex で候補生成
CANDIDATES="$(
  printf '%s\n' "$DIFF" |
    codex exec -m gpt-5.1-codex \
      "以下は git diff --staged の出力です。リポジトリ全体のコンテキストを考慮しつつ、このステージされた変更のみに基づいて適切なコミットメッセージを日本語で3つ提案してください。重要：ステージされていない変更（unstaged changes）はこのコミットに含まれないため、コミットメッセージには含めないでください。Conventional Commitsの形式（feat:, fix:, refactor: など）で、スコープは含めず type: description の形式で出力してください。各提案は1行ずつ、番号や説明なしで出力してください。" \
      2>/dev/null |
    grep -E '^(feat|fix|refactor|docs|test|chore|style|perf):' |
    head -3
)"

if [ -z "$CANDIDATES" ]; then
  echo "❌ Codex から有効なコミットメッセージ候補を取得できませんでした。"
  exit 1
fi

echo "✅ 生成完了！"
echo

# fzf で候補を選択
base_msg="$(echo "$CANDIDATES" | fzf \
  --prompt="🤖 コミットメッセージを選択 (Esc でキャンセル)> " \
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

# 選択したメッセージを表示
echo
echo "📝 選択したメッセージ:"
echo "  $base_msg"
echo

# 編集するかどうか確認
read -rp "このままコミットしますか？ [y=そのまま / e=編集 / その他=中止] " yn

tmpfile="$(mktemp)"

case "$yn" in
  y|Y)
    # そのまま使う
    echo "$base_msg" > "$tmpfile"
    ;;
  e|E)
    # エディタで編集
    {
      echo "$base_msg"
      echo
      echo "# ここから下に説明文などを自由に書いてください"
      echo "# 行頭が # の行はコミットメッセージには含まれません"
    } >"$tmpfile"
    "${EDITOR:-vim}" "$tmpfile"
    ;;
  *)
    echo "キャンセルしました。"
    rm -f "$tmpfile"
    exit 0
    ;;
esac

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
