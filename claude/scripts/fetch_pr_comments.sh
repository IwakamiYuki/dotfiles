#!/bin/bash

# PR レビューコメント取得スクリプト
# Usage: ./tools/review-pr/fetch_pr_comments.sh [OPTIONS]
#
# Options:
#   -s, --since <timestamp>  特定の日時以降のコメントのみ取得
#   -p, --priority <level>   優先度フィルタ (P1, P2, etc.)
#   -h, --help              ヘルプを表示

set -euo pipefail

# デフォルト設定
SINCE=""
PRIORITY=""

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ヘルプ表示
show_help() {
    cat << EOF
PR レビューコメント取得スクリプト

Usage: $0 [OPTIONS]

Options:
  -s, --since <timestamp>  特定の日時以降のコメントのみ取得
                           例: "2025-01-08T09:00:00Z"
  -p, --priority <level>   優先度フィルタ (P1, P2, etc.)
  -h, --help              このヘルプを表示

Examples:
  $0                            # 全コメント取得
  $0 -s "2025-01-08T09:00:00Z"  # 特定日時以降のコメント
  $0 -p P1                      # P1 優先度のコメントのみ

EOF
    exit 0
}

# 引数解析
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--since)
            if [[ $# -lt 2 ]]; then
                echo -e "${RED}エラー: -s オプションには引数が必要です${NC}" >&2
                show_help
            fi
            SINCE="$2"
            shift 2
            ;;
        -p|--priority)
            if [[ $# -lt 2 ]]; then
                echo -e "${RED}エラー: -p オプションには引数が必要です${NC}" >&2
                show_help
            fi
            PRIORITY="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            ;;
        *)
            echo -e "${RED}エラー: 不明なオプション: $1${NC}" >&2
            show_help
            ;;
    esac
done

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}PR レビューコメント取得${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

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

# 1. インラインコメント取得
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}インラインコメント (Pull Request Review Comments)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [[ -n "$SINCE" ]]; then
    gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments" | \
      jq --arg since "$SINCE" '.[] | select(.created_at > $since) | "File: \(.path)\nLine: \(.line // .original_line)\nAuthor: \(.user.login)\nCreated: \(.created_at)\n\(.body)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"' -r
elif [[ -n "$PRIORITY" ]]; then
    gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments" | \
      jq --arg priority "$PRIORITY" '.[] | select(.body | contains($priority)) | "File: \(.path)\nLine: \(.line // .original_line)\nAuthor: \(.user.login)\nCreated: \(.created_at)\n\(.body)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"' -r
else
    gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments" | \
      jq '.[] | "File: \(.path)\nLine: \(.line // .original_line)\nAuthor: \(.user.login)\nCreated: \(.created_at)\n\(.body)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"' -r
fi

# 2. 一般コメント取得
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}一般コメント (Issue Comments)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

ISSUE_COMMENTS=$(gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" | jq '. | length')
if [[ "$ISSUE_COMMENTS" -gt 0 ]]; then
    if [[ -n "$SINCE" ]]; then
        gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" | \
          jq --arg since "$SINCE" '.[] | select(.created_at > $since) | "Author: \(.user.login)\nCreated: \(.created_at)\n\(.body)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"' -r
    else
        gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" | \
          jq '.[] | "Author: \(.user.login)\nCreated: \(.created_at)\n\(.body)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"' -r
    fi
else
    echo "一般コメントなし"
fi

# 3. レビューコメント取得
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}レビューコメント (Pull Request Reviews)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [[ -n "$SINCE" ]]; then
    gh api "repos/${REPO}/pulls/${PR_NUMBER}/reviews" | \
      jq --arg since "$SINCE" '.[] | select(.body and (.body | length) > 0 and .submitted_at > $since) | "Review by: \(.user.login)\nState: \(.state)\nSubmitted: \(.submitted_at)\n\(.body)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"' -r
else
    gh api "repos/${REPO}/pulls/${PR_NUMBER}/reviews" | \
      jq '.[] | select(.body and (.body | length) > 0) | "Review by: \(.user.login)\nState: \(.state)\nSubmitted: \(.submitted_at)\n\(.body)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"' -r
fi

# サマリー
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}取得完了${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

INLINE_COUNT=$(gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments" | jq '. | length')
ISSUE_COUNT=$(gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" | jq '. | length')
REVIEW_COUNT=$(gh api "repos/${REPO}/pulls/${PR_NUMBER}/reviews" | jq '[.[] | select(.body and (.body | length) > 0)] | length')

echo "インラインコメント: $INLINE_COUNT 件"
echo "一般コメント: $ISSUE_COUNT 件"
echo "レビューコメント: $REVIEW_COUNT 件"
echo "合計: $((INLINE_COUNT + ISSUE_COUNT + REVIEW_COUNT)) 件"

if [[ -n "$SINCE" ]]; then
    echo ""
    echo -e "${YELLOW}フィルタ: $SINCE 以降のコメントを表示${NC}"
fi

if [[ -n "$PRIORITY" ]]; then
    echo ""
    echo -e "${YELLOW}フィルタ: $PRIORITY を含むコメントを表示${NC}"
fi
