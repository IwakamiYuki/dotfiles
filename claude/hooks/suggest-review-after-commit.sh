#!/bin/bash

# PostToolUse フック: git commit 後に review-diff スキルを提案する
# Claude Code が git commit を実行した直後に発動

INPUT=$(cat)

# ツール名を確認
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')

# Bash ツールの場合のみ処理
if [ "$TOOL_NAME" != "Bash" ]; then
    exit 0
fi

# 実行されたコマンドを取得
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# git commit コマンドかどうか確認
# git commit, git commit -m, git commit --amend など
if ! echo "$TOOL_INPUT" | grep -qE 'git commit'; then
    exit 0
fi

# ツール実行結果（終了コード）を確認
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exitCode // 0')
if [ "$EXIT_CODE" != "0" ]; then
    # コミット失敗時は提案しない
    exit 0
fi

# PostToolUse フックは stdout への出力でユーザーへのメッセージを追加できる
# JSON 形式で Claude へのメッセージを出力
cat <<'EOF'
{
  "type": "inject_context",
  "message": "\n---\n💡 **コードレビューの提案**: コミットが完了しました。`/review-diff` を実行すると、このコミットの差分を Security・Performance・Code Quality・Architecture・Testing の 5 観点から並列でレビューできます。"
}
EOF

exit 0
