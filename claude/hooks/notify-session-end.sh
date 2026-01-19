#!/bin/bash

# SessionEnd フック: セッション終了時に通知をクリアする

# 標準入力からhookのInputデータを読み取り
INPUT=$(cat)

# デバッグ: 入力データをログに出力
echo "========== notify-session-end.sh DEBUG ==========" >> /tmp/notify-hook-debug.log
echo "$(date): INPUT data:" >> /tmp/notify-hook-debug.log
echo "$INPUT" | jq '.' >> /tmp/notify-hook-debug.log 2>&1
echo "$(date): Current TMUX: $TMUX" >> /tmp/notify-hook-debug.log
echo "$(date): Current TMUX_PANE: $TMUX_PANE" >> /tmp/notify-hook-debug.log
echo "=============================================" >> /tmp/notify-hook-debug.log

# tmux環境かどうかチェック
if [ -z "$TMUX" ]; then
    # tmux環境でない場合は何もしない（通知管理が別）
    exit 0
fi

# TMUX_PANE からセッション/ペイン情報を取得
PANE_ID="${TMUX_PANE}"

if [ -n "$PANE_ID" ]; then
    SESSION_NAME=$(tmux display-message -p -t "$PANE_ID" '#{session_name}' 2>/dev/null)

    if [ -n "$SESSION_NAME" ]; then
        # GROUP ID を安全に構築
        GROUP_ID="claude-code-${SESSION_NAME}-${PANE_ID}"

        # セッション終了時に前の通知を削除
        /opt/homebrew/bin/terminal-notifier -remove "$GROUP_ID" 2>/dev/null || true
        echo "$(date): Removed notification for $GROUP_ID" >> /tmp/notify-hook-debug.log
    fi
fi

exit 0
