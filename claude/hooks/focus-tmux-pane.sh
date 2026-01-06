#!/bin/bash

# Focus handler script for tmux pane notifications
# This script is executed when a user clicks on a Claude Code notification
# It activates Ghostty and focuses the specific tmux session/pane

# Set PATH to ensure tmux is found
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"

SESSION_NAME="$1"
PANE_ID="$2"
TMUX_SOCKET="$3"

LOG="/tmp/focus-pane-debug.log"

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
