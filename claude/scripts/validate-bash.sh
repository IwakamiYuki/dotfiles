#!/bin/bash

# Claude Code PreToolUse hook: Bash コマンド検証
# ファイルリダイレクトと heredoc 操作をブロック

# 標準入力から JSON を読み込み
input=$(cat)

# デバッグ: 入力をファイルに記録（デバッグ時はコメント解除）
# echo "$input" > /tmp/claude-hook-debug.log

# JSON からコマンドを抽出（jq が利用可能な場合は使用、なければ Python で代替）
if command -v jq >/dev/null 2>&1; then
    command=$(echo "$input" | jq -r '.tool_input.command // empty')
else
    # フォールバック: Python で JSON をパース
    command=$(echo "$input" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('tool_input', {}).get('command', ''))")
fi

# 禁止パターンをチェック
if echo "$command" | grep -qE '(cat|echo|printf).*(>|>>)'; then
    echo "ERROR: cat/echo/printf でのファイルリダイレクトは禁止されています。Edit または Write ツールを使用してください。" >&2
    exit 2
fi

if echo "$command" | grep -qE '(cat|echo|printf).*<<'; then
    echo "ERROR: cat/echo/printf での heredoc は禁止されています。Edit または Write ツールを使用してください。" >&2
    exit 2
fi

if echo "$command" | grep -qE 'sed.*-[ie]'; then
    echo "ERROR: sed でのインライン編集は禁止されています。Edit ツールを使用してください。" >&2
    exit 2
fi

if echo "$command" | grep -qE 'perl.*-[ip]'; then
    echo "ERROR: perl でのインライン編集は禁止されています。Edit ツールを使用してください。" >&2
    exit 2
fi

# コマンド実行を許可
exit 0
