#!/bin/bash
#
# Claude Code 会話タイトル生成スクリプト（AI 生成）
# codex exec を使用して会話を要約し、30 文字のタイトルを生成
#
# 使用方法:
#   generate-title.sh /path/to/transcript.jsonl
#
# 出力:
#   AI で生成した 30 文字のタイトル、
#   または抽出されたタイトル、
#   またはデフォルト "新しい会話"
#
# 環境変数:
#   CLAUDE_DISABLE_AI_TITLE - 1 に設定すると AI 生成をスキップ
#   CLAUDE_TITLE_MAX_LENGTH - タイトルの最大文字数（デフォルト: 30）
#

set -e

TRANSCRIPT_PATH="$1"
MAX_LENGTH="${CLAUDE_TITLE_MAX_LENGTH:-15}"

# macOS での timeout コマンド（GNU timeout がない場合は gtimeout を試す）
TIMEOUT_CMD="timeout"
if ! command -v timeout &> /dev/null; then
    if command -v gtimeout &> /dev/null; then
        TIMEOUT_CMD="gtimeout"
    else
        TIMEOUT_CMD=""  # タイムアウト機能なし
    fi
fi
TIMEOUT_DURATION=10

# 引数チェック
if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
    # フォールバック: extract-title.sh を呼び出す
    bash ~/.claude/scripts/extract-title.sh "$TRANSCRIPT_PATH"
    exit 0
fi

# セッション ID を生成
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

# 環境変数で無効化されている場合はルールベースにフォールバック
if [ "$CLAUDE_DISABLE_AI_TITLE" = "1" ]; then
    bash ~/.claude/scripts/extract-title.sh "$TRANSCRIPT_PATH"
    exit 0
fi

# codex exec が利用可能か確認
if ! command -v codex &> /dev/null; then
    # codex がない場合はルールベースにフォールバック
    bash ~/.claude/scripts/extract-title.sh "$TRANSCRIPT_PATH"
    exit 0
fi

# 会話履歴を整形（直近 300 メッセージのみ、20000 文字まで）
# content が文字列の場合はそのまま、配列の場合は[0].text を使用
CONVERSATION=$(jq -r '.message? |
  if .content | type == "array" then
    "\(.role): \(.content[0].text?)"
  else
    "\(.role): \(.content?)"
  end' "$TRANSCRIPT_PATH" 2>/dev/null | \
    tail -300 | \
    head -c 20000)

# トランスクリプトが空の場合
if [ -z "$CONVERSATION" ]; then
    bash ~/.claude/scripts/extract-title.sh "$TRANSCRIPT_PATH"
    exit 0
fi

# プロンプト作成
PROMPT="以下の会話を 15 文字以内で一言で要約してください。形式: 動詞+対象、または名詞。例：『バグ修正』『機能実装』『設定変更』

会話履歴:
$CONVERSATION

タイトル:"

# codex exec でタイトル生成（タイムアウト付き）
if [ -n "$TIMEOUT_CMD" ]; then
    TITLE=$($TIMEOUT_CMD $TIMEOUT_DURATION /opt/homebrew/bin/codex exec "$PROMPT" 2>/dev/null | \
        head -1 | \
        sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | \
        cut -c1-${MAX_LENGTH}) || true
else
    TITLE=$(/opt/homebrew/bin/codex exec "$PROMPT" 2>/dev/null | \
        head -1 | \
        sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | \
        cut -c1-${MAX_LENGTH}) || true
fi

# 生成失敗時のフォールバック（TITLE が空またはタイムアウト）
if [ -z "$TITLE" ] || [ ${#TITLE} -lt 2 ]; then
    bash ~/.claude/scripts/extract-title.sh "$TRANSCRIPT_PATH"
    exit 0
fi

# 「新しい会話」以外のみキャッシュに保存
if [ "$TITLE" != "新しい会話" ]; then
    echo "$TITLE" > "$CACHE_FILE" 2>/dev/null || true
    echo "$CURRENT_MSG_COUNT" > "$CACHE_META_FILE" 2>/dev/null || true
fi

# 出力
echo "$TITLE"
