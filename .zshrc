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

## Aliasの設定
alias ls='ls --color=auto'
alias l='ls'
alias ll='ls -la'
