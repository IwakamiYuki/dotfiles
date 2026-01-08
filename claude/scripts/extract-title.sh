#!/bin/bash
#
# Claude Code 会話タイトル抽出スクリプト（ルールベース）
# 最初のユーザーメッセージから 30 文字を抽出してタイトルを生成
#
# 使用方法:
#   extract-title.sh /path/to/transcript.jsonl
#
# 出力:
#   最初のユーザーメッセージから抽出した 30 文字のタイトル、
#   またはキャッシュ内容、またはデフォルト "新しい会話"
#

set -e

TRANSCRIPT_PATH="$1"
MAX_LENGTH="${CLAUDE_TITLE_MAX_LENGTH:-20}"

# 引数チェック
if [ -z "$TRANSCRIPT_PATH" ]; then
    echo "新しい会話"
    exit 0
fi

# トランスクリプトファイル存在チェック
if [ ! -f "$TRANSCRIPT_PATH" ]; then
    echo "新しい会話"
    exit 0
fi

# セッション ID を生成（ディレクトリ名から取得）
# トランスクリプトパス: /Users/a13445/.claude/projects/-Users-a13445-dotfiles/87e610fe-3f81-4469-aa8d-9ea44b5ca1ff.jsonl
# セッション ID: 87e610fe-3f81-4469-aa8d-9ea44b5ca1ff（ベースネーム、拡張子なし）
SESSION_ID=$(basename "$TRANSCRIPT_PATH" .jsonl)
CACHE_FILE="/tmp/claude-title-${SESSION_ID}.txt"
CACHE_META_FILE="/tmp/claude-title-${SESSION_ID}.meta"

# 現在のメッセージ数を取得
CURRENT_MSG_COUNT=$(wc -l < "$TRANSCRIPT_PATH" 2>/dev/null || echo 0)

# キャッシュとメタデータを確認
if [ -f "$CACHE_FILE" ] && [ -f "$CACHE_META_FILE" ]; then
    CACHED_MSG_COUNT=$(cat "$CACHE_META_FILE" 2>/dev/null || echo 0)
    # メッセージ数の差が 100 未満ならキャッシュを使用
    if [ $((CURRENT_MSG_COUNT - CACHED_MSG_COUNT)) -lt 100 ]; then
        cat "$CACHE_FILE"
        exit 0
    fi
    # メッセージ数が 100 以上増えた場合は古いキャッシュを削除
    rm -f "$CACHE_FILE" "$CACHE_META_FILE"
fi

# JSONL から最初の user メッセージを抽出
# - role が "user" の最初のエントリを取得
# - content が文字列の場合はそのまま使用、配列の場合は[0].text を使用
# - 改行を空白に変換、MAX_LENGTH 文字に省略
TITLE=$(jq -r 'select(.message? and .message.role? == "user") |
  if .message.content | type == "array" then
    .message.content[0].text?
  else
    .message.content?
  end' "$TRANSCRIPT_PATH" 2>/dev/null | \
    head -1 | \
    tr '\n' ' ' | \
    sed 's/[[:space:]]\+/ /g' | \
    sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | \
    cut -c1-${MAX_LENGTH})

# タイトルが空の場合のフォールバック
if [ -z "$TITLE" ]; then
    TITLE="新しい会話"
fi

# メッセージ数が 10 以上で、かつ「新しい会話」以外のみキャッシュに保存
if [ "$CURRENT_MSG_COUNT" -ge 10 ] && [ "$TITLE" != "新しい会話" ]; then
    echo "$TITLE" > "$CACHE_FILE" 2>/dev/null || true
    echo "$CURRENT_MSG_COUNT" > "$CACHE_META_FILE" 2>/dev/null || true
fi

# 出力
echo "$TITLE"
