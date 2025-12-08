#!/bin/bash
#
# Claude Code statusLine の入力データをデバッグするスクリプト
# 標準入力から受け取る JSON を /tmp/statusline-input.json に保存
#

# 環境変数でstatusLineが無効化されている場合は何も出力しない（無限ループ防止）
if [ "$CLAUDE_DISABLE_STATUSLINE" = "1" ]; then
    exit 0
fi

# 標準入力からClaude Codeのコンテキスト情報を取得
input=$(cat)

# デバッグ: 入力 JSON を保存
echo "$input" | jq '.' > /tmp/statusline-input.json 2>/dev/null

# 簡易出力
model=$(echo "$input" | jq -r '.model.display_name // .model' 2>/dev/null)
echo "🐛 Debug mode | Model: $model | Input saved to /tmp/statusline-input.json"
