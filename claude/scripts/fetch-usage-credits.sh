#!/bin/bash
#
# usage credits（今月の支出と上限）を取得して、statusline.sh 用のキャッシュへ書く
#
# 取得元: 「claude -p」の stream-json 入力へ get_usage の control_request を 1 つ送る。
# /usage と同じデータで、モデルへの問い合わせは発生しない（応答の total_api_duration_ms が 0）。
# Claude Code 自身のログインを使うので、トークンを自分で取り出さない。
# ⚠️ Agent SDK の usage_EXPERIMENTAL_MAY_CHANGE_DO_NOT_RELY_ON_THIS_API_YET と同じ経路で、
#    公式には「変更されうる」実験的 API。形が変わったら取得失敗として扱い、表示しない。
#
# キャッシュ: {enabled, used, limit, percent, currency, fetched_at}
#   used / limit は最小単位（セント等）を exponent で通貨単位に直した値。limit は上限なしなら null
#   取得に失敗しても前回の値と fetched_at は消さない（0 円と取り違えないため）
#
# 環境変数（主にテスト用）:
#   CLAUDE_CREDITS_CACHE      キャッシュのパス（既定 /tmp/claude-credits.json）
#   CLAUDE_CREDITS_CLAUDE_BIN claude の実行ファイル（既定 claude）
#   CLAUDE_CREDITS_TTL        再取得の間隔の秒数（既定 300）

# statusline から起動された claude -p がさらに取得を始めないための歯止め
if [ -n "$CLAUDE_CREDITS_FETCHING" ]; then
    exit 0
fi

CACHE="${CLAUDE_CREDITS_CACHE:-/tmp/claude-credits.json}"
CLAUDE_BIN="${CLAUDE_CREDITS_CLAUDE_BIN:-claude}"
TTL="${CLAUDE_CREDITS_TTL:-300}"
FETCH_TIMEOUT_SEC=45
# 取得が異常終了してロックが残ったときに、次の取得を止め続けないための猶予
LOCK_STALE_SEC=120
LOCK="$CACHE.lock"
# 失敗したときも TTL の間は再試行しない（壊れた状態で毎回 claude を起動しないため）
ATTEMPT="$CACHE.attempt"

REQUEST='{"type":"control_request","request_id":"u1","request":{"subtype":"get_usage","skip_behaviors":true}}'

file_mtime() {
    stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null
}

is_fresh_cache() {
    [ -f "$CACHE" ] || return 1
    local fetched
    fetched=$(jq -r '.fetched_at // 0' "$CACHE" 2>/dev/null)
    [ -n "$fetched" ] && [ $((NOW - ${fetched%.*})) -lt "$TTL" ]
}

is_recent_attempt() {
    [ -f "$ATTEMPT" ] || return 1
    [ $((NOW - $(file_mtime "$ATTEMPT"))) -lt "$TTL" ]
}

acquire_lock() {
    mkdir "$LOCK" 2>/dev/null && return 0
    local mtime
    mtime=$(file_mtime "$LOCK")
    if [ -n "$mtime" ] && [ $((NOW - mtime)) -ge "$LOCK_STALE_SEC" ]; then
        rmdir "$LOCK" 2>/dev/null
        mkdir "$LOCK" 2>/dev/null && return 0
    fi
    return 1
}

run_with_timeout() {
    if command -v gtimeout >/dev/null 2>&1; then
        gtimeout "$FETCH_TIMEOUT_SEC" "$@"
    elif command -v timeout >/dev/null 2>&1; then
        timeout "$FETCH_TIMEOUT_SEC" "$@"
    else
        "$@"
    fi
}

# 標準入力の stream-json から get_usage の応答を探し、キャッシュ用の JSON を標準出力へ返す。
# 成功した応答でないとき、金額が読み取れないときは何も出さない。
# 金額は spend（単位つき）を優先し、無ければ extra_usage（decimal_places）を使う
extract_credits() {
    jq -R -c --argjson now "$NOW" '
        fromjson?
        | select(.type == "control_response" and .response.request_id == "u1" and .response.subtype == "success")
        | .response.response.rate_limits as $r
        | ($r.spend // null) as $s
        | ($r.extra_usage // null) as $x
        | def to_unit($amount; $exp): if $amount == null then null else $amount / pow(10; $exp) end;
          (if $x != null then $x.is_enabled elif $s != null then $s.enabled else null end) as $enabled
        | (if $s != null and $s.used != null
              then to_unit($s.used.amount_minor; $s.used.exponent // 2)
              elif $x != null then to_unit($x.used_credits; $x.decimal_places // 2)
              else null end) as $used
        | (if $s != null and $s.limit != null
              then to_unit($s.limit.amount_minor; $s.limit.exponent // 2)
              elif $x != null then to_unit($x.monthly_limit; $x.decimal_places // 2)
              else null end) as $limit
        | ($s.used.currency // $x.currency // "USD") as $currency
        | select($enabled != null and ($enabled == false or $used != null))
        | {
            enabled: $enabled,
            used: (if $enabled then $used else null end),
            limit: (if $enabled then $limit else null end),
            percent: (if $enabled and $limit != null and $limit > 0 then ($used / $limit * 100) else null end),
            currency: $currency,
            fetched_at: $now
          }
    ' 2>/dev/null | head -1
}

NOW=$(date +%s)

is_fresh_cache && exit 0
is_recent_attempt && exit 0
acquire_lock || exit 0
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

touch "$ATTEMPT" 2>/dev/null

output=$(printf '%s\n' "$REQUEST" \
    | CLAUDE_CREDITS_FETCHING=1 run_with_timeout "$CLAUDE_BIN" -p \
        --input-format stream-json --output-format stream-json --verbose 2>/dev/null)

result=$(printf '%s\n' "$output" | extract_credits)
[ -n "$result" ] || exit 0

printf '%s\n' "$result" > "$CACHE.tmp" 2>/dev/null && mv "$CACHE.tmp" "$CACHE"
