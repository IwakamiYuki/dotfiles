#!/bin/bash

# PR レビューコメント返信投稿ヘルパー
# Usage: ./post_pr_reply.sh <comment_type> <comment_id> <message> [thread_id]
#
# comment_type: "inline" または "discussion"
# comment_id: コメント ID (inline の場合) または databaseId (discussion の場合)
# message: 返信メッセージ
# thread_id: (オプション) discussion の場合、pullRequestReviewThreadId を直接指定

set -euo pipefail

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 引数チェック
if [[ $# -lt 3 ]]; then
    echo -e "${RED}エラー: 引数が不足しています${NC}" >&2
    echo "Usage: $0 <comment_type> <comment_id> <message> [thread_id]" >&2
    echo "  comment_type: 'inline' または 'discussion'" >&2
    echo "  thread_id: (オプション) discussion の場合、pullRequestReviewThreadId" >&2
    exit 1
fi

COMMENT_TYPE="$1"
COMMENT_ID="$2"
MESSAGE="$3"
THREAD_ID="${4:-}"

# AI 署名を追加
MESSAGE="${MESSAGE}"$'\n\n'"---"$'\n'"🤖 _This reply was generated with AI assistance_"

# PR 情報を取得
PR_NUMBER=$(gh pr view --json number --jq '.number' 2>/dev/null)
if [[ -z "$PR_NUMBER" ]]; then
    echo -e "${RED}エラー: 現在のブランチに関連付けられた PR が見つかりません${NC}" >&2
    exit 1
fi

REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)
if [[ -z "$REPO" ]]; then
    echo -e "${RED}エラー: リポジトリ情報を取得できません${NC}" >&2
    exit 1
fi

OWNER=$(echo "$REPO" | cut -d/ -f1)
REPO_NAME=$(echo "$REPO" | cut -d/ -f2)

# コメントタイプに応じて投稿
case "$COMMENT_TYPE" in
    inline)
        # REST API: インラインコメントへの返信
        # 注意: REST API では返信エンドポイントが非公式のため、GraphQL を推奨
        echo -e "${YELLOW}インラインコメントへの返信を投稿中...${NC}"
        RESPONSE=$(gh api -X POST \
          "/repos/${REPO}/pulls/${PR_NUMBER}/comments/${COMMENT_ID}/replies" \
          -f body="$MESSAGE" 2>&1)

        if [[ $? -ne 0 ]]; then
            # REST API が失敗した場合、GraphQL にフォールバック
            echo -e "${YELLOW}REST API が失敗しました。GraphQL API を試行します...${NC}"

            # インラインコメントの reply_to_id を取得
            REPLY_TO_ID=$(gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments/${COMMENT_ID}" | jq -r '.id')

            gh api graphql -f query="
mutation {
  addPullRequestReviewComment(input: {
    pullRequestId: \"$(gh api graphql -f query="query { repository(owner: \"$OWNER\", name: \"$REPO_NAME\") { pullRequest(number: $PR_NUMBER) { id } } }" | jq -r '.data.repository.pullRequest.id')\"
    body: \"$MESSAGE\"
    inReplyTo: \"$REPLY_TO_ID\"
  }) {
    comment {
      id
    }
  }
}
"
            if [[ $? -ne 0 ]]; then
                echo -e "${RED}エラー: 返信の投稿に失敗しました${NC}" >&2
                exit 1
            fi
        fi
        ;;

    discussion)
        # GraphQL API: Discussion コメントへの返信
        echo -e "${YELLOW}Discussion コメントへの返信を投稿中...${NC}"

        # threadId が指定されている場合はそれを使用、なければ取得
        if [[ -n "$THREAD_ID" ]]; then
            echo -e "${GREEN}threadId が指定されています: $THREAD_ID${NC}"
            COMMENT_THREAD_ID="$THREAD_ID"
        else
            echo -e "${YELLOW}threadId が指定されていないため、GraphQL で取得します...${NC}"
            # Discussion コメントのスレッド ID を取得
            COMMENT_THREAD_ID=$(gh api graphql -f query="
query {
  repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {
    pullRequest(number: $PR_NUMBER) {
      reviewThreads(first: 100) {
        nodes {
          id
          comments(first: 10) {
            nodes {
              databaseId
            }
          }
        }
      }
    }
  }
}" | jq -r --arg db_id "$COMMENT_ID" '.data.repository.pullRequest.reviewThreads.nodes[] | select(.comments.nodes[]?.databaseId == ($db_id | tonumber)) | .id')

            if [[ -z "$COMMENT_THREAD_ID" ]]; then
                echo -e "${RED}エラー: スレッド ID を取得できません${NC}" >&2
                exit 1
            fi
            echo -e "${GREEN}取得したスレッド ID: $COMMENT_THREAD_ID${NC}"
        fi

        # 返信を投稿
        gh api graphql -f query="
mutation(\$threadId: ID!, \$body: String!) {
  addPullRequestReviewThreadReply(input: {
    pullRequestReviewThreadId: \$threadId
    body: \$body
  }) {
    comment {
      id
    }
  }
}" -f threadId="$COMMENT_THREAD_ID" -f body="$MESSAGE"

        if [[ $? -ne 0 ]]; then
            echo -e "${RED}エラー: 返信の投稿に失敗しました${NC}" >&2
            exit 1
        fi
        ;;

    *)
        echo -e "${RED}エラー: 不明なコメントタイプ: $COMMENT_TYPE${NC}" >&2
        echo "指定可能な値: 'inline' または 'discussion'" >&2
        exit 1
        ;;
esac

echo -e "${GREEN}✅ 返信を投稿しました${NC}"
echo -e "${BLUE}Comment ID: $COMMENT_ID${NC}"
echo -e "${BLUE}Type: $COMMENT_TYPE${NC}"
