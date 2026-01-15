#!/bin/bash

# AI レビュー待機＆再チェックスクリプト
# Usage: ./wait_and_recheck_pr_comments.sh <pr_number> <repo>
#
# 機能:
# 1. 30 秒 × 20 回（合計 10 分）待機
# 2. 各待機後、新しいコメントがあるかチェック
# 3. 新しいコメントがあれば通知して終了
# 4. なければ最後まで待機

set -euo pipefail

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 引数チェック
if [[ $# -lt 2 ]]; then
    echo -e "${RED}エラー: 引数が不足しています${NC}" >&2
    echo "Usage: $0 <pr_number> <repo>" >&2
    exit 1
fi

PR_NUMBER="$1"
REPO="$2"
OWNER=$(echo "$REPO" | cut -d/ -f1)
REPO_NAME=$(echo "$REPO" | cut -d/ -f2)

# 待機開始時刻を記録
START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}AI レビュー待機開始${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}PR #$PR_NUMBER ($REPO) の AI レビューを待機中...${NC}"
echo -e "${YELLOW}開始時刻: $START_TIME${NC}"
echo -e "${YELLOW}待機時間: 10 分（30 秒 × 20 回チェック）${NC}"
echo ""

# 30 秒 × 20 回 = 10 分
WAIT_INTERVAL=30
MAX_ATTEMPTS=20

for i in $(seq 1 $MAX_ATTEMPTS); do
    ELAPSED=$((i * WAIT_INTERVAL))
    REMAINING=$((MAX_ATTEMPTS * WAIT_INTERVAL - ELAPSED))

    echo -e "${BLUE}[チェック $i/$MAX_ATTEMPTS] 経過時間: ${ELAPSED}秒 / 残り: ${REMAINING}秒${NC}"

    # 新しいコメントがあるかチェック
    INLINE_COUNT=$(gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments" | jq --arg since "$START_TIME" '[.[] | select(.created_at > $since)] | length')

    DISCUSSION_COUNT=$(gh api graphql -f query="
query {
  repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {
    pullRequest(number: $PR_NUMBER) {
      reviewThreads(first: 100) {
        nodes {
          comments(first: 10) {
            nodes {
              createdAt
            }
          }
        }
      }
    }
  }
}" | jq --arg since "$START_TIME" '[.data.repository.pullRequest.reviewThreads.nodes[]?.comments.nodes[]? | select(.createdAt > $since)] | length')

    TOTAL_NEW_COMMENTS=$((INLINE_COUNT + DISCUSSION_COUNT))

    if [[ $TOTAL_NEW_COMMENTS -gt 0 ]]; then
        echo ""
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}✅ 新しいコメントを検出しました！${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo ""
        echo -e "${YELLOW}検出したコメント:${NC}"
        echo "  インラインコメント: $INLINE_COUNT 件"
        echo "  Discussion コメント: $DISCUSSION_COUNT 件"
        echo "  合計: $TOTAL_NEW_COMMENTS 件"
        echo ""
        echo -e "${CYAN}Claude に再度レビューコメント対応を依頼してください：${NC}"
        echo -e "${CYAN}「レビューコメントに対応」${NC}"
        echo ""

        # macOS 通知
        if command -v terminal-notifier &> /dev/null; then
            terminal-notifier -title "PR Review" \
                -message "PR #$PR_NUMBER に新しいコメント $TOTAL_NEW_COMMENTS 件" \
                -sound default \
                >/dev/null 2>&1 || true
        fi

        exit 0
    fi

    # 最後の試行でなければ待機
    if [[ $i -lt $MAX_ATTEMPTS ]]; then
        echo -e "${YELLOW}  新しいコメントなし。${WAIT_INTERVAL}秒後に再チェック...${NC}"
        sleep $WAIT_INTERVAL
    fi
done

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}待機完了（10 分経過）${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${CYAN}新しいコメントは検出されませんでした。${NC}"
echo -e "${CYAN}AI レビューが完了していない可能性があります。${NC}"
echo ""
