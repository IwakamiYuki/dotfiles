# dotfiles

```
ln -sf ~/dotfiles/.vimrc ~/.vimrc
ln -sf ~/dotfiles/.tmux.conf ~/.tmux.conf
```

## vimrc
neobundleのインストールをする

```
mkdir -p ~/.vim/bundle
git clone git://github.com/Shougo/neobundle.vim ~/.vim/bundle/neobundle.vim
:NeoBundleInstall
```
※macの場合、クリップボードの共有をするときに、brewからインストールし直さないといけない。参考：https://qiita.com/shoma2da/items/92ea8badcd4655b6106c

## tmux

```
brew install reattach-to-user-namespace
```
