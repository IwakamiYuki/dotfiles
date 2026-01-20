# dotfiles - Claude Code ガイド

macOS 開発環境用の dotfiles リポジトリ。vim、tmux、zsh、Claude Code の設定を管理。すべてホームディレクトリからシンボリックリンクで参照。

## 重要な原則

**完了の合い言葉**: すべてのタスクが完了したら `May the Force be with you.` と報告

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
⚠️ **重要**: TPM 自動初期化は無効化済み。手動でプラグインをクローン：
```bash
mkdir -p ~/.tmux/plugins && cd ~/.tmux/plugins
git clone https://github.com/tmux-plugins/tpm
git clone https://github.com/tmux-plugins/tmux-sensible
git clone https://github.com/tmux-plugins/tmux-resurrect
git clone https://github.com/tmux-plugins/tmux-continuum
git clone https://github.com/tmux-plugins/tmux-cpu
git clone https://github.com/tmux-plugins/tmux-battery
chmod +x ~/.tmux/plugins/tmux-cpu/scripts/*.sh
chmod +x ~/.tmux/plugins/tmux-battery/scripts/*.sh
```

### 依存関係インストール
```bash
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

**scripts/**: 各種スクリプト
- `statusline.sh`: カスタムステータスライン（会話タイトル、コンテキスト使用量、セッション情報、処理時間、コード変更量を表示）
- `extract-title.sh`: 会話タイトル抽出（ルールベース）。トランスクリプトから最初のユーザーメッセージを抽出して 30 文字のタイトルを生成。キャッシュ機構付き
- `generate-title.sh`: 会話タイトル生成（AI 生成）。codex CLI で会話全体を要約してタイトルを作成。失敗時は extract-title.sh にフォールバック
- `get-session-usage.sh`: セッション使用率取得（キャッシュ機構付き）
- `notify-end.sh`, `notify-ask.sh`: 通知フックスクリプト（notify-end.sh は AI 生成タイトルで通知タイトルを更新）
- `debug-statusline-input.sh`: statusLine 入力データのデバッグ用
- `fetch_pr_comments.sh`: PR コメント取得（表示専用）
- `auto_reply_pr_comments.sh`: PR コメント自動対応（修正 + 返信）
- `post_pr_reply.sh`: PR コメント返信投稿
- `wait_and_recheck_pr_comments.sh`: AI レビュー待機＆再チェック

**会話タイトル機能について**:
- **statusLine での表示**: 2 行表示で最初の行に会話タイトルを表示。例: `📝 statusLine実装調査` / `🤖 Haiku | 📊 ...`
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

### Ghostty (ghostty/config)
- Dracula テーマ + 透過背景（opacity 0.70）
- フォント: Osaka（太字化有効）
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
├── lazygit/config.yml     # Lazygit 設定
├── ghostty/config         # Ghostty 設定（Shift+Enter 対応）
├── CLAUDE.md              # このファイル（プロジェクト固有指示）
└── README.md              # セットアップ手順
```
