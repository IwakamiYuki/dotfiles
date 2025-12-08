#!/bin/bash
#
# Claude Code statusLine カスタムスクリプト
#
# 表示項目：
# 🤖 モデル名 - 使用中のClaudeモデル
# 📊 セッション使用率 - /usage の Current session 情報（%とリセット時間）
# 💬 コンテキスト使用量 - 現在の会話のトークン使用量（概算）
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
    local input_tok=$1
    local output_tok=$2
    local cache_read_tok=$3
    local cache_create_tok=$4
    local transcript=$5
    local model_id=$6

    local context_window=$(get_context_window "$model_id")

    # トークン情報が利用可能な場合
    if [ -n "$input_tok" ] && [ "$input_tok" != "null" ] && [ "$input_tok" != "" ]; then
        local total_tokens=$((input_tok + output_tok))
        # キャッシュ読み取りトークンは入力トークンの一部なので、追加しない
        local usage_pct=$((total_tokens * 100 / context_window))
        local context_window_k=$((context_window / 1000))

        # 1K 単位で表示（可読性向上）
        if [ $total_tokens -ge 1000 ]; then
            local tokens_k=$((total_tokens / 1000))
            printf "${tokens_k}K/${context_window_k}K (${usage_pct}%%)"
        else
            printf "${total_tokens}/${context_window} (${usage_pct}%%)"
        fi
        return
    fi

    # トランスクリプトファイルから取得
    if [ -n "$transcript" ] && [ "$transcript" != "null" ] && [ -f "$transcript" ]; then
        # JSONL 形式の場合、usage 情報から正確なトークン数を取得
        if [[ "$transcript" == *.jsonl ]]; then
            # 最後の assistant メッセージの cache_read_input_tokens が最も正確
            # これは累積コンテキスト（システムプロンプト + ツール + メッセージ履歴）を表す
            # tail -r で逆順にして最初の assistant メッセージを取得（macOS 互換）
            local last_usage=$(tail -r "$transcript" 2>/dev/null | jq -r 'select(.message.role == "assistant") | .message.usage.cache_read_input_tokens // 0' 2>/dev/null | head -1)

            # メッセージ数をカウント（全体）
            local msg_count=$(wc -l < "$transcript" 2>/dev/null | tr -d ' ' || echo "0")

            if [ -n "$last_usage" ] && [ "$last_usage" != "null" ] && [ "$last_usage" != "0" ] && [ "$last_usage" -gt 0 ] 2>/dev/null; then
                # assistant メッセージが存在する場合
                # cache_read_input_tokens がコンテキストの大部分を表している
                # 固定オーバーヘッド（約 52k: システムプロンプト + ツール定義 + メモリ + 出力）を加算
                # /context の実測: 128k = 76k (cache_read) + 52k (固定)
                local total_tokens=$((last_usage + 52000))

                local usage_pct=$((total_tokens * 100 / context_window))
                local context_window_k=$((context_window / 1000))

                # 1K 単位で表示
                if [ $total_tokens -ge 1000 ]; then
                    local tokens_k=$((total_tokens / 1000))
                    printf "${tokens_k}K/${context_window_k}K (${usage_pct}%%) ${msg_count}msg"
                else
                    printf "${total_tokens}/${context_window} (${usage_pct}%%) ${msg_count}msg"
                fi
                return
            else
                # assistant メッセージがまだない場合（新しいセッション）
                # 固定オーバーヘッドのみを表示（約 42k）
                local total_tokens=42000
                local usage_pct=$((total_tokens * 100 / context_window))
                local context_window_k=$((context_window / 1000))
                local tokens_k=$((total_tokens / 1000))

                printf "${tokens_k}K/${context_window_k}K (${usage_pct}%%) ${msg_count}msg"
                return
            fi
        else
            # Markdown 形式の場合は概算（後方互換性）
            local file_size=$(wc -c < "$transcript" 2>/dev/null || echo "0")
            local msg_count=$(grep -c "^##\+ Message" "$transcript" 2>/dev/null || echo "0")

            if [ "$file_size" -gt 0 ]; then
                local estimated_tokens=$((file_size / 3))
                local usage_pct=$((estimated_tokens * 100 / context_window))
                local context_window_k=$((context_window / 1000))

                if [ $estimated_tokens -ge 1000 ]; then
                    local tokens_k=$((estimated_tokens / 1000))
                    printf "~${tokens_k}K/${context_window_k}K (${usage_pct}%%) ${msg_count}msg"
                else
                    printf "~${estimated_tokens}/${context_window} (${usage_pct}%%) ${msg_count}msg"
                fi
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
session_usage=$(echo "$session_info" | jq -r '.usage' 2>/dev/null || echo "N/A")
session_reset=$(echo "$session_info" | jq -r '.resets' 2>/dev/null || echo "N/A")

# コンテキスト使用量を計算
context_usage=$(calculate_context_usage "$input_tokens" "$output_tokens" "$cache_read_tokens" "$cache_creation_tokens" "$transcript_path" "$model_id")

# 出力
echo "🤖 $model | 📊 Session: $session_usage (resets $session_reset) | 💬 Context: $context_usage | ⏱️ ${duration_formatted} | 🔧 API: ${api_duration_formatted} | ✏️ +${lines_added}/-${lines_removed} | 📦 $version"
