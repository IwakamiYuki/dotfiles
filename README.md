# dotfiles

```
ln -sf ~/dotfiles/.vimrc ~/.vimrc
ln -sf ~/dotfiles/.tmux.conf ~/.tmux.conf
ln -s ~/.vimrc ~/.ideavimrc
```

※homeディレクトリにクローンした場合の手順になる

## vimrcの初期設定
neobundleのインストールをする

```
mkdir -p ~/.vim/bundle
git clone git://github.com/Shougo/neobundle.vim ~/.vim/bundle/neobundle.vim
:NeoBundleInstall
```
※macの場合、クリップボードの共有をするときに、brewからインストールし直さないといけない。参考：https://qiita.com/shoma2da/items/92ea8badcd4655b6106c

## tmuxの初期設定

```
brew install reattach-to-user-namespace
```
