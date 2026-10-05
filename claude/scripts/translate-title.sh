#!/bin/bash
#
# プラン承認で付く英語のセッション名（例: eve-account-takeover-redesign）を日本語に訳す
#
# 使用方法:
#   translate-title.sh <session_id> <session_name> [transcript_path]
#
# 出力:
#   訳が保存済みならその訳。無ければハイフンを空白にした名前をすぐ返し、
#   バックグラウンドで codex に訳させる（statusLine の描画を待たせないため）。
#   訳が出来たら /tmp/claude-title-<session_id>.txt を書き直すので、
#   それを読む sidebar・通知にも次の読み込みで反映される。
#
# 呼び出し側（statusline.sh）が、英小文字・数字のハイフンつなぎの名前だけを渡す前提。
#
# 環境変数:
#   CLAUDE_DISABLE_AI_TITLE    - 1 に設定すると訳さない（空白区切りだけ返す）
#   CLAUDE_TITLE_JA_CACHE      - 訳の保存先（"英語名|訳" の行。既定: /tmp/claude-title-ja-cache.txt）
#   CLAUDE_TITLE_CODEX_BIN     - codex のパス（主にテスト用）
#

# 訳の整形（tr・${var:0:N}）を文字単位で行うため。C ロケールで起動されるとバイト単位になり日本語が壊れる
export LC_ALL=en_US.UTF-8

SESSION_ID="$1"
NAME="$2"
TRANSCRIPT_PATH="$3"

JA_CACHE_FILE="${CLAUDE_TITLE_JA_CACHE:-/tmp/claude-title-ja-cache.txt}"
CODEX_BIN="${CLAUDE_TITLE_CODEX_BIN:-/opt/homebrew/bin/codex}"
TITLE_CACHE_FILE="/tmp/claude-title-${SESSION_ID}.txt"
# 名前ごとに分ける: セッション単位だと、前の名前の翻訳中に名前が変わったとき新しい名前の翻訳が始まらない
LOCK_FILE="/tmp/claude-title-${SESSION_ID}.${NAME}.ja.lock"

# codex がプロンプトの文字数を守らなかったときの切り捨て上限
MAX_LENGTH=20
TIMEOUT_DURATION=40
# 参考に渡すプランの文字数。名前だけだと "takeover" を「乗っ取り」と訳すなど意味を取り違えるため
PLAN_CONTEXT_CHARS=800

TIMEOUT_CMD="timeout"
if ! command -v timeout &> /dev/null; then
    if command -v gtimeout &> /dev/null; then
        TIMEOUT_CMD="gtimeout"
    else
        TIMEOUT_CMD=""
    fi
fi

spaced_name="${NAME//-/ }"

lookup_translation() {
    awk -F'|' -v k="$NAME" '$1 == k { v = $2 } END { print v }' "$JA_CACHE_FILE" 2>/dev/null
}

latest_plan() {
    [ -f "$TRANSCRIPT_PATH" ] || return 0
    # 末尾だけでなく全体を探す: 機能導入前に承認したプランは末尾から遠い。数十 MB でも grep は数十 ms
    grep -a '"name":"ExitPlanMode"' "$TRANSCRIPT_PATH" 2>/dev/null | tail -n 1 \
        | jq -r --argjson n "$PLAN_CONTEXT_CHARS" \
            '.message.content[]? | select(.type == "tool_use" and .name == "ExitPlanMode") | .input.plan // "" | .[0:$n]' \
            2>/dev/null
}

build_prompt() {
    local plan="$1"
    printf '%s\n' "次の英語のセッション名を、日本語の短いタイトル（12 文字程度、長くても 15 文字）に訳してください。
- 意味は「参考: 作業計画」の内容に合わせる（無ければ一般的な意味で訳す）
- 固有名詞・略語・コード上の識別子はそのまま残す
- 「〜の実装」「〜について」のような無くても意味が通じる語は省く
- 出力はタイトルだけ（説明や引用符は付けない）

セッション名: $NAME

参考: 作業計画
$plan"
}

# codex の出力から最初の空でない行を取り、括弧・引用符と区切り文字の | を除いて MAX_LENGTH 文字に切る
clean_translation() {
    local line
    line=$(grep -v '^[[:space:]]*$' | head -n 1)
    line=$(printf '%s' "$line" | tr -d '|「」『』"' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    printf '%s' "${line:0:$MAX_LENGTH}"
}

run_codex() {
    # stdin で渡す: 引数だと codex が stdin も読みに行き、statusLine から起動すると待ち続けるため
    if [ -n "$TIMEOUT_CMD" ]; then
        build_prompt "$1" | $TIMEOUT_CMD $TIMEOUT_DURATION "$CODEX_BIN" exec --skip-git-repo-check - 2>/dev/null
    else
        build_prompt "$1" | "$CODEX_BIN" exec --skip-git-repo-check - 2>/dev/null
    fi
}

translate_in_background() {
    (
        local translation
        translation=$(run_codex "$(latest_plan)" | clean_translation)
        if [ ${#translation} -ge 2 ]; then
            echo "${NAME}|${translation}" >> "$JA_CACHE_FILE" 2>/dev/null
            # 訳している間に名前が変わっていたら（表示が仮のものでなくなっていたら）古い訳で上書きしない
            if [ "$(cat "$TITLE_CACHE_FILE" 2>/dev/null)" = "$spaced_name" ]; then
                echo "$translation" > "$TITLE_CACHE_FILE" 2>/dev/null
            fi
        fi
        rm -f "$LOCK_FILE"
    ) < /dev/null > /dev/null 2>&1 &
}

translation=$(lookup_translation)
if [ -n "$translation" ]; then
    echo "$translation"
    exit 0
fi

echo "$spaced_name"

[ "$CLAUDE_DISABLE_AI_TITLE" = "1" ] && exit 0
[ -x "$CODEX_BIN" ] || exit 0

# statusLine は短い間隔で何度も呼ばれるので、同じ名前の翻訳は 1 つだけ走らせる
if [ -f "$LOCK_FILE" ]; then
    # タイムアウトより古いロックは、異常終了の残りとみなして消す
    [ "$(find "$LOCK_FILE" -mmin +1 2>/dev/null)" ] || exit 0
    rm -f "$LOCK_FILE"
fi
touch "$LOCK_FILE"
translate_in_background
