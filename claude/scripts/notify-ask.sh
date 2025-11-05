#!/bin/bash


# 標準入力からhookのInputデータを読み取り
INPUT=$(cat)

# 現在のセッションディレクトリ名を取得（hooksはsessionと同じディレクトリで実行される）
SESSION_DIR=$(basename "$(pwd)")

MSG=$(echo "$INPUT" | jq -r '.message')
/opt/homebrew/bin/terminal-notifier -title "⚠️Claude Code [$SESSION_DIR]" -message $'許可を求めています！\n'"$MSG" -sender "com.anthropic.claudefordesktop"

