"""cockpit の「Daily ダッシュボード表示」(tmux-agent-cockpit view / tmux-agent-cockpit-slot) のテスト。

専用ソケット（tmux -S <一時ソケット>）の別 tmux サーバーだけを使い、本物の tmux-agent-cockpit と slot を動かす。
普段使っている tmux のサーバーには触れない（kill-server も一時ソケットを明示する）。
ソケットのパスは長いと接続できないので、短い /tmp 直下の一時ディレクトリに置く。
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")
COCKPIT = os.path.join(SCRIPTS, "tmux-agent-cockpit")
SLOT = os.path.join(SCRIPTS, "tmux-agent-cockpit-slot")
TIMEOUT_SEC = 8


class CockpitDailyTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cpd.", dir="/tmp")
        self.sock = os.path.join(self.dir, "s")
        self.addCleanup(self.cleanup)
        self.make_daily_fixture()
        env = dict(os.environ)
        env.pop("TMUX", None)
        env.update(
            AGENT_DAILY_DIR=os.path.join(self.dir, "daily"),
            AGENT_DAILY_CLAUDE_PROJECTS=os.path.join(self.dir, "claude"),
            AGENT_DAILY_CODEX_SESSIONS=os.path.join(self.dir, "codex"),
            AGENT_DAILY_TITLE_DIR=os.path.join(self.dir, "titles"),
            AGENT_DAILY_NO_TMUX="1",
        )
        os.makedirs(env["AGENT_DAILY_TITLE_DIR"])
        # サーバーは最初のクライアントの環境を引き継ぐ。slot（ダッシュボードを描く）はこの環境で動く
        subprocess.run(
            ["tmux", "-S", self.sock, "-f", "/dev/null", "new-session", "-d", "-s", "t", "-x", "100", "-y", "30",
             "-n", "cockpit", f"'{SLOT}'"],
            check=True, env=env,
        )
        self.slot = self.tmux("display-message", "-p", "-t", "t:cockpit.0", "#{pane_id}").stdout.strip()
        self.tmux("set-option", "-w", "-t", "t:cockpit", "@agent_cockpit", "1")
        self.tmux("set-option", "-w", "-t", "t:cockpit", "@agent_cockpit_slot", self.slot)
        self.tmux("set-option", "-p", "-t", self.slot, "@agent_cockpit_slot_pane", "1")
        # Agent の代わりの pane（別 window）
        self.tmux("new-window", "-d", "-t", "t:", "-n", "work", "cat")
        self.agent = self.tmux("display-message", "-p", "-t", "t:work.0", "#{pane_id}").stdout.strip()

    def cleanup(self):
        subprocess.run(["tmux", "-S", self.sock, "kill-server"], capture_output=True)  # 一時ソケットのサーバーだけ
        shutil.rmtree(self.dir, ignore_errors=True)

    def make_daily_fixture(self):
        """4 時間前に更新したノートと、10 分前に動いた Claude のセッション 1 つ。"""
        daily = os.path.join(self.dir, "daily")
        os.makedirs(daily)
        note = os.path.join(daily, time.strftime("%Y-%m-%d") + ".md")
        with open(note, "w") as f:
            f.write("## やったこと\n\n- 朝のメモ\n")
        old = time.time() - 4 * 3600
        os.utime(note, (old, old))
        proj = os.path.join(self.dir, "claude", "p")
        os.makedirs(proj)
        session = os.path.join(proj, "s1.jsonl")
        with open(session, "w") as f:
            f.write(json.dumps({"type": "user", "cwd": "/w/myrepo"}) + "\n")
            f.write(json.dumps({"type": "ai-title", "aiTitle": "ダッシュボード検証用の作業"}) + "\n")
        recent = time.time() - 600
        os.utime(session, (recent, recent))

    def tmux(self, *args):
        return subprocess.run(["tmux", "-S", self.sock, *args], capture_output=True, text=True)

    def cockpit(self, *args):
        """tmux-agent-cockpit を、サーバーの中(run-shell。TMUX が設定される)で実行する。"""
        return self.tmux("run-shell", f"'{COCKPIT}' " + " ".join(args))

    def view_option(self):
        return self.tmux("show-options", "-wqv", "-t", "t:cockpit", "@agent_cockpit_view").stdout.strip()

    def shown_option(self):
        return self.tmux("show-options", "-wqv", "-t", "t:cockpit", "@agent_cockpit_shown").stdout.strip()

    def pane_window(self, pane):
        return self.tmux("display-message", "-p", "-t", pane, "#{window_name}").stdout.strip()

    def wait_for(self, pane, text):
        deadline = time.time() + TIMEOUT_SEC
        screen = ""
        while time.time() < deadline:
            screen = self.tmux("capture-pane", "-p", "-t", pane).stdout
            if text in screen:
                return screen
            time.sleep(0.2)
        self.fail(f"{text!r} が {pane} に出ませんでした:\n{screen}")

    def test_view_daily_で_slot_が_ダッシュボードを描く(self):
        self.cockpit("view", "daily")
        self.assertEqual(self.view_option(), "daily")
        screen = self.wait_for(self.slot, "Daily Note")
        self.assertIn("ダッシュボード検証用の作業", screen)
        self.assertIn("myrepo", screen)
        self.assertIn("4h", screen)

    def test_ダッシュボードには_操作のヒントが出る(self):
        self.cockpit("view", "daily")
        screen = self.wait_for(self.slot, "Daily Note")
        self.assertIn("Obsidian", screen)

    def test_view_daily_は_表示中の_Agent_を元の_window_へ戻す(self):
        self.cockpit("show", self.agent)
        self.assertEqual(self.pane_window(self.agent), "cockpit")
        self.assertEqual(self.shown_option(), self.agent)
        self.cockpit("view", "daily")
        self.assertEqual(self.shown_option(), "")
        self.assertEqual(self.pane_window(self.agent), "work")
        self.assertEqual(self.pane_window(self.slot), "cockpit")
        self.wait_for(self.slot, "Daily Note")

    def test_show_で_Agent_を出すと_ダッシュボード表示は解除される(self):
        self.cockpit("view", "daily")
        self.wait_for(self.slot, "Daily Note")
        self.cockpit("show", self.agent)
        self.assertEqual(self.view_option(), "")
        self.assertEqual(self.pane_window(self.agent), "cockpit")

    def test_view_none_で_ダッシュボードを閉じる(self):
        self.cockpit("view", "daily")
        self.wait_for(self.slot, "Daily Note")
        self.cockpit("view", "none")
        self.assertEqual(self.view_option(), "")
        self.wait_for(self.slot, "Agent cockpit")

    def test_ダッシュボードの後の_slot_は_cockpit_を出たら_通常の目印に戻る(self):
        self.cockpit("view", "daily")
        self.wait_for(self.slot, "Daily Note")
        self.cockpit("show", self.agent)  # slot は Agent の元の window へ移る
        screen = self.wait_for(self.slot, "cockpit に表示中")
        self.assertNotIn("Daily Note", screen)


if __name__ == "__main__":
    unittest.main()
