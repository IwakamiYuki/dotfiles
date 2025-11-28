#!/bin/bash
#
# Claude Code の Current session 情報を取得（statusLine 用）
# tmux capture-pane を使用して /usage の TUI 画面をキャプチャ

# タイムアウト時間（秒）
TIMEOUT=30

# 一時的なセッション名（現在のセッションとは独立）
TEMP_SESSION="claude-usage-$$"
CAPTURE_FILE="/tmp/claude-usage-$$.txt"

# クリーンアップ関数（スクリプト終了時に必ず実行）
cleanup() {
    # セッションが存在する場合は強制削除
    if tmux has-session -t "$TEMP_SESSION" 2>/dev/null; then
        tmux kill-session -t "$TEMP_SESSION" 2>/dev/null
    fi
    # 一時ファイルを削除
    rm -f "$CAPTURE_FILE"
}

# スクリプト終了時（正常終了/異常終了問わず）に必ずクリーンアップを実行
trap cleanup EXIT INT TERM

# 新しいバックグラウンドセッションを作成して claude を起動（環境変数でstatusLineを無効化）
# CLAUDE_DISABLE_STATUSLINE=1 を設定することで、このインスタンスではstatusLineが呼ばれない
# 完全に独立したセッションなので、ユーザーの画面には一切表示されない
# バックグラウンドでタイムアウト後に自身のセッションを強制終了
tmux new-session -d -s "$TEMP_SESSION" "(sleep $TIMEOUT; tmux kill-session -t '$TEMP_SESSION') & CLAUDE_DISABLE_STATUSLINE=1 claude" 2>/dev/null

# 少し待ってから /usage コマンドを送信
sleep 2
tmux send-keys -t "$TEMP_SESSION" "/usage" C-m 2>/dev/null

# オートコンプリートメニューが表示されるので、もう一度 Enter を送信
tmux send-keys -t "$TEMP_SESSION" C-m 2>/dev/null

# TUI が完全に描画されるまで待つ
sleep 2

# ペインの内容をキャプチャ
tmux capture-pane -t "$TEMP_SESSION" -p > "$CAPTURE_FILE" 2>/dev/null

# Esc を送信して終了
sleep 1
tmux send-keys -t "$TEMP_SESSION" Escape 2>/dev/null

# Current session の使用率を抽出
session_pct=$(grep -A1 "Current session" "$CAPTURE_FILE" | tail -1 | grep -oE '[0-9]+% used' | grep -oE '[0-9]+')

# Current session のリセット時間を抽出
session_reset=$(grep "Resets" "$CAPTURE_FILE" | head -1 | sed 's/^[[:space:]]*//' | sed 's/Resets //')

# 結果を出力（JSON形式）
if [ -n "$session_pct" ] && [ -n "$session_reset" ]; then
    echo "{\"usage\":\"${session_pct}%\",\"resets\":\"${session_reset}\"}"
else
    echo "{\"usage\":\"N/A\",\"resets\":\"N/A\"}"
fi

# クリーンアップはtrapで自動実行される
