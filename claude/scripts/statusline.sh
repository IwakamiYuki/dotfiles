#!/bin/bash
#
# Claude Code statusLine カスタムスクリプト
#
# 表示項目：
# 🤖 モデル名 - 使用中のClaudeモデル
# 📊 セッション使用率 - /usage の Current session 情報（%とリセット時間）
# ⏱️ 総処理時間 - セッション開始からの経過時間（秒）
# 🔧 API処理時間 - 実際のAPI呼び出しに費やした時間（秒）
# ✏️ コード変更量 - 追加/削除された行数
# 📦 バージョン - Claude Codeのバージョン番号

# 環境変数でstatusLineが無効化されている場合は何も出力しない（無限ループ防止）
if [ "$CLAUDE_DISABLE_STATUSLINE" = "1" ]; then
    exit 0
fi

# 標準入力からClaude Codeのコンテキスト情報を取得
input=$(cat)

# Claude Code標準データを抽出
model=$(echo "$input" | jq -r '.model.display_name // .model')   # モデル名（display_nameがあればそれを、なければmodelをそのまま）
duration=$(echo "$input" | jq -r '.cost.total_duration_ms')       # 総処理時間（ミリ秒）
api_duration=$(echo "$input" | jq -r '.cost.total_api_duration_ms') # API処理時間（ミリ秒）
lines_added=$(echo "$input" | jq -r '.cost.total_lines_added')    # 追加された行数
lines_removed=$(echo "$input" | jq -r '.cost.total_lines_removed') # 削除された行数
version=$(echo "$input" | jq -r '.version')                       # Claude Codeバージョン

# 秒単位に変換
duration_sec=$(echo "$duration / 1000" | bc 2>/dev/null || echo "0")
api_duration_sec=$(echo "$api_duration / 1000" | bc 2>/dev/null || echo "0")

# 時間:分:秒形式に変換する関数
format_time() {
    local total_sec=$1
    local hours=$((total_sec / 3600))
    local minutes=$(((total_sec % 3600) / 60))
    local seconds=$((total_sec % 60))

    if [ $hours -gt 0 ]; then
        printf "%dh%dm%ds" $hours $minutes $seconds
    elif [ $minutes -gt 0 ]; then
        printf "%dm%ds" $minutes $seconds
    else
        printf "%ds" $seconds
    fi
}

# 時間形式に変換
duration_formatted=$(format_time "$duration_sec")
api_duration_formatted=$(format_time "$api_duration_sec")

# /usage からセッション使用情報を取得（JSON形式）
session_info=$(bash ~/.claude/scripts/get-session-usage.sh 2>/dev/null)
session_usage=$(echo "$session_info" | jq -r '.usage' 2>/dev/null || echo "N/A")
session_reset=$(echo "$session_info" | jq -r '.resets' 2>/dev/null || echo "N/A")

# 出力
echo "🤖 $model | 📊 Session: $session_usage (resets $session_reset) | ⏱️ ${duration_formatted} | 🔧 API: ${api_duration_formatted} | ✏️ +${lines_added}/-${lines_removed} | 📦 $version"
