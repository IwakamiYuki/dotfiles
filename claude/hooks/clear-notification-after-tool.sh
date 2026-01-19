#!/bin/bash
# PostToolUse Hook: ツール実行後に通知を削除
# すべてのツール実行後に発火し、前回の通知をクリアする

# 入力を読み取って破棄（標準入力の JSON を消費）
cat > /dev/null

# tmux 環境の場合、セッション名とペイン ID を特定
if [ -n "$TMUX" ] && [ -n "$TMUX_PANE" ]; then
    PANE_ID="${TMUX_PANE}"
    SESSION_NAME=$(tmux display-message -p -t "$PANE_ID" '#{session_name}' 2>/dev/null)

    if [ -n "$SESSION_NAME" ]; then
        # GROUP ID を安全に構築
        GROUP_ID="claude-code-${SESSION_NAME}-${PANE_ID}"

        # notify-ask.sh で設定した group ID を使用して通知を削除
        /opt/homebrew/bin/terminal-notifier -remove "$GROUP_ID" >/dev/null 2>&1
    fi
fi

# AppleScript で通知センターの通知を削除（フォールバック）
osascript -e 'tell application "System Events" to tell process "NotificationCenter" to set visible to false' >/dev/null 2>&1

exit 0
