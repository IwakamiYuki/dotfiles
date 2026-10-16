#!/bin/bash

# Focus handler script for tmux pane notifications
# This script is executed when a user clicks on a Claude Code notification
# It activates Ghostty and focuses the specific tmux session/pane
#
# Agent cockpit(@agent_cockpit=1 の window)が対象の session にあるときは、元の window へ飛ばず、
# cockpit の右の枠へその Agent を入れて、そこへフォーカスする(sidebar の選択も追従させる)。
# cockpit が無い、または枠へ入れられなかったときは、従来どおり元の window・pane へ飛ぶ。

# Set PATH to ensure tmux is found
export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"

# 環境変数または引数から値を取得
SESSION_NAME="${FOCUS_SESSION_NAME:-$1}"
PANE_ID="${FOCUS_PANE_ID:-$2}"
TMUX_SOCKET="${FOCUS_SOCKET_PATH:-$3}"

LOG="${FOCUS_LOG:-/tmp/focus-pane-debug.log}"
COCKPIT_BIN="${FOCUS_COCKPIT_BIN:-$HOME/.tmux/scripts/tmux-agent-cockpit}"

# 対象の session の cockpit の枠へ Agent($1)を入れる。入れられたら cockpit の window_id を標準出力へ返す(失敗なら空)
cockpit_enter() {
    local target=$1 cock sb target_win
    cock=$(tmux -S "$TMUX_SOCKET" list-windows -t "$SESSION_NAME" -F '#{window_id} #{@agent_cockpit}' 2>/dev/null | awk '$2 == 1 { print $1; exit }')
    [ -n "$cock" ] || return 0
    [ -x "$COCKPIT_BIN" ] || return 0
    target_win=$(tmux -S "$TMUX_SOCKET" display-message -p -t "$target" '#{window_id}' 2>/dev/null)
    [ -n "$target_win" ] || return 0
    # すでに cockpit の中(枠に入っている Agent)なら、従来の選択だけでよい
    [ "$target_win" = "$cock" ] && return 0

    TMUX="$TMUX_SOCKET,0,0" "$COCKPIT_BIN" show "$target" >/dev/null 2>&1
    [ "$(tmux -S "$TMUX_SOCKET" display-message -p -t "$target" '#{window_id}' 2>/dev/null)" = "$cock" ] || return 0

    # sidebar の選択を追従させる(sidebar は次の更新で @agent_new_pane の Agent を選ぶ。枠にはもう入っているので表示は変わらない)
    sb=$(tmux -S "$TMUX_SOCKET" list-panes -t "$cock" -F '#{pane_id} #{@agent_sidebar}' 2>/dev/null | awk '$2 == 1 { print $1; exit }')
    [ -n "$sb" ] && tmux -S "$TMUX_SOCKET" set-option -p -t "$sb" @agent_new_pane "$target" 2>/dev/null
    echo "$cock"
}

# Debug logging
{
  echo "=========================================="
  echo "$(date): Focusing SESSION_NAME=$SESSION_NAME, PANE_ID=$PANE_ID, TMUX_SOCKET=$TMUX_SOCKET"
  echo "$(date): PATH=$PATH"
  echo "$(date): tmux location: $(which tmux)"
} >> "$LOG"

if [ -n "$SESSION_NAME" ] && [ -n "$PANE_ID" ] && [ -n "$TMUX_SOCKET" ]; then
    # Get all tmux clients
    clients=$(tmux -S "$TMUX_SOCKET" list-clients -F '#{client_tty}:#{session_name}' 2>&1)

    echo "$(date): Found clients: $clients" >> "$LOG"

    if [ -n "$clients" ] && [ "$clients" != "error"* ]; then
        cockpit_done=""
        cockpit_win=""
        while IFS=: read -r client_tty current_session; do
            echo "$(date): Processing client: $client_tty (current session: $current_session)" >> "$LOG"

            # Only switch if client is in a different session
            if [ "$current_session" != "$SESSION_NAME" ]; then
                echo "$(date): Switching client from session '$current_session' to '$SESSION_NAME'" >> "$LOG"
                switch_result=$(tmux -S "$TMUX_SOCKET" switch-client -c "$client_tty" -t "$SESSION_NAME" 2>&1)
                echo "$(date): switch-client result: '$switch_result'" >> "$LOG"
            else
                echo "$(date): Client already in target session '$SESSION_NAME'" >> "$LOG"
            fi

            # cockpit があれば Agent を枠へ入れる(入れたあとは PANE_ID が cockpit の window にいるので、下の選択でそこへ移る)
            if [ -z "$cockpit_done" ]; then
                cockpit_done=1
                cockpit_win=$(cockpit_enter "$PANE_ID")
                echo "$(date): cockpit window for entering: '${cockpit_win}'" >> "$LOG"
            fi

            # Get window index for the target pane
            window_index=$(tmux -S "$TMUX_SOCKET" display-message -t "$PANE_ID" -p '#{window_index}' 2>&1)
            echo "$(date): Target pane $PANE_ID is in window $window_index" >> "$LOG"

            # First, select the window
            if [ -n "$window_index" ]; then
                echo "$(date): Selecting window $window_index in session $SESSION_NAME" >> "$LOG"
                window_result=$(tmux -S "$TMUX_SOCKET" select-window -t "$SESSION_NAME:$window_index" 2>&1)
                echo "$(date): select-window result: '$window_result'" >> "$LOG"
            fi

            # Then select the target pane
            echo "$(date): Selecting pane $PANE_ID" >> "$LOG"
            select_result=$(tmux -S "$TMUX_SOCKET" select-pane -t "$PANE_ID" 2>&1)
            echo "$(date): select-pane result: '$select_result'" >> "$LOG"
        done <<< "$clients"
    else
        echo "$(date): No valid clients found or error occurred" >> "$LOG"
    fi

    # Activate Ghostty at the end
    osascript -e 'tell application "Ghostty" to activate' 2>/dev/null
else
    # If parameters are missing, just activate Ghostty
    osascript -e 'tell application "Ghostty" to activate' 2>/dev/null
fi

echo "=========================================" >> "$LOG"
exit 0
