#!/bin/bash

# PR レビューコメント自動対応スクリプト
# Usage: ./auto_reply_pr_comments.sh [--wait-for-ai-review]
#
# 機能:
# 1. 直前 push 以降のレビューコメントを取得
# 2. Claude が修正案を生成（ユーザー承認）
# 3. 修正を適用 + commit & push
# 4. 各コメントへの返信を生成（ユーザー承認）
# 5. 一括投稿
# 6. (オプション) AI レビュー待機後に再実行
#
# Options:
#   --wait-for-ai-review  push 後 10 分待機して AI レビューコメントに対応

set -euo pipefail

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# オプション解析
WAIT_FOR_AI_REVIEW=false
if [[ "${1:-}" == "--wait-for-ai-review" ]]; then
    WAIT_FOR_AI_REVIEW=true
fi

# 一時ファイル
COMMENTS_JSON=$(mktemp)
trap "rm -f $COMMENTS_JSON" EXIT

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}PR レビューコメント自動対応${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# PR 番号を取得
echo -e "${YELLOW}PR 情報を取得中...${NC}"
PR_NUMBER=$(gh pr view --json number --jq '.number' 2>/dev/null)
if [[ -z "$PR_NUMBER" ]]; then
    echo -e "${RED}エラー: 現在のブランチに関連付けられた PR が見つかりません${NC}" >&2
    exit 1
fi

# リポジトリを取得
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
if [[ -z "$REPO" ]]; then
    echo -e "${RED}エラー: リポジトリ情報を取得できません${NC}" >&2
    exit 1
fi

echo -e "${GREEN}PR 番号: $PR_NUMBER${NC}"
echo -e "${GREEN}リポジトリ: $REPO${NC}"
echo ""

# 待機完了フラグファイル（AI レビュー待機中かを判定）
WAIT_FLAG_FILE="/tmp/review-pr-waiting-${PR_NUMBER}.flag"

# 直前 push 時刻を取得
echo -e "${YELLOW}直前の push 時刻を取得中...${NC}"
get_last_push_time() {
    local branch remote_name
    branch=$(git branch --show-current 2>/dev/null)
    if [[ -z "$branch" ]]; then
        return 1
    fi

    if git remote | grep -q "^origin$"; then
        remote_name="origin"
    else
        remote_name=$(git remote | head -n 1)
    fi

    if [[ -z "$remote_name" ]]; then
        return 1
    fi

    if ! git rev-parse "${remote_name}/${branch}" >/dev/null 2>&1; then
        return 1
    fi

    git fetch "$remote_name" 2>/dev/null || return 1
    git log -1 --format=%aI "${remote_name}/${branch}" 2>/dev/null
}

SINCE=$(get_last_push_time)
if [[ -z "$SINCE" ]]; then
    echo -e "${YELLOW}警告: push 時刻を取得できません。全コメントを対象にします。${NC}"
else
    echo -e "${GREEN}フィルタ: $SINCE 以降のコメントを対象にします${NC}"
fi
echo ""

# コメントを JSON 形式で取得
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}レビューコメント取得中...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

OWNER=$(echo "$REPO" | cut -d/ -f1)
REPO_NAME=$(echo "$REPO" | cut -d/ -f2)

# 1. インラインコメント取得
INLINE_COMMENTS=$(gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments")
if [[ -n "$SINCE" ]]; then
    INLINE_COMMENTS=$(echo "$INLINE_COMMENTS" | jq --arg since "$SINCE" '[.[] | select(.created_at > $since)]')
fi

# 2. Review Thread コメント取得（GraphQL）
# 重要: threadId（pullRequestReviewThreadId）も取得して各コメントに紐付ける
if [[ -n "$SINCE" ]]; then
    SINCE_UTC=$(python3 -c "from datetime import datetime; dt = datetime.fromisoformat('$SINCE'); print(dt.astimezone(__import__('datetime').timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))" 2>/dev/null || echo "$SINCE")
    DISCUSSION_COMMENTS=$(gh api graphql -f query="
query {
  repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {
    pullRequest(number: $PR_NUMBER) {
      reviewThreads(first: 100) {
        nodes {
          id
          comments(first: 10) {
            nodes {
              databaseId
              author { login }
              body
              createdAt
              path
              position
            }
          }
        }
      }
    }
  }
}" | jq --arg since "$SINCE_UTC" '[.data.repository.pullRequest.reviewThreads.nodes[] | .id as $threadId | .comments.nodes[]? | select(.createdAt > $since) | . + {threadId: $threadId}]')
else
    DISCUSSION_COMMENTS=$(gh api graphql -f query="
query {
  repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {
    pullRequest(number: $PR_NUMBER) {
      reviewThreads(first: 100) {
        nodes {
          id
          comments(first: 10) {
            nodes {
              databaseId
              author { login }
              body
              createdAt
              path
              position
            }
          }
        }
      }
    }
  }
}" | jq '[.data.repository.pullRequest.reviewThreads.nodes[] | .id as $threadId | .comments.nodes[]? | . + {threadId: $threadId}]')
fi

# 統合 JSON の作成
cat > "$COMMENTS_JSON" <<EOF
{
  "pr_number": $PR_NUMBER,
  "repository": "$REPO",
  "since": "$SINCE",
  "inline_comments": $INLINE_COMMENTS,
  "discussion_comments": $DISCUSSION_COMMENTS
}
EOF

# コメント数を確認
INLINE_COUNT=$(echo "$INLINE_COMMENTS" | jq 'length')
DISCUSSION_COUNT=$(echo "$DISCUSSION_COMMENTS" | jq 'length')
TOTAL_COUNT=$((INLINE_COUNT + DISCUSSION_COUNT))

echo ""
echo -e "${GREEN}取得完了:${NC}"
echo "  インラインコメント: $INLINE_COUNT 件"
echo "  Discussion コメント: $DISCUSSION_COUNT 件"
echo "  合計: $TOTAL_COUNT 件"
echo ""

if [[ $TOTAL_COUNT -eq 0 ]]; then
    echo -e "${YELLOW}対応すべきコメントはありません。${NC}"
    exit 0
fi

# コメント一覧を表示
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}コメント一覧${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# インラインコメント表示
if [[ $INLINE_COUNT -gt 0 ]]; then
    echo "$INLINE_COMMENTS" | jq -r '.[] | "[\(.id)] \(.path):\(.line // .original_line)\n  \(.user.login): \(.body)\n"'
fi

# Discussion コメント表示
if [[ $DISCUSSION_COUNT -gt 0 ]]; then
    echo "$DISCUSSION_COMMENTS" | jq -r '.[] | "[discussion_r\(.databaseId)] \(.path // "N/A"):\(.position // "N/A") (threadId: \(.threadId))\n  \(.author.login): \(.body)\n"'
fi

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}Claude による修正案生成とレビューコメント返信を開始します${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}JSON データを Claude に渡しています...${NC}"
echo -e "${YELLOW}JSON ファイル: $COMMENTS_JSON${NC}"
echo ""
echo -e "${GREEN}次のステップ:${NC}"
echo "  1. Claude がコメントを分析"
echo "  2. 修正案を生成・承認"
echo "  3. コードを修正 + commit & push"
echo "  4. 返信文を生成・承認"
echo "  5. 返信を一括投稿"
echo ""

# Claude が JSON ファイルを読み取れるように出力
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}JSON データが準備できました${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
cat "$COMMENTS_JSON"

# AI レビュー待機モードの場合
if [[ "$WAIT_FOR_AI_REVIEW" == true ]]; then
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}AI レビュー待機モード有効${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}push 後に AI レビューが完了するまで待機します...${NC}"
    echo -e "${YELLOW}待機時間: 10 分（30 秒 × 20 回チェック）${NC}"
    echo ""

    # 待機フラグを作成
    touch "$WAIT_FLAG_FILE"

    echo -e "${GREEN}待機情報:${NC}"
    echo "  PR 番号: $PR_NUMBER"
    echo "  リポジトリ: $REPO"
    echo "  フラグファイル: $WAIT_FLAG_FILE"
    echo ""
    echo -e "${BLUE}Claude が修正・返信を完了した後、自動的に待機を開始します${NC}"
fi
