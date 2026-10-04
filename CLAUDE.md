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
# tmux/scripts/ 配下は全部リンクする（.tmux.conf が ~/.tmux/scripts/ を参照。漏れると C-t b 等が no such file で失敗する）
mkdir -p ~/.tmux/scripts
for f in ~/dotfiles/tmux/scripts/*; do ln -sf "$f" ~/.tmux/scripts/"$(basename "$f")"; done
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
- `Ctrl-t c` → 新規 window を作り、左端に sidebar を追加（フォーカスは main pane）
- `Ctrl-t b` → 現在の window に sidebar を追加。すでにあれば二重起動せず sidebar へフォーカス
- sidebar 上で `Ctrl-C` → sidebar だけ終了して pane が閉じる。main pane は残る
- ⚠️ `Ctrl-t a`（Claude 一覧ポップアップ）が使用済みのため、再表示キーは `b`
- sidebar 上で `j` / `k`（`↓` / `↑`、マウスホイール）→ 選択を移動。選択中のカードはオレンジの角丸罫線で囲まれる（sidebar にフォーカスがあるときだけ表示。このとき 2 行目に操作ヒントも出る）
- sidebar 上で `Enter`、または Agent の行を **クリック** → その Agent の window・pane へジャンプ（`r` で即時更新）
- sidebar 上で `j` / `k`（`↓` / `↑`）→ 選択を動かして、そのまま **ポップアップでプレビュー**を開く（`@agent_sidebar_auto_preview`、後述）。マウスホイールは選択を動かすだけで、開かない
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
- 見た目は Orca の worktree 一覧を意識したカード表示。window ごとの見出し（`── 6 dotfiles ───`）で区切り、各 Agent は背景色を敷いた 3〜4 行のカードで、左端のバーが状態色
  - `project ……… 種別(右寄せ)` / 会話タイトル（あれば）/ ` ブランチ   親ディレクトリ` / `[ ⠋ WORKING ] 待機理由 ……… 継続時間`。pane 番号と状態アイコン（●等）は出さない
  - 状態は背景色付きのピル（WORKING=黄 / WAITING=赤 / DONE=緑 / IDLE=くすんだ橙 / UNKNOWN=灰）。working のピルの中でスピナーが回る（`read -t` が整数秒のため 1 秒 1 コマ）
  - 先頭行に状態別の件数（カードのバーと同じ色の `▎1 ▎1`）
  - **選択**（カーソル）と**現在地**（いま見ている pane）は別の表現にして混同を避ける
    - 選択: カードを **オレンジの角丸罫線 `╭─╮ │ │ ╰─╯` で丸ごと囲む**。カード間の区切り行を罫線に兼用するので行数は増えない（区切り行は選択時に上辺/下辺になる）
    - 現在地: 左端を **シアンの `▶`**、project 名を **シアンの太字**にする（選択中は左端が罫線になるため名前の色だけで示す）
  - 文字幅は `char_width`（UTF-8 のバイトからコードポイントを復元して判定。East Asian Ambiguous の `’ “ — → ▶` や罫線は 1 桁、CJK・絵文字は 2 桁）で数える。
    以前は ASCII 以外を一律 2 桁と数えていて、`’` や `—` を含む行で右端の罫線が左へずれていた。
    さらにカードの右端の縁は `ESC[row;colH` で桁を指定して描くので、幅の見積もりがずれても縁の位置は動かない
  - 注意が必要な状態はカードの背景に色味を付ける（WAITING=暗い赤、DONE=暗い緑。選択中は一段明るい）
  - 下部に固定の `── USAGE ──` 欄で Claude Code の 5h / 1w レートリミット使用率（バー + % + リセットまでの残り時間。色は `tmux-rate-limits` と同じ段階で 80% 以上は赤）を表示。元データは `statusline.sh` が書く `/tmp/claude-rate-limits.json`。端末の高さが 14 未満、またはファイルが無いときは出さない
  - **種別アイコン（画像）** `@agent_sidebar_type_icon`: `text`（既定。project 名の右に `Claude` / `Codex` の文字）| `image`（project 名の左に 2 桁 × 1 行の画像。project 名の幅が増える）
    - 画像は `tmux/assets/agent-icons/{claude,codex}.png`（出所は同ディレクトリの `NOTICE.md`。Simple Icons の SVG を色付け・PNG 化したもの）
    - Kitty graphics protocol の **Unicode placeholders** を使う: 画像データを tmux のパススルー（`ESC P tmux ; … ESC \`）で端末へ一度登録し、
      カードには `U+10EEEE` + 行/列の結合文字（`U+0305` / `U+030D`）の文字を置く（前景色の 256 色番号が画像 ID）。画像が文字として扱われるので、
      window 切り替え・再描画で残像が出ない。10 秒ごとに登録し直す（端末の再接続で消えても戻る）
    - `allow-passthrough on`（既定は off）・Ghostty（Kitty graphics 対応）・アイコンが読めること、が条件。満たさなければ自動で `text` に戻る
    - 画像 ID は 250 / 251（他のアプリと衝突しにくい値）。tmux のパススルーは表示中の window の pane からしか端末へ届かない
  - アイコンは Nerd Font 前提（`@agent_sidebar_icons nerd`）。`plain` にすると記号なしになる
  - タイトルは `/tmp/claude-title-<sessionId>.txt`、継続時間は `~/.claude/sessions/<pid>.json` の `statusUpdatedAt`、ブランチは cwd での `git branch --show-current`（10 秒キャッシュ。detached HEAD なら短縮 SHA）
  - 行数はタイトルの有無で 3〜4 行に変わる（見出し・区切り行は別。window ごとに「見出し → [区切り → カード]… → 閉じの区切り」）。収まらない分は `+N more` にし、選択に追従してスクロールする
- Claude: `claude agents --json`（約 0.2 秒）と各セッションの更新時刻を `/tmp/tmux-agent-sidebar-claude2.txt` に 3 秒キャッシュして全 sidebar で共有。pid の祖先をたどって pane に紐付ける。status は working / waiting / idle。未読の完了は `tmux-claude-agents-status` の状態ファイルを参照して done 表示
- Codex: ps の引数（`codex` 本体、または `node .../codex`）で検出。状態を確実に判定する手段が無いため unknown 固定（推測しない）
- 内部は共通レコード `R|session|window|window_name|pane|type|pane_id|active|project|status|detail|elapsed_sec|title|cwd`。検出（awk）と表示（render）を分離しているので、状態判定の追加は collect 側だけで済む
- 環境変数（主にデバッグ用）: `AGENT_SIDEBAR_INTERVAL`、`AGENT_SIDEBAR_CLAUDE_BIN`、`AGENT_SIDEBAR_CLAUDE_CACHE`、`AGENT_SIDEBAR_SESSIONS_DIR`、`AGENT_SIDEBAR_RATE_LIMITS`、`AGENT_SIDEBAR_ICON_DIR`、`AGENT_SIDEBAR_DEBUG=1`（stderr を捨てない）

**既知の制限**:
- 別の Mac へ移したときは `~/.tmux/scripts/` へのリンクが必要（git では運ばれない）。「初期セットアップ」のループで `tmux/scripts/*` を全部リンクする。足りないと `C-t b` / `C-t c` が `no such file or directory: ~/.tmux/scripts/tmux-agent-sidebar-open` で失敗する
- tmux-resurrect で復元すると、sidebar pane は空のシェル pane になる（`C-t b` を押す前に邪魔なら閉じる）
- 既存 window へは自動追加しない（必要な window で `C-t b`）
- 起動中のスクリプトを書き換えると bash が壊れた読み方をするため、スクリプトを更新したら sidebar は閉じて開き直す

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
- `debug-statusline-input.sh`: statusLine 入力データのデバッグ用
- `fetch_pr_comments.sh`: PR コメント取得（表示専用）
- `auto_reply_pr_comments.sh`: PR コメント自動対応（修正 + 返信）
- `post_pr_reply.sh`: PR コメント返信投稿
- `wait_and_recheck_pr_comments.sh`: AI レビュー待機＆再チェック

**会話タイトル機能について**:
- **statusLine での表示**: 1 行表示の先頭に会話タイトルを表示。例: `📝 statusLine見直し | 🤖 Opus 5.5 xhigh | 💬 ... | 🧊 ~14:38 | ...`
- **タイトルの取得元**: Claude Code が渡す `session_name`（`/rename` の名前か AI 生成タイトル）を優先し、キャッシュファイルにも書き出す。`session_name` が無い間のみ `generate-title.sh` で生成
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
│   ├── tmux-rate-limits   # レートリミット使用率表示（現在はステータスバーから外し、sidebar の USAGE 欄が代替）
│   └── ...                # その他スクリプト
├── lazygit/config.yml     # Lazygit 設定
├── ghostty/config         # Ghostty 設定（Shift+Enter 対応）
├── CLAUDE.md              # このファイル（プロジェクト固有指示）
└── README.md              # セットアップ手順
```
