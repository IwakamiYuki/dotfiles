#!/usr/bin/env python3
"""PreToolUse hook: default ブランチへの git push を ask にする。

権限ルール（settings.json の allow / ask）はコマンド文字列にしか当たらない。
`git push` は文字列には現れなくても、master / main 上で実行すれば default ブランチへ push する。
そのため、実際の push 先（現在のブランチ・upstream・refspec）をここで判定する。

default ブランチは `origin/HEAD` から求める。未設定のときは main / master を default とみなす。
判定に失敗したときは何も出力せず、通常の権限判定に任せる。
"""
import json
import os
import re
import shlex
import subprocess
import sys

FALLBACK_DEFAULT_BRANCHES = {"main", "master"}
COMMAND_SEPARATORS = {"&&", "||", ";", "|", "&"}
REDIRECT_PATTERN = re.compile(r"^[<>&|()]+$")
# 値を別トークンで取る push のオプション（`--repo=x` のように = で続ける形は 1 トークン）
PUSH_OPTIONS_WITH_VALUE = {"--repo", "-o", "--push-option", "--receive-pack", "--exec"}
GIT_OPTIONS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


def run_git(cwd, *args):
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def default_branches(cwd):
    origin_head = run_git(cwd, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if "/" in origin_head:
        return {origin_head.split("/", 1)[1]}
    return FALLBACK_DEFAULT_BRANCHES


def tokenize(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def split_commands(tokens):
    """トークン列を `&&` `;` `|` などで分け、リダイレクト（`2>&1` など）を落とす。"""
    commands, current = [], []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in COMMAND_SEPARATORS:
            commands.append(current)
            current = []
        elif REDIRECT_PATTERN.match(token):
            skip_next = True
            if current and current[-1].isdigit():
                current.pop()
        else:
            current.append(token)
    commands.append(current)
    return [c for c in commands if c]


def resolve_dir(base, path):
    return os.path.normpath(os.path.join(base, os.path.expanduser(path)))


def parse_git_push(command_tokens, cwd):
    """`git push` なら (作業ディレクトリ, push の引数) を返す。それ以外は None。"""
    i = 0
    while i < len(command_tokens) and re.match(r"^\w+=", command_tokens[i]):
        i += 1
    if i >= len(command_tokens) or command_tokens[i] != "git":
        return None
    i += 1
    while i < len(command_tokens) and command_tokens[i].startswith("-"):
        option = command_tokens[i]
        if option in GIT_OPTIONS_WITH_VALUE and i + 1 < len(command_tokens):
            if option == "-C":
                cwd = resolve_dir(cwd, command_tokens[i + 1])
            i += 1
        i += 1
    if i >= len(command_tokens) or command_tokens[i] != "push":
        return None
    return cwd, command_tokens[i + 1:]


def pushed_branch_names(cwd, push_args):
    """push が書き換えるブランチ名の集合と、特別扱いする理由（あれば）を返す。"""
    flags, positionals = [], []
    skip_next = False
    for arg in push_args:
        if skip_next:
            skip_next = False
        elif arg in PUSH_OPTIONS_WITH_VALUE:
            skip_next = True
        elif arg.startswith("-"):
            flags.append(arg)
        else:
            positionals.append(arg)

    if "--all" in flags or "--mirror" in flags:
        return set(), "全ブランチを push する指定（default ブランチを含む）"

    current = run_git(cwd, "branch", "--show-current")
    refspecs = positionals[1:]  # 先頭はリモート名
    if not refspecs:
        names = {current} if current else set()
        upstream = run_git(cwd, "config", f"branch.{current}.merge") if current else ""
        if upstream.startswith("refs/heads/"):
            names.add(upstream[len("refs/heads/"):])
        return names, None

    names = set()
    for refspec in refspecs:
        refspec = refspec.lstrip("+")
        source, _, destination = refspec.partition(":")
        target = destination if ":" in refspec else source
        if source == "HEAD" and ":" not in refspec:
            target = current
        if "*" in target:
            return set(), "ワイルドカードの refspec"
        names.add(re.sub(r"^refs/heads/", "", target))
    return names, None


def evaluate(command, cwd):
    """ask が必要なら理由を返す。不要なら None。"""
    if "push" not in command:
        return None
    try:
        commands = split_commands(tokenize(command))
    except ValueError:
        # 引用符が閉じていないなど。コミットメッセージに "git push" と書いただけの場合もあるので、
        # 文字列に `git push` が現れるときだけ止める
        return "コマンドを解析できず、git push を含む可能性があります" if re.search(
            r"\bgit\b.*\bpush\b", command
        ) else None

    for command_tokens in commands:
        if command_tokens[0] == "cd" and len(command_tokens) > 1:
            cwd = resolve_dir(cwd, command_tokens[1])
            continue
        parsed = parse_git_push(command_tokens, cwd)
        if parsed is None:
            continue
        push_cwd, push_args = parsed
        if not run_git(push_cwd, "rev-parse", "--git-dir"):
            continue
        names, reason = pushed_branch_names(push_cwd, push_args)
        if reason:
            return reason
        hit = names & default_branches(push_cwd)
        if hit:
            return f"default ブランチ（{', '.join(sorted(hit))}）への push です"
    return None


def main():
    try:
        data = json.load(sys.stdin)
        command = data.get("tool_input", {}).get("command", "")
        cwd = data.get("cwd") or os.getcwd()
        reason = evaluate(command, cwd)
    except Exception:
        return
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason,
            }
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
