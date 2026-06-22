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

# Why: AI 生成版（generate-title.sh）と /tmp/claude-title-*.txt を共用すると、
# 遅延フォールバック呼び出しが AI タイトルを上書きしてしまうため、
# 本スクリプトはキャッシュの読み書きを行わず、毎回 transcript から抽出する。

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

# 出力
echo "$TITLE"
