#!/bin/bash

# 標準入力からhookのInputデータを読み取り
INPUT=$(cat)

# デバッグ: 入力データをログに出力
echo "========== notify-end.sh DEBUG ==========" >> /tmp/notify-hook-debug.log
echo "$(date): INPUT data:" >> /tmp/notify-hook-debug.log
echo "$INPUT" | jq '.' >> /tmp/notify-hook-debug.log 2>&1
echo "$(date): Current TMUX: $TMUX" >> /tmp/notify-hook-debug.log
echo "$(date): Current TMUX_PANE: $TMUX_PANE" >> /tmp/notify-hook-debug.log
echo "=========================================" >> /tmp/notify-hook-debug.log

# 現在のセッションディレクトリ名を取得（hooksはsessionと同じディレクトリで実行される）
SESSION_DIR=$(basename "$(pwd)")

# transcript_pathを抽出
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path')

# transcript_pathが存在する場合、最新のassistantメッセージを取得
if [ -f "$TRANSCRIPT_PATH" ]; then
    # 最後の10行から assistant のメッセージを抽出し、最新のもの（最後）を取得
    # content は配列で、最初の要素に text フィールドがある
    MSG=$(tail -10 "$TRANSCRIPT_PATH" | \
          jq -r 'select(.message? and .message.role? == "assistant") | .message.content[]? | select(.type? == "text") | .text' | \
          tail -1 | \
          tr '\n' ' ' | \
          cut -c1-60)

    # メッセージが取得できない場合のフォールバック
    MSG=${MSG:-"Task completed"}
else
    MSG="Task completed"
fi

# tmux環境かどうかチェック
if [ -z "$TMUX" ]; then
    # tmux環境でない場合は、terminal-notifier で通知
    /opt/homebrew/bin/terminal-notifier -title "✅ Claude Code [$SESSION_DIR]" -message "${MSG}" -sender "com.anthropic.claudefordesktop"
    exit 0
fi

# TMUX環境の場合：セッション/ペイン情報を抽出
# 重要: $TMUX_PANE を使用してこのスクリプトが実行されているペインのIDを取得
PANE_ID="${TMUX_PANE}"
SESSION_NAME=$(tmux display-message -p -t "$PANE_ID" '#{session_name}')
# TMUX 変数から正しいソケットパスを抽出（最初のカンマまで）
SOCKET_PATH="${TMUX%%,*}"

echo "$(date): Using PANE_ID from TMUX_PANE: $PANE_ID" >> /tmp/notify-hook-debug.log
echo "$(date): SESSION_NAME: $SESSION_NAME" >> /tmp/notify-hook-debug.log
echo "$(date): SOCKET_PATH: $SOCKET_PATH" >> /tmp/notify-hook-debug.log

# tmuxコマンドのPATHを明示的に設定
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# 通知を送信（クリック時に Ghostty をアクティベートしペインにフォーカス）
FOCUS_SCRIPT="$HOME/.claude/hooks/focus-tmux-pane.sh"
ICON_PATH="$HOME/.claude/icons/claude-ai-icon.png"

# アイコンが存在する場合は -contentImage オプションを追加
if [ -f "$ICON_PATH" ]; then
  /opt/homebrew/bin/terminal-notifier \
    -title "✅ Claude Code [$SESSION_DIR]" \
    -message "${MSG}" \
    -group "claude-code-$SESSION_NAME-$PANE_ID" \
    -contentImage "$ICON_PATH" \
    -activate "com.mitchellh.ghostty" \
    -execute "$FOCUS_SCRIPT '$SESSION_NAME' '$PANE_ID' '$SOCKET_PATH'"
else
  /opt/homebrew/bin/terminal-notifier \
    -title "✅ Claude Code [$SESSION_DIR]" \
    -message "${MSG}" \
    -group "claude-code-$SESSION_NAME-$PANE_ID" \
    -activate "com.mitchellh.ghostty" \
    -execute "$FOCUS_SCRIPT '$SESSION_NAME' '$PANE_ID' '$SOCKET_PATH'"
fi
