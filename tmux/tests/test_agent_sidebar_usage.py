"""sidebar 下部の USAGE 欄（5h / 1w のレートリミットと、usage credits の今月の支出）のテスト。

専用ソケット（tmux -S <一時ソケット>）の別 tmux サーバーで本物の tmux-agent-sidebar を起動し、
capture-pane で描画を読む。普段使っている tmux のサーバーには触れない（kill-server も一時ソケットを明示する）。
ソケットのパスは長いと接続できない（sun_path の上限）ので、短い /tmp 直下の一時ディレクトリに置く。
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest

SIDEBAR = os.path.join(os.path.dirname(__file__), "..", "scripts", "tmux-agent-sidebar")
FAR_FUTURE = "9999999999"
RENDER_TIMEOUT_SEC = 8


def rate_limits(five_hour=18, seven_day=40, five_resets=FAR_FUTURE, seven_resets=FAR_FUTURE):
    data = {}
    if five_hour is not None:
        data.update(five_hour_pct=five_hour, five_hour_resets=five_resets)
    if seven_day is not None:
        data.update(seven_day_pct=seven_day, seven_day_resets=seven_resets)
    return data


def credits(**fields):
    data = {
        "enabled": True,
        "used": 29.84,
        "limit": 1300,
        "percent": 2.2953846153846156,
        "currency": "USD",
        "fetched_at": int(time.time()),
    }
    data.update(fields)
    return data


class SidebarUsageTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="sbu.", dir="/tmp")
        self.sock = os.path.join(self.dir, "s")
        self.addCleanup(self.cleanup)

    def cleanup(self):
        subprocess.run(["tmux", "-S", self.sock, "kill-server"], capture_output=True)  # 一時ソケットのサーバーだけ
        shutil.rmtree(self.dir, ignore_errors=True)

    def tmux(self, *args):
        return subprocess.run(["tmux", "-S", self.sock, *args], capture_output=True, text=True)

    def render(self, limits=None, cred=None):
        """sidebar を起動して、描画が出そろった画面（文字だけ）を返す。None のファイルは作らない。"""
        rl_file = os.path.join(self.dir, "rate-limits.json")
        cr_file = os.path.join(self.dir, "credits.json")
        for path, data in ((rl_file, limits), (cr_file, cred)):
            if data is not None:
                with open(path, "w") as f:
                    json.dump(data, f)
        env = " ".join(
            [
                "env -u TMUX",
                f"AGENT_SIDEBAR_RATE_LIMITS={rl_file}",
                f"AGENT_SIDEBAR_CREDITS={cr_file}",
                "AGENT_SIDEBAR_CLAUDE_BIN=true",
                f"AGENT_SIDEBAR_ALERT_STATE={self.dir}/none",
                f"AGENT_SIDEBAR_TITLE_CACHE={self.dir}/titles",
                f"AGENT_SIDEBAR_CLAUDE_CACHE={self.dir}/claude-cache",
                f"AGENT_SIDEBAR_SESSIONS_DIR={self.dir}/sessions",
                "bash",
                SIDEBAR,
            ]
        )
        subprocess.run(
            ["tmux", "-S", self.sock, "-f", "/dev/null", "new-session", "-d", "-s", "t", "-x", "60", "-y", "24", "-c", "/tmp"],
            check=True,
        )
        self.tmux("split-window", "-d", "-f", "-h", "-b", "-l", "32", "-t", "t:0.0", env)
        # 最下行の WEB 欄は常に描かれるので、これが出れば 1 回目の描画が済んでいる
        deadline = time.time() + RENDER_TIMEOUT_SEC
        screen = ""
        while time.time() < deadline:
            screen = self.tmux("capture-pane", "-p", "-t", "t:0.0").stdout
            if "WEB" in screen:
                return screen
            time.sleep(0.2)
        self.fail(f"sidebar が描画されませんでした:\n{screen}")

    def test_credits_だけなら_今月の支出と上限と使用率を出す(self):
        screen = self.render(cred=credits())
        self.assertIn("USAGE", screen)
        self.assertRegex(screen, r"💳 \$29\.84 / \$1,300\s+2%")
        self.assertNotIn("5h", screen)

    def test_レートリミットだけなら_5h_と_1w_を出して_credits_は出さない(self):
        screen = self.render(limits=rate_limits())
        self.assertIn("5h", screen)
        self.assertIn("1w", screen)
        self.assertNotIn("💳", screen)

    def test_両方あれば_全部出す(self):
        screen = self.render(limits=rate_limits(), cred=credits())
        self.assertIn("5h", screen)
        self.assertIn("1w", screen)
        self.assertIn("💳 $29.84", screen)

    def test_データが何も無ければ_USAGE_欄を出さない(self):
        screen = self.render()
        self.assertNotIn("USAGE", screen)

    def test_リセット時刻を過ぎた窓は_古い値なので出さない(self):
        # 契約を替えたあと、statusline が書かなくなった古い値が出続けないようにする
        screen = self.render(limits=rate_limits(five_resets="1000000000", seven_resets="1000000000"), cred=credits())
        self.assertNotIn("5h", screen)
        self.assertNotIn("1w", screen)
        self.assertIn("💳 $29.84", screen)

    def test_5h_だけ過ぎていて_1w_は有効なら_1w_だけ出す(self):
        screen = self.render(limits=rate_limits(five_resets="1000000000"))
        self.assertNotIn("5h", screen)
        self.assertIn("1w", screen)

    def test_期限切れの窓しか無ければ_USAGE_欄ごと出さない(self):
        screen = self.render(limits=rate_limits(five_resets="1000000000", seven_resets="1000000000"))
        self.assertNotIn("USAGE", screen)

    def test_上限なしなら_支出だけ出す(self):
        screen = self.render(cred=credits(limit=None, percent=None))
        self.assertIn("💳 $29.84", screen)
        self.assertNotIn("/ $", screen)

    def test_credits_が無効なら_出さない(self):
        screen = self.render(cred=credits(enabled=False, used=None, limit=None, percent=None))
        self.assertNotIn("💳", screen)
        self.assertNotIn("USAGE", screen)

    def test_古い値には_経過時間を添える(self):
        screen = self.render(cred=credits(fetched_at=int(time.time()) - 3 * 3600))
        self.assertRegex(screen, r"💳 \$29\.84.*3h")

    def test_新しい値には_経過時間を出さない(self):
        screen = self.render(cred=credits())
        self.assertIsNone(re.search(r"💳 .*\d+[hm]前", screen))
        self.assertNotRegex(screen, r"💳 [^\n]*\b\d+h\b")

    def test_通貨が_USD_以外なら_通貨コードを付ける(self):
        screen = self.render(cred=credits(currency="JPY", used=1500, limit=100000, percent=1.5))
        self.assertIn("JPY 1,500", screen)

    def test_桁区切りと小数は_金額ごとに整える(self):
        screen = self.render(cred=credits(used=1234.5, limit=5000.5, percent=24.7))
        self.assertIn("$1,234.50 / $5,000.50", screen)

    def test_幅に収まる(self):
        screen = self.render(cred=credits(used=12345.67, limit=100000, percent=12.3))
        for line in screen.splitlines():
            self.assertLessEqual(len(line), 32, line)


class SidebarSurvivalTest(unittest.TestCase):
    """pane が閉じたあとに sidebar が CPU 99% で居座った件の再発防止。tmux は使わない（普段の tmux に触れない）。"""

    # read_key と同じ read の失敗処理(note_read_failure)だけを sidebar から切り出し、同じ形のループを回す
    READ_LOOP = (
        f'eval "$(sed -n \'/^READ_FAIL_MAX=/,/^READ_FAIL_N=/p;/^note_read_failure()/,/^}}/p\' {SIDEBAR})"\n'
        'TICK=1\nwhile :; do IFS= read -rsn1 -t "$TICK" c || note_read_failure; done\n'
    )

    def test_端末が無くて_read_が即失敗し続けても_自分で終了する(self):
        started = time.time()
        try:
            proc = subprocess.run(["bash", "-c", self.READ_LOOP], input=b"", capture_output=True, timeout=5)  # EOF = 端末が切れた状態
        except subprocess.TimeoutExpired:
            self.fail("5 秒たっても終了せず、ビジーループになっている")
        self.assertEqual(proc.returncode, 0)
        self.assertLess(time.time() - started, 3)

    def test_通常の_1_秒タイムアウトでは_終了しない(self):
        # 入力が来ない(stdin が開いたまま)通常の待機。read は 1 秒ごとに失敗するが、終了してはいけない
        with subprocess.Popen(["sleep", "6"], stdout=subprocess.PIPE) as idle:
            with self.assertRaises(subprocess.TimeoutExpired):
                subprocess.run(["bash", "-c", self.READ_LOOP], stdin=idle.stdout, capture_output=True, timeout=4)
            idle.kill()

    def test_本体は関数に包み_main_と_exit_を同じ行に置く(self):
        # 起動中にファイルを書き換えられても暴走しないための形。main と exit が別の行だと、main から戻ったあとに
        # 書き換え後の内容を途中から読んでしまう（実証済み）
        with open(SIDEBAR) as f:
            lines = [line.rstrip("\n") for line in f if line.strip()]
        self.assertEqual(lines[-1], 'main "$@"; exit $?')
        self.assertIn("main() {", lines)


if __name__ == "__main__":
    unittest.main()
