"""メニューバー(SwiftBar)のプラグイン tmux/swiftbar/tmux-agents.10s.py と、その元になる tmux-agent-web --list-agents。"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PLUGIN = os.path.join(ROOT, "tmux", "swiftbar", "tmux-agents.10s.py")
WEB = os.path.join(ROOT, "tmux", "scripts", "tmux-agent-web")


def agent(pane, status, name="作業", repo="dotfiles", elapsed=90, window="default:1.1", kind="Claude", branch="master"):
    return {"id": int(pane.lstrip("%")), "pane": pane, "type": kind, "status": status, "detail": "", "name": name, "repo": repo,
            "repoKey": f"/r/{repo}", "branch": branch, "worktree": f"/r/{repo}", "cwd": f"/r/{repo}", "elapsed": elapsed,
            "window": window, "active": False, "cols": 80, "rows": 24}


class PluginTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="swb.")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def fake_list(self, payload, raw=None):
        path = os.path.join(self.dir, "fake-list")
        with open(path, "w") as f:
            f.write(raw if raw is not None else json.dumps(payload, ensure_ascii=False))
        return path

    def run_plugin(self, payload=None, raw=None, socket="/tmp/fake.sock"):
        # 偽の一覧は、そのまま標準出力へ出す python スクリプトとして渡す(本物の tmux / claude は呼ばない)
        script = os.path.join(self.dir, "list.py")
        data = self.fake_list(payload, raw)
        with open(script, "w") as f:
            f.write(f"import sys\nsys.stdout.write(open({data!r}).read())\n")
        env = {"PATH": "/usr/bin:/bin", "HOME": self.dir, "TMUX_AGENTS_SWIFTBAR_LIST_BIN": script,
               "TMUX_AGENTS_SWIFTBAR_FOCUS_BIN": "/x/focus.sh", "TMUX_AGENTS_SWIFTBAR_SOCKET": socket}
        out = subprocess.run([sys.executable, PLUGIN], capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.splitlines()

    def test_タイトルは_要確認と作業中の件数(self):
        lines = self.run_plugin([agent("%1", "waiting"), agent("%2", "done"), agent("%3", "done"), agent("%4", "working"), agent("%5", "idle")])
        self.assertEqual(lines[0], "🔴1 🟢2 🟡1")

    def test_動いているものが無ければ_Agent_の数だけ出す(self):
        self.assertEqual(self.run_plugin([agent("%1", "idle"), agent("%2", "idle")])[0], "🤖 2")

    def test_項目は_要確認_作業中_待機_の順に並ぶ(self):
        lines = self.run_plugin([agent("%1", "idle"), agent("%2", "working"), agent("%3", "waiting")])
        headers = [l for l in lines if l.endswith("size=11 color=#888888")]
        self.assertEqual([h.split(" (")[0] for h in headers], ["要確認", "作業中", "待機"])

    def test_項目をクリックすると_通知と同じ_focus_スクリプトで飛ぶ(self):
        lines = self.run_plugin([agent("%7", "waiting", name="確認待ち", repo="wow", window="dev:3.2")])
        item = next(l for l in lines if "確認待ち" in l)
        self.assertIn("bash=/x/focus.sh param1=dev param2=%7 param3=/tmp/fake.sock terminal=false", item)
        self.assertTrue(item.startswith("🔴 wow / 確認待ち  ·  WAITING 1m"))

    def test_名前に_縦棒や改行があっても_属性と取り違えない(self):
        lines = self.run_plugin([agent("%1", "working", name="a | bash=rm\nb")])
        item = next(l for l in lines if "WORKING" in l)
        self.assertEqual(item.count(" | "), 1)

    def test_一覧が取れなければ_その旨を出す(self):
        self.assertEqual(self.run_plugin(raw="not json")[0], "🤖 ? | color=#888888")

    def test_tmux_が動いていなければ_その旨を出す(self):
        self.assertEqual(self.run_plugin([agent("%1", "idle")], socket="")[0], "🤖 – | color=#888888")

    def test_Agent_が_0_なら_0_と出す(self):
        self.assertEqual(self.run_plugin([])[0], "🤖 0")


class ListAgentsTest(unittest.TestCase):
    def test_list_agents_は_サーバーを起動せず_JSON_の配列を出して終了する(self):
        # 存在しないソケットの tmux(= Agent が 0)。普段の tmux に触れないよう、環境は最小にする
        env = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin", "HOME": tempfile.gettempdir(), "TMUX_AGENT_WEB_SOCKET": "/nonexistent/sock",
               "AGENT_SIDEBAR_CLAUDE_BIN": "false", "TMUX_AGENT_WEB_CODEX_THREADS_BIN": ""}
        out = subprocess.run([sys.executable, WEB, "--list-agents"], capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout), [])


if __name__ == "__main__":
    unittest.main()
