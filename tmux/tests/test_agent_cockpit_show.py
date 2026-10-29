"""cockpit の show（右の枠へ Agent を入れる）の動作と、外部コマンドの起動回数のテスト。

環境によっては exec が 1 回 0.3 秒ほどかかるため（セキュリティ製品の検査など）、sidebar の j/k は
show の中で起動する外部コマンドの数に比例して遅くなる。そこで、tmux と dirname の起動回数を PATH 上の
偽物（呼ばれたら記録して本物へ渡す）で数え、増えないことを確かめる。
専用ソケット（tmux -S <一時ソケット>）の別 tmux サーバーだけを使い、普段使っている tmux には触れない。
"""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")
COCKPIT = os.path.join(SCRIPTS, "tmux-agent-cockpit")

# 呼ばれたコマンド名を 1 行ずつ記録して、本物を呼ぶ
SHIM = """#!/bin/bash
echo "$(basename "$0")" >> "$SHIM_LOG"
exec "{real}" "$@"
"""


def which(name):
    return shutil.which(name)


class CockpitShowTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cps.", dir="/tmp")
        self.sock = os.path.join(self.dir, "s")
        self.addCleanup(self.cleanup)
        self.log = os.path.join(self.dir, "calls.log")
        self.make_shims()
        env = dict(os.environ)
        env.pop("TMUX", None)
        subprocess.run(
            ["tmux", "-S", self.sock, "-f", "/dev/null", "new-session", "-d", "-s", "t", "-x", "100", "-y", "30",
             "-n", "cockpit", "cat"],
            check=True, env=env,
        )
        # cockpit window: slot(右の枠の交換用)と、sidebar の代わりの pane
        self.slot = self.pane_id("t:cockpit.0")
        self.sidebar = self.tmux("split-window", "-d", "-h", "-t", self.slot, "-P", "-F", "#{pane_id}", "cat").stdout.strip()
        self.tmux("set-option", "-w", "-t", "t:cockpit", "@agent_cockpit", "1")
        self.tmux("set-option", "-w", "-t", "t:cockpit", "@agent_cockpit_slot", self.slot)
        self.tmux("set-option", "-p", "-t", self.slot, "@agent_cockpit_slot_pane", "1")
        self.tmux("set-option", "-p", "-t", self.sidebar, "@agent_sidebar", "1")
        # Agent の代わりの pane(別 window)
        self.tmux("new-window", "-d", "-t", "t:", "-n", "work1", "cat")
        self.tmux("new-window", "-d", "-t", "t:", "-n", "work2", "cat")
        self.a1 = self.pane_id("t:work1.0")
        self.a2 = self.pane_id("t:work2.0")

    def cleanup(self):
        subprocess.run(["tmux", "-S", self.sock, "kill-server"], capture_output=True)  # 一時ソケットのサーバーだけ
        shutil.rmtree(self.dir, ignore_errors=True)

    def make_shims(self):
        self.shim_dir = os.path.join(self.dir, "shims")
        os.makedirs(self.shim_dir)
        for name in ("tmux", "dirname"):
            path = os.path.join(self.shim_dir, name)
            with open(path, "w") as f:
                f.write(SHIM.format(real=which(name)))
            os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def tmux(self, *args):
        return subprocess.run(["tmux", "-S", self.sock, *args], capture_output=True, text=True)

    def pane_id(self, target):
        return self.tmux("display-message", "-p", "-t", target, "#{pane_id}").stdout.strip()

    def window_of(self, pane):
        return self.tmux("display-message", "-p", "-t", pane, "#{window_name}").stdout.strip()

    def shown(self):
        return self.tmux("show-options", "-wqv", "-t", "t:cockpit", "@agent_cockpit_shown").stdout.strip()

    def show(self, target, with_tmux_pane=True):
        """sidebar と同じく、cockpit の pane の中から(TMUX と TMUX_PANE が設定された状態で)show を呼び、記録を返す。"""
        env = dict(os.environ)
        env["TMUX"] = f"{self.sock},0,0"
        env["PATH"] = self.shim_dir + os.pathsep + env["PATH"]
        env["SHIM_LOG"] = self.log
        if with_tmux_pane:
            env["TMUX_PANE"] = self.sidebar
        else:
            env.pop("TMUX_PANE", None)
        if os.path.exists(self.log):
            os.remove(self.log)
        result = subprocess.run([COCKPIT, "show", target], env=env, capture_output=True, text=True)
        calls = []
        if os.path.exists(self.log):
            with open(self.log) as f:
                calls = [line.strip() for line in f if line.strip()]
        return result, calls

    def test_show_で_Agent_が右の枠へ入り_slot_が元の位置へ移る(self):
        result, _ = self.show(self.a1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.window_of(self.a1), "cockpit")
        self.assertEqual(self.window_of(self.slot), "work1")
        self.assertEqual(self.shown(), self.a1)

    def test_別の_Agent_を_show_すると_前の_Agent_は元の_window_へ戻る(self):
        self.show(self.a1)
        result, _ = self.show(self.a2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.window_of(self.a1), "work1")
        self.assertEqual(self.window_of(self.a2), "cockpit")
        self.assertEqual(self.shown(), self.a2)

    def test_すでに表示中の_Agent_を_show_しても何も変わらない(self):
        self.show(self.a1)
        result, _ = self.show(self.a1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.window_of(self.a1), "cockpit")
        self.assertEqual(self.shown(), self.a1)

    def test_TMUX_PANE_が無くても_show_できる(self):
        result, _ = self.show(self.a1, with_tmux_pane=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.window_of(self.a1), "cockpit")

    def test_show_は_dirname_を起動しない(self):
        _, calls = self.show(self.a1)
        self.assertEqual(calls.count("dirname"), 0, calls)

    def test_高速パスの_tmux_呼び出しは_2_回だけ(self):
        # 状態の取得(list-panes -a)と、入れ替えの複合コマンドの 2 回。自分の window を調べる display-message は要らない
        self.show(self.a1)  # 1 回目は何も表示していない状態から。2 回目以降の j/k を測る
        _, calls = self.show(self.a2)
        self.assertEqual(calls.count("tmux"), 2, calls)


if __name__ == "__main__":
    unittest.main()
