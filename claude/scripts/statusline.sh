#!/bin/bash
#
# Claude Code statusLine カスタムスクリプト
#
# 表示項目：
# 🤖 モデル名 - 使用中のClaudeモデル
# 💬 コンテキスト使用量 - 現在の会話のトークン使用量（v2.0.70以降は正確、それ以前は概算）
# ⏱️ 総処理時間 - セッション開始からの経過時間（秒）
# 🔧 API処理時間 - 実際のAPI呼び出しに費やした時間（秒）
# ✏️ コード変更量 - 追加/削除された行数
# 📦 バージョン - Claude Codeのバージョン番号
#
# 5h/1w のレートリミット（rate_limits, v2.1.80+）はアカウント単位で全セッション共通のため、
# ここでは表示せず /tmp/claude-rate-limits.json に書き出すのみ。
# 表示は tmux ヘッダー側の tmux-rate-limits スクリプトが担当する。

# 環境変数でstatusLineが無効化されている場合は何も出力しない（無限ループ防止）
if [ "$CLAUDE_DISABLE_STATUSLINE" = "1" ]; then
    exit 0
fi

# 標準入力からClaude Codeのコンテキスト情報を取得
input=$(cat)

# Claude Code標準データを抽出
model=$(echo "$input" | jq -r '.model.display_name // .model')   # モデル名（display_nameがあればそれを、なければmodelをそのまま）
model_id=$(echo "$input" | jq -r '.model.id // ""')               # モデルID（コンテキストウィンドウサイズ判定用）
duration=$(echo "$input" | jq -r '.cost.total_duration_ms')       # 総処理時間（ミリ秒）
api_duration=$(echo "$input" | jq -r '.cost.total_api_duration_ms') # API処理時間（ミリ秒）
lines_added=$(echo "$input" | jq -r '.cost.total_lines_added')    # 追加された行数
lines_removed=$(echo "$input" | jq -r '.cost.total_lines_removed') # 削除された行数
version=$(echo "$input" | jq -r '.version')                       # Claude Codeバージョン
transcript_path=$(echo "$input" | jq -r '.transcript_path // ""') # トランスクリプトパス

# コンテキストウィンドウ情報の取得（v2.1.80+）
context_pct=$(echo "$input" | jq -r '.context_window.used_percentage // ""')
context_window_size=$(echo "$input" | jq -r '.context_window.context_window_size // ""')
# 使用トークン数: cache_read + cache_creation + input + output
context_tokens=$(echo "$input" | jq -r '
    .context_window.current_usage
    | if . then
        ((.cache_read_input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.input_tokens // 0) + (.output_tokens // 0))
      else "" end' 2>/dev/null)

# レートリミット情報の取得（v2.1.80+）
five_hour_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // ""')
five_hour_resets=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // ""')
seven_day_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // ""')
seven_day_resets=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // ""')

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

# トークン数を人間が読みやすい形式にフォーマットする関数（例: 1000K → 1M）
format_tokens() {
    local tokens=$1
    local k=$((tokens / 1000))
    if [ $((k % 1000)) -eq 0 ] && [ $k -ge 1000 ]; then
        echo "$((k / 1000))M"
    else
        echo "${k}K"
    fi
}

# コンテキスト使用量をフォーマットする関数
# 引数: context_tokens, context_pct, context_window_size
calculate_context_usage() {
    local tokens=$1
    local pct=$2
    local window=$3

    if [ -n "$pct" ] && [ "$pct" != "null" ] && [ "$pct" != "" ]; then
        pct=$(round_pct "$pct")
        local window_display=""
        if [ -n "$window" ] && [ "$window" != "null" ] && [ "$window" != "" ]; then
            window_display="/$(format_tokens "$window")"
        fi
        local tokens_display=""
        if [ -n "$tokens" ] && [ "$tokens" != "null" ] && [ "$tokens" != "0" ] && [ "$tokens" -gt 0 ] 2>/dev/null; then
            tokens_display="$(format_tokens "$tokens")${window_display} "
        elif [ -n "$window" ] && [ "$window" != "null" ] && [ "$window" != "" ]; then
            # トークン数が取れない場合はパーセンテージから逆算
            local estimated=$((pct * window / 100))
            tokens_display="$(format_tokens "$estimated")${window_display} "
        fi
        printf "${tokens_display}${pct}%%"
        return
    fi

    printf "N/A"
}

# 時間形式に変換
duration_formatted=$(format_time "$duration_sec")
api_duration_formatted=$(format_time "$api_duration_sec")

# 浮動小数点を整数に丸める関数（四捨五入）
round_pct() {
    printf "%.0f" "$1" 2>/dev/null || echo "0"
}

# レートリミット情報はアカウント単位で全セッション共通のため、statusLine には表示せず
# tmux ヘッダー（tmux-rate-limits）用にキャッシュファイルへ書き出すだけにする
RATE_LIMITS_CACHE="/tmp/claude-rate-limits.json"
if [ -n "$five_hour_pct" ] && [ "$five_hour_pct" != "null" ] && [ "$five_hour_pct" != "" ]; then
    jq -n \
        --arg five_hour_pct "$five_hour_pct" \
        --arg five_hour_resets "$five_hour_resets" \
        --arg seven_day_pct "$seven_day_pct" \
        --arg seven_day_resets "$seven_day_resets" \
        '{five_hour_pct: ($five_hour_pct | tonumber), five_hour_resets: $five_hour_resets, seven_day_pct: (if $seven_day_pct == "" or $seven_day_pct == "null" then null else ($seven_day_pct | tonumber) end), seven_day_resets: $seven_day_resets}' \
        > "$RATE_LIMITS_CACHE" 2>/dev/null
fi

# コンテキスト使用量を計算
context_usage=$(calculate_context_usage "$context_tokens" "$context_pct" "$context_window_size")

# 会話タイトルを取得（AI生成、キャッシュあればそれを使用）
conversation_title=""
if [ -n "$transcript_path" ] && [ "$transcript_path" != "null" ]; then
    conversation_title=$(bash ~/.claude/scripts/generate-title.sh "$transcript_path" 2>/dev/null)
    if [ -n "$conversation_title" ] && [ "$conversation_title" != "新しい会話" ]; then
        conversation_title="📝 ${conversation_title} | "
    fi
fi

# パーセンテージから ANSI カラー付き進捗バーを生成する関数
# 引数: パーセンテージ（数値）、バー幅（デフォルト10）
make_bar() {
    local pct=$1
    local width=${2:-10}
    local filled=$((pct * width / 100))
    # 1% 以上なら最低 1 ブロック表示
    if [ "$pct" -gt 0 ] && [ "$filled" -eq 0 ]; then
        filled=1
    fi
    local empty=$((width - filled))

    # 使用率に応じた色（ANSI 256色）: 緑→黄→赤
    local color
    if [ "$pct" -lt 30 ]; then
        color="38;5;82"    # 緑
    elif [ "$pct" -lt 60 ]; then
        color="38;5;208"   # オレンジ
    elif [ "$pct" -lt 80 ]; then
        color="38;5;214"   # 黄橙
    else
        color="38;5;196"   # 赤
    fi

    local bar="\033[${color}m"
    for ((i=0; i<filled; i++)); do bar+="█"; done
    bar+="\033[38;5;240m"
    for ((i=0; i<empty; i++)); do bar+="░"; done
    bar+="\033[0m"

    printf "%b" "$bar"
}

# 進捗バーを生成（数値が取得できた場合のみ）
context_bar=""
if [ -n "$context_pct" ] && [ "$context_pct" != "null" ] && [ "$context_pct" != "" ]; then
    local_context_pct=$(round_pct "$context_pct")
    context_bar=$(make_bar "$local_context_pct" 10)
fi

# 出力（1行表示、echo -e で ANSI エスケープを有効化）
# 5h/1w のレートリミットは tmux ヘッダーに集約したため、statusLine は1行に収まる
lines_display="\033[38;5;82m+${lines_added}\033[0m/\033[38;5;196m-${lines_removed}\033[0m"
echo -e "${conversation_title}🤖 ${model} | ⏱️ ${duration_formatted} 🔧 ${api_duration_formatted} | ✏️ ${lines_display} | 💬 ${context_bar} ${context_usage} | 📦 ${version}"
