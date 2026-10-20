"""tmux-agent-new（sidebar の n で、リポジトリに新しい pane を作って Agent を起動する）のテスト。
専用ソケットの別 tmux だけを使い、起動コマンドは AGENT_NEW_CMD で echo に差し替える（本物の Claude / Codex は起動しない）。"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "tmux-agent-new")


class AgentNewTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="agn.", dir="/tmp")
        self.sock = os.path.join(self.dir, "s")
        self.addCleanup(self.cleanup)

    def cleanup(self):
        subprocess.run(["tmux", "-S", self.sock, "kill-server"], capture_output=True)  # 一時ソケットのサーバーだけ
        shutil.rmtree(self.dir, ignore_errors=True)

    def tmux(self, *args):
        return subprocess.run(["tmux", "-S", self.sock, *args], capture_output=True, text=True)

    def run_new(self, anchor, *extra):
        env = {**os.environ, "TMUX": f"{self.sock},0,0", "AGENT_NEW_CMD": "echo launched-here"}
        return subprocess.run([SCRIPT, "claude", anchor, self.dir, "--print", *extra], env=env, capture_output=True, text=True)

    def test_分割できないほど小さい_anchor_でも_起動できる(self):
        # 幅 80（< 120 なので上下に分割しようとする）で、縦に詰めて分割の余地を無くす
        subprocess.run(["tmux", "-S", self.sock, "-f", "/dev/null", "new-session", "-d", "-s", "t", "-x", "80", "-y", "9", "-c", "/tmp"], check=True)
        while self.tmux("split-window", "-d", "-v", "-t", "t:0.0").returncode == 0:
            pass
        anchor = self.tmux("list-panes", "-t", "t:0", "-F", "#{pane_id}").stdout.split()[0]
        # 前提: 上下には分割できない
        self.assertNotEqual(self.tmux("split-window", "-d", "-v", "-t", anchor).returncode, 0)
        before = set(self.tmux("list-panes", "-a", "-F", "#{pane_id}").stdout.split())
        proc = self.run_new(anchor)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        new = proc.stdout.strip()
        self.assertTrue(new.startswith("%") and new not in before, proc.stdout)
        deadline = time.time() + 5
        text = ""
        while time.time() < deadline and "launched-here" not in text.replace("echo launched-here", ""):
            time.sleep(0.2)
            text = self.tmux("capture-pane", "-p", "-t", new).stdout
        self.assertIn("launched-here", text.replace("echo launched-here", ""))


if __name__ == "__main__":
    unittest.main()
