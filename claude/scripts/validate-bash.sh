#!/bin/bash

# Claude Code PreToolUse hook: Bash コマンド検証
# sed -i と git add の危険な形をブロック

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

# sed -i（--in-place）をブロック
# 理由: macOS（BSD sed）は `sed -i 's/a/b/' f` で拡張子の引数が必須。GNU 流に書くとファイルを壊す
# （~/.zshrc を空にした事例がある）。他のコマンド（cat > file や perl -pi など）は、
# 迂回しやすく誤検知も多いため、権限モード / auto mode の判定に任せる。
# 許可: sed -n 's/a/b/p' f, sed -e 's/a/b/' f | cmd, cmd | grep -i foo
if echo "$command" | grep -qE '(^|[^[:alnum:]_/.-])sed[[:space:]]+([^|;&]*[[:space:]])?(-[a-zA-Z]*i[^[:space:]]*|--in-place[^[:space:]]*)([[:space:]]|$)'; then
    echo "ERROR: sed でのインライン編集（-i）は禁止されています。Edit ツールを使用してください。" >&2
    exit 2
fi

# git add の安全性チェック
if echo "$command" | grep -qE '^git[[:space:]]+add'; then
    # 危険なパターンを検出: -A, --all, .
    if echo "$command" | grep -qE 'git[[:space:]]+add[[:space:]]+(-A|--all|\.([[:space:]]|$))'; then
        echo "ERROR: git add -A, git add ., git add --all は禁止されています。" >&2
        echo "" >&2
        echo "理由:" >&2
        echo "  - 意図しないファイルのステージングリスク" >&2
        echo "  - 機密情報の誤コミット防止" >&2
        echo "" >&2
        echo "代わりに以下を実行してください:" >&2
        echo "  1. git status で変更ファイルを確認" >&2
        echo "  2. ステージングするファイルを個別に指定" >&2
        echo "  3. git add <file1> <file2> ..." >&2
        exit 2
    fi

    # ワイルドカードの使用を警告（ブロックはしない）
    if echo "$command" | grep -qE 'git[[:space:]]+add[[:space:]].*\*'; then
        echo "WARNING: git add でのワイルドカード使用が検出されました。より具体的にファイルを指定することを推奨します。" >&2
    fi
fi

# コマンド実行を許可
exit 0
