#!/bin/bash

# 標準入力からhookのInputデータを読み取り
INPUT=$(cat)

# デバッグ: 入力データをログに出力
echo "========== notify-ask.sh DEBUG ==========" >> /tmp/notify-hook-debug.log
echo "$(date): INPUT data:" >> /tmp/notify-hook-debug.log
echo "$INPUT" | jq '.' >> /tmp/notify-hook-debug.log 2>&1
echo "$(date): Current TMUX: $TMUX" >> /tmp/notify-hook-debug.log
echo "$(date): Current TMUX_PANE: $TMUX_PANE" >> /tmp/notify-hook-debug.log
echo "=========================================" >> /tmp/notify-hook-debug.log

# セッションディレクトリ名を取得（cwdから抽出）
SESSION_DIR=$(echo "$INPUT" | jq -r '.cwd' | xargs basename)
echo "$(date): SESSION_DIR: $SESSION_DIR" >> /tmp/notify-hook-debug.log

# メッセージを抽出
MSG=$(echo "$INPUT" | jq -r '.message')
echo "$(date): MSG: $MSG" >> /tmp/notify-hook-debug.log

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
NOTIFICATION_TITLE="⚠️ $TRUNCATED_DIR"
CONV_TITLE=""
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
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

# ツール情報を取得（permission_promptの場合）
TOOL_INFO=""
NOTIFICATION_TYPE=$(echo "$INPUT" | jq -r '.notification_type // "unknown"')
echo "$(date): NOTIFICATION_TYPE: $NOTIFICATION_TYPE" >> /tmp/notify-hook-debug.log

if [[ "$NOTIFICATION_TYPE" == "permission_prompt" && -n "$TRANSCRIPT_PATH" && -f "$TRANSCRIPT_PATH" ]]; then
  echo "$(date): Extracting tool info from transcript..." >> /tmp/notify-hook-debug.log

  # ツール情報を2段階で取得：1. ツール名、2. コマンド/パラメータ
  TOOL_NAME=$(tail -20 "$TRANSCRIPT_PATH" | jq -r '
    select(.message.role == "assistant" and .message.content != null) |
    .message.content[] |
    select(.type == "tool_use") |
    .name
  ' | tail -1)

  TOOL_COMMAND=$(tail -20 "$TRANSCRIPT_PATH" | jq -r '
    select(.message.role == "assistant" and .message.content != null) |
    .message.content[] |
    select(.type == "tool_use") |
    if .name == "Bash" then
      .input.command // .input.description // ""
    else
      .input | to_entries | map(select(.key != "description") | "\(.key): \(.value | tostring | .[0:100])") | join("\n")
    end
  ' | tail -1)

  if [ -n "$TOOL_NAME" ] && [ -n "$TOOL_COMMAND" ]; then
    TOOL_INFO="🔧 $TOOL_NAME: $TOOL_COMMAND"
  else
    TOOL_INFO=""
  fi

  echo "$(date): TOOL_INFO (raw):" >> /tmp/notify-hook-debug.log
  printf '%s\n' "$TOOL_INFO" >> /tmp/notify-hook-debug.log
  echo "$(date): TOOL_INFO (hex): $(printf '%s' "$TOOL_INFO" | od -An -tx1 | tr -d ' \n')" >> /tmp/notify-hook-debug.log
fi

# メッセージを組み立て（会話タイトル + ツール情報）
if [ -n "$CONV_TITLE" ]; then
    FULL_MESSAGE=" 💬 $CONV_TITLE"
else
    FULL_MESSAGE="$MSG"
fi

if [ -n "$TOOL_INFO" ]; then
    FULL_MESSAGE="$FULL_MESSAGE"$'\n'"$TOOL_INFO"
    echo "$(date): Added TOOL_INFO to message" >> /tmp/notify-hook-debug.log
else
    # ツール情報がない場合は元のメッセージを追加
    if [ -n "$CONV_TITLE" ]; then
        FULL_MESSAGE="$FULL_MESSAGE"$'\n'"$MSG"
    fi
    echo "$(date): No TOOL_INFO to add" >> /tmp/notify-hook-debug.log
fi

# tmux環境かどうかチェック
if [ -z "$TMUX" ]; then
    # tmux環境でない場合は、terminal-notifier で通知
    /opt/homebrew/bin/terminal-notifier -title "$NOTIFICATION_TITLE" -message "$FULL_MESSAGE" -sender "com.anthropic.claudefordesktop"
    exit 0
fi

# TMUX環境の場合：ソケットパスとセッション/ペイン情報を抽出
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

# クリック可能な通知を送信（クリック時に Ghostty をアクティベートしペインにフォーカス）
FOCUS_SCRIPT="$HOME/.claude/hooks/focus-tmux-pane.sh"
ICON_PATH="$HOME/.claude/icons/claude-ai-icon.png"
echo "$(date): NOTIFICATION_TITLE: $NOTIFICATION_TITLE" >> /tmp/notify-hook-debug.log
echo "$(date): CONV_TITLE: $CONV_TITLE" >> /tmp/notify-hook-debug.log
echo "$(date): FULL_MESSAGE: $FULL_MESSAGE" >> /tmp/notify-hook-debug.log
echo "$(date): FULL_MESSAGE (hex): $(echo -n "$FULL_MESSAGE" | od -An -tx1 | tr -d ' ')" >> /tmp/notify-hook-debug.log

# アイコンが存在する場合は -contentImage オプションを追加
if [ -f "$ICON_PATH" ]; then
  echo "$(date): Sending notification with icon" >> /tmp/notify-hook-debug.log
  echo "$(date): About to call terminal-notifier with:" >> /tmp/notify-hook-debug.log
  echo "  -title: $NOTIFICATION_TITLE" >> /tmp/notify-hook-debug.log
  echo "  -message length: ${#FULL_MESSAGE}" >> /tmp/notify-hook-debug.log
  /opt/homebrew/bin/terminal-notifier \
    -title "$NOTIFICATION_TITLE" \
    -message "$FULL_MESSAGE" \
    -group "claude-code-$SESSION_NAME-$PANE_ID" \
    -contentImage "$ICON_PATH" \
    -activate "com.mitchellh.ghostty" \
    -execute "$FOCUS_SCRIPT '$SESSION_NAME' '$PANE_ID' '$SOCKET_PATH'" 2>> /tmp/notify-hook-debug.log
  echo "$(date): terminal-notifier exit code: $?" >> /tmp/notify-hook-debug.log
else
  echo "$(date): Sending notification without icon" >> /tmp/notify-hook-debug.log
  /opt/homebrew/bin/terminal-notifier \
    -title "$NOTIFICATION_TITLE" \
    -message "$FULL_MESSAGE" \
    -group "claude-code-$SESSION_NAME-$PANE_ID" \
    -activate "com.mitchellh.ghostty" \
    -execute "$FOCUS_SCRIPT '$SESSION_NAME' '$PANE_ID' '$SOCKET_PATH'" 2>> /tmp/notify-hook-debug.log
fi
