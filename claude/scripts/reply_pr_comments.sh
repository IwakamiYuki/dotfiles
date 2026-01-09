#!/bin/bash

# PR レビューコメント返信スクリプト
# Usage: ./reply_pr_comments.sh -c <comment_id> -m <message> [--dry-run]

set -euo pipefail

# デフォルト設定
DRY_RUN=false
COMMENT_ID=""
REPLY_MESSAGE=""
NO_AI_SIGNATURE=false

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ヘルプ表示
show_help() {
    cat << EOF
PR レビューコメント返信スクリプト

Usage: $0 -c <comment_id> -m <message> [OPTIONS]

Options:
  -c, --comment-id <id>    返信対象のコメント ID (必須)
  -m, --message <text>     返信メッセージ (必須)
  --dry-run                実際には投稿せず、プレビューのみ表示
  --no-ai-signature        AI 署名を追加しない
  -h, --help              このヘルプを表示

Examples:
  $0 -c 123456 -m "ご指摘ありがとうございます。修正しました。"
  $0 --dry-run -c 123456 -m "テスト返信"
  $0 --no-ai-signature -c 123456 -m "人間が直接書いた返信"

EOF
    exit 0
}

# 引数解析
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-ai-signature)
            NO_AI_SIGNATURE=true
            shift
            ;;
        -c|--comment-id)
            if [[ $# -lt 2 ]]; then
                echo -e "${RED}エラー: -c オプションには引数が必要です${NC}" >&2
                show_help
            fi
            COMMENT_ID="$2"
            shift 2
            ;;
        -m|--message)
            if [[ $# -lt 2 ]]; then
                echo -e "${RED}エラー: -m オプションには引数が必要です${NC}" >&2
                show_help
            fi
            REPLY_MESSAGE="$2"
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

# 必須パラメータのチェック
if [[ -z "$COMMENT_ID" ]]; then
    echo -e "${RED}エラー: コメント ID (-c) は必須です${NC}" >&2
    show_help
fi

if [[ -z "$REPLY_MESSAGE" ]]; then
    echo -e "${RED}エラー: 返信メッセージ (-m) は必須です${NC}" >&2
    show_help
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}PR レビューコメント返信${NC}"
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
echo -e "${GREEN}コメント ID: $COMMENT_ID${NC}"
echo ""

# AI 署名を追加（デフォルト）
if [[ "$NO_AI_SIGNATURE" != true ]]; then
    REPLY_MESSAGE="${REPLY_MESSAGE}"$'\n\n'"---"$'\n'"🤖 _This reply was generated with AI assistance_"
fi

# ドライランモード
if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}ドライランモード（実際には投稿しません）${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}返信内容:${NC}"
    echo "$REPLY_MESSAGE"
    echo ""
    echo -e "${YELLOW}実際に投稿する場合は --dry-run オプションを外してください${NC}"
    exit 0
fi

# 返信を投稿
echo -e "${YELLOW}返信を投稿中...${NC}"
RESPONSE=$(gh api -X POST \
  "/repos/${REPO}/pulls/${PR_NUMBER}/comments/${COMMENT_ID}/replies" \
  -f body="$REPLY_MESSAGE" 2>&1)

# エラーチェック
if [[ $? -ne 0 ]]; then
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}エラー: 返信の投稿に失敗しました${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo "$RESPONSE"
    echo ""
    echo -e "${YELLOW}トラブルシューティング:${NC}"
    echo "- 404 Not Found: コメント ID が無効です"
    echo "- 403 Forbidden: 権限不足です。gh auth refresh -s repo を実行してください"
    echo "- 422 Unprocessable Entity: 返信本文が空または無効です"
    exit 1
fi

# 成功メッセージ
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ 返信を投稿しました${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Comment ID: $COMMENT_ID${NC}"
echo ""
echo -e "${BLUE}返信内容:${NC}"
echo "$REPLY_MESSAGE"
