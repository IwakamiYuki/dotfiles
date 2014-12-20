" Configuration file for vim
set modelines=0		" CVE-2007-2438

" Normally we use vim-extensions. If you want true vi-compatibility
" remove change the following statements
set nocompatible	" Use Vim defaults instead of 100% vi compatibility
set backspace=2		" more powerful backspacing

" Don't write backup file if vim is being called by "crontab -e"
au BufWrite /private/tmp/crontab.* set nowritebackup
" Don't write backup file if vim is being called by "chpass"
au BufWrite /private/etc/pw.* set nowritebackup

" コードの色分け
colorscheme desert
syntax on

" タブの表示
set list
set listchars=tab:▸\ ,eol:↲,extends:❯,precedes:❮

set incsearch
set hlsearch
set cindent

" 大文字/小文字の区別なく検索する
set ignorecase
" 検索文字列に大文字が含まれている場合は区別して検索する
set smartcase
" 検索時に最後まで行ったら最初に戻る
set wrapscan

" macとクリップボードを連携する
set clipboard=unnamed,autoselect

set scrolloff=8               " 上下8行の視界を確保
set sidescrolloff=16           " 左右スクロール時の視界を確保
set sidescroll=1               " 左右スクロールは一文字づつ行う

set autoindent
" インデントをスペース2つ分に設定
set tabstop=2
set shiftwidth=2

" 外部でファイルに変更された場合は読みなおす
set autoread

set backspace=indent,eol,start  " バックスペースで各種消せるようにする
" ビープ音を消す
set vb t_vb=
set novisualbell

" 対応括弧に<と>のペアを追加
set matchpairs& matchpairs+=<:>
" 対応括弧をハイライト表示する
set showmatch
" 対応括弧の表示秒数を3秒にする
set matchtime=2
" インデントをshiftwidthの倍数に丸める
set shiftround

" 行番号を表示
set number
" 編集中のファイル名を表示
set title

set cursorline
set laststatus=2
set cmdheight=2

" 選択している範囲のインデントを帰るときに選択が外されない
vnoremap > >gv
vnoremap < <gv

" 前回終了したカーソル行に移動
autocmd BufReadPost * if line("'\"") > 0 && line("'\"") <= line("$") | exe "normal g`\"" | endif

" insertモードを抜けるとIMEオフ
set noimdisable
set iminsert=0 imsearch=0
set noimcmdline
inoremap <silent> <ESC> <ESC>:set iminsert=0<CR>


"入力モード時、ステータスラインのカラーを変更
augroup InsertHook
autocmd!
autocmd InsertEnter * highlight StatusLine guifg=#ccdc90 guibg=#2E4340
autocmd InsertLeave * highlight StatusLine guifg=#2E4340 guibg=#ccdc90
augroup END

" w!! でスーパーユーザーとして保存（sudoが使える環境限定）
cmap w!! w !sudo tee > /dev/null %
" ESCを二回押すことでハイライトを消す
nmap <silent> <Esc><Esc> :nohlsearch<CR>
" カーソル下の単語を * で検索
vnoremap <silent> * "vy/\V<C-r>=substitute(escape(@v, '\/'), "\n", '\\n', 'g')<CR><CR>
" 検索後にジャンプした際に検索単語を画面中央に持ってくる
nnoremap n nzz
nnoremap N Nzz
nnoremap * *zz
nnoremap # #zz
nnoremap g* g*zz
nnoremap g# g#zz

" j の二度押しでノーマルモードへ戻る
inoremap jj <Esc>

" ノーマルモードではセミコロンをコロンに。
nnoremap ; :

imap <C-j> <esc>

" insert mode での移動
inoremap <C-e> <END>
inoremap <C-a> <HOME>
inoremap <C-j> <Down>
inoremap <C-k> <Up>
inoremap <C-h> <Left>
inoremap <C-l> <Right>
inoremap <ESC> <ESC>:set iminsert=0<CR> " ESCでIMEを確実にOFF
" 行単位で移動(1行が長い場合に便利)
nnoremap j gj
nnoremap k gk


"--------------------------------------------------------------------------
" ペーストする際に、自動でpaste modeにする
if &term =~ "xterm"
  let &t_ti .= "\e[?2004h"
  let &t_te .= "\e[?2004l"
  let &pastetoggle = "\e[201~"

  function XTermPasteBegin(ret)
    set paste
    return a:ret
  endfunction

  noremap <special> <expr> <Esc>[200~ XTermPasteBegin("0i")
  inoremap <special> <expr> <Esc>[200~ XTermPasteBegin("")
  cnoremap <special> <Esc>[200~ <nop>
  cnoremap <special> <Esc>[201~ <nop>
endif

"--------------------------------------------------------------------------
"" neobundle
set nocompatible               " Be iMproved
filetype off                   " Required!

if has('vim_starting')
  set runtimepath+=~/.vim/bundle/neobundle.vim/
endif

call neobundle#rc(expand('~/.vim/bundle/'))

filetype plugin indent on     " Required!

" Installation check.
if neobundle#exists_not_installed_bundles()
  echomsg 'Not installed bundles : ' .
        \ string(neobundle#get_not_installed_bundle_names())
  echomsg 'Please execute ":NeoBundleInstall" command.'
  "finish
endif

NeoBundle 'editorconfig/editorconfig-vim'

execute pathogen#infect()

" 行番号を表示
set number

set title
set cursorline
set laststatus=2
set cmdheight=2


set mouse=a

NeoBundle "scrooloose/syntastic"

NeoBundle 'hail2u/vim-css3-syntax'


