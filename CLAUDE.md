# dotfiles - Claude Code ガイド

macOS 開発環境用の dotfiles リポジトリ。vim、tmux、zsh、Claude Code の設定を管理。すべてホームディレクトリからシンボリックリンクで参照。

## 事実確認と情報源

- 情報源を自ら確認し、憶測を事実として述べない
- **以下の場合は自動的に Web 調査を実施**:
  - 時間依存情報（バージョン、API、セキュリティ、ベストプラクティス）
  - 設計・実装方針の判断が必要な場合（他の選択肢・事例の確認）
  - 確信がない情報

## プロジェクト固有のルール

### カラースキーム統一
- すべてのツールでオレンジ/アンバー系（ANSI 色 172-215）に統一
- Vim: カスタム desert テーマ（オレンジハイライト）
- Tmux: colour208 のステータスバー
- Lazygit: オレンジ系カラースキーム

### シンボリックリンク構造
- すべての設定ファイルは `~/dotfiles/` から `~/` へリンク
- 変更は必ずリポジトリ内のファイルに対して実行
- リンク切れに注意（特に Claude Code 関連）

## よく使うコマンド

### 初期セットアップ
```bash
# シンボリックリンク作成（ホームディレクトリにクローン後）
ln -sf ~/dotfiles/.vimrc ~/.vimrc
ln -sf ~/dotfiles/.tmux.conf ~/.tmux.conf
ln -s ~/.vimrc ~/.ideavimrc
ln -sf ~/dotfiles/.zshrc ~/.zshrc
# tmux/scripts/ はディレクトリごとリンクする（.tmux.conf が ~/.tmux/scripts/ を参照。スクリプトが増えてもリンクの追加は不要）
# 旧方式（ファイルごとのリンク）で ~/.tmux/scripts が実ディレクトリのときは、先に退避する: mv ~/.tmux/scripts ~/.tmux/scripts.bak
mkdir -p ~/.tmux
ln -sfn ~/dotfiles/tmux/scripts ~/.tmux/scripts
ln -sf ~/dotfiles/claude/agents ~/.claude/agents
ln -sf ~/dotfiles/claude/commands ~/.claude/commands
ln -sf ~/dotfiles/claude/scripts ~/.claude/scripts
ln -sf ~/dotfiles/claude/skills ~/.claude/skills
ln -sf ~/dotfiles/claude/hooks ~/.claude/hooks
ln -sf ~/dotfiles/claude/icons/claude-ai-icon.png ~/.claude/icons/claude-ai-icon.png
ln -sf ~/dotfiles/claude/settings.json ~/.claude/settings.json
ln -sf ~/dotfiles/claude/CLAUDE.md ~/.claude/CLAUDE.md
ln -sf ~/dotfiles/claude/commands ~/.codex/prompts
ln -sf ~/dotfiles/claude/skills ~/.codex/skills
mkdir -p ~/Library/Application\ Support/lazygit
ln -sf ~/dotfiles/lazygit/config.yml ~/Library/Application\ Support/lazygit/config.yml
mkdir -p ~/Library/Application\ Support/com.mitchellh.ghostty
ln -sf ~/dotfiles/ghostty/config ~/Library/Application\ Support/com.mitchellh.ghostty/config
```

### Vim プラグインセットアップ
```bash
mkdir -p ~/.vim/bundle
git clone git@github.com:Shougo/neobundle.vim.git ~/.vim/bundle/neobundle.vim
# vim 起動後に :NeoBundleInstall を実行
```

### Tmux プラグインセットアップ
TPM（Tmux Plugin Manager）で管理。初回のみ手動でクローン：
```bash
git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
```
その後 tmux 内で `Ctrl-t I`（大文字 I）でプラグインをインストール。

**主要キー**:
- `Ctrl-t I` → プラグインインストール
- `Ctrl-t U` → プラグインアップデート
- `Ctrl-t Alt-u` → 不要プラグイン削除

### 依存関係インストール
```bash
brew install coreutils                    # GNU coreutils（gtimeout で使用）
brew install reattach-to-user-namespace  # tmux クリップボード連携
brew install lazygit                      # Git UI（Ctrl-t g で起動）
brew install terminal-notifier            # Claude Code 通知（フック用）
go get -u github.com/Code-Hex/battery/cmd/battery  # バッテリー情報表示
```

## コアファイルとキーバインド

### Vim (.vimrc)
- `jj` → ノーマルモードへ
- `;` → コマンドモード (`:` の代替)
- `<Space>j/k` → ページ送り/戻し
- `<Esc><Esc>` → 検索ハイライト解除
- 保存時に行末空白を自動削除
- カスタム desert テーマ（オレンジハイライト）

### Tmux (.tmux.conf)
**プレフィックス**: `Ctrl-t`（`Ctrl-b` から変更）

**主要キーバインド**:
- `Ctrl-t |` / `Ctrl-t -` → 縦/横分割
- `Ctrl-t h/j/k/l` → Vim スタイルペイン移動
- `Ctrl-t s` → pane 番号を表示し、押した番号の pane と現在の pane を入れ替え（標準の session 切り替え `choose-tree` は上書き）
- `Ctrl-t S` → window の並び替えポップアップ（`tmux-window-reorder`）。`j`/`k` で選択、`J`/`K` で選択中の window を上下へ移動（`swap-window -d` で即座に反映）、`Enter` で開く、`q` で閉じる、`Esc` で開く前の並びに戻して閉じる
- `Ctrl-t g` → Lazygit 起動
- `Ctrl-t m` → Claude powered コミットメッセージ生成
- `Ctrl-t T` → Claude Code の /todos 表示（Ctrl+t との競合を回避）
- `Ctrl-t r` → 設定リロード
- `Ctrl-t Ctrl-s` / `Ctrl-t Ctrl-r` → セッション保存/復元

**自動機能**:
- 15 分ごとにセッション自動保存
- tmux 起動時に自動復元
- CPU/バッテリー情報をステータスバーに表示
- Claude Code の状態表示と 5h/1w レートリミットは、ステータスバーから **Agent Sidebar へ移した**（下の「Agent Sidebar」参照）
  - ステータスバーには `tmux-claude-agents-status --state-only` だけを残している（表示は無し）。
    sidebar の DONE（完了して未読）判定が使う状態ファイル `/tmp/tmux-claude-agents-state` を更新し続けるため。
    これを外すと sidebar の DONE が出なくなる
  - フォーカスで未読を消す `pane-focus-in` → `tmux-claude-agents-mark-read` も同じ状態ファイルを使う
  - `⬤`（U+2B24）の STIX Two Math 指定（`ghostty/config`）は旧ステータスバー表示の名残で、sidebar は `⬤` を使わない

### Agent Sidebar (tmux/scripts/tmux-agent-sidebar*)
各 window の左端に置く「普通の pane」で、現在の session 内の Claude Code / Codex の状態を一覧表示する。
daemon なし。各 sidebar が 2 秒ごとに tmux と ps を見て描画するだけの軽量スクリプト。

**キー**:
- `Ctrl-t c` → 新規 window を作る（sidebar は自動では付けない。Agent の一覧・選択は cockpit の sidebar が担うため。以前は自動で付けていたが、window の数だけ sidebar のプロセスが増えるため、やめた）
- `Ctrl-t b` → 現在の window に sidebar を追加。すでにあれば二重起動せず sidebar へフォーカス
- sidebar 上で `Ctrl-C` → sidebar だけ終了して pane が閉じる。main pane は残る
- ⚠️ `Ctrl-t a`（Claude 一覧ポップアップ）が使用済みのため、再表示キーは `b`
- sidebar 上で `j` / `k`（`↓` / `↑`、マウスホイール）→ 選択を移動。`j` / `k`（`↓` / `↑`）はそのまま **ポップアップでプレビュー**も開く（`@agent_sidebar_auto_preview`、後述）。マウスホイールは移動だけで、開かない。選択中のカードはオレンジの角丸罫線で囲まれる（sidebar にフォーカスがあるときだけ表示。このとき 2 行目に操作ヒントも出る）
- sidebar 上で `Enter` / `l` / `h`、または Agent の行を **クリック** → その Agent の window・pane へジャンプ（`r` で即時更新）
- sidebar 上で `R`（大文字）→ 選択中の Claude Code を **再起動**（バージョンアップや設定の反映用。通常の sidebar・cockpit のどちらでも効く。ヒント行には出さない）
  - `tmux-agent-restart <pane_id>` が、`claude agents --json` で pane の Agent（pid・sessionId・cwd）を特定 → `SIGTERM` で終了 → 戻ったシェルに `claude <引き継ぐ引数> --resume <sessionId>` を入力して実行する
  - IDLE / DONE は確認なしで再起動。WORKING / WAITING のときは、tmux の確認プロンプト（`y/n`）を挟む（会話は resume で戻るが、実行中の処理は失われる）。結果は `display-message` に出る
  - 引き継ぐ引数は許可リストだけ（`--dangerously-skip-permissions` / `--allow-dangerously-skip-permissions` / `--chrome` / `--no-chrome` / `--ide` / `--model` / `--effort` / `--permission-mode` / `--fallback-model`）。`ps` から引用符つきの引数を正確に復元できないため、`--append-system-prompt` などは引き継がない（落とした数を結果に出す）
  - Agent の cwd がシェルの cwd と違うとき（worktree へ移った場合など）は、`cd <cwd> &&` を付けて再開する
  - **扱わないケース**: Agent が pane の直下で起動されていて、シェルが無い pane（終了すると pane ごと閉じるため）。戻った先が既知のシェル（zsh / bash / sh / dash / ksh / fish）でないときも、何も入力しない。Codex は未対応
  - 環境変数: `AGENT_RESTART_CLAUDE_CMD`（入力するコマンド名。既定 `claude`）
- sidebar 上で `n` → 選択中のカードの **リポジトリで新しい pane を作り**、Claude Code / Codex を新規セッションで起動する（tmux のメニューで `c` = Claude / `x` = Codex を選ぶ。通常の sidebar・cockpit のどちらでも効く）
  - `tmux-agent-new <claude|codex> <anchor_pane_id> <dir> (--focus | --notify <sidebar_pane_id> | --print)` が処理する（`--print` は、スマホの Web 画面（`tmux-agent-web`）用。Mac のフォーカスを動かさず、作った pane_id だけを標準出力へ返す）
  - **ディレクトリ**: リポジトリの本体（worktree のカードを選んでいても、大本のディレクトリ。見出しのリポジトリと同じ `AG_RKEY`）。git 管理外のグループはそのディレクトリ
  - **置き場所**: そのリポジトリの **先頭に表示されている Agent の window**（anchor の pane を分割する。幅が 120 以上なら左右、狭ければ上下）。anchor が cockpit の枠に入っているときは、元の window を交換用の枠（slot）の位置から割り出す（slot は枠に入った Agent の元の位置に居るため）。割り出せなければ新しい window にする
  - シェルを立ち上げてからコマンドを入力するので、Agent が終了してもシェルが残り、`R`（再起動）がそのまま使える
  - 通常の sidebar（`--focus`）は、作った pane へ移動する。cockpit（`--notify`）は、作った pane を **すぐ右の枠へ入れ、フォーカスもそこへ移す**（sidebar が選ばれたままにならず、すぐ入力できる）。さらに sidebar の pane option `@agent_new_pane` に pane_id を書き、sidebar は **Agent として検出されたら**（Claude は `claude agents --json` に載るまで数秒かかる。40 秒まで探す）そのカードを選択する。検出までは右の枠の中身と選択が合わないので、選択の表示（タブ・罫線）を出さない
  - 起動コマンドは tmux の option で変えられる: `@agent_sidebar_claude_cmd`（既定 `claude`）/ `@agent_sidebar_codex_cmd`（既定 `codex`）。たとえば `set -g @agent_sidebar_claude_cmd 'claude --dangerously-skip-permissions'`
  - パスにクォートや `$` `#` `\` などを含むときは（tmux のコマンド文字列に埋め込むため）扱わない
  - **Agent が 1 つも居ないリポジトリ（空きシェルの欄）**: そのリポジトリに **空いているシェルの pane**（zsh / bash / sh / dash / ksh / fish が前面で動いていて、Agent が居ない）があれば、見出しの下に `┆ + New agent   n` の 1 行の欄を出す（背景なしの点線の縁。種別は内部で `Shell`）
    - 選択して `n` を押すと、**その pane のシェルへそのまま入力して**起動する（`tmux-agent-new ... --here`。pane は分割しない。cwd はシェルの今の場所）。`Enter` / クリックはその pane へジャンプ。`R` は「Agent が起動していません」と出す
    - 対象外: home のシェル（`C-t c` が home で window を開くため、候補だらけになる）、コマンド実行中の pane（vim など）、sidebar、cockpit の slot。同じリポジトリに空きシェルが複数あっても欄は 1 つ（若い window・pane のもの）。Agent が 1 つでも居るリポジトリには出さない（通常のカードの `n` を使う）
    - 起動の直前に `tmux-agent-new` が、anchor がまだ空きシェルか確かめる（実行中のコマンドへ入力してしまわないため）。違えば何もしない
    - 見出しの件数と先頭行の `AGENTS` は Agent だけ数える（欄は数えない）。Agent が起動して欄がカードに変わっても、選択は pane_id で引き継ぐ（`@agent_new_pane` は使わない）
    - cockpit では、欄を選ぶと、その空きシェルの本物の pane が右の枠に入る。そこで `n` を押すと、枠の中のシェルで起動する
- sidebar 上で `w` → スマホ用 Web サーバー（`tmux-agent-web`、後述「Agent Web」）を **ON / OFF**。`W`（大文字）→ 起動中なら URL（トークンつき）をクリップボードへ（通常の sidebar・cockpit のどちらでも効く）
  - 最下行の **WEB 欄**に状態を出す（`○ WEB off  w start` / `● WEB ON :8765  w stop W copy`。閲覧のみのときは `ro`）。端末の高さが 14 未満のときは USAGE 欄と同様に出さない。幅に収まらないときはヒント（`W copy`）から省く
  - 実際の入り切りは `tmux-agent-web-toggle`（`R` と同じく、sidebar からは裏で `--notify` つきで呼ぶだけ。起動の待ちで sidebar を止めない）。結果は `display-message` に出る。ON にしたときは URL をクリップボードへコピーする
  - 状態は `~/.cache/tmux-agent-web/state.json`（`tmux-agent-web` が書く。pid・ポート・URL）。sidebar は毎 tick（約 1 秒）これを fork なしで読み、変わったときだけ再描画する。pid が死んでいれば OFF 扱い（古い状態ファイルは無視される）
  - 手動（端末）で起動した `tmux-agent-web` も同じ状態ファイルを書くので、WEB 欄に ON と出て、`w` で止められる。**状態ファイルを書かない古い版で起動したものは、WEB 欄に出ず、`w` でも止められない**（二重起動はポート衝突で失敗する）。止めてから `w` で起動し直す
- sidebar 上で `p`（または Space）→ 選択中の Agent の pane を **ポップアップでプレビュー**（`tmux-agent-sidebar-preview`）
  - 中身は `tmux capture-pane -e -p`（色つき・読み取り専用）を 1 秒ごとに更新。Agent には影響しない
  - ポップアップ内で `j` / `k`（`↓` / `↑`、Tab）→ 前後の Agent に切り替え、`Enter` → その pane へ移動、`q` / Esc / `p` / Space → 閉じる
  - ポップアップは sidebar の **右隣**に開く（幅が 40 未満なら中央に大きく）。j/k で切り替えるたびに、裏の sidebar の選択（罫線）も追従する
    （ポップアップが `<result_file>.cur` に現在の添字を書いて sidebar へ SIGUSR1 を送り、`display-popup` をバックグラウンドで起動した sidebar のハンドラが
    即座に読んで再描画する。`display-popup` はポップアップが閉じるまで戻らないため。ポーリングだと最大 0.2 秒の遅れが出ていた）
  - 閉じると、sidebar の選択位置は最後に見ていた Agent に引き継がれる
  - **自動プレビュー** `@agent_sidebar_auto_preview`（実行中のサーバーでは `tmux set -g ...` で 2 秒以内に反映）:
    `key`（既定。j/k で開く）/ `focus`（さらに sidebar がアクティブになったときも開く）/ `off`（p のみ）
  - `focus` は端末のフォーカスイベント（`ESC[?1004h` → `ESC[I`）で検知する。`focus-events on` が前提（`.tmux.conf` に明示）。
    ポップアップを閉じた直後の 2 秒は開き直さない。ポップアップ中は tmux の prefix キーが効かない（ポップアップがキーを受けるため）ので、
    他の pane へ移るときは q で閉じるか Enter で移動する
  - 幅の広い pane は自動折り返し（DECAWM）を切ってターミナルに右端でクリップさせる。下部の空行は落として、下から表示行数ぶんを出す

**仕組み**:
- 識別は pane option `@agent_sidebar=1`（sidebar プロセス自身も起動時に付与）。Agent 検出対象と `tmux-window-name` の共通パス計算から除外される
- `-f` 付き split なので、main pane が複数ある window でも window 全体の左端・全高に置かれる
- main pane が全て閉じて sidebar だけが残った window は、sidebar が自分で終了して window ごと閉じる
- 入力は `read -t 1` で待つ（データ更新は 2 秒ごと、キー入力・リサイズは 1 秒以内に反応）。クリックは SGR マウス報告（`ESC[?1000h` + `?1006h`）で受け取り、行→Agent の対応表で対象を決める。tmux の `mouse on` が前提
- ジャンプは `select-window -t <pane_id>` + `select-pane -t <pane_id>`（`scope=all` で別 session の Agent なら `switch-client` も行う）
- 設定: `@agent_sidebar_width`（既定 32）、`@agent_sidebar_scope`（`session` | `all`）、`@agent_sidebar_icons`（`nerd` | `plain`）。`.tmux.conf` に定義
- 見た目は Orca の worktree 一覧を意識したカード表示。 **リポジトリごと**の見出し（`── dotfiles ─────── 3`、右端は Agent の件数）で区切り、各 Agent は背景色を敷いた 3 行のカードで、左端のバーが状態色
  - **グルーピング**: cwd の git から判定する（`git rev-parse --path-format=absolute --show-toplevel --git-common-dir`）。worktree の `--git-common-dir` は本体の `.git` を指すので、同じリポジトリの worktree は 1 つのリポジトリにまとまる。サブディレクトリで動く Agent は、その worktree に含まれる。git 管理外はディレクトリ名で 1 グループ（home は `~`）。結果は cwd ごとに 10 秒キャッシュ
  - **worktree / ブランチ**: 見出しには出さず、**各カードの 2 行目**に出す（同じリポジトリでも worktree ごとにブランチが違うため。以前は worktree ごとの小見出しにしていたが、カードに移した）。同じ worktree の Agent は並び順で隣り合う。git 管理外のディレクトリは、ブランチの代わりに親ディレクトリを出す
  - **並び順**: リポジトリは **window 順**（そのリポジトリの Agent が居る最も若い元の window 番号、同じ window なら pane 番号の若い順。それも同じならリポジトリのパス）→ worktree のパス → 元の window 番号 → 元の pane 番号 → session。cockpit での入れ替え（j/k）では動かない（枠に入った Agent は元の window・pane 番号を使う）。一方、`Ctrl-t S` などで window を並び替えたり、若い番号の window に Agent が増えたりすると、リポジトリのまとまりごと動く（window 番号は見出しに出さない。以前は動かないようにリポジトリ名の ABC 順にしていた）
  - 1 行目は **名前**、2 行目は **ブランチ**、3 行目は状態。常に 3 行（`名前 ……… 種別(右寄せ)` / ` ブランチ` / `[ ⠋ WORKING ] 待機理由 ……… 継続時間`）。リポジトリは見出しに出すのでカードには出さない。pane 番号と状態アイコン（●等）も出さない
  - **名前の優先順位**: 会話タイトル（`/tmp/claude-title-<sessionId>.txt`。statusline が書く。`/rename` の名前もここに入る）→
    トランスクリプトの `ai-title`（`~/.claude/projects/*/<sessionId>.jsonl` の `{"type":"ai-title","aiTitle":"…"}`。Claude Code 自身が書くので、
    statusline が動いていないセッションでも取れる。末尾 300KB だけ読み、`/tmp/tmux-agent-sidebar-titles.txt` に 30 秒キャッシュ）→ セッション名（`~/.claude/sessions/<pid>.json` の `nameSource` が `derived` 以外のとき。
    `derived` は「ディレクトリ名 + 英数字」で情報が無いので使わない）→ project（cwd 末尾）。名前が無いカードは 1 行目が project（cwd 末尾）になる
  - 状態は背景色付きのピル（WORKING=黄 / WAITING=赤 / DONE=緑 / IDLE=落ち着いた緑 / UNKNOWN=灰）。IDLE（入力待ち）と DONE（完了・未読）は同じ緑系で、どちらもカード全体に緑の色味を付ける（WAITING の赤と同じ作り）。DONE のほうを強い緑（背景 28、IDLE は 22）・鮮やかなピルにして、「新しい結果がある」を区別する。working のピルの中でスピナーが回る（`read -t` が整数秒のため 1 秒 1 コマ）
  - 先頭行に状態別の件数（カードのバーと同じ色の `▎1 ▎1`）
  - **選択**（カーソル）と**現在地**（いま見ている pane）は別の表現にして混同を避ける
    - 選択: カードを **オレンジの角丸罫線 `╭─╮ │ │ ╰─╯` で丸ごと囲む**。カード間の区切り行を罫線に兼用するので行数は増えない（区切り行は選択時に上辺/下辺になる）
    - 現在地: 左端を **シアンの `▶`**、project 名を **シアンの太字**にする（選択中は左端が罫線になるため名前の色だけで示す）
  - 文字幅は `char_width`（UTF-8 のバイトからコードポイントを復元して判定。East Asian Ambiguous の `’ “ — → ▶` や罫線は 1 桁、CJK・絵文字は 2 桁）で数える。
    以前は ASCII 以外を一律 2 桁と数えていて、`’` や `—` を含む行で右端の罫線が左へずれていた。
    さらにカードの右端の縁は `ESC[row;colH` で桁を指定して描くので、幅の見積もりがずれても縁の位置は動かない
  - 状態に応じてカードの背景に色味を付ける（WAITING=暗い赤、DONE=強い緑、IDLE=暗い緑。選択中は一段明るい）
  - 下部に固定の `── USAGE ──` 欄で Claude Code の 5h / 1w レートリミット使用率（バー + % + リセットまでの残り時間。色は `tmux-rate-limits` と同じ段階で 80% 以上は赤）を表示。元データは `statusline.sh` が書く `/tmp/claude-rate-limits.json`。端末の高さが 14 未満、またはファイルが無いときは出さない
  - **種別アイコン（画像）** `@agent_sidebar_type_icon`: `text`（既定。project 名の右に `Claude` / `Codex` の文字）| `image`（project 名の左に 2 桁 × 1 行の画像。project 名の幅が増える）
    - 画像は `tmux/assets/agent-icons/{claude,codex}.png`（出所は同ディレクトリの `NOTICE.md`。Simple Icons の SVG を色付け・PNG 化したもの）
    - Kitty graphics protocol の **Unicode placeholders** を使う: 画像データを tmux のパススルー（`ESC P tmux ; … ESC \`）で端末へ一度登録し、
      カードには `U+10EEEE` + 行/列の結合文字（`U+0305` / `U+030D`）の文字を置く（前景色の 256 色番号が画像 ID）。画像が文字として扱われるので、
      window 切り替え・再描画で残像が出ない。10 秒ごとに登録し直す（端末の再接続で消えても戻る）
    - `allow-passthrough on`（既定は off）・Ghostty（Kitty graphics 対応）・アイコンが読めること、が条件。満たさなければ自動で `text` に戻る
    - 画像 ID は 250 / 251（他のアプリと衝突しにくい値）。tmux のパススルーは表示中の window の pane からしか端末へ届かない
  - アイコンは Nerd Font 前提（`@agent_sidebar_icons nerd`）。`plain` にすると記号なしになる
  - 継続時間は `~/.claude/sessions/<pid>.json` の `statusUpdatedAt`、ブランチは cwd での `git branch --show-current`（10 秒キャッシュ。detached HEAD なら短縮 SHA）
  - カードは常に 3 行（見出し・区切り行は別。リポジトリごとに「見出し → [区切り → カード]… → 閉じの区切り」）。収まらない分は `+N more` にし、選択に追従してスクロールする
- Claude: `claude agents --json`（約 0.2 秒）と各セッションの更新時刻を `/tmp/tmux-agent-sidebar-claude2.txt` に 3 秒キャッシュして全 sidebar で共有。pid の祖先をたどって pane に紐付ける。status は working / waiting / idle。未読の完了は `tmux-claude-agents-status` の状態ファイルを参照して done 表示
- Codex: ps の引数（`codex` 本体、または `node .../codex`）で検出。状態を確実に判定する手段が無いため unknown 固定（推測しない）
- 内部は共通レコード `R|session|window|window_name|pane|type|pane_id|active|project|status|detail|elapsed_sec|name|cwd`（`type` は `Claude` / `Codex` / `Shell`）。検出（awk）と表示（render）を分離しているので、状態判定の追加は collect 側だけで済む
- 環境変数（主にデバッグ用）: `AGENT_SIDEBAR_INTERVAL`、`AGENT_SIDEBAR_CLAUDE_BIN`、`AGENT_SIDEBAR_CLAUDE_CACHE`、`AGENT_SIDEBAR_SESSIONS_DIR`、`AGENT_SIDEBAR_RATE_LIMITS`、`AGENT_SIDEBAR_ICON_DIR`、`AGENT_SIDEBAR_ALERT_STATE`、`AGENT_SIDEBAR_PROJECTS_DIR`、`AGENT_SIDEBAR_TITLE_CACHE`、`AGENT_SIDEBAR_DEBUG=1`（stderr を捨てない）

**既知の制限**:
- 別の Mac へ移したときは `~/.tmux/scripts` へのリンクが必要（git では運ばれない）。「初期セットアップ」のとおりディレクトリごとリンクする（以前のファイルごとのリンクは、スクリプトの追加時に漏れていた）。リンクが無いと `C-t b` / `C-t B` が `no such file or directory: ~/.tmux/scripts/tmux-agent-sidebar-open` で失敗する
- tmux-resurrect で復元すると、sidebar pane は空のシェル pane になる（`C-t b` を押す前に邪魔なら閉じる）
- 既存 window へは自動追加しない（必要な window で `C-t b`）
- 起動中のスクリプトを書き換えると bash が壊れた読み方をするため、スクリプトを更新したら sidebar は閉じて開き直す

### Agent cockpit (tmux/scripts/tmux-agent-cockpit*)
左に sidebar、右に「sidebar で選択した Agent の **本物の pane**」を出す専用 window。この window だけで、あらゆる window の Claude Code / Codex を確認・指示出しできる。
本物の pane なので、カーソル・上へのスクロール（コピーモード）・マウス・貼り付けがそのまま使える（`capture-pane` の代理表示では出来ない）。

**キー**:
- `Ctrl-t B` → cockpit window を開く（あれば移動）。開くと、選択中の Agent が右の枠に入る
- cockpit の sidebar で `j` / `k`（`↓` / `↑`、ホイール、クリック）→ 右の枠の Agent が切り替わる。`Enter` / `l` / `h` → 右の枠へフォーカス（戻るのは `Ctrl-t h`）
- `Ctrl-t &` → cockpit window では **先に Agent を元へ戻してから**閉じる（通常の window は従来どおり確認つき kill-window）
- cockpit の sidebar で `q`（または `Ctrl-C`）→ 枠の Agent を元へ戻し、不要になった交換用の枠も消して、**cockpit window ごと閉じる**（通常の sidebar では `q` は何もしない。閉じるのは `Ctrl-C`）
- 「いまアクティブな pane の Agent」(`▶`)は通常 2 秒ごとの収集で更新されるが、フォーカスが動く操作（Enter / フォーカスイベント）の直後は、動き先が分かっているので手元で先に反映してから収集をやり直す（約 30ms で変わる。以前は 1〜2 秒）

**見た目（選択中のカード）**: cockpit の sidebar では、選択中のカードを右の枠と結ぶ（選択 = 右の枠に出ている Agent なので、通常 sidebar の罫線カーソルと現在地の `▶` を一つにまとめる）。橙は「ここに注目」を示し、**形**でフォーカス位置を区別する。
- sidebar にフォーカス（選んでいる最中）= **橙で塗りつぶしたタブ**（背景 130、左端に明るい縁 `█` 208）。塗りつぶしなので状態色は隠れる（ピルは残る）。塗りの上で読めるよう補助の文字色を明るくする
- 右の枠にフォーカス（Enter で移った後・操作している最中）= **状態色のカードを橙（208）の角丸罫線で囲む**。WAITING / DONE などの色味が戻り、罫線は通常の sidebar のカーソルと同じ作り（区切り行を兼用するので行数は増えない）
- どちらも、中段の行末に右の枠を指す矢印（Nerd Font の Powerline `U+E0B0`。`@agent_sidebar_icons plain` のときは `▶`）を置く。矢印の色はタブでは塗りの色、罫線のときは橙
- 通常の window の sidebar は従来どおり罫線のカーソル（sidebar にフォーカスがあるときだけ）

**仕組み**:
- 右の枠には「交換用 pane（slot、`tmux-agent-cockpit-slot`）」が 1 つだけある。Agent を選ぶと、その Agent の pane と slot を `swap-pane` で入れ替える
  （Agent は枠に入ってサイズも枠に合い、slot は Agent の元の位置に移って「cockpit に表示中」と出す）。切り替えは、元へ戻してから次を入れる（slot は使い回す）
- 状態は tmux の option: window `@agent_cockpit`（=1）/ `@agent_cockpit_slot` / `@agent_cockpit_shown`、pane `@agent_cockpit_slot_pane` / `@agent_origin_widx` / `@agent_origin_wname` / `@agent_origin_pidx`
  （枠に入っている Agent の元の window 番号・名前と pane 番号。sidebar は、cwd からリポジトリを判定するので、枠に入っても所属は変わらない。元の window 番号・pane 番号は、worktree 内の並び順に使う。
  pane 番号を記録しないと、cockpit 内の番号で並べ替わってしまい、j/k のたびにカードの順番が入れ替わる）
- `tmux-window-name` は cockpit window と slot を計算から外す（Agent の入れ替えで window 名が変わらないように）
- 制御は `tmux-agent-cockpit open | show <pane_id> | restore | teardown | close | heal`。`teardown` は sidebar の終了時に呼ばれ、`restore` で Agent を戻したあと slot を消す（Agent を戻せなかったときは、巻き込まないよう何も消さない）。`heal` は、枠の Agent が終了して slot が元の window に取り残されたときに slot を cockpit へ戻す（`join-pane` は既定で sidebar と slot を 1:1 に分けてしまうので、戻したあと sidebar を `@agent_sidebar_width` の幅へ直す。slot を作り直すときも同じ）
  （sidebar は起動時と、cockpit の main pane が 0 になったときに呼ぶ。直後に次の Agent が自動で枠に入る）
- `show` は高速パスで動く: 状態の確認を `list-panes -a` の 1 回にまとめ、「元へ戻す → 元の位置を記録 → 入れ替え → 記録」を tmux の複合コマンド（`;` 区切り）1 回で実行する
  （以前は tmux を約 25 回呼んで約 130ms、今は約 26ms）。想定外の状態（slot が無い・表示中の pane が消えた・複合コマンドが途中で失敗）は、確実に直せる従来の処理（`do_show_slow`）に任せる。
  sidebar は j/k で、入れ替えを待たずに先に選択の罫線を描き、そのあとで入れ替える（罫線は約 13ms で動く）
- `display-message -t <存在しない pane>` はエラーにならず空を返すので、pane の存在確認は返ってきた `#{pane_id}` の一致で行う

**危険な点（重要）**: Agent が枠に入っている間に cockpit window を **tmux の外から** 閉じると、Agent も終了する。tmux には「閉じる直前」のフックが無い（`window-unlinked` 等は閉じた後）。
守れる経路: `prefix + &`（差し替え済み）、sidebar の終了、次回起動時の `heal`。**守れない経路**: `prefix :` から `kill-window` を直接実行、`kill-session`、tmux サーバーの終了。
その場合も会話の記録は残る（`claude --resume`）が、実行中の処理は失われる。

### Agent Web (tmux/scripts/tmux-agent-web)
スマホのブラウザから、この Mac の tmux 上の Claude Code / Codex を **確認・操作**する小さな Web サーバー（Python 3 標準ライブラリのみ）。
メニュー（☰）に sidebar と同じ Agent 一覧、メインに選んだ Agent の pane、下に入力欄とクイックキー（`/` / Esc / Tab / ⇧Tab / 矢印 / Enter / ^C / y / n / 1-3 / ⌫）。
`/` は Claude Code のスラッシュコマンドのメニューを開く（空の入力欄に `/` を 1 文字だけ送る。続きは入力欄で打って送信するか、↑↓ と Enter で選ぶ）。送れるキーは許可リストのみ（`/ y n 1-9` と名前つきキー）。
**入力欄の送信ボタン**は、文字があるときは **「入力」= 文字を入れるだけ（Enter は押さない）**、空のときは **「⏎」= Enter を押す**。
Enter まで一度に押すと、`/` やスキルの補完（Tab・↑↓で選ぶ）を使えないため。文字を入れたあと、補完を選んで、⏎ で確定する。
文字があるときだけ出る **「入力+⏎」**は、従来どおり「文字を入れて Enter まで」を 1 回で済ませる（デスクトップでは Ctrl/Cmd+Enter も同じ）。
1 行の文字は **キーボードで打った形**で届ける（`paste-buffer` の `-p` なし。補完メニューは、貼り付けでは出ないため）。**改行を含む文字だけ**、貼り付け（bracketed paste）の形にする。
文字は `load-buffer` の標準入力で渡すので、「;」で終わる・「-」で始まる文字も、tmux の引数として誤解釈されない（`send-keys -l` だと崩れるため、使わない）。

**起動**（必要なときだけ。常駐させない）:
- **sidebar の `w`**（ON / OFF）と `W`（URL のコピー）。ON にすると URL がクリップボードに入る（ユニバーサルクリップボードでスマホに貼れる）。詳細は上の「Agent Sidebar」
- 起動引数を変えたいときは tmux の option: `set -g @agent_web_args '--read-only --idle-timeout 120'`（空白区切りの単純なフラグだけ。サーバー起動中の変更は、次の起動から効く）
- 端末から直接:
```bash
~/.tmux/scripts/tmux-agent-web --copy        # LAN 側 IP で待ち受け。URL をクリップボードへ
~/.tmux/scripts/tmux-agent-web --read-only   # 閲覧のみ
~/.tmux/scripts/tmux-agent-web-toggle status # ON host:port / OFF（トークンは出さない）。ほかに start / stop / toggle / url
```
他のオプション: `--host IP`、`--port N`（既定 8765）、`--idle-timeout 分`、`--allow-host 名前`、`--state-file パス`。端末に出る URL の `#token=…` つきで開く（トークンは起動のたびに変わる。`TMUX_AGENT_WEB_TOKEN`（20 文字以上）で固定できる）。
スマホは同じ Wi-Fi に繋ぐ。mDNS 名（`<LocalHostName>.local`）でも開ける。
**二重起動はしない**（状態ファイルの pid が生きていれば「すでに起動しています」で終了）。SIGTERM（`w` の OFF）でも Ctrl+C と同じ後片付け（状態ファイルの削除）をする。
状態ファイル `~/.cache/tmux-agent-web/state.json`（`TMUX_AGENT_WEB_STATE` で変更）は **トークンつきの URL を含む**ので、本人だけが読めるディレクトリ（0700）・ファイル（0600）にしている。サーバーのエラーログは同じディレクトリの `server.log`（URL は出さない）

**仕組み・設計判断**:
- 表示は `capture-pane -e -p` の読み取りだけ（1 秒ごとにポーリング。内容が同じなら `rev` 一致で本文を返さない）、入力は `load-buffer` + `paste-buffer -p`（+ Enter）と `send-keys` だけ。
  `swap-pane`・リサイズ・window 切り替えはしないので、Mac 側の画面（cockpit を含む）に影響しない
- 検出は sidebar と同じ方式（`claude agents --json` + ps の祖先 → pane、Codex は ps の引数、DONE は `/tmp/tmux-claude-agents-state`、
  名前は `/tmp/claude-title-<sid>.txt` → トランスクリプトの `ai-title` → セッション名）を **Python で再実装**している。
  `tmux-agent-sidebar` は起動中に書き換えると壊れるので、検出ロジックを共有するための変更はしなかった（検出の仕様を変えたら両方を直す）
- tmux の外で動いている Claude（別ターミナル・アプリ）は pane が無いので一覧に出ない
- 並び順は sidebar と同じ（リポジトリ → worktree → 元の window・pane 番号。cockpit に入っている Agent は元の番号）
- **ソフトキーボードで入力欄が隠れない**ようにしている: viewport の `interactive-widget=resizes-content`（Android の Chrome 108 以降は、既定だとキーボードが画面に重なるだけでページが縮まない）と、
  縮まない端末（iOS Safari 等）向けに `visualViewport` の高さを `--vvh` としてページ高さに反映（ピンチズーム中は反映しない）。実機のキーボードでの確認は人手（テストはメタ・CSS の存在だけ）
- 画面は pane の実際の幅で描かれる。**幅の広い pane はスマホでは読みにくい**ので、表示の「幅に合わせる」（内容の幅で文字サイズを決める。下限 7px）、
  A−/A＋、横スクロール、ピンチズームで調整する。履歴ボタンで過去 500 行も読める

**セキュリティ**（`ssh` と同じ重さの口なので、最小限を重ねている）:
- 待ち受けは **特定の LAN の IPv4 だけ**（RFC1918 / ループバック / リンクローカル / CGNAT）。`0.0.0.0`・公開 IP・ホスト名は起動時に拒否。接続元 IP も同じ範囲だけ許す
- トークン（URL の `#` 以降。サーバーには送られない）→ ログインで **HttpOnly / SameSite=Strict の Cookie**（トークンそのものは Cookie に入れない）。比較は timing-safe。
  **ログインは 30 日間有効で、サーバーを起動し直しても続く**（トークンは起動のたびに変わるが、ログイン済みの端末は再認証なし）。
  記録は `~/.cache/tmux-agent-web/sessions.json`（0600）に **Cookie の sha256 だけ**を残す（ファイルが漏れても Cookie としては使えない）。期限は延長しない（ログインから 30 日。`--session-days` で 1〜365）、最大 32 端末。
  **全端末のログアウトは `tmux-agent-web-toggle revoke`**（= `tmux-agent-web --revoke-sessions`。記録を消す。動いているサーバーも次のリクエストで気づく）。スマホの紛失・譲渡のときに使う
  （⚠️ 紛失したスマホは、取り消すまで最大 30 日 操作できる。画面のメニューの「ログアウト」はその端末だけ）
- **Host ヘッダーを許可名（待ち受け IP・localhost・`.local` 名・`--allow-host`）に限定**（DNS rebinding 対策）。POST は Origin 一致と `X-Requested-With` も必須
- ログイン失敗は IP ごとに 5 回で締め出し（指数的に延びる。最大 15 分）
- 操作できる pane は **検出済みの Agent だけ**（他の pane の番号は 404）。キーは許可リスト、本文は 8000 文字まで、リクエストは 64KB まで
- CSP（script は自分のファイルのみ）、`Cache-Control: no-store`、`Referrer-Policy: no-referrer`
- **HTTP と HTTPS の両方でつながる**（下の「HTTP と HTTPS の両方」）。**HTTP は平文**なので、信頼できる自宅の Wi-Fi でだけ使う。HTTPS は自己署名（警告を越えて使う）なので、暗号化はされるが、なりすましには弱い。URL（トークン）を他人に見せない・共有チャットに貼らない。
  `--dangerously-skip-permissions` で動く Agent があれば、トークンが漏れた時点で Mac のシェルを操作されるのと同じ
- ⚠️ 会社管理（Jamf）の Mac では、LAN に待ち受けるサーバー自体が社内ルールに触れないか確認する

**HTTP と HTTPS の両方**: 同じポート（既定 8765）で、`http://` でも `https://` でもつながる（接続の最初の 1 バイトで見分ける）。
- HTTPS の証明書は **自己署名**で、起動時に無ければ自動で作る（`~/.cache/tmux-agent-web/tls/`、鍵は 0600。`openssl` が要る。無ければ HTTP だけで起動する）。
  ブラウザには「安全ではない」と警告されるが、**「詳細設定 → 続行」で使える**。証明書は 10 年有効で、作り直さない（作り直すと、ブラウザの「続行」の記憶が無効になり、もう一度警告を越えることになる）
- **CA を作ってスマホに入れる方式は、やめた**（一度作ったが、スマホへのインストールが難しく、警告を越えれば足りたため）。警告を消したくなったら、その方式を作り直すことになる（コミット前に削除したので、履歴には残っていない。名前制限（Name Constraints）つきの CA を `openssl` で作り、`/ca.crt` で配る形だった）
- Cookie の `Secure` と Origin の検証は、**接続ごとの scheme**で判断する（https の接続には `Secure` を付け、`Origin` も `https://…` と一致したものだけ通す）。HTTP の接続は、これまでどおり
- HTTPS が要る理由: Android の Chrome が「アプリをインストール」で作るアプリ（WebAPK）は、**スコープを https に書き換える**。http のサイトでインストールすると、起動した URL がスコープの外になり、
  **Chrome のタブで開いてしまう**（実機の `chrome://webapks` で、`URI: http://…` に対して `Scope: https://…` だったことで判明）。**https の URL を開いてインストールすれば、独立したアプリとして起動する**（実機で確認済み）
- `w`（sidebar）で起動すると、**`.local` の URL（`<scheme>://<Mac の名前>.local:8765/#token=…`）がクリップボードに入る**。`.local` が引けない端末用の IP の URL は、端末に出る（状態ファイルの `ipUrl`）
- `--no-tls` で HTTP だけにする。HTTP のままだと、トークンと Cookie が LAN で平文になる（信頼できる自宅の Wi-Fi でだけ使う）

**テスト**: `cd tmux/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v`（検出・セキュリティ・HTTP / HTTPS の結合・証明書・状態ファイル・入り切りスクリプト。`openssl` と `jq` が必要。結合テストは専用ソケット `tmux -S` の別 tmux サーバーだけを使い、普段の tmux には触れない。
入り切りスクリプトのテストは、`AGENT_WEB_CLIP_CMD`（コピー先のコマンド）を偽物にして、本物のクリップボードを書き換えない。`jq` が必要）、
`cd tmux/tests && node --test`（`assets/agent-web/ansi.js` の ANSI 変換）。
環境変数 `TMUX_AGENT_WEB_SOCKET`（tmux のソケットパス）はテスト用。

**新しい Agent の起動**（sidebar の `n` と同じ）: 画面のメニュー（☰）で、リポジトリの見出しの **「＋」**を押し、**Claude Code / Codex** を選ぶ。そのリポジトリのディレクトリで、新しい pane を作って起動する。
- 実体は `tmux-agent-new <kind> <anchor> <dir> --print`。**Mac 側のフォーカスは動かさない**（`--focus` / `--notify` は、Mac の画面を作った pane へ移すので使わない）。起動するコマンドは、sidebar と同じ tmux の option（`@agent_sidebar_claude_cmd` / `@agent_sidebar_codex_cmd`。
  たとえば `--dangerously-skip-permissions` を付けている場合は、スマホからの起動にも付く）
- **ディレクトリと置き場所は、クライアントからは受け取らない**（`POST /api/new` は `id`（検出済みの Agent）と `kind`（`claude` / `codex` の許可リスト）だけを読む）。ディレクトリはその Agent のリポジトリの本体、置き場所はそのリポジトリの先頭の Agent の window。
  閲覧のみのモードでは使えない（403）。失敗の理由は、画面のトーストに出る
- 作った pane が Agent として検出されるまで（Claude は数秒）、画面は 1 秒ごとに一覧を見て、検出されたらその Agent を自動で選ぶ（最長 60 秒）
- テストは、専用ソケットの別 tmux で、本物の `tmux-agent-new` まで通す（起動コマンドを `echo` に差し替えるので、本物の Claude / Codex は起動しない）

**ホーム画面のアイコン**: オレンジのゴースト（`tmux/assets/agent-web/icon.svg` が角丸版、`icon-maskable.svg` が全面塗り版。PNG は `rsvg-convert -w <幅> -h <幅> <svg> -o <png>` で作った
`icon-48/192/512.png`・`icon-maskable-512.png`・`apple-touch-icon.png`）。`manifest.webmanifest`（名前 `tmux agents`、ホーム画面の表示名 `Agents`、`standalone`、アイコン 192/512/maskable）と
`<link rel="icon" / "apple-touch-icon" / "manifest">` を配信する（秘密を含まないのでログイン不要）。表示名・色を変えるときは `manifest.webmanifest` と `index.html` の `apple-mobile-web-app-title` を直す。
`sw.js` は「アプリとして追加」の条件（fetch ハンドラ）を満たすためだけの Service Worker で、**何もキャッシュしない**（認証済みの内容を端末に残さない）。
- **Android の Chrome の「アプリをインストール」**: **https の URL を開いて**インストールする（上の「HTTP と HTTPS の両方」）。証明書の警告は「詳細設定 → 続行」で越える（CA の導入は不要。実機で確認済み）。
  http のままだと、アプリは作られても、タブで開いてしまう。「ホーム画面に追加」（ショートカット）だけだと、アイコンに **Chrome のバッジ**が付く（Android 8 以降が付ける印で、サイト側では消せない）
- 補足（http のまま使う場合のみ）: スマホの Chrome の `chrome://flags`（アドレスバーに手で入力。リンクのタップでは開けない）→ `insecure` → 「Insecure origins treated as secure」に
  `http://<Mac の名前>.local:8765`（末尾の `/` なし）を入れて Enabled → 再起動すると、http でも「アプリをインストール」が出る。ただし上のとおり、起動はタブになる
- ⚠️ 「アプリをインストール」が出ないときは、まず Mac のログ（`~/.cache/tmux-agent-web/server.log`）で、スマホが `manifest.webmanifest` を取得しているか見る。
  取得していなければ、CSP が `manifest-src` を止めている（以前はこれで失敗していた。`default-src 'none'` のままだと manifest も Service Worker も止まるので、CSP に明示している）
- iOS の Safari は、`apple-touch-icon` でホーム画面のアイコンが付く（バッジは付かない）。ホーム画面から開くアプリは Safari と Cookie が別なので、そこで一度ログインし直す

**既知の制限・今後**: Agent の居ない空きシェルの欄からの起動（sidebar の `n` の `--here`）・再起動（`R`）は未対応。pane 表示は端末のミラーなので、読みやすさは pane の幅に依存する
（改善案: トランスクリプトからチャット形式で表示、承認待ちの画面をボタン化）。

### Claude Code (claude/)
**settings.json**: MCP サーバーの事前承認とフック設定
- Serena（セマンティックコード操作）、JetBrains、Context7
- タスク完了/ユーザープロンプト時に terminal-notifier で通知
- カスタム statusLine で使用量とコンテキスト情報を表示

**commands/serena.md**: `/serena` コマンド
- 構造化問題解決用カスタムスラッシュコマンド
- モード: `-q`（クイック）、`-d`（詳細）、`-c`（コード重視）、`-s`（ステップバイステップ）
- 問題タイプ自動検出（デバッグ/設計/実装/レビュー）

**commands/wiki.md**: `/wiki` コマンド
- プロジェクト全体を解析し体系的なドキュメントを自動生成
- 出力先: `wiki/` ディレクトリ（00-目次.md から 11-まとめ.md まで）
- TodoWrite でタスク管理しながら段階的に生成
- `ドキュメント構成.md` でカスタマイズ可能

**hooks: Git add 安全性強化**
- `validate-bash.sh` で `git add -A`、`git add .`、`git add --all` を自動的にブロック
- PreToolUse フックで Claude Code が git add を実行する前に検証
- 機密ファイルの誤コミットを防止
- 補助ツール: `scripts/safe-git-add.sh` で手動実行時も同様の検証を提供

**hooks: default ブランチへの push を ask にする**
- `hooks/guard-default-branch-push.py`（PreToolUse）。`git push` は allow だが、push 先が default ブランチのときだけ確認を出す
- 権限ルールはコマンド文字列にしか当たらず、master 上の素の `git push` を区別できないため、フックで実際の push 先を判定する
- default ブランチは `origin/HEAD` から求める（未設定なら main / master）。現在のブランチ・upstream・refspec（`HEAD:master`、`:master`、`+x:master`）・`--all` / `--mirror` を見る。`cd x && git push` や `git -C x push` も追う
- 判定に失敗したときは何も出さず、通常の権限判定に任せる（force push などは settings.json の ask / deny が引き続き効く）
- テスト: `cd claude/hooks/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v`

**OpenAI Codex CLI 統合**:
- `claude/commands/` は `~/.codex/prompts/` にもリンク
- Codex CLI では `/prompts:serena`、`/prompts:wiki` で実行
- コマンドファイルは両方の AI CLI で共有可能

**skills/review-pr/**: PR レビュー自動対応スキル
- ユーザーが「レビューコメントに対応」と依頼すると自動起動
- 完全自動化ワークフロー:
  1. 直前 push 以降のコメントを取得
  2. Claude が修正案を生成（一括承認）
  3. 修正を適用 + commit & push
  4. 返信文を生成（一括承認）
  5. GitHub に一括投稿
  6. (オプション) AI レビュー待機（10 分）→ 新しいコメント検出で再実行
- `auto_reply_pr_comments.sh`: メインスクリプト（JSON 形式でコメント取得）
- `post_pr_reply.sh`: 返信投稿ヘルパー（REST/GraphQL API）
- `wait_and_recheck_pr_comments.sh`: AI レビュー待機スクリプト（30 秒 × 20 回チェック）
- AI 署名を自動追加（透明性確保）

**skills/start-worktree/**: worktree 作業開始スキル
- `/start-worktree <作業内容>` で、作業内容からブランチ名を決めて worktree を作成
- `bin/create-worktree` で作成 → `EnterWorktree(path)` でセッション移動 → プランモード開始

**skills/cleanup-worktrees/**: merge 済み worktree 削除スキル
- 「merge 済みの worktree を消して」で、merge 済みの worktree を検知 → 一覧提示 → 一括承認 → worktree とブランチを削除
- 判定は worktree の HEAD SHA で行い、命名規則に依存しない（`gh api commits/<sha>/pulls` で merged かつ `head.sha` 一致。`gh` が使えなければ merge commit の第 2 親で判定）
- 未コミット変更があってもスキップしない。tracked の変更は削除前に `.claude/tmp/worktree-patches/` へ patch を退避
- `bin/scan-worktrees`（検知、削除なし）/ `bin/remove-worktree`（1 件削除）

**scripts/**: 各種スクリプト
- `statusline.sh`: カスタムステータスライン（会話タイトル、モデル + effort、コンテキスト使用量、プロンプトキャッシュ状態と cold 時の再キャッシュ量、推定コスト、支出上限、PR とレビュー状態、処理時間、バージョン、レートリミット警告を表示）
- `extract-title.sh`: 会話タイトル抽出（ルールベース）。トランスクリプトから最初のユーザーメッセージを抽出して 30 文字のタイトルを生成。キャッシュ機構付き
- `generate-title.sh`: 会話タイトル生成（AI 生成）。codex CLI で会話全体を要約してタイトルを作成。失敗時は extract-title.sh にフォールバック
- `translate-title.sh`: プラン承認で付く英語のハイフンつなぎのセッション名（例: `eve-account-takeover-redesign`）を codex で日本語に訳す（statusline から呼ぶ）
- `debug-statusline-input.sh`: statusLine 入力データのデバッグ用
- `fetch_pr_comments.sh`: PR コメント取得（表示専用）
- `auto_reply_pr_comments.sh`: PR コメント自動対応（修正 + 返信）
- `post_pr_reply.sh`: PR コメント返信投稿
- `wait_and_recheck_pr_comments.sh`: AI レビュー待機＆再チェック

**会話タイトル機能について**:
- **statusLine での表示**: 1 行表示の先頭に会話タイトルを表示。例: `📝 statusLine見直し | 🤖 Opus 5.5 xhigh | 💬 ... | 🧊 ~14:38 | ...`
- **タイトルの取得元**: Claude Code が渡す `session_name`（`/rename` の名前か AI 生成タイトル）を優先し、キャッシュファイルにも書き出す。`session_name` が無い間のみ `generate-title.sh` で生成
- **プラン承認後の英語名の翻訳**: Claude Code はプランを承認するとタイトルを `eve-account-takeover-redesign` のような英語のハイフンつなぎに付け替える（言語や形式を変える設定は無い）。
  `session_name` が `^[a-z0-9]+(-[a-z0-9]+)+$` に合うときだけ `translate-title.sh` が日本語にする
  - 訳が無い間はハイフンを空白にした名前を出し、バックグラウンドで codex に訳させる（約 10〜20 秒）。訳が出来たらキャッシュファイルを書き直すので、sidebar・通知にもそのまま反映される
  - 名前だけだと意味を取り違える（"takeover" が「乗っ取り」になる等）ため、トランスクリプトの最後の `ExitPlanMode` のプラン本文（先頭 800 文字）を参考に渡す
  - 訳は `/tmp/claude-title-ja-cache.txt`（`英語名|訳`）に保存し、同じ名前は訳し直さない。誤訳を直すときはこのファイルの該当行を消す
  - statusline が動いていないセッションの sidebar（トランスクリプトの `ai-title` を使う）は英語のまま
- **通知での表示**: タスク完了時の通知タイトルに AI 生成タイトルを含める。例: `✅ Claude Code [dotfiles] - statusLine実装調査`
- **キャッシュ**: `/tmp/claude-title-<session_id>.txt` にキャッシュされ、同じセッション内での重複生成を回避
- **環境変数**:
  - `CLAUDE_DISABLE_AI_TITLE=1`: AI 生成をスキップしてルールベース抽出のみを使用
  - `CLAUDE_TITLE_MAX_LENGTH=30`: タイトルの最大文字数（デフォルト: 30）
- **トラブルシューティング**: キャッシュをクリアする場合は `rm /tmp/claude-title-*.txt`

### Zsh (.zshrc)
- 100 万行の履歴管理
- FZF 統合（`Ctrl-R` で履歴検索）
- mise（バージョンマネージャー）、gcloud SDK
- エイリアス: `l`, `ll`

### Lazygit (lazygit/config.yml)
- オレンジ系カラースキーム
- カスタムコマンド定義
- Worktrees パネルで `n` → `bin/create-worktree` で worktree 作成

### bin/create-worktree
- `create-worktree <branch>` で `../<repo>_worktree_<branch>` に worktree を作成し、未コミット・gitignore 対象のファイルをコピー
- stdout は作成したパスのみ（lazygit と start-worktree スキルで共用）

### Ghostty (ghostty/config)
- Dracula テーマ + 透過背景（opacity 0.70）
- フォント: HackGen Console NF（太字化有効）
  - 全角が半角の正確に 2 倍幅で tmux の罫線がズレない
  - `font-codepoint-map` で英数のみ JetBrains Mono に差し替え
  - 同じく `⬤`（U+2B24）のみ STIX Two Math に差し替え
    （tmux のセッション状態表示用。詳細は Tmux の項を参照）
- **Shift+Enter で改行入力**（Claude Code 対応）
- 起動時に tmux の `default` セッションを自動再開（存在しなければ新規作成）
- 全画面モード（非ネイティブ、透過メニューバー）
- カスタムアイコン（オレンジゴースト）

## 注意事項

⚠️ **Tmux プラグイン**: TPM 自動初期化は無効化済み。手動クローンが必要
⚠️ **macOS 専用**: クリップボード統合、terminal-notifier など macOS 固有機能を使用
⚠️ **Claude Code フック**: `/opt/homebrew/bin/terminal-notifier` のインストールが前提
⚠️ **透明化**: vim と tmux で背景透明化を設定（ターミナルテーマと統合）

## ファイル構造
```
.
├── .vimrc                 # Vim 設定（カスタム desert テーマ）
├── .tmux.conf             # Tmux 設定（プレフィックス Ctrl-t）
├── .zshrc                 # Zsh シェル設定
├── claude/                # Claude Code 設定ディレクトリ
│   ├── CLAUDE.md          # グローバル指示書（~/.claude/ へリンク）
│   ├── settings.json      # 権限設定・フック
│   ├── commands/          # カスタムコマンド
│   │   ├── serena.md      # /serena（構造化問題解決）
│   │   └── wiki.md        # /wiki（ドキュメント自動生成）
│   ├── scripts/           # 通知フックスクリプト
│   ├── agents/            # カスタムエージェント
│   └── skills/            # カスタムスキル
│       ├── review-pr/     # PR レビュー自動対応スキル
│       ├── sequential-thinking/  # 段階的思考スキル
│       └── ...            # その他スキル
├── tmux/scripts/          # Tmux ステータスバー用スクリプト
│   ├── tmux-claude-agents-status  # sidebar の DONE 判定用の状態ファイルを更新（--state-only、表示なし）
│   ├── tmux-claude-agents-jump    # C-t a のポップアップ一覧（選択したペインへジャンプ）
│   ├── tmux-agent-sidebar         # window 左端に置く Agent 一覧 pane の本体
│   ├── tmux-agent-sidebar-open    # sidebar を window 左端に追加（二重起動防止）
│   ├── tmux-agent-sidebar-preview # sidebar の p で開くポップアップ（pane のライブプレビュー）
│   ├── tmux-agent-cockpit         # Agent cockpit の制御（open / show / restore / close / heal）
│   ├── tmux-agent-cockpit-slot    # cockpit の右の枠に常駐する交換用 pane
│   ├── tmux-agent-restart         # sidebar の R で呼ばれる Claude Code の再起動（終了 → --resume で入り直す）
│   ├── tmux-agent-new             # sidebar の n で呼ばれる、リポジトリでの新規 pane + Claude / Codex の新規起動
│   ├── tmux-agent-web             # スマホのブラウザから Agent を確認・操作する Web サーバー（Python。画面は tmux/assets/agent-web/）
│   ├── tmux-agent-web-toggle      # sidebar の w / W から呼ばれる、tmux-agent-web の入り切り・URL コピー
│   ├── tmux-window-reorder        # C-t S の window 並び替えポップアップ
│   ├── tmux-rate-limits   # レートリミット使用率表示（現在はステータスバーから外し、sidebar の USAGE 欄が代替）
│   └── ...                # その他スクリプト
├── lazygit/config.yml     # Lazygit 設定
├── ghostty/config         # Ghostty 設定（Shift+Enter 対応）
├── CLAUDE.md              # このファイル（プロジェクト固有指示）
└── README.md              # セットアップ手順
```
