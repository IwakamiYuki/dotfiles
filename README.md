# dotfiles

```
ln -sf ~/dotfiles/.vimrc ~/.vimrc
ln -sf ~/dotfiles/.tmux.conf ~/.tmux.conf
ln -s ~/.vimrc ~/.ideavimrc
ln -sf ~/dotfiles/.zshrc ~/.zshrc
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

```
brew install reattach-to-user-namespace
go get -u github.com/Code-Hex/battery/cmd/battery
```
※wifiコマンドは以下からコピペして/usr/local/bin/wifiなどに配置する
https://github.com/b4b4r07/dotfiles/blob/master/.tmux/bin/wifi
