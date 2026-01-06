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
# cat/echo/printf でのファイルリダイレクトを検出
#
# 禁止: cat > file, echo "text" > file, printf "text" >> file
# 許可: command 2>/dev/null, echo "text" >&2, cat file 2>&1

# ファイルへの書き込みリダイレクトを検出
# 許可: >&数字, 数字>/dev/, 数字>&数字
# 禁止: > ファイル名, >> ファイル名
if echo "$command" | grep -qE '(cat|echo|printf)'; then
    # cat/echo/printf を含む部分コマンドを抽出（パイプや ; までの部分）
    subcmd=$(echo "$command" | grep -oE '(cat|echo|printf)[^|;]*')

    # ファイルリダイレクトを検出:
    # - > の前が数字でも & でもない（通常のリダイレクト）
    # - > の後に /dev/ 以外のファイル名が続く
    # 重要: この正規表現は >&2 や 2>/dev/null を除外し、> file.txt のみを検出する
    if echo "$subcmd" | grep -qE '[^0-9&]>>?[[:space:]]*[^&]' && \
       ! echo "$subcmd" | grep -qE '[^0-9&]>>?[[:space:]]*/dev/'; then
        echo "ERROR: cat/echo/printf でのファイルリダイレクトは禁止されています。Edit または Write ツールを使用してください。" >&2
        exit 2
    fi
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
