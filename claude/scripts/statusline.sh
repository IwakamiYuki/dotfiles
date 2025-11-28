#!/bin/bash
#
# Claude Code statusLine カスタムスクリプト
#
# 表示項目：
# 🤖 モデル名 - 使用中のClaudeモデル（例：Sonnet 4.5）
# 💰 セッションコスト - 現在のセッションで使用した金額（USD）
# ⏱️ 総処理時間 - セッション開始からの経過時間（秒）
# 🔧 API処理時間 - 実際のAPI呼び出しに費やした時間（秒）
# ✏️ コード変更量 - 追加/削除された行数
# 📦 バージョン - Claude Codeのバージョン番号

# 標準入力からClaude Codeのコンテキスト情報を取得
input=$(cat)

# Claude Code標準データを抽出
model=$(echo "$input" | jq -r '.model.display_name')              # モデル名
cost=$(echo "$input" | jq -r '.cost.total_cost_usd')              # セッションコスト（USD）
duration=$(echo "$input" | jq -r '.cost.total_duration_ms')       # 総処理時間（ミリ秒）
api_duration=$(echo "$input" | jq -r '.cost.total_api_duration_ms') # API処理時間（ミリ秒）
lines_added=$(echo "$input" | jq -r '.cost.total_lines_added')    # 追加された行数
lines_removed=$(echo "$input" | jq -r '.cost.total_lines_removed') # 削除された行数
version=$(echo "$input" | jq -r '.version')                       # Claude Codeバージョン

# 秒単位に変換
duration_sec=$(echo "scale=1; $duration / 1000" | bc 2>/dev/null || echo "0.0")
api_duration_sec=$(echo "scale=1; $api_duration / 1000" | bc 2>/dev/null || echo "0.0")

# コストを小数点以下2桁に丸める
cost_rounded=$(printf "%.2f" "$cost")

# 出力
echo "🤖 $model | 💰 \$$cost_rounded | ⏱️ ${duration_sec}s | 🔧 API: ${api_duration_sec}s | ✏️ +${lines_added}/-${lines_removed} | 📦 $version"
