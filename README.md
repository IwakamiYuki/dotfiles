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
ln -sf ~/dotfiles/claude/hooks ~/.claude/hooks
mkdir -p ~/.claude/icons
ln -sf ~/dotfiles/claude/icons/claude-ai-icon.png ~/.claude/icons/claude-ai-icon.png
ln -sf ~/dotfiles/claude/settings.json ~/.claude/settings.json
ln -sf ~/dotfiles/claude/CLAUDE.md ~/.claude/CLAUDE.md
mkdir -p ~/.tmux/scripts
ln -sf ~/dotfiles/tmux/scripts/tmux-pane-border ~/.tmux/scripts/tmux-pane-border
mkdir -p ~/Library/Application\ Support/lazygit
ln -sf ~/dotfiles/lazygit/config.yml ~/Library/Application\ Support/lazygit/config.yml
mkdir -p ~/Library/Application\ Support/com.mitchellh.ghostty
ln -sf ~/dotfiles/ghostty/config ~/Library/Application\ Support/com.mitchellh.ghostty/config
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

## zshの初期設定

### zoxideのインストール
```
brew install zoxide
```
zoxide を使うことで `cd` コマンドを強力にし、複数ディレクトリへのナビゲーションが効率化されます。

## tmuxの初期設定

### 基本的な依存関係のインストール
```
brew install reattach-to-user-namespace
go get -u github.com/Code-Hex/battery/cmd/battery
```
※wifiコマンドは以下からコピペして/usr/local/bin/wifiなどに配置する
https://github.com/b4b4r07/dotfiles/blob/master/.tmux/bin/wifi
### オプション機能

#### lazygitのインストール
```bash
brew install lazygit
brew install git-delta
```
`Ctrl-t g`でlazygitをポップアップで開けます
※lazygitのdiff表示にはdeltaが必要です

#### tmux-aiの設定（必要な場合）
tmux-aiを使用する場合は、別途インストールが必要です。

## Claude Codeの通知設定

### terminal-notifierのインストール
```bash
brew install terminal-notifier
```

### 機能
- Claude Codeがタスク完了や許可要求時にmacOS通知を送信
- 通知クリックでGhosttyがアクティブ化し、該当のtmuxペインにフォーカス
- カスタムマスコットアイコン表示（オレンジ色のAIロボット）
- tmux内にもメッセージを表示

### フックの仕組み
- `claude/hooks/notify-end.sh`: タスク完了時に実行
- `claude/hooks/notify-ask.sh`: 許可要求時に実行
- `claude/hooks/focus-tmux-pane.sh`: 通知クリック時にペインフォーカス
- `claude/icons/claude-ai-icon.png`: 通知アイコン

通知システムはGhosttyとtmuxで自動的に動作します。
