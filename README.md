# dotfiles
`ln -sf ~/dotfiles/.vimrc ~/.vimrc`

## vimrc
neobundleのインストールをする
```
mkdir -p ~/.vim/bundle
git clone git://github.com/Shougo/neobundle.vim ~/.vim/bundle/neobundle.vim
:NeoBundleInstall
```
※macの場合、クリップボードの共有をするときに、brewからインストールし直さないといけない
