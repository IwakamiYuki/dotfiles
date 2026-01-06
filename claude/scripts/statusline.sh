#!/bin/bash
#
# Claude Code statusLine カスタムスクリプト
#
# 表示項目：
# 🤖 モデル名 - 使用中のClaudeモデル
# 📊 5h セッション使用率 - /usage の Current session 情報（%とリセット時間）
# 📅 1w 週間使用率 - /usage の One week 情報（%とリセット時間）
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

# トークン情報の取得を試行（もしフィールドが存在すれば）
input_tokens=$(echo "$input" | jq -r '.cost.total_input_tokens // ""')
output_tokens=$(echo "$input" | jq -r '.cost.total_output_tokens // ""')
cache_read_tokens=$(echo "$input" | jq -r '.cost.total_cache_read_tokens // ""')
cache_creation_tokens=$(echo "$input" | jq -r '.cost.total_cache_creation_tokens // ""')
current_usage=$(echo "$input" | jq -r '.current_usage // ""')  # v2.0.70で追加されたコンテキスト使用量

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

# コンテキストウィンドウサイズを判定する関数
get_context_window() {
    local model_id=$1
    # Claude 3.5 Sonnet と Claude Sonnet 4/4.5 は 200K トークン
    if [[ "$model_id" == *"sonnet"* ]]; then
        echo "200000"
    else
        echo "200000"  # デフォルト
    fi
}

# コンテキスト使用量を計算・フォーマットする関数
calculate_context_usage() {
    local current_usage=$1
    local transcript=$2
    local model_id=$3

    local context_window=$(get_context_window "$model_id")

    # v2.0.70 以降の current_usage フィールドを優先的に使用（最も正確）
    if [ -n "$current_usage" ] && [ "$current_usage" != "null" ] && [ "$current_usage" != "" ] && [ "$current_usage" -gt 0 ] 2>/dev/null; then
        local usage_pct=$((current_usage * 100 / context_window))
        local context_window_k=$((context_window / 1000))
        local tokens_k=$((current_usage / 1000))

        # メッセージ数をカウント
        local msg_count=0
        if [ -n "$transcript" ] && [ "$transcript" != "null" ] && [ -f "$transcript" ]; then
            if [[ "$transcript" == *.jsonl ]]; then
                msg_count=$(wc -l < "$transcript" 2>/dev/null | tr -d ' ' || echo "0")
            else
                msg_count=$(grep -c "^##\+ Message" "$transcript" 2>/dev/null || echo "0")
            fi
        fi

        printf "${tokens_k}K/${context_window_k}K (${usage_pct}%%) ${msg_count}msg"
        return
    fi

    # フォールバック: トランスクリプトファイルから取得（後方互換性）
    if [ -n "$transcript" ] && [ "$transcript" != "null" ] && [ -f "$transcript" ]; then
        # JSONL 形式の場合
        if [[ "$transcript" == *.jsonl ]]; then
            local last_usage=$(tail -r "$transcript" 2>/dev/null | jq -r 'select(.message.role == "assistant") | .message.usage.cache_read_input_tokens // 0' 2>/dev/null | head -1)
            local msg_count=$(wc -l < "$transcript" 2>/dev/null | tr -d ' ' || echo "0")

            if [ -n "$last_usage" ] && [ "$last_usage" != "null" ] && [ "$last_usage" != "0" ] && [ "$last_usage" -gt 0 ] 2>/dev/null; then
                # 固定オーバーヘッド（約 52k）を加算
                local total_tokens=$((last_usage + 52000))
                local usage_pct=$((total_tokens * 100 / context_window))
                local context_window_k=$((context_window / 1000))
                local tokens_k=$((total_tokens / 1000))

                printf "${tokens_k}K/${context_window_k}K (${usage_pct}%%) ${msg_count}msg"
                return
            else
                # 新しいセッション
                local total_tokens=42000
                local usage_pct=$((total_tokens * 100 / context_window))
                local context_window_k=$((context_window / 1000))
                local tokens_k=$((total_tokens / 1000))

                printf "${tokens_k}K/${context_window_k}K (${usage_pct}%%) ${msg_count}msg"
                return
            fi
        else
            # Markdown 形式の場合は概算
            local file_size=$(wc -c < "$transcript" 2>/dev/null || echo "0")
            local msg_count=$(grep -c "^##\+ Message" "$transcript" 2>/dev/null || echo "0")

            if [ "$file_size" -gt 0 ]; then
                local estimated_tokens=$((file_size / 3))
                local usage_pct=$((estimated_tokens * 100 / context_window))
                local context_window_k=$((context_window / 1000))
                local tokens_k=$((estimated_tokens / 1000))

                printf "~${tokens_k}K/${context_window_k}K (${usage_pct}%%) ${msg_count}msg"
                return
            fi
        fi
    fi

    # 情報が取得できない場合
    printf "N/A"
}

# 時間形式に変換
duration_formatted=$(format_time "$duration_sec")
api_duration_formatted=$(format_time "$api_duration_sec")

# /usage からセッション使用情報を取得（JSON形式）
session_info=$(bash ~/.claude/scripts/get-session-usage.sh 2>/dev/null)
session_usage=$(echo "$session_info" | jq -r '.session_usage' 2>/dev/null || echo "N/A")
session_reset=$(echo "$session_info" | jq -r '.session_resets' 2>/dev/null || echo "N/A")
week_usage=$(echo "$session_info" | jq -r '.week_usage' 2>/dev/null || echo "N/A")
week_reset=$(echo "$session_info" | jq -r '.week_resets' 2>/dev/null || echo "N/A")

# コンテキスト使用量を計算
context_usage=$(calculate_context_usage "$current_usage" "$transcript_path" "$model_id")

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
        # 2行表示を試す（設計案 A）
        echo "📝 ${conversation_title}"
    fi
fi

# 出力
echo "🤖 $model | 📊 5h:$session_usage$session_resets_display 1w:$week_usage | 💬 $context_usage | ⏱️ ${duration_formatted} | 🔧 ${api_duration_formatted} | ✏️ +${lines_added}/-${lines_removed} | 📦 $version"
