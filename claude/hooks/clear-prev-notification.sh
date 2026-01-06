#!/bin/bash

# ユーザーがプロンプトを送信したときに、前の通知を削除するスクリプト
# UserPromptSubmit フックから呼び出される

# 標準入力からhookのInputデータを読み取り
INPUT=$(cat)

# tmux環境でない場合は何もしない（非tmux環境では通知が別管理）
if [ -z "$TMUX" ]; then
  exit 0
fi

# TMUX_PANE から現在のセッション/ペイン情報を取得
PANE_ID="${TMUX_PANE}"

if [ -n "$PANE_ID" ]; then
  SESSION_NAME=$(tmux display-message -p -t "$PANE_ID" '#{session_name}' 2>/dev/null)

  if [ -n "$SESSION_NAME" ]; then
    # 前の通知を削除
    /opt/homebrew/bin/terminal-notifier -remove "claude-code-$SESSION_NAME-$PANE_ID" 2>/dev/null || true
  fi
fi

exit 0
