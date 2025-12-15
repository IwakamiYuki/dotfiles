Unity プロジェクトから空ディレクトリと対応する .meta ファイルを削除します。

まず `~/dotfiles/claude/scripts/clean-empty-unity-dirs.sh -n` で dry-run を実行し、削除対象を確認してください。問題なければ `-f` オプション付きで実行します。

Unity プロジェクトでは空のディレクトリが存在すると無駄な .meta ファイルが生成されます。このコマンドはそれらを一括で削除します。
