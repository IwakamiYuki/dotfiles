#!/usr/bin/env python3
# <xbar.title>tmux agents</xbar.title>
# <xbar.desc>tmux 上の Claude Code / Codex の状態を、Mac のメニューバーに出す</xbar.desc>
# <xbar.dependencies>python3,tmux</xbar.dependencies>
# <swiftbar.hideAbout>true</swiftbar.hideAbout>
# <swiftbar.hideRunInTerminal>true</swiftbar.hideRunInTerminal>
# <swiftbar.hideLastUpdated>true</swiftbar.hideLastUpdated>
# <swiftbar.hideDisablePlugin>true</swiftbar.hideDisablePlugin>
# <swiftbar.hideSwiftBar>true</swiftbar.hideSwiftBar>
#
# 一覧は `tmux-agent-web --list-agents`（sidebar と同じ検出の Python 版。サーバーは起動しない）から取る。
# 項目をクリックすると、通知のクリックと同じ処理（claude/hooks/focus-tmux-pane.sh）で、その Agent へ飛ぶ
# （cockpit があれば右の枠へ入れて、Ghostty を前面に出す）。
# SwiftBar は 10 秒ごとにこのスクリプトを実行する（ファイル名の 10s）。検出が数百 ms かかるので、これより短くしない。
import json
import os
import subprocess
import sys
from pathlib import Path

# SwiftBar の PATH は最小限なので、tmux（homebrew）と claude（~/.local/bin）が見えるようにする
os.environ["PATH"] = ":".join([str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin", os.environ.get("PATH", "/usr/bin:/bin")])

ROOT = Path(__file__).resolve().parent.parent.parent
LIST_BIN = os.environ.get("TMUX_AGENTS_SWIFTBAR_LIST_BIN") or str(ROOT / "tmux/scripts/tmux-agent-web")
FOCUS_BIN = os.environ.get("TMUX_AGENTS_SWIFTBAR_FOCUS_BIN") or str(ROOT / "claude/hooks/focus-tmux-pane.sh")

# 要確認(waiting / done) → 作業中 → 待機 の順に出す。絵文字は、sidebar の状態色（赤 / 緑 / 黄 / 灰）に合わせる
MARK = {"waiting": "🔴", "done": "🟢", "working": "🟡", "idle": "⚪", "unknown": "⚫"}
LABEL = {"waiting": "WAITING", "done": "DONE", "working": "WORKING", "idle": "IDLE", "unknown": "UNKNOWN"}
SECTIONS = [("要確認", ("waiting", "done")), ("作業中", ("working",)), ("待機", ("idle", "unknown"))]


def run(cmd, timeout=15):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def socket_path():
    # テストでは、本物の tmux を呼ばないよう環境変数で差し替える
    if "TMUX_AGENTS_SWIFTBAR_SOCKET" in os.environ:
        return os.environ["TMUX_AGENTS_SWIFTBAR_SOCKET"]
    return run(["tmux", "display-message", "-p", "#{socket_path}"], timeout=3).strip()


def agents():
    try:
        data = json.loads(run([sys.executable, LIST_BIN, "--list-agents"]))
    except ValueError:
        return None
    return data if isinstance(data, list) else None


def fmt_elapsed(sec):
    if sec is None:
        return ""
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m"
    if sec < 86400:
        return f"{sec // 3600}h{sec % 3600 // 60}m"
    return f"{sec // 86400}d{sec % 86400 // 3600}h"


def title(items):
    count = {k: sum(1 for a in items if a["status"] == k) for k in MARK}
    parts = [f"{MARK[k]}{count[k]}" for k in ("waiting", "done", "working") if count[k]]
    return " ".join(parts) if parts else f"🤖 {len(items)}"


def entry(a, sock):
    session = a["window"].split(":")[0]
    elapsed = fmt_elapsed(a.get("elapsed"))
    # 1 行に収める(サブメニューを付けると、クリックが「ジャンプ」ではなく「開く」になるため)。
    # 項目の文字に | や改行が入ると SwiftBar の属性と取り違えるので落とす
    text = f"{MARK[a['status']]} {a['repo']} / {a['name']}  ·  {LABEL[a['status']]}" + (f" {elapsed}" if elapsed else "")
    text = text.replace("|", "¦").replace("\n", " ")
    return f"{text} | bash={FOCUS_BIN} param1={session} param2={a['pane']} param3={sock} terminal=false refresh=true"


def main():
    sock = socket_path()
    if not sock:
        print("🤖 – | color=#888888\n---\ntmux が動いていません")
        return
    items = agents()
    if items is None:
        print("🤖 ? | color=#888888\n---\nAgent 一覧を取得できません")
        return
    if not items:
        print("🤖 0\n---\nAgent は動いていません")
        return
    print(title(items))
    for label, statuses in SECTIONS:
        group = [a for a in items if a["status"] in statuses]
        if not group:
            continue
        print("---")
        print(f"{label} ({len(group)}) | size=11 color=#888888")
        for a in group:
            print(entry(a, sock))


if __name__ == "__main__":
    main()
