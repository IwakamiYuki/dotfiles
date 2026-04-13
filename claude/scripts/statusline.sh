#!/bin/bash
#
# Claude Code statusLine カスタムスクリプト
#
# 表示項目：
# 🤖 モデル名 - 使用中のClaudeモデル
# 📊 5h セッション使用率 - rate_limits.five_hour から取得（v2.1.80+）
# 📅 1w 週間使用率 - rate_limits.seven_day から取得（v2.1.80+）
# 💬 コンテキスト使用量 - 現在の会話のトークン使用量（v2.0.70以降は正確、それ以前は概算）
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

# リセット時刻を相対時間に変換する関数（例: "2h30m"）
# 入力: epoch 秒（数値）または ISO 8601 文字列（UTC）
format_resets_at() {
    local resets_at=$1
    local reset_epoch=""

    # 数値（epoch 秒）の場合はそのまま使用
    if [[ "$resets_at" =~ ^[0-9]+$ ]]; then
        reset_epoch="$resets_at"
    else
        # ISO 8601 文字列: "Z" や ".000Z" を除去して UTC としてパース
        local clean="${resets_at%%.*}"
        clean="${clean%Z}"
        reset_epoch=$(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%S" "$clean" "+%s" 2>/dev/null)
    fi

    if [ -z "$reset_epoch" ] || [ "$reset_epoch" = "0" ]; then
        echo "$resets_at"
        return
    fi
    local now=$(date +%s)
    local diff=$((reset_epoch - now))
    if [ $diff -le 0 ]; then
        echo "now"
        return
    fi
    # 時間と分のみ表示（秒は省略）
    local hours=$((diff / 3600))
    local minutes=$(((diff % 3600) / 60))
    if [ $hours -gt 0 ]; then
        printf "%dh%dm" $hours $minutes
    else
        printf "%dm" $minutes
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

# レートリミット情報の整形（rate_limits フィールドから直接取得、v2.1.80+）
if [ -n "$five_hour_pct" ] && [ "$five_hour_pct" != "null" ] && [ "$five_hour_pct" != "" ]; then
    five_hour_pct=$(round_pct "$five_hour_pct")
    session_usage="${five_hour_pct}%"
else
    session_usage="N/A"
fi

if [ -n "$five_hour_resets" ] && [ "$five_hour_resets" != "null" ] && [ "$five_hour_resets" != "" ]; then
    session_reset=$(format_resets_at "$five_hour_resets")
else
    session_reset="N/A"
fi

if [ -n "$seven_day_pct" ] && [ "$seven_day_pct" != "null" ] && [ "$seven_day_pct" != "" ]; then
    seven_day_pct=$(round_pct "$seven_day_pct")
    week_usage="${seven_day_pct}%"
else
    week_usage="N/A"
fi

# コンテキスト使用量を計算
context_usage=$(calculate_context_usage "$context_tokens" "$context_pct" "$context_window_size")

# resets 情報の整形（5h のみ表示、1w は省略）
session_resets_display=""
if [ -n "$session_reset" ] && [ "$session_reset" != "N/A" ]; then
    session_resets_display=" ($session_reset)"
fi

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
session_bar=""
if [ -n "$five_hour_pct" ] && [ "$five_hour_pct" != "null" ] && [ "$five_hour_pct" != "" ]; then
    session_bar=$(make_bar "$five_hour_pct" 10)
fi
week_bar=""
if [ -n "$seven_day_pct" ] && [ "$seven_day_pct" != "null" ] && [ "$seven_day_pct" != "" ]; then
    week_bar=$(make_bar "$seven_day_pct" 10)
fi
context_bar=""
if [ -n "$context_pct" ] && [ "$context_pct" != "null" ] && [ "$context_pct" != "" ]; then
    local_context_pct=$(round_pct "$context_pct")
    context_bar=$(make_bar "$local_context_pct" 10)
fi

# 出力（2行表示、echo -e で ANSI エスケープを有効化）
# 1行目: タイトル + モデル + 数値情報（テキストのみ、コンパクト）
# 2行目: 進捗バー 3 本をまとめて表示（視覚的インジケーター）
line1="${conversation_title}🤖 ${model} | ⏱️ ${duration_formatted} 🔧 ${api_duration_formatted} | ✏️ +${lines_added}/-${lines_removed} | 📦 ${version}"
line2="📊 5h:${session_bar} ${session_usage}${session_resets_display}  1w:${week_bar} ${week_usage}  💬 ${context_bar} ${context_usage}"
echo -e "${line1}\n${line2}"
