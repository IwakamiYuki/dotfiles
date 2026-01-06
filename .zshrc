# 環境変数
export LANG=ja_JP.UTF-8

## 色を使用出来るようにする
autoload -Uz colors
colors

## 日本語ファイル名を表示可能にする
setopt print_eight_bit

## ヒストリの設定
HISTFILE=~/.zsh_history
HISTSIZE=1000000
SAVEHIST=1000000

# 履歴検索の設定
# setopt hist_ignore_dups     # 重複を記録しない
setopt hist_ignore_space    # スペースで始まるコマンドを記録しない
setopt hist_reduce_blanks   # 余分な空白を削除
# setopt share_history        # 履歴を共有
setopt append_history       # 履歴を追加
## Aliasの設定
alias ls='ls --color=auto'
alias l='ls'
alias ll='ls -la'

# FZFの履歴検索設定（フィルタ文字列を非表示）
export FZF_CTRL_R_OPTS="--reverse --exact --no-sort --height=40% --border --prompt='履歴検索: ' --header='Ctrl+R: 履歴検索 | Enter: 実行 | Esc: キャンセル'"
# export FZF_TMUX_OPTS="-p"

[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# zoxide
eval "$(zoxide init zsh --hook prompt )" 2>/dev/null || true

# cd コマンド - zoxide の z コマンドを試し、成功したら戻る、失敗したら組み込み cd を使用
alias cd='__cd_wrapper() { z "$@" 2>/dev/null && return 0; builtin cd "$@" }; __cd_wrapper'

