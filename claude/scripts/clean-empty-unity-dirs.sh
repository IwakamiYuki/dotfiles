#!/bin/bash

# Unity プロジェクトから空ディレクトリと対応する .meta ファイルを削除するスクリプト

set -euo pipefail

# カラー定義（オレンジ/アンバー系に統一）
readonly COLOR_RESET='\033[0m'
readonly COLOR_ORANGE='\033[38;5;208m'
readonly COLOR_AMBER='\033[38;5;214m'
readonly COLOR_RED='\033[38;5;196m'
readonly COLOR_GREEN='\033[38;5;34m'
readonly COLOR_GRAY='\033[38;5;240m'

# アイコン
readonly ICON_SEARCH="🔍"
readonly ICON_FOLDER="📁"
readonly ICON_META="🗑️ "
readonly ICON_SUCCESS="✅"
readonly ICON_WARNING="⚠️ "
readonly ICON_INFO="ℹ️ "

# デフォルト値
DRY_RUN=true
VERBOSE=false
TARGET_PATH="."

# 除外するディレクトリパターン
readonly EXCLUDE_PATTERNS=(
  ".git"
  "node_modules"
  ".DS_Store"
  "Library"
  "Temp"
  "Obj"
  "Build"
  "Builds"
)

# 使用方法を表示
show_usage() {
  cat << EOF
Unity プロジェクトから空ディレクトリと対応する .meta ファイルを削除

使用方法:
  $0 [OPTIONS]

オプション:
  -n, --dry-run       削除せず表示のみ（デフォルト）
  -f, --force         確認なしで即座に削除
  -v, --verbose       詳細ログ表示
  --path <path>       対象ディレクトリ指定（デフォルト: .）
  -h, --help          このヘルプを表示

例:
  $0 -n               # Dry-run で空ディレクトリを確認
  $0 -f               # 実際に削除を実行
  $0 -f --path Assets # Assets 配下のみ対象
EOF
}

# 引数パース
parse_args() {
  while [[ $# -gt 0 ]]; do
    case $1 in
      -n|--dry-run)
        DRY_RUN=true
        shift
        ;;
      -f|--force)
        DRY_RUN=false
        shift
        ;;
      -v|--verbose)
        VERBOSE=true
        shift
        ;;
      --path)
        TARGET_PATH="$2"
        shift 2
        ;;
      -h|--help)
        show_usage
        exit 0
        ;;
      *)
        echo -e "${COLOR_RED}エラー: 不明なオプション: $1${COLOR_RESET}" >&2
        show_usage
        exit 1
        ;;
    esac
  done
}

# 除外パターンに該当するか判定
is_excluded() {
  local path="$1"
  for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    if [[ "$path" == *"$pattern"* ]]; then
      return 0
    fi
  done
  return 1
}

# 空ディレクトリを検出
find_empty_dirs() {
  local target="$1"
  local empty_dirs=()

  while IFS= read -r -d '' dir; do
    # 除外パターンをスキップ
    if is_excluded "$dir"; then
      [[ "$VERBOSE" == true ]] && echo -e "${COLOR_GRAY}  スキップ: $dir${COLOR_RESET}" >&2
      continue
    fi

    # ディレクトリが空か確認（隠しファイルも含む）
    if [[ -z "$(ls -A "$dir" 2>/dev/null)" ]]; then
      empty_dirs+=("$dir")
    fi
  done < <(find "$target" -type d -print0 2>/dev/null | sort -z)

  # 配列が空でない場合のみ出力
  if [[ ${#empty_dirs[@]} -gt 0 ]]; then
    printf '%s\n' "${empty_dirs[@]}"
  fi
}

# グローバル変数：イテレーション結果
ITERATION_FOUND_COUNT=0

# 1回のイテレーションで空ディレクトリを処理
process_iteration() {
  local iteration=$1

  # 空ディレクトリを検出
  local empty_dirs=()
  while IFS= read -r dir; do
    [[ -n "$dir" ]] && empty_dirs+=("$dir")
  done < <(find_empty_dirs "$TARGET_PATH")

  ITERATION_FOUND_COUNT=${#empty_dirs[@]}

  if [[ $ITERATION_FOUND_COUNT -eq 0 ]]; then
    return 0
  fi

  # 結果表示
  if [[ "$VERBOSE" == true ]] || [[ "$DRY_RUN" == true ]]; then
    if [[ $iteration -gt 1 ]]; then
      echo -e "${COLOR_AMBER}--- イテレーション $iteration ---${COLOR_RESET}"
    fi
    echo -e "${COLOR_AMBER}発見した空ディレクトリ:${COLOR_RESET}"

    local meta_count=0
    for dir in "${empty_dirs[@]}"; do
      echo -e "  ${COLOR_ORANGE}${ICON_FOLDER} $dir${COLOR_RESET}"

      # 対応する .meta ファイルを確認
      local meta_file="${dir}.meta"
      if [[ -f "$meta_file" ]]; then
        echo -e "     ${COLOR_GRAY}${ICON_META}対応する .meta: $meta_file${COLOR_RESET}"
        ((meta_count++))
      fi
    done
    echo ""
  fi

  # Dry-run の場合は削除せず終了
  if [[ "$DRY_RUN" == true ]]; then
    return 0
  fi

  # 削除実行
  local deleted_count=0
  for dir in "${empty_dirs[@]}"; do
    if [[ -d "$dir" ]]; then
      # 対応する .meta ファイルを先に削除
      local meta_file="${dir}.meta"
      if [[ -f "$meta_file" ]]; then
        rm -f "$meta_file"
        [[ "$VERBOSE" == true ]] && echo -e "${COLOR_GRAY}  削除: $meta_file${COLOR_RESET}"
      fi

      # ディレクトリを削除
      if rmdir "$dir" 2>/dev/null; then
        ((deleted_count++))
        [[ "$VERBOSE" == true ]] && echo -e "${COLOR_GRAY}  削除: $dir${COLOR_RESET}"
      fi
    fi
  done

  return 0
}

# メイン処理
main() {
  parse_args "$@"

  # ターゲットパスの検証
  if [[ ! -d "$TARGET_PATH" ]]; then
    echo -e "${COLOR_RED}エラー: ディレクトリが見つかりません: $TARGET_PATH${COLOR_RESET}" >&2
    exit 1
  fi

  if [[ "$DRY_RUN" == true ]]; then
    # Dry-run: 1回だけスキャンして結果表示
    echo -e "${COLOR_ORANGE}${ICON_SEARCH} 空ディレクトリをスキャン中...${COLOR_RESET}\n"

    process_iteration 1

    if [[ $ITERATION_FOUND_COUNT -eq 0 ]]; then
      echo -e "${COLOR_GREEN}${ICON_SUCCESS} 空ディレクトリは見つかりませんでした${COLOR_RESET}"
      exit 0
    fi

    # .meta ファイル数をカウント
    local meta_count=0
    while IFS= read -r dir; do
      [[ -n "$dir" ]] || continue
      local meta_file="${dir}.meta"
      [[ -f "$meta_file" ]] && ((meta_count++))
    done < <(find_empty_dirs "$TARGET_PATH" 2>/dev/null || true)

    echo -e "${COLOR_AMBER}合計: ${ITERATION_FOUND_COUNT} ディレクトリ, ${meta_count} .meta ファイル${COLOR_RESET}\n"
    echo -e "${COLOR_ORANGE}${ICON_INFO}実際に削除するには: -f オプションを付けて実行してください${COLOR_RESET}"
    echo -e "${COLOR_GRAY}※ 削除後に親ディレクトリが空になる場合、再帰的に削除されます${COLOR_RESET}"
  else
    # 実行モード: 空ディレクトリがなくなるまで繰り返し
    echo -e "${COLOR_ORANGE}${ICON_SEARCH} 空ディレクトリを再帰的に削除中...${COLOR_RESET}\n"

    local total_dirs=0
    local iteration=1
    local max_iterations=100  # 無限ループ防止

    while [[ $iteration -le $max_iterations ]]; do
      process_iteration $iteration

      if [[ $ITERATION_FOUND_COUNT -eq 0 ]]; then
        break
      fi

      ((total_dirs += ITERATION_FOUND_COUNT))
      ((iteration++))
    done

    if [[ $total_dirs -eq 0 ]]; then
      echo -e "${COLOR_GREEN}${ICON_SUCCESS} 空ディレクトリは見つかりませんでした${COLOR_RESET}"
    else
      echo ""
      echo -e "${COLOR_GREEN}${ICON_SUCCESS} 削除完了: ${total_dirs} ディレクトリ${COLOR_RESET}"
      if [[ $iteration -gt 2 ]]; then
        echo -e "${COLOR_GRAY}（$((iteration - 1)) イテレーションで完了）${COLOR_RESET}"
      fi
    fi
  fi
}

main "$@"
