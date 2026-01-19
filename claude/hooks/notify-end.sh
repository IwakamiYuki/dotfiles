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

# セッションディレクトリ名を取得（cwdから抽出）
SESSION_DIR=$(echo "$INPUT" | jq -r '.cwd' | xargs basename)

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

# 会話タイトルを取得（キャッシュがあれば使用）
# タイトルの長さを制限（絵文字2文字 + スペース1文字 + プロジェクト名 = 最大30文字）
MAX_PROJECT_NAME_LENGTH=30
if [ ${#SESSION_DIR} -gt $MAX_PROJECT_NAME_LENGTH ]; then
    # 先頭と末尾を保持して中間を省略（先頭3/10、末尾7/10）
    PREFIX_LEN=$((MAX_PROJECT_NAME_LENGTH * 3 / 10))
    SUFFIX_LEN=$((MAX_PROJECT_NAME_LENGTH - PREFIX_LEN - 3))
    PREFIX="${SESSION_DIR:0:$PREFIX_LEN}"
    SUFFIX="${SESSION_DIR:(-$SUFFIX_LEN)}"
    TRUNCATED_DIR="$PREFIX...$SUFFIX"
else
    TRUNCATED_DIR="$SESSION_DIR"
fi
NOTIFICATION_TITLE="✅ $TRUNCATED_DIR"
CONV_TITLE=""
if [ -f "$TRANSCRIPT_PATH" ]; then
    # セッション ID を生成
    SESSION_ID=$(basename "$TRANSCRIPT_PATH" .jsonl)
    CACHE_FILE="/tmp/claude-title-${SESSION_ID}.txt"

    # キャッシュを確認（既に存在するなら使用）
    if [ -f "$CACHE_FILE" ]; then
        TITLE=$(cat "$CACHE_FILE" 2>/dev/null)
        if [ -n "$TITLE" ] && [ "$TITLE" != "新しい会話" ]; then
            CONV_TITLE="$TITLE"
        fi
    fi
fi

# メッセージを組み立て（会話タイトル + 本体）
if [ -n "$CONV_TITLE" ]; then
    FULL_MESSAGE=" 💬 $CONV_TITLE"$'\n'"${MSG}"
else
    FULL_MESSAGE="${MSG}"
fi

# tmux環境かどうかチェック
if [ -z "$TMUX" ]; then
    # tmux環境でない場合は、terminal-notifier で通知
    /opt/homebrew/bin/terminal-notifier -title "$NOTIFICATION_TITLE" -message "$FULL_MESSAGE" -sender "com.anthropic.claudefordesktop"
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

# 通知送信前に前の通知を削除
/opt/homebrew/bin/terminal-notifier -remove "claude-code-$SESSION_NAME-$PANE_ID" 2>/dev/null || true

# 通知を送信（クリック時に Ghostty をアクティベートしペインにフォーカス）
FOCUS_SCRIPT="$HOME/.claude/hooks/focus-tmux-pane.sh"
ICON_PATH="$HOME/.claude/icons/claude-ai-icon.png"
GROUP_ID="claude-code-${SESSION_NAME}-${PANE_ID}"

# アイコンが存在する場合は -contentImage オプションを追加
if [ -f "$ICON_PATH" ]; then
  /opt/homebrew/bin/terminal-notifier \
    -title "$NOTIFICATION_TITLE" \
    -message "$FULL_MESSAGE" \
    -group "$GROUP_ID" \
    -contentImage "$ICON_PATH" \
    -activate "com.mitchellh.ghostty" \
    -execute "env FOCUS_SESSION_NAME='$SESSION_NAME' FOCUS_PANE_ID='$PANE_ID' FOCUS_SOCKET_PATH='$SOCKET_PATH' $FOCUS_SCRIPT"
else
  /opt/homebrew/bin/terminal-notifier \
    -title "$NOTIFICATION_TITLE" \
    -message "$FULL_MESSAGE" \
    -group "$GROUP_ID" \
    -activate "com.mitchellh.ghostty" \
    -execute "env FOCUS_SESSION_NAME='$SESSION_NAME' FOCUS_PANE_ID='$PANE_ID' FOCUS_SOCKET_PATH='$SOCKET_PATH' $FOCUS_SCRIPT"
fi
