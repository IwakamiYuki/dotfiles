#!/bin/bash
#
# Claude Code statusLine カスタムスクリプト
#
# 表示項目：
# 📝 会話タイトル - session_name（/rename の名前か AI 生成タイトル）。無ければ generate-title.sh で生成
# 🤖 モデル名 + effort - 使用中のモデルと reasoning effort（fast mode 時は ⚡）
# 💬 コンテキスト使用量 - 入力トークン数 / ウィンドウサイズ と使用率
# 🧊 プロンプトキャッシュ - warm なら失効時刻、切れていれば cold。miss があれば件数
# ✏️ コード変更量 - 追加/削除された行数
# ⏱️ 総処理時間 - セッション開始からの経過時間
# ⚠️ レートリミット警告 - 5h/1w のどちらかが閾値以上のときだけ表示
#
# 5h/1w のレートリミット（rate_limits）はアカウント単位で全セッション共通のため、
# 常時表示は tmux ヘッダー側の tmux-rate-limits スクリプトが担当し、
# ここでは /tmp/claude-rate-limits.json に書き出す。

# 環境変数でstatusLineが無効化されている場合は何も出力しない（無限ループ防止）
if [ "$CLAUDE_DISABLE_STATUSLINE" = "1" ]; then
    exit 0
fi

# レートリミットをセッション内でも警告表示する使用率（%）
RATE_LIMIT_WARN_PCT=80

# 標準入力からClaude Codeのコンテキスト情報を取得
input=$(cat)

# jq の呼び出しを 1 回にまとめる（statusLine は頻繁に実行されるため）
# 空値は "" で揃え、US（\x1f）区切りで受け取る（タブは IFS の空白扱いで空欄が詰まるため）
IFS=$'\x1f' read -r model session_id session_name transcript_path effort fast_mode \
    duration lines_added lines_removed \
    context_tokens context_pct context_window_size \
    cache_observed cache_warm cache_expires_at cache_misses \
    five_hour_pct five_hour_resets seven_day_pct seven_day_resets \
    < <(echo "$input" | jq -r '[
        (.model.display_name // .model // ""),
        (.session_id // ""),
        (.session_name // ""),
        (.transcript_path // ""),
        (.effort.level // ""),
        (.fast_mode // false),
        (.cost.total_duration_ms // 0),
        (.cost.total_lines_added // 0),
        (.cost.total_lines_removed // 0),
        (.context_window.total_input_tokens // ""),
        (.context_window.used_percentage // ""),
        (.context_window.context_window_size // ""),
        (.prompt_cache.caching_observed // false),
        (.prompt_cache.warm // false),
        (.prompt_cache.expires_at // ""),
        (.prompt_cache.misses // 0),
        (.rate_limits.five_hour.used_percentage // ""),
        (.rate_limits.five_hour.resets_at // ""),
        (.rate_limits.seven_day.used_percentage // ""),
        (.rate_limits.seven_day.resets_at // "")
    ] | map(tostring) | join("\u001f")')

# 浮動小数点を整数に丸める関数（四捨五入）
round_pct() {
    printf "%.0f" "$1" 2>/dev/null || echo "0"
}

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

# 会話タイトル: session_name を優先し、他スクリプト（notify-ask.sh、tmux-claude-agents-jump）が
# 読むキャッシュファイルにも書き出す。session_name が無い間は従来の AI 生成にフォールバック
build_title() {
    local title="$session_name"
    if [ -n "$title" ] && [ -n "$session_id" ]; then
        local cache_file="/tmp/claude-title-${session_id}.txt"
        if [ "$(cat "$cache_file" 2>/dev/null)" != "$title" ]; then
            echo "$title" > "$cache_file" 2>/dev/null
        fi
    elif [ -n "$transcript_path" ]; then
        title=$(bash ~/.claude/scripts/generate-title.sh "$transcript_path" 2>/dev/null)
    fi

    if [ -n "$title" ] && [ "$title" != "新しい会話" ]; then
        printf "📝 %s | " "$title"
    fi
}

# モデル名 + effort（例: "Opus 5.5 xhigh⚡"）
build_model() {
    local display="🤖 ${model}"
    [ -n "$effort" ] && display+=" ${effort}"
    [ "$fast_mode" = "true" ] && display+="⚡"
    printf "%s" "$display"
}

# コンテキスト使用量（used_percentage と同じく入力トークンのみで数える）
build_context() {
    if [ -z "$context_pct" ]; then
        printf "💬 N/A"
        return
    fi

    local pct
    pct=$(round_pct "$context_pct")
    local tokens_display=""
    if [ -n "$context_window_size" ]; then
        local tokens=${context_tokens:-0}
        # 数値が取れない場合はパーセンテージから逆算
        if [ "$tokens" -eq 0 ] 2>/dev/null; then
            tokens=$((pct * context_window_size / 100))
        fi
        tokens_display="$(format_tokens "$tokens")/$(format_tokens "$context_window_size") "
    fi
    printf "💬 %s %s%s%%" "$(make_bar "$pct" 10)" "$tokens_display" "$pct"
}

# プロンプトキャッシュ: 残り時間ではなく失効時刻を出す（イベント駆動の再描画でも古くならないため）
build_cache() {
    [ "$cache_observed" != "true" ] && return

    local display
    if [ "$cache_warm" = "true" ] && [ -n "$cache_expires_at" ]; then
        display="🧊 ~$(date -r "$cache_expires_at" +%H:%M 2>/dev/null)"
    else
        display="\033[38;5;240m🧊 cold\033[0m"
    fi
    if [ "$cache_misses" -gt 0 ] 2>/dev/null; then
        display+=" \033[38;5;208mmiss ${cache_misses}\033[0m"
    fi
    printf " | %b" "$display"
}

# レートリミット: 閾値以上のウィンドウだけ警告表示
build_rate_limit_warning() {
    local warnings=""
    local pct
    if [ -n "$five_hour_pct" ]; then
        pct=$(round_pct "$five_hour_pct")
        [ "$pct" -ge "$RATE_LIMIT_WARN_PCT" ] && warnings+=" 5h ${pct}%"
    fi
    if [ -n "$seven_day_pct" ]; then
        pct=$(round_pct "$seven_day_pct")
        [ "$pct" -ge "$RATE_LIMIT_WARN_PCT" ] && warnings+=" 1w ${pct}%"
    fi
    [ -n "$warnings" ] && printf " | \033[38;5;196m⚠️%s\033[0m" "$warnings"
}

# tmux ヘッダー（tmux-rate-limits）用にレートリミット情報をキャッシュファイルへ書き出す
RATE_LIMITS_CACHE="/tmp/claude-rate-limits.json"
if [ -n "$five_hour_pct" ]; then
    jq -n \
        --arg five_hour_pct "$five_hour_pct" \
        --arg five_hour_resets "$five_hour_resets" \
        --arg seven_day_pct "$seven_day_pct" \
        --arg seven_day_resets "$seven_day_resets" \
        '{five_hour_pct: ($five_hour_pct | tonumber), five_hour_resets: $five_hour_resets, seven_day_pct: (if $seven_day_pct == "" then null else ($seven_day_pct | tonumber) end), seven_day_resets: $seven_day_resets}' \
        > "$RATE_LIMITS_CACHE" 2>/dev/null
fi

duration_formatted=$(format_time $((${duration%.*} / 1000)))
lines_display="\033[38;5;82m+${lines_added}\033[0m/\033[38;5;196m-${lines_removed}\033[0m"

# 出力（1行表示）
printf "%s%s | %s%s | ✏️ %b | ⏱️ %s%s\n" \
    "$(build_title)" \
    "$(build_model)" \
    "$(build_context)" \
    "$(build_cache)" \
    "$lines_display" \
    "$duration_formatted" \
    "$(build_rate_limit_warning)"
