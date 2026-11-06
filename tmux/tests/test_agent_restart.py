"""tmux-agent-restart（sidebar の R で再起動、f で複製）のテスト。Claude Code と Codex。
専用ソケットの別 tmux だけを使う。Agent は `exec -a codex sleep` の偽のプロセス、検出（claude agents --json / tmux-agent-web --list-agents）は
偽のコマンド、再開のコマンド名は echo に差し替える（本物の Claude / Codex は起動しない）。"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "tmux-agent-restart")
THREAD = "019e1111-2222-7333-8444-555566667777"
SESSION = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class RestartTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="rst.", dir="/tmp")
        self.sock = os.path.join(self.dir, "s")
        self.addCleanup(self.cleanup)
        subprocess.run(["tmux", "-S", self.sock, "-f", "/dev/null", "new-session", "-d", "-s", "t", "-x", "200", "-y", "50", "-c", self.dir,
                        "bash --norc --noprofile"], check=True, env={**os.environ, "PS1": "$ "})
        self.pane = self.tmux("display-message", "-p", "-t", "t:0", "#{pane_id}").stdout.strip()
        self.pane_pid = int(self.tmux("display-message", "-p", "-t", self.pane, "#{pane_pid}").stdout.strip())

    def cleanup(self):
        subprocess.run(["tmux", "-S", self.sock, "kill-server"], capture_output=True)  # 一時ソケットのサーバーだけ
        shutil.rmtree(self.dir, ignore_errors=True)

    def tmux(self, *args):
        return subprocess.run(["tmux", "-S", self.sock, *args], capture_output=True, text=True)

    def start_agent(self, argv0):
        """pane のシェルの子として、argv0 を名乗る偽の Agent(sleep)を動かす。その pid を返す。"""
        self.tmux("send-keys", "-t", self.pane, "-l", f"bash -c 'exec -a \"{argv0}\" sleep 600'")
        self.tmux("send-keys", "-t", self.pane, "Enter")
        deadline = time.time() + 5
        while time.time() < deadline:
            for line in subprocess.run(["ps", "-axo", "pid=,ppid=,args="], capture_output=True, text=True).stdout.splitlines():
                parts = line.split(None, 2)
                if len(parts) == 3 and parts[1] == str(self.pane_pid) and parts[2].startswith(argv0):
                    return int(parts[0])
            time.sleep(0.1)
        self.fail("偽の Agent が起動しません")

    def script(self, name, body):
        path = os.path.join(self.dir, name)
        with open(path, "w") as f:
            f.write("#!/bin/sh\n" + body)
        os.chmod(path, 0o755)
        return path

    def run_restart(self, pid, thread=THREAD, kind="Codex", claude=None, extra=(), env=None):
        agents = [{"pane": self.pane, "type": kind, "pid": pid, "threadId": thread, "cwd": self.dir}] if kind else []
        listing = self.script("list", f"cat <<'EOF'\n{json.dumps(agents)}\nEOF\n")
        claude_json = json.dumps(claude or [])
        fake_claude = self.script("claude", f"cat <<'EOF'\n{claude_json}\nEOF\n")
        e = {**os.environ, "TMUX": f"{self.sock},0,0", "AGENT_RESTART_LIST_BIN": listing, "AGENT_SIDEBAR_CLAUDE_BIN": fake_claude,
             "AGENT_RESTART_CODEX_CMD": "echo FAKECODEX", "AGENT_RESTART_CLAUDE_CMD": "echo FAKECLAUDE"}
        e.update(env or {})
        return subprocess.run([SCRIPT, self.pane, *extra], env=e, capture_output=True, text=True, timeout=60)

    def screen(self, pane=None):
        return self.tmux("capture-pane", "-p", "-t", pane or self.pane).stdout

    def wait_line(self, text, pane=None):
        """text と一致する行(入力したコマンド行ではなく、echo の出力の行)が出るまで待つ。"""
        deadline = time.time() + 8
        while time.time() < deadline:
            if any(l.strip() == text for l in self.screen(pane).splitlines()):
                return True
            time.sleep(0.2)
        return False

    def alive(self, pid):
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    # --- Codex の再起動 ---

    def test_codex_終了して_同じ_pane_で_resume_つきに入り直す(self):
        pid = self.start_agent("codex")
        proc = self.run_restart(pid)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.alive(pid))
        self.assertTrue(self.wait_line(f"FAKECODEX resume {THREAD}"), self.screen())

    def test_codex_許可リストの引数だけを引き継ぐ(self):
        pid = self.start_agent("codex --model gpt-5.5 --search --dangerously-bypass-approvals-and-sandbox -c model_reasoning_effort=high --unknown-flag")
        self.run_restart(pid)
        self.assertTrue(self.wait_line(
            f"FAKECODEX resume --model gpt-5.5 --search --dangerously-bypass-approvals-and-sandbox -c model_reasoning_effort=high {THREAD}"), self.screen())

    def test_codex_安全でない値の引数は引き継がない(self):
        pid = self.start_agent("codex --model a;b")
        self.run_restart(pid)
        self.assertTrue(self.wait_line(f"FAKECODEX resume {THREAD}"), self.screen())

    def test_codex_元から_resume_で起動していても_サブコマンドとセッションIDを重ねない(self):
        pid = self.start_agent(f"codex resume {THREAD} --model gpt-5.5")
        self.run_restart(pid, thread="019e9999-2222-7333-8444-555566667777")
        self.assertTrue(self.wait_line("FAKECODEX resume --model gpt-5.5 019e9999-2222-7333-8444-555566667777"), self.screen())

    def test_codex_スレッドが決まらなければ_何もしない(self):
        pid = self.start_agent("codex")
        proc = self.run_restart(pid, thread="")
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(self.alive(pid), "スレッドを特定できないのに終了させてしまった")
        self.assertNotIn("FAKECODEX", self.screen())

    def test_codex_も_claude_も居なければ_何もしない(self):
        pid = self.start_agent("sleep-like")
        proc = self.run_restart(pid, kind=None)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(self.alive(pid))

    def test_codex_シェルを介さずに起動された_pane_は_終了しない(self):
        # pane の直下(pane_pid)が Agent のとき
        self.assertTrue(self.alive(self.pane_pid))
        proc = self.run_restart(self.pane_pid)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(self.alive(self.pane_pid))

    # --- Codex の複製 ---

    def test_codex_複製は_元を止めず_新しい_pane_で_fork_を実行する(self):
        pid = self.start_agent("codex --model gpt-5.5")
        before = set(self.tmux("list-panes", "-a", "-F", "#{pane_id}").stdout.split())
        proc = self.run_restart(pid, extra=("--fork", "--focus"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.alive(pid), "複製で元の Agent を止めてしまった")
        new = (set(self.tmux("list-panes", "-a", "-F", "#{pane_id}").stdout.split()) - before).pop()
        self.assertTrue(self.wait_line(f"FAKECODEX fork --model gpt-5.5 {THREAD}", new), self.screen(new))

    # --- Claude(これまでの動きが変わっていないこと) ---

    def test_claude_終了して_resume_つきに入り直す(self):
        pid = self.start_agent("claude --model opus")
        claude = [{"pid": pid, "sessionId": SESSION, "cwd": self.dir}]
        proc = self.run_restart(pid, kind=None, claude=claude)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(self.alive(pid))
        self.assertTrue(self.wait_line(f"FAKECLAUDE --model opus --resume {SESSION}"), self.screen())

    def test_claude_複製は_fork_session_つきで新しい_pane_を作る(self):
        pid = self.start_agent("claude")
        claude = [{"pid": pid, "sessionId": SESSION, "cwd": self.dir}]
        before = set(self.tmux("list-panes", "-a", "-F", "#{pane_id}").stdout.split())
        self.run_restart(pid, kind=None, claude=claude, extra=("--fork", "--focus"))
        new = (set(self.tmux("list-panes", "-a", "-F", "#{pane_id}").stdout.split()) - before).pop()
        self.assertTrue(self.wait_line(f"FAKECLAUDE --resume {SESSION} --fork-session", new), self.screen(new))
        self.assertTrue(self.alive(pid))


if __name__ == "__main__":
    unittest.main()
