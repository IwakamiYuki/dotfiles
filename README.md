# dotfiles

```
ln -sf ~/dotfiles/.vimrc ~/.vimrc
ln -sf ~/dotfiles/.tmux.conf ~/.tmux.conf
ln -s ~/.vimrc ~/.ideavimrc
ln -sf ~/dotfiles/.zshrc ~/.zshrc
ln -sf ~/dotfiles/.gitignore_global ~/.gitignore_global
ln -sf ~/dotfiles/claude/agents ~/.claude/agents
ln -sf ~/dotfiles/claude/commands ~/.claude/commands
ln -sf ~/dotfiles/claude/scripts ~/.claude/scripts
ln -sf ~/dotfiles/claude/skills ~/.claude/skills
ln -sf ~/dotfiles/claude/settings.json ~/.claude/settings.json
ln -sf ~/dotfiles/claude/CLAUDE.md ~/.claude/CLAUDE.md
```

※homeディレクトリにクローンした場合の手順になる

## vimrcの初期設定
neobundleのインストールをする

```
mkdir -p ~/.vim/bundle
git clone git@github.com:Shougo/neobundle.vim.git ~/.vim/bundle/neobundle.vim
:NeoBundleInstall
```
※macの場合、クリップボードの共有をするときに、brewからインストールし直さないといけない。参考：https://qiita.com/shoma2da/items/92ea8badcd4655b6106c

## tmuxの初期設定

### 基本的な依存関係のインストール
```
brew install reattach-to-user-namespace
go get -u github.com/Code-Hex/battery/cmd/battery
```
※wifiコマンドは以下からコピペして/usr/local/bin/wifiなどに配置する
https://github.com/b4b4r07/dotfiles/blob/master/.tmux/bin/wifi
