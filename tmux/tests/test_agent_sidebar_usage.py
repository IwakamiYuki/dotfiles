"""sidebar 下部の USAGE 欄（5h / 1w のレートリミットと、usage credits の今月の支出）のテスト。

専用ソケット（tmux -S <一時ソケット>）の別 tmux サーバーで本物の tmux-agent-sidebar を起動し、
capture-pane で描画を読む。普段使っている tmux のサーバーには触れない（kill-server も一時ソケットを明示する）。
ソケットのパスは長いと接続できない（sun_path の上限）ので、短い /tmp 直下の一時ディレクトリに置く。
"""
import fcntl
import json
import os
import pty
import re
import select
import shutil
import struct
import subprocess
import tempfile
import termios
import threading
import time
import unicodedata
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


def codex_usage(**fields):
    data = {
        "enabled": True,
        "used": 2533.19,
        "limit": 20000.0,
        "percent": 12.66,
        "unit": "credits",
        "resets_at": 1793491200,
        "fetched_at": int(time.time()),
    }
    data.update(fields)
    return data


def display_width(text):
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


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

    def render(self, limits=None, cred=None, codex=None, codex_threads=None, tasks_dir=None, today=None, colors=False, daily_dir=None, open_cmd=None, obsidian_config=None, extra_env=None, cockpit=False, windows=None, preset=None, tasks_today="2026-10-17"):
        """sidebar を起動して、描画が出そろった画面を返す。None のファイルは作らない。
        today: 「今日」の日付(YYYY-MM-DD)。着地予想の色が日付で変わるので、固定して確認する。
        colors: True なら色の制御文字つき(capture-pane -e)で返す。
        daily_dir: Daily Note のディレクトリ(AGENT_SIDEBAR_DAILY_DIR)。None なら未設定。
        open_cmd: o キーで呼ぶコマンド(AGENT_SIDEBAR_OPEN_CMD)。実際の open は呼ばない。
        obsidian_config: Obsidian の obsidian.json のパス(AGENT_DAILY_OBSIDIAN_CONFIG)。None なら存在しないパスにして、本物の設定を読まない。
        extra_env: sidebar に足す環境変数({名前: 値})。
        cockpit: True なら、描画のあとで window を cockpit にして(@agent_cockpit=1)、cockpit の欄(d のヒント)が出るまで待つ。
          "early" なら、sidebar を起動する前から cockpit にする(本物の C-t B と同じ順序。起動時の復元を試すとき)。
        windows: 別 window を作るディレクトリのリスト。それぞれ空きシェルの pane になり、sidebar の選択肢(カード)が増える。pane_id は self.extra_panes に入る。
        preset: sidebar を起動する前に、tmux のグローバル option に入れる値({名前: 値。callable なら self.extra_panes を渡して求める})。"""
        rl_file = os.path.join(self.dir, "rate-limits.json")
        cr_file = os.path.join(self.dir, "credits.json")
        cx_file = os.path.join(self.dir, "codex-usage.json")
        self.threads_file = os.path.join(self.dir, "codex-threads.txt")
        if codex_threads is not None:
            with open(self.threads_file, "w") as f:
                f.write("".join(line + "\n" for line in codex_threads))
        for path, data in ((rl_file, limits), (cr_file, cred), (cx_file, codex)):
            if data is not None:
                with open(path, "w") as f:
                    json.dump(data, f)
        env = " ".join(
            [
                "env",  # TMUX は外さない: pane に設定される専用ソケットの値を引き継ぎ、sidebar が普段の tmux ではなく一時サーバーを見るようにする
                f"AGENT_SIDEBAR_RATE_LIMITS={rl_file}",
                f"AGENT_SIDEBAR_CREDITS={cr_file}",
                f"AGENT_SIDEBAR_CODEX_USAGE={cx_file}",
                "AGENT_SIDEBAR_CODEX_USAGE_BIN=true",  # 本物の codex は起動しない
                f"AGENT_TASKS_DIR={tasks_dir}" if tasks_dir else "AGENT_TASKS_DIR=",  # 未指定なら、本物の vault を読まない(下の AGENT_DAILY_OBSIDIAN_CONFIG が存在しないパスのため)
                "AGENT_TASKS_NO_TMUX=1",
                f"AGENT_TASKS_TODAY={tasks_today}",
                f"AGENT_SIDEBAR_CODEX_THREADS_CACHE={self.threads_file}",
                "AGENT_SIDEBAR_CODEX_THREADS_BIN=true",  # 本物のデーモンへは問い合わせない
                "AGENT_SIDEBAR_CLAUDE_BIN=true",
                f"AGENT_SIDEBAR_ALERT_STATE={self.dir}/none",
                f"AGENT_SIDEBAR_BELL_STATE={self.dir}/bell-state",  # 普段の sidebar と記録を共有しない
                "AGENT_SIDEBAR_SOUND_CMD=true",  # 本物の音は鳴らさない(音のテストだけが extra_env で偽物に替える)
                f"AGENT_SIDEBAR_TITLE_CACHE={self.dir}/titles",
                f"AGENT_SIDEBAR_CLAUDE_CACHE={self.dir}/claude-cache",
                f"AGENT_SIDEBAR_SESSIONS_DIR={self.dir}/sessions",
                f"AGENT_SIDEBAR_TODAY={today}" if today else "AGENT_SIDEBAR_TODAY=",
                f"AGENT_SIDEBAR_DAILY_DIR={daily_dir}" if daily_dir else "AGENT_SIDEBAR_DAILY_DIR=",
                f"AGENT_SIDEBAR_OPEN_CMD={open_cmd}" if open_cmd else "AGENT_SIDEBAR_OPEN_CMD=true",
                f"AGENT_DAILY_OBSIDIAN_CONFIG={obsidian_config or self.dir + '/no-obsidian.json'}",
                f"TMUX_AGENT_WEB_STATE={self.dir}/no-web-state.json",  # 普段の WEB サーバーの状態を読まない
                f"AGENT_WEB_HOME_FILE={self.dir}/home-networks",  # 本物の自宅の登録を読まない(自宅でテストを回しても、本物のサーバーを起動しない)
                "AGENT_SIDEBAR_WEB_BIN=true",  # auto の判定・モードの切り替えは呼ばない(呼ぶテストだけが、偽物のコマンドに替える)
                "AGENT_SIDEBAR_DAILY_BLINK=off",  # 点滅は、点滅のテストだけが extra_env で有効にする
                "bash",
                SIDEBAR,
            ]
        )
        # 1 つのテストで続けて描画できるよう、前の一時サーバーを止める（一時ソケットを明示。普段の tmux には触れない）
        subprocess.run(["tmux", "-S", self.sock, "kill-server"], capture_output=True)
        subprocess.run(
            ["tmux", "-S", self.sock, "-f", "/dev/null", "new-session", "-d", "-s", "t", "-x", "60", "-y", "24", "-c", "/tmp"],
            check=True,
        )
        self.extra_panes = []
        for d in windows or []:
            os.makedirs(d, exist_ok=True)
            self.tmux("new-window", "-d", "-t", "t:", "-c", d)
            self.extra_panes.append(self.tmux("list-panes", "-t", f"t:{len(self.extra_panes) + 1}", "-F", "#{pane_id}").stdout.split()[0])
        for name, value in (preset or {}).items():
            self.tmux("set-option", "-g", name, value(self.extra_panes) if callable(value) else value)
        if cockpit == "early":
            # 本物の tmux-agent-cockpit open と同じ: cockpit window の中身は slot だけ(元のシェルは slot に置き換わる)
            slot_cmd = os.path.join(os.path.dirname(SIDEBAR), "tmux-agent-cockpit-slot")
            self.tmux("respawn-pane", "-k", "-t", "t:0.0", slot_cmd)
            slot = self.tmux("list-panes", "-t", "t:0", "-F", "#{pane_id}").stdout.split()[0]
            self.tmux("set-option", "-p", "-t", slot, "@agent_cockpit_slot_pane", "1")
            self.tmux("set-option", "-w", "-t", "t:0", "@agent_cockpit_slot", slot)
            self.tmux("set-option", "-w", "-t", "t:0", "@agent_cockpit", "1")
        # sidebar が呼ぶ tmux-agent-daily が、本物の ~/.claude や ~/.codex を読まないようにする
        extra = {"AGENT_DAILY_CLAUDE_PROJECTS": self.dir + "/none-claude", "AGENT_DAILY_CODEX_SESSIONS": self.dir + "/none-codex"}
        extra.update(extra_env or {})
        env = env.replace("bash " + SIDEBAR, " ".join(f"{k}={v}" for k, v in extra.items()) + " bash " + SIDEBAR)
        self.tmux("split-window", "-d", "-f", "-h", "-b", "-l", "32", "-t", "t:0.0", env)
        # 最下行の WEB 欄は常に描かれるので、これが出れば 1 回目の描画が済んでいる
        deadline = time.time() + RENDER_TIMEOUT_SEC
        screen = ""
        while time.time() < deadline:
            flags = ["-e", "-p"] if colors else ["-p"]
            screen = self.tmux("capture-pane", *flags, "-t", "t:0.0").stdout
            if "WEB" in screen:
                if cockpit == "early":
                    # ダッシュボードに復元された場合は d view ではなく d back になる
                    return self.wait_screen(lambda scr: any(h in self.daily_row(scr) for h in ("d view", "d back")), flags)
                if cockpit:
                    return self.become_cockpit(flags)
                return screen
            time.sleep(0.2)
        self.fail(f"sidebar が描画されませんでした:\n{screen}")

    def become_cockpit(self, flags):
        """window を cockpit にして、sidebar が気づく(収集の周期。最大 2 秒)まで待つ。気づくと Daily 欄に d のヒントが出る。"""
        self.tmux("set-option", "-w", "-t", "t:0", "@agent_cockpit", "1")
        return self.wait_screen(lambda scr: "d view" in self.daily_row(scr), flags)

    def wait_screen(self, predicate, flags=("-p",)):
        deadline = time.time() + RENDER_TIMEOUT_SEC
        screen = ""
        while time.time() < deadline:
            screen = self.tmux("capture-pane", *flags, "-t", "t:0.0").stdout
            if predicate(screen):
                return screen
            time.sleep(0.2)
        self.fail(f"期待した画面になりませんでした:\n{screen}")

    def press(self, key):
        self.tmux("send-keys", "-t", "t:0.0", key)

    def view_option(self):
        return self.tmux("show-options", "-wqv", "-t", "t:0", "@agent_cockpit_view").stdout.strip()

    def wait_view(self, expected):
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while time.time() < deadline:
            if self.view_option() == expected:
                return
            time.sleep(0.2)
        self.fail(f"@agent_cockpit_view が {expected!r} になりませんでした(いま {self.view_option()!r})")

    def daily_work(self, title="ダッシュボード用の作業", cwd="/w/myrepo"):
        """今日のノートが 4 時間前の更新で、10 分前に動いた Claude のセッションが 1 つある状態を作る。extra_env を返す。"""
        daily = self.daily_note(4 * 3600)
        proj = os.path.join(self.dir, "claude", "p")
        os.makedirs(proj, exist_ok=True)
        path = os.path.join(proj, "s1.jsonl")
        with open(path, "w") as f:
            f.write(json.dumps({"type": "user", "cwd": cwd}) + "\n")
            f.write(json.dumps({"type": "ai-title", "aiTitle": title}) + "\n")
        os.utime(path, (time.time() - 600, time.time() - 600))
        titles = os.path.join(self.dir, "titles-dir")
        os.makedirs(titles, exist_ok=True)
        return {"AGENT_SIDEBAR_DAILY_DIR": daily, "AGENT_DAILY_CLAUDE_PROJECTS": os.path.join(self.dir, "claude"),
                "AGENT_DAILY_TITLE_DIR": titles}

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
        # 行のラベル(行頭の 5h)だけを見る。1w の残り時間("94998d15h" など)が、時刻によって "5h" で終わるため、部分一致は不安定
        self.assertNotRegex(screen, r"(?m)^ 5h ")
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
            self.assertLessEqual(display_width(line), 32, line)


    # --- 使った額を、身近なものの絵文字に置き換えて並べる行（ドル換算のはしご） ---

    def icon_row(self, screen):
        """💳 の行の次の行（絵文字を並べる行）の中身を返す。"""
        lines = screen.splitlines()
        for i, line in enumerate(lines):
            if "💳" in line:
                return lines[i + 1].strip()
        self.fail(f"💳 の行がありません:\n{screen}")

    def test_ラーメン1杯とジュース2本(self):
        screen = self.render(cred=credits(used=9.67))
        self.assertEqual(self.icon_row(screen), "🍜🧃🧃")

    def test_1つ下の単位が4つ並んでも_まだ繰り上がらない(self):
        screen = self.render(cred=credits(used=32.43))
        self.assertEqual(self.icon_row(screen), "🍜🍜🍜🍜🧃🧃🧃🧃")

    def test_33ドルで_飲み会に繰り上がる(self):
        screen = self.render(cred=credits(used=33))
        self.assertEqual(self.icon_row(screen), "🍻")

    def test_大きい単位から順に並べる(self):
        screen = self.render(cred=credits(used=150))
        self.assertEqual(self.icon_row(screen), "🚄🍻🍜🍜🧃🧃🧃")

    def test_200ドルは新幹線2本(self):
        screen = self.render(cred=credits(used=200))
        self.assertEqual(self.icon_row(screen), "🚄🚄")

    def test_1000ドルは_iPhone_1台(self):
        screen = self.render(cred=credits(used=1000, percent=76.9))
        self.assertEqual(self.icon_row(screen), "📱")

    def test_上限いっぱいでも収まる(self):
        screen = self.render(cred=credits(used=1300, percent=100))
        self.assertEqual(self.icon_row(screen), "📱🚄🚄🚄")

    def test_1ドル未満なら_絵文字の行を出さない(self):
        screen = self.render(cred=credits(used=0.5, percent=0.04))
        self.assertIn("💳 $0.50", screen)
        for icon in "🧃🍜🍻🚄🎮📱":
            self.assertNotIn(icon, screen)

    def test_ドル以外の通貨では_絵文字の行を出さない(self):
        screen = self.render(cred=credits(currency="JPY", used=1500, limit=100000, percent=1.5))
        for icon in "🧃🍜🍻🚄🎮📱":
            self.assertNotIn(icon, screen)

    def test_絵文字は幅に収まる個数で打ち切る(self):
        # 幅 32 では 13 個まで。大きい単位を優先して見せる
        screen = self.render(cred=credits(used=100000, limit=None, percent=None))
        row = self.icon_row(screen)
        self.assertEqual(row, "📱" * 13)
        for line in screen.splitlines():
            self.assertLessEqual(display_width(line), 32, line)

    def test_絵文字の行を足しても_WEB_欄は最下行に残る(self):
        screen = self.render(limits=rate_limits(), cred=credits(used=150))
        lines = [l for l in screen.splitlines() if l.strip()]
        self.assertIn("WEB", lines[-1])
        # 絵文字の行は、USAGE 区画の最後(TOOLS の見出しの直前)
        tools = next(i for i, l in enumerate(lines) if "TOOLS" in l)
        self.assertIn("🚄", lines[tools - 1])

    def test_credits_が無効なら_絵文字も出さない(self):
        screen = self.render(cred=credits(enabled=False, used=None, limit=None, percent=None))
        for icon in "🧃🍜🍻🚄🎮📱":
            self.assertNotIn(icon, screen)


    # --- 色: 今月の着地予想（営業日ベース）が上限を超えそうか ---
    # 2026-10-13(火) は、10 月の営業日 22 日のうち 9 日目まで経過（祝日は考慮しない）。着地予想 = 使用額 × 22 / 9

    GREEN, YELLOW, RED = "108", "220", "196"

    def amount_color(self, screen):
        """💳 の行の金額につく色(38;5;N の N)を返す。"""
        m = re.search(r"💳 [^\n]*?\x1b\[38;5;(\d+)m\$", screen)
        self.assertIsNotNone(m, f"色つきの 💳 行がありません:\n{screen!r}")
        return m.group(1)

    def color_for(self, today, **cred_fields):
        screen = self.render(cred=credits(**cred_fields), today=today, colors=True)
        return self.amount_color(screen)

    def test_着地予想が上限の7割以下なら緑(self):
        # 300 → 着地 733 / 1300 = 56%
        self.assertEqual(self.color_for("2026-10-13", used=300, percent=23.1), self.GREEN)

    def test_着地予想が上限の7割を超えたら黄(self):
        # 500 → 着地 1222 / 1300 = 94%
        self.assertEqual(self.color_for("2026-10-13", used=500, percent=38.5), self.YELLOW)

    def test_着地予想が上限を超えそうなら赤(self):
        # 600 → 着地 1466 / 1300 = 113%
        self.assertEqual(self.color_for("2026-10-13", used=600, percent=46.2), self.RED)

    def test_現在の使用率が低くても_ペースが速ければ赤(self):
        # 使用率は 46% で、絶対値の段階では黄止まり。月の 9/22 しか経っていないので着地は上限超え
        self.assertEqual(self.color_for("2026-10-13", used=600, percent=46.2), self.RED)

    def test_土日は_直前の金曜までの営業日で数える(self):
        # 2026-10-17(土): 営業日は 12 日目まで経過。600 → 着地 1100 / 1300 = 85%
        self.assertEqual(self.color_for("2026-10-17", used=600, percent=46.2), self.YELLOW)

    def test_30日の月でも営業日を数える(self):
        # 2026-09-15(火): 9 月の営業日 22 日のうち 11 日目まで。700 → 着地 1400 / 1300 = 108%
        self.assertEqual(self.color_for("2026-09-15", used=700, percent=53.8), self.RED)
        self.assertEqual(self.color_for("2026-09-15", used=400, percent=30.8), self.GREEN)

    def test_うるう年の2月は29日で数える(self):
        # 2024-02-15(木): 2 月の営業日 21 日のうち 11 日目まで。600 → 着地 1145 / 1300 = 88%（20 日と数えると別の値）
        self.assertEqual(self.color_for("2024-02-15", used=600, percent=46.2), self.YELLOW)
        self.assertEqual(self.color_for("2024-02-15", used=700, percent=53.8), self.RED)

    def test_月初の営業日がまだ無い日は_現在の使用率の色に戻る(self):
        # 2026-08-01(土): 営業日の経過が 0 日。使用率 46% の段階の色(黄)を使い、0 で割らない
        self.assertEqual(self.color_for("2026-08-01", used=600, percent=46.2), self.YELLOW)

    def test_上限なしなら_予想できないので_現在の使用率の色(self):
        self.assertEqual(self.color_for("2026-10-13", used=600, limit=None, percent=None), "214")

    def test_取得が止まって古い値なら_予想の色を使わない(self):
        # 3 時間前の値。予想なら赤(113%)だが、古い値で赤は出さず、使用率 46% の段階(黄)にする
        color = self.color_for("2026-10-13", used=600, percent=46.2, fetched_at=int(time.time()) - 3 * 3600)
        self.assertEqual(color, self.YELLOW)


    # ---- Daily 欄: 今日の Daily Note の最終更新からの経過時間と、o で Obsidian を開く操作 ----

    def daily_note(self, age_sec, days_ago=0):
        """今日(days_ago=1 なら昨日)の Daily Note を、age_sec 秒前に更新されたことにして作る。ディレクトリを返す。"""
        d = os.path.join(self.dir, "daily")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, time.strftime("%Y-%m-%d", time.localtime(time.time() - days_ago * 86400)) + ".md")
        with open(path, "w") as f:
            f.write("## やったこと\n")
        mtime = time.time() - age_sec
        os.utime(path, (mtime, mtime))
        return d

    def daily_row(self, screen):
        return next((l for l in screen.splitlines() if "Daily" in l), "")

    def test_daily_ディレクトリが未設定でも_開く操作だけの行を出す(self):
        row = self.daily_row(self.render())
        self.assertIn("📝 Daily", row)
        self.assertIn("o open", row)

    def test_daily_最終更新からの経過時間を出す(self):
        row = self.daily_row(self.render(daily_dir=self.daily_note(4 * 3600 + 30)))
        self.assertRegex(row, r"📝 Daily 4h00m\s+o open")

    def test_daily_1時間未満は分だけ出す(self):
        row = self.daily_row(self.render(daily_dir=self.daily_note(35 * 60 + 10)))
        self.assertRegex(row, r"📝 Daily 35m\s+o open")

    def test_daily_今日のノートが無ければ_未作成と出す(self):
        d = os.path.join(self.dir, "empty-daily")
        os.makedirs(d)
        self.assertIn("未作成", self.daily_row(self.render(daily_dir=d)))

    def test_daily_経過時間の色は_2時間と3時間で変わる(self):
        green, yellow, red = "38;5;108m", "38;5;220m", "38;5;196m"
        for age, color in ((30 * 60, green), (2 * 3600 + 600, yellow), (3 * 3600 + 600, red)):
            row = self.daily_row(self.render(daily_dir=self.daily_note(age), colors=True))
            self.assertIn(color, row, f"{age} 秒前: {row!r}")

    def test_daily_欄を足しても_WEB_欄は最下行で_幅にも収まる(self):
        screen = self.render(limits=rate_limits(), cred=credits(), daily_dir=self.daily_note(600))
        lines = [l for l in screen.splitlines() if l.strip()]
        self.assertIn("WEB", lines[-1])
        for line in screen.splitlines():
            self.assertLessEqual(display_width(line), 32, line)

    def test_daily_ディレクトリ未設定なら_Obsidian_の設定から求める(self):
        # vault/.obsidian/daily-notes.json の folder を、Daily Note の置き場にする(プロジェクトが変わっても設定に追従する)
        vault = os.path.join(self.dir, "vault")
        os.makedirs(os.path.join(vault, ".obsidian"))
        with open(os.path.join(vault, ".obsidian", "daily-notes.json"), "w") as f:
            json.dump({"folder": "daily/proj"}, f)
        note_dir = os.path.join(vault, "daily", "proj")
        os.makedirs(note_dir)
        path = os.path.join(note_dir, time.strftime("%Y-%m-%d") + ".md")
        with open(path, "w") as f:
            f.write("x")
        mtime = time.time() - 4 * 3600 - 30
        os.utime(path, (mtime, mtime))
        cfg = os.path.join(self.dir, "obsidian.json")
        with open(cfg, "w") as f:
            json.dump({"vaults": {"a": {"path": vault, "open": True}}}, f)
        self.assertRegex(self.daily_row(self.render(obsidian_config=cfg)), r"📝 Daily 4h00m\s+o open")

    def test_daily_ディレクトリを明示すれば_Obsidian_の設定より優先する(self):
        d = self.daily_note(35 * 60 + 10)
        cfg = os.path.join(self.dir, "obsidian.json")
        with open(cfg, "w") as f:
            json.dump({"vaults": {"a": {"path": "/nonexistent", "open": True}}}, f)
        self.assertRegex(self.daily_row(self.render(daily_dir=d, obsidian_config=cfg)), r"📝 Daily 35m")

    # ---- Daily ダッシュボード(cockpit: d で右の枠に出す / c で作業の一覧をコピー / 通常: d でポップアップ) ----

    def clip_cmd(self):
        """コピー先を、ファイルへ書く偽のコマンドにする。(コマンドのパス, 書き込み先)"""
        out = os.path.join(self.dir, "clip.txt")
        fake = os.path.join(self.dir, "fake-clip")
        with open(fake, "w") as f:
            f.write(f"#!/bin/sh\ncat > {out}\n")
        os.chmod(fake, 0o755)
        return fake, out

    def wait_file(self, path):
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while time.time() < deadline and not os.path.exists(path):
            time.sleep(0.2)
        self.assertTrue(os.path.exists(path), f"{path} が作られませんでした")
        with open(path) as f:
            return f.read()

    def test_dashboard_cockpit_では_d_のヒントを出し_通常の_sidebar_では出さない(self):
        self.assertNotIn("d view", self.daily_row(self.render(daily_dir=self.daily_note(600))))
        screen = self.render(daily_dir=self.daily_note(600), cockpit=True)
        self.assertRegex(self.daily_row(screen), r"o open\s+d view")

    def test_dashboard_d_で_右の枠に_Daily_を出し_もう一度押すと戻す(self):
        self.render(daily_dir=self.daily_note(600), cockpit=True)
        self.press("d")
        self.wait_view("daily")
        screen = self.wait_screen(lambda scr: "d back" in self.daily_row(scr))
        self.assertNotIn("d view", self.daily_row(screen))
        self.press("d")
        self.wait_view("")
        self.wait_screen(lambda scr: "d view" in self.daily_row(scr))

    def test_dashboard_表示中の_Daily_欄は_橙のタブで示す(self):
        self.render(daily_dir=self.daily_note(600), cockpit=True)
        self.press("d")
        self.wait_screen(lambda scr: "d back" in self.daily_row(scr))
        # 色つきの画面は制御文字で文字列が分断されるので、表示を確かめたあとで、色だけを見る
        colored = self.tmux("capture-pane", "-e", "-p", "-t", "t:0.0").stdout
        self.assertIn("48;5;130m", self.daily_row(colored))

    def test_dashboard_j_で_Agent_の選択に戻ると_Daily_表示は解除される(self):
        self.render(daily_dir=self.daily_note(600), cockpit=True)
        self.press("d")
        self.wait_view("daily")
        self.press("j")
        self.wait_view("")

    def test_dashboard_表示中の_Enter_は_Obsidian_を開く(self):
        log = os.path.join(self.dir, "open.log")
        fake = os.path.join(self.dir, "fake-open")
        with open(fake, "w") as f:
            f.write(f'#!/bin/sh\necho "$@" > {log}\n')
        os.chmod(fake, 0o755)
        self.render(daily_dir=self.daily_note(600), open_cmd=fake, cockpit=True)
        self.press("d")
        self.wait_view("daily")
        self.press("Enter")
        self.assertEqual(self.wait_file(log).strip(), "obsidian://daily")

    def test_dashboard_通常の_sidebar_の_d_は_落ちずに_描画を続ける(self):
        # ポップアップは client が無いと出ないので、キーを受けても sidebar が生きていることだけ確かめる
        self.render(daily_dir=self.daily_note(600))
        self.press("d")
        time.sleep(1)
        self.assertIn("WEB", self.wait_screen(lambda scr: "WEB" in scr))

    def test_dashboard_c_で_前回の更新以降の作業をコピーする(self):
        fake, out = self.clip_cmd()
        env = self.daily_work(title="コピー対象の作業")
        env["AGENT_SIDEBAR_CLIP_CMD"] = fake
        self.render(extra_env=env)
        self.press("c")
        self.assertEqual(self.wait_file(out), "- myrepo\n\t- コピー対象の作業\n")

    def test_dashboard_c_は_作業が無ければクリップボードを書き換えない(self):
        fake, out = self.clip_cmd()
        self.render(daily_dir=self.daily_note(600), extra_env={"AGENT_SIDEBAR_CLIP_CMD": fake})
        self.press("c")
        time.sleep(1.5)
        self.assertFalse(os.path.exists(out))

    # ---- Daily 欄の点滅: 長く更新されていないとき、勤務時間帯だけ 📝 と ⏰ を入れ替える ----

    BLINK_ON = {"AGENT_SIDEBAR_DAILY_BLINK": "on", "AGENT_SIDEBAR_DAILY_WORK_DAYS": "1234567",
                "AGENT_SIDEBAR_DAILY_WORK_FROM": "0", "AGENT_SIDEBAR_DAILY_WORK_TO": "24"}

    def seen_icons(self, seconds=3.5):
        """Daily 欄の先頭のアイコンを、seconds 秒のあいだ繰り返し読んで、見えたものの集合を返す。"""
        seen = set()
        deadline = time.time() + seconds
        while time.time() < deadline:
            row = self.daily_row(self.tmux("capture-pane", "-p", "-t", "t:0.0").stdout).strip()
            for icon in ("📝", "⏰"):
                if row.startswith(icon):
                    seen.add(icon)
            time.sleep(0.25)
        return seen

    def test_blink_3時間超えて勤務時間帯なら_アイコンが入れ替わる(self):
        self.render(daily_dir=self.daily_note(4 * 3600), extra_env=self.BLINK_ON)
        self.assertEqual(self.seen_icons(), {"📝", "⏰"})

    def test_blink_更新から3時間以内なら_点滅しない(self):
        self.render(daily_dir=self.daily_note(2 * 3600 + 600), extra_env=self.BLINK_ON)
        self.assertEqual(self.seen_icons(), {"📝"})

    def test_blink_勤務日でなければ_点滅しない(self):
        env = dict(self.BLINK_ON, AGENT_SIDEBAR_DAILY_WORK_DAYS="0")  # %u は 1〜7 なので、どの日にも当たらない
        self.render(daily_dir=self.daily_note(4 * 3600), extra_env=env)
        self.assertEqual(self.seen_icons(), {"📝"})

    def test_blink_勤務時間帯でなければ_点滅しない(self):
        env = dict(self.BLINK_ON, AGENT_SIDEBAR_DAILY_WORK_FROM="24", AGENT_SIDEBAR_DAILY_WORK_TO="25")
        self.render(daily_dir=self.daily_note(4 * 3600), extra_env=env)
        self.assertEqual(self.seen_icons(), {"📝"})

    def test_blink_off_なら_点滅しない(self):
        env = dict(self.BLINK_ON, AGENT_SIDEBAR_DAILY_BLINK="off")
        self.render(daily_dir=self.daily_note(4 * 3600), extra_env=env)
        self.assertEqual(self.seen_icons(), {"📝"})

    def test_blink_tmux_option_で止められる(self):
        env = dict(self.BLINK_ON, AGENT_SIDEBAR_DAILY_BLINK="")  # 環境変数は空 → tmux option を見る(未設定は on)
        self.render(daily_dir=self.daily_note(4 * 3600), extra_env=env)
        self.assertEqual(self.seen_icons(), {"📝", "⏰"})
        self.tmux("set-option", "-g", "@agent_sidebar_daily_blink", "off")
        time.sleep(2.5)  # option は収集の周期(2 秒)で読み直す
        self.assertEqual(self.seen_icons(2), {"📝"})

    # 24 時を過ぎた深夜(25 時 = 翌 1 時)は、前日の続きとして数える。WORK_TO=48 にすると、いつ実行しても「前日の続き」になる
    LATE_NIGHT = {"AGENT_SIDEBAR_DAILY_BLINK": "on", "AGENT_SIDEBAR_DAILY_WORK_DAYS": "1234567",
                  "AGENT_SIDEBAR_DAILY_WORK_FROM": "0", "AGENT_SIDEBAR_DAILY_WORK_TO": "48"}

    def test_blink_24時を過ぎた深夜は_前日のノートで判定して点滅する(self):
        # 未作成の点滅(猶予 10 時以降)が働かないよう MISSING_FROM を遠ざけ、前日のノートの古さだけで点滅することを確かめる
        env = dict(self.LATE_NIGHT, AGENT_SIDEBAR_DAILY_MISSING_FROM="48")
        self.render(daily_dir=self.daily_note(4 * 3600, days_ago=1), extra_env=env)
        self.assertEqual(self.seen_icons(), {"📝", "⏰"})

    def test_blink_24時を過ぎた深夜は_今日のノートを見ない(self):
        # 前日のノートが無く、今日のノートだけがある(4 時間前の更新)ときは、前日のノートが「未作成」扱いで、猶予の時刻(10 時)前なので点滅しない
        env = dict(self.LATE_NIGHT, AGENT_SIDEBAR_DAILY_MISSING_FROM="48")
        self.render(daily_dir=self.daily_note(4 * 3600), extra_env=env)
        self.assertEqual(self.seen_icons(), {"📝"})

    def test_blink_深夜の判定は_前日の曜日で行う(self):
        # WORK_DAYS に前日の曜日(%u)だけを入れると点滅し、今日の曜日だけを入れると点滅しない
        import datetime
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoweekday()
        today = datetime.date.today().isoweekday()
        d = self.daily_note(4 * 3600, days_ago=1)
        base = dict(self.LATE_NIGHT, AGENT_SIDEBAR_DAILY_MISSING_FROM="48")
        self.render(daily_dir=d, extra_env=dict(base, AGENT_SIDEBAR_DAILY_WORK_DAYS=str(yesterday)))
        self.assertEqual(self.seen_icons(), {"📝", "⏰"})
        if today != yesterday:  # (常に真だが、曜日の取り違えを明示するため)
            self.render(daily_dir=d, extra_env=dict(base, AGENT_SIDEBAR_DAILY_WORK_DAYS=str(today)))
            self.assertEqual(self.seen_icons(), {"📝"})

    def empty_daily_dir(self):
        d = os.path.join(self.dir, "empty-daily")
        os.makedirs(d, exist_ok=True)
        return d

    def test_blink_ノートが未作成でも_勤務時間帯の猶予後なら点滅する(self):
        # 今日のノートがまだ無いのは、一番知らせたい場面(cron の最初の通知も 10:20 だった)
        env = dict(self.BLINK_ON, AGENT_SIDEBAR_DAILY_MISSING_FROM="0")
        self.render(daily_dir=self.empty_daily_dir(), extra_env=env)
        self.assertEqual(self.seen_icons(), {"📝", "⏰"})

    def test_blink_ノートが未作成でも_猶予の時刻前なら点滅しない(self):
        env = dict(self.BLINK_ON, AGENT_SIDEBAR_DAILY_MISSING_FROM="24")  # 朝一番から点滅しないための猶予
        self.render(daily_dir=self.empty_daily_dir(), extra_env=env)
        self.assertEqual(self.seen_icons(), {"📝"})

    def test_blink_ノートが未作成でも_勤務日でなければ点滅しない(self):
        env = dict(self.BLINK_ON, AGENT_SIDEBAR_DAILY_MISSING_FROM="0", AGENT_SIDEBAR_DAILY_WORK_DAYS="0")
        self.render(daily_dir=self.empty_daily_dir(), extra_env=env)
        self.assertEqual(self.seen_icons(), {"📝"})

    # ---- 下部欄の区画: USAGE(データがあるとき)と TOOLS(Daily 欄・WEB 欄。常に) ----

    def footer_lines(self, screen):
        return [l for l in screen.splitlines() if l.strip()]

    def test_tools_Daily_と_WEB_を_TOOLS_の見出しでまとめる(self):
        lines = self.footer_lines(self.render(limits=rate_limits(), cred=credits(), daily_dir=self.daily_note(600)))
        tools = next(i for i, l in enumerate(lines) if "TOOLS" in l)
        self.assertIn("Daily", lines[tools + 1])
        self.assertIn("WEB", lines[tools + 2])
        self.assertEqual(len(lines), tools + 3)  # WEB 欄が最下行

    def test_tools_USAGE_の下に_TOOLS_が来る(self):
        lines = self.footer_lines(self.render(limits=rate_limits()))
        usage = next(i for i, l in enumerate(lines) if "USAGE" in l)
        tools = next(i for i, l in enumerate(lines) if "TOOLS" in l)
        self.assertLess(usage, tools)
        self.assertIn("5h", lines[usage + 1])

    def test_tools_USAGE_のデータが無くても_TOOLS_は出す(self):
        screen = self.render()
        self.assertNotIn("USAGE", screen)
        self.assertIn("TOOLS", screen)

    def test_tools_見出しは_罫線で幅いっぱいに引く(self):
        for line in self.render(limits=rate_limits()).splitlines():
            if "TOOLS" in line or "USAGE" in line:
                self.assertTrue(line.startswith("──"), line)
                self.assertEqual(display_width(line), 31, line)  # sidebar の幅 32 の 1 桁手前まで(右端の桁は折り返しを避けて空ける)

    # ---- cockpit を閉じて開き直したとき、直前に選んでいた Agent(またはダッシュボード)に戻る ----

    def option(self, name):
        return self.tmux("show-options", "-gqv", name).stdout.strip()

    def shown(self):
        return self.tmux("show-options", "-wqv", "-t", "t:0", "@agent_cockpit_shown").stdout.strip()

    def wait_shown(self, predicate, what):
        deadline = time.time() + RENDER_TIMEOUT_SEC * 2
        while time.time() < deadline:
            if predicate(self.shown()):
                return self.shown()
            time.sleep(0.2)
        self.fail(f"{what}(いま @agent_cockpit_shown={self.shown()!r})")

    def two_windows(self):
        return [os.path.join(self.dir, "repo-a"), os.path.join(self.dir, "repo-b")]

    def test_restore_cockpit_で選択を変えると_その_Agent_を保存する(self):
        self.render(cockpit="early", windows=self.two_windows())
        first = self.wait_shown(bool, "枠に最初の Agent が入りません")
        self.press("j")
        moved = self.wait_shown(lambda v: v and v != first, "j で別の Agent に切り替わりません")
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while time.time() < deadline and not self.option("@agent_sidebar_last_sel").startswith(moved + "|"):
            time.sleep(0.2)
        self.assertTrue(self.option("@agent_sidebar_last_sel").startswith(moved + "|"), self.option("@agent_sidebar_last_sel"))

    def test_restore_保存した_Agent_を_起動時に選んで枠へ入れる(self):
        target = lambda panes: f"{panes[1]}|Shell"  # noqa: E731
        self.render(cockpit="early", windows=self.two_windows(), preset={"@agent_sidebar_last_sel": target})
        self.assertEqual(self.wait_shown(bool, "枠に Agent が入りません"), self.extra_panes[1])

    def test_restore_保存した_Agent_が無ければ_既定の選択にする(self):
        self.render(cockpit="early", windows=self.two_windows(), preset={"@agent_sidebar_last_sel": "%9999|Shell"})
        self.assertNotEqual(self.wait_shown(bool, "枠に Agent が入りません"), "%9999")

    def test_restore_すでに枠に入っている_Agent_を_保存した値より優先する(self):
        # sidebar だけを付け直したとき(Agent は枠に入ったまま)、選択を枠の中身に合わせる
        self.render(cockpit="early", windows=self.two_windows(), preset={"@agent_sidebar_last_sel": lambda panes: f"{panes[1]}|Shell"})
        shown = self.wait_shown(bool, "枠に Agent が入りません")
        self.assertEqual(shown, self.extra_panes[1])

    def test_restore_ダッシュボードを出していたなら_ダッシュボードに戻る(self):
        self.render(cockpit="early", windows=self.two_windows(),
                    preset={"@agent_sidebar_last_view": "daily"}, daily_dir=self.daily_note(600))
        self.wait_view("daily")
        self.assertEqual(self.shown(), "")

    def test_restore_ダッシュボードを出した状態も保存する(self):
        self.render(cockpit="early", windows=self.two_windows(), daily_dir=self.daily_note(600))
        self.wait_shown(bool, "枠に Agent が入りません")
        self.press("d")
        self.wait_view("daily")
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while time.time() < deadline and self.option("@agent_sidebar_last_view") != "daily":
            time.sleep(0.2)
        self.assertEqual(self.option("@agent_sidebar_last_view"), "daily")
        self.press("d")  # 戻すと、保存も「ダッシュボードではない」に戻る
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while time.time() < deadline and self.option("@agent_sidebar_last_view") != "":
            time.sleep(0.2)
        self.assertEqual(self.option("@agent_sidebar_last_view"), "")

    def test_restore_通常の_sidebar_は_選択を保存しない(self):
        self.render(windows=self.two_windows())
        self.press("j")
        time.sleep(2.5)
        self.assertEqual(self.option("@agent_sidebar_last_sel"), "")

    def test_daily_o_キーで_Obsidian_の_Daily_Note_を開く(self):
        log = os.path.join(self.dir, "open.log")
        fake = os.path.join(self.dir, "fake-open")
        with open(fake, "w") as f:
            f.write(f'#!/bin/sh\necho "$@" > {log}\n')
        os.chmod(fake, 0o755)
        self.render(open_cmd=fake)
        self.tmux("send-keys", "-t", "t:0.0", "o")
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while time.time() < deadline and not os.path.exists(log):
            time.sleep(0.2)
        self.assertTrue(os.path.exists(log), "o キーで open が呼ばれませんでした")
        with open(log) as f:
            self.assertEqual(f.read().strip(), "obsidian://daily")


    # --- Codex の今月の使用量(クレジット)の行 ---
    # 着地予想の色は、上の 💳 と同じ(2026-10-13 は営業日 22 日のうち 9 日目。着地予想 = 使用量 × 22 / 9)

    def codex_color(self, today, **fields):
        screen = self.render(codex=codex_usage(**fields), today=today, colors=True)
        m = re.search(r"🤖 [^\n]*?\x1b\[38;5;(\d+)m\d", screen)
        self.assertIsNotNone(m, f"色つきの 🤖 行がありません:\n{screen!r}")
        return m.group(1)

    def test_使用量と上限と使用率を桁区切りで出す(self):
        screen = self.render(codex=codex_usage())
        self.assertIn("USAGE", screen)
        self.assertRegex(screen, r"🤖 2,533 / 20,000\s+13%")

    def test_Codex_だけなら_5h_と_1w_と_credits_は出さない(self):
        screen = self.render(codex=codex_usage())
        for word in ("5h", "1w", "💳"):
            self.assertNotIn(word, screen)

    def test_データが無ければ_出さない(self):
        screen = self.render()
        self.assertNotIn("🤖", screen)
        self.assertNotIn("USAGE", screen)

    def test_無効なら_出さない(self):
        screen = self.render(codex={"enabled": False, "fetched_at": int(time.time())})
        self.assertNotIn("🤖", screen)

    def test_上限が読めなければ_出さない(self):
        screen = self.render(codex=codex_usage(limit=None, percent=None))
        self.assertNotIn("🤖", screen)

    def test_取得が止まっていれば_経過時間を添える(self):
        screen = self.render(codex=codex_usage(fetched_at=int(time.time()) - 3 * 3600))
        self.assertRegex(screen, r"🤖 2,533 / 20,000\s+13%\s+3h")

    def test_5h_1w_と_credits_と並べても_順番は_credits_の後ろで_WEB_欄が最下行(self):
        screen = self.render(limits=rate_limits(), cred=credits(used=150), codex=codex_usage())
        lines = [l for l in screen.splitlines() if l.strip()]
        self.assertIn("WEB", lines[-1])
        tools = next(i for i, l in enumerate(lines) if "TOOLS" in l)
        self.assertIn("🤖", lines[tools - 1])  # USAGE 区画の最後
        self.assertIn("🚄", lines[tools - 2])  # 💳 の絵文字の行の次
        for line in screen.splitlines():
            self.assertLessEqual(display_width(line), 32, line)

    def test_codex_着地予想が上限の7割以下なら緑(self):
        # 5000 → 着地 12222 / 20000 = 61%
        self.assertEqual(self.codex_color("2026-10-13", used=5000, percent=25), self.GREEN)

    def test_codex_着地予想が上限の7割を超えたら黄(self):
        # 8000 → 着地 19555 / 20000 = 97%
        self.assertEqual(self.codex_color("2026-10-13", used=8000, percent=40), self.YELLOW)

    def test_codex_着地予想が上限を超えそうなら赤(self):
        # 10000 → 着地 24444 / 20000 = 122%
        self.assertEqual(self.codex_color("2026-10-13", used=10000, percent=50), self.RED)

    def test_取得が止まった古い値は_着地予想を使わず_使用率の段階の色(self):
        # 10000(使用率 50%)は、新しければ着地予想で赤。古い値は予想しないので使用率 50% の段階(黄系 220)
        screen = self.render(
            codex=codex_usage(used=10000, percent=50, fetched_at=int(time.time()) - 3 * 3600),
            today="2026-10-13",
            colors=True,
        )
        m = re.search(r"🤖 [^\n]*?\x1b\[38;5;(\d+)m\d", screen)
        self.assertEqual(m.group(1), "220")

    PLACEHOLDER = "\U0010EEEE"  # Kitty graphics の Unicode placeholder(Agent 一覧のカードと同じ画像アイコンの文字)

    def use_image_icons(self):
        """画像アイコンの条件(type_icon=image と allow-passthrough)を一時サーバーに設定して、sidebar が気づくまで待つ。"""
        self.tmux("set-option", "-g", "@agent_sidebar_type_icon", "image")
        self.tmux("set-option", "-g", "allow-passthrough", "on")
        return self.wait_screen(lambda scr: self.PLACEHOLDER in scr)

    def test_画像モードなら_Codex_の行頭は_Codex_のアイコン(self):
        self.render(codex=codex_usage())
        screen = self.use_image_icons()
        row = next(l for l in screen.splitlines() if "2,533" in l)
        self.assertTrue(row.lstrip().startswith(self.PLACEHOLDER), row)
        self.assertNotIn("🤖", screen)
        self.assertRegex(row, r"2,533 / 20,000\s+13%")
        self.assertIn("38;5;251m" + self.PLACEHOLDER, self.tmux("capture-pane", "-e", "-p", "-t", "t:0.0").stdout)  # 画像 ID 251 = Codex

    def test_画像モードなら_credits_の行頭は_Claude_のアイコン(self):
        self.render(cred=credits())
        screen = self.use_image_icons()
        row = next(l for l in screen.splitlines() if "29.84" in l)
        self.assertTrue(row.lstrip().startswith(self.PLACEHOLDER), row)
        self.assertNotIn("💳", screen)
        self.assertIn("38;5;250m" + self.PLACEHOLDER, self.tmux("capture-pane", "-e", "-p", "-t", "t:0.0").stdout)  # 画像 ID 250 = Claude

    def test_画像モードでない時は_絵文字のまま(self):
        screen = self.render(cred=credits(), codex=codex_usage())
        self.assertNotIn(self.PLACEHOLDER, screen)
        self.assertIn("💳", screen)
        self.assertIn("🤖", screen)

    # --- Codex のスレッド(状態・名前・モデル)をカードに出す ---

    def thread_line(self, cwd=None, status="idle", flags="", name="設計書の確認", model="gpt-6-astra", effort="low", since=None):
        """tmux-agent-codex-threads が書く X| の行。cwd は実体のパス(tmux の pane_current_path と同じ形)。"""
        cwd = cwd or os.path.realpath(self.dir)
        since = since if since is not None else int(time.time()) - 125
        return f"X|01a0-{abs(hash((cwd, name)))}|{cwd}|{status}|{flags}|{name}|{model}|{effort}|{since}|{since}"

    def start_codex_pane(self, cwd=None, first=True):
        """argv[0] が codex のプロセスを pane で動かす(sidebar は ps の引数で Codex を検出する)。first なら元の main pane を置き換え、そうでなければ分割して足す。"""
        cwd = cwd or os.path.realpath(self.dir)
        cmd = "exec -a codex sleep 600"
        if first:
            main = [l.split()[0] for l in self.tmux("list-panes", "-t", "t:0", "-F", "#{pane_id} #{@agent_sidebar}").stdout.splitlines() if l.split()[-1:] != ["1"]][0]
            self.tmux("respawn-pane", "-k", "-t", main, "-c", cwd, cmd)
        else:
            self.tmux("split-window", "-d", "-t", "t:0.1", "-c", cwd, cmd)

    def codex_card(self, screen):
        """画面の Codex のカードの行(名前・状態)を返す。"""
        return [l for l in screen.splitlines() if l.strip()]

    def test_codex_スレッドが一意なら_名前と状態とモデルを出す(self):
        self.render(codex_threads=[self.thread_line()])
        self.start_codex_pane()
        screen = self.wait_screen(lambda scr: "設計書の確認" in scr)
        self.assertIn("IDLE", screen)
        self.assertIn("gpt-6-astra low", screen)
        self.assertNotIn("UNKNOWN", screen)
        self.assertRegex(screen, r"IDLE.*2m")  # 125 秒前から idle

    def test_codex_作業中は_WORKING(self):
        self.render(codex_threads=[self.thread_line(status="active", flags="")])
        self.start_codex_pane()
        screen = self.wait_screen(lambda scr: "WORKING" in scr)
        self.assertIn("設計書の確認", screen)

    def test_codex_承認待ちは_WAITING_で_理由を添える(self):
        self.render(codex_threads=[self.thread_line(status="active", flags="waitingOnApproval")])
        self.start_codex_pane()
        screen = self.wait_screen(lambda scr: "WAITING" in scr)
        self.assertIn("approval", screen)

    def test_codex_入力待ちは_WAITING_で_input(self):
        self.render(codex_threads=[self.thread_line(status="active", flags="waitingOnUserInput")])
        self.start_codex_pane()
        screen = self.wait_screen(lambda scr: "WAITING" in scr)
        self.assertIn("input", screen)

    def test_codex_スレッドの情報が無ければ_unknown(self):
        self.render()
        self.start_codex_pane()
        screen = self.wait_screen(lambda scr: "UNKNOWN" in scr)
        self.assertNotIn("設計書の確認", screen)

    def test_codex_cwd_が違うスレッドは使わない(self):
        self.render(codex_threads=[self.thread_line(cwd="/somewhere/else")])
        self.start_codex_pane()
        screen = self.wait_screen(lambda scr: "UNKNOWN" in scr)
        self.assertNotIn("設計書の確認", screen)

    def test_codex_同じ_cwd_に_pane_もスレッドも複数あれば_推測せず_unknown(self):
        self.render(codex_threads=[self.thread_line(name="一つ目"), self.thread_line(name="二つ目")])
        self.start_codex_pane()
        self.start_codex_pane(first=False)
        screen = self.wait_screen(lambda scr: scr.count("UNKNOWN") >= 2)
        self.assertNotIn("一つ目", screen)
        self.assertNotIn("二つ目", screen)

    def test_codex_pane_が複数でスレッドが一つなら_どれか分からないので_unknown(self):
        self.render(codex_threads=[self.thread_line()])
        self.start_codex_pane()
        self.start_codex_pane(first=False)
        screen = self.wait_screen(lambda scr: scr.count("UNKNOWN") >= 2)
        self.assertNotIn("設計書の確認", screen)

    def test_codex_取得が止まって古いキャッシュは使わない(self):
        self.render(codex_threads=[self.thread_line()])
        old = time.time() - 3600
        os.utime(self.threads_file, (old, old))
        self.start_codex_pane()
        screen = self.wait_screen(lambda scr: "UNKNOWN" in scr)
        self.assertNotIn("設計書の確認", screen)

    def test_codex_スレッドの取得を裏で起動する(self):
        marker = os.path.join(self.dir, "threads-fetched")
        fake = os.path.join(self.dir, "fake-threads")
        with open(fake, "w") as f:
            f.write(f"#!/bin/bash\ntouch {marker}\n")
        os.chmod(fake, 0o755)
        self.render(extra_env={"AGENT_SIDEBAR_CODEX_THREADS_BIN": fake})
        self.wait_screen(lambda _: os.path.exists(marker))
        self.assertTrue(os.path.exists(marker))

    # --- 同じ cwd の Codex が複数あるときは、pane のタイトル(Codex の TUI は「スレッド名 | ディレクトリ」にする)で見分ける ---

    def codex_panes(self):
        """sidebar 以外の pane_id(表示の順)。"""
        return [l.split()[0] for l in self.tmux("list-panes", "-t", "t:0", "-F", "#{pane_id} #{@agent_sidebar}").stdout.splitlines() if l.split()[-1:] != ["1"]]

    def set_titles(self, *titles):
        for pane, title in zip(self.codex_panes(), titles):
            self.tmux("select-pane", "-t", pane, "-T", title)

    def card_status(self, screen, name):
        """name のカードの状態の行(カードは 名前 / ブランチ / 状態 の 3 行)。"""
        lines = screen.splitlines()
        for i, line in enumerate(lines):
            if name in line and i + 2 < len(lines):
                return lines[i + 2]
        self.fail(f"{name} のカードが画面にありません:\n{screen}")

    def test_codex_同じ_cwd_に複数あっても_pane_のタイトルで見分ける(self):
        self.render(codex_threads=[
            self.thread_line(name="一つ目", status="active", flags="waitingOnApproval"),
            self.thread_line(name="二つ目"),
        ])
        self.start_codex_pane()
        self.start_codex_pane(first=False)
        self.set_titles("一つ目 | proj...", "二つ目 | proj...")
        screen = self.wait_screen(lambda scr: "一つ目" in scr and "二つ目" in scr and "UNKNOWN" not in scr)
        self.assertIn("WAITING", self.card_status(screen, "一つ目"))
        self.assertIn("IDLE", self.card_status(screen, "二つ目"))

    def test_codex_タイトルが逆の順でも_取り違えない(self):
        self.render(codex_threads=[
            self.thread_line(name="一つ目", status="active", flags="waitingOnApproval"),
            self.thread_line(name="二つ目"),
        ])
        self.start_codex_pane()
        self.start_codex_pane(first=False)
        self.set_titles("二つ目 | proj...", "一つ目 | proj...")  # 表示の順とスレッドの順が逆
        screen = self.wait_screen(lambda scr: "一つ目" in scr and "二つ目" in scr and "UNKNOWN" not in scr)
        self.assertIn("WAITING", self.card_status(screen, "一つ目"))
        self.assertIn("IDLE", self.card_status(screen, "二つ目"))

    def test_codex_pane_が_1_つでスレッドが複数でも_タイトルが一致すれば使う(self):
        self.render(codex_threads=[self.thread_line(name="一つ目"), self.thread_line(name="別のスレッド", status="active", flags="")])
        self.start_codex_pane()
        self.set_titles("別のスレッド | proj...")
        screen = self.wait_screen(lambda scr: "別のスレッド" in scr)
        self.assertIn("WORKING", self.card_status(screen, "別のスレッド"))

    def test_codex_タイトルが同じ_pane_が複数なら_決めずに_unknown(self):
        self.render(codex_threads=[self.thread_line(name="同名"), self.thread_line(name="別名")])
        self.start_codex_pane()
        self.start_codex_pane(first=False)
        self.set_titles("同名 | proj...", "同名 | proj...")
        screen = self.wait_screen(lambda scr: scr.count("UNKNOWN") >= 2)
        self.assertNotIn("別名", screen)

    def test_codex_タイトルにスレッド名が無ければ_決めずに_unknown(self):
        self.render(codex_threads=[self.thread_line(name="一つ目"), self.thread_line(name="二つ目")])
        self.start_codex_pane()
        self.start_codex_pane(first=False)
        self.set_titles("codex", "zsh")  # 「名前 | ディレクトリ」の形ではない
        screen = self.wait_screen(lambda scr: scr.count("UNKNOWN") >= 2)
        self.assertNotIn("一つ目", screen)

    # --- Tasks 欄(Obsidian のタスクの件数と、t のポップアップ) ---

    def make_tasks(self, specs=(("2026-10-16-a", "false"), ("2026-10-10-b", "false"), ("2026-08-01-c", "false")), dirname="tasks"):
        """一時ディレクトリにタスクを作る。2026-10-17 を今日として、c だけが 30 日を超えて古い。"""
        directory = os.path.join(self.dir, dirname)
        os.makedirs(directory, exist_ok=True)
        for name, done in specs:
            with open(os.path.join(directory, name + ".md"), "w") as f:
                f.write(f"---\ndone: {done}\ntags:\n  - mimi\n  - bug\n---\n本文\n")
        return directory

    def tasks_row(self, screen):
        return next((l for l in screen.splitlines() if "Tasks" in l), "")

    def test_tasks_未完了の件数と古い件数と_t_のヒントを出す(self):
        screen = self.render(tasks_dir=self.make_tasks())
        self.assertRegex(self.tasks_row(screen), r"📋 Tasks 3 \(1 old\)\s+t list")

    def test_tasks_古いものが無ければ_件数だけ(self):
        screen = self.render(tasks_dir=self.make_tasks(specs=(("2026-10-16-a", "false"),)))
        self.assertRegex(self.tasks_row(screen), r"📋 Tasks 1\s+t list")
        self.assertNotIn("old", screen)

    def test_tasks_完了待ちは数えない(self):
        screen = self.render(tasks_dir=self.make_tasks(specs=(("2026-10-16-a", "false"), ("2026-10-15-b", "true"))))
        self.assertRegex(self.tasks_row(screen), r"Tasks 1\b")

    def test_tasks_ディレクトリが決まらなければ_欄ごと出さない(self):
        screen = self.render()
        self.assertNotIn("Tasks", screen)
        self.assertNotIn("📋", screen)

    def test_tasks_欄は_Daily_欄と_WEB_欄の間(self):
        screen = self.render(tasks_dir=self.make_tasks())
        lines = [l for l in screen.splitlines() if l.strip()]
        tools = next(i for i, l in enumerate(lines) if "TOOLS" in l)
        self.assertIn("Daily", lines[tools + 1])
        self.assertIn("Tasks", lines[tools + 2])
        self.assertIn("WEB", lines[tools + 3])
        self.assertEqual(len(lines) - 1, tools + 3)  # WEB 欄が最下行

    def test_tasks_欄は幅に収まる(self):
        screen = self.render(tasks_dir=self.make_tasks(specs=tuple((f"2026-01-{d:02d}-t", "false") for d in range(1, 29))))
        self.assertRegex(self.tasks_row(screen), r"Tasks 28 \(28 old\)")
        for line in screen.splitlines():
            self.assertLessEqual(display_width(line), 32, line)

    def attach_client(self):
        """専用ソケットのサーバーへ、pty つきの本物のクライアントをつなぐ(display-popup は client が居ないと開けない)。"""
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
        client = subprocess.Popen(["tmux", "-S", self.sock, "attach", "-t", "t"], stdin=slave, stdout=slave, stderr=slave,
                                  env={**os.environ, "TERM": "xterm-256color"}, start_new_session=True)
        os.close(slave)
        stop = threading.Event()
        self.client_output = bytearray()  # クライアントの端末(= Ghostty の役)に届いた出力。BEL の確認に使う

        def drain():
            while not stop.is_set():
                if select.select([master], [], [], 0.2)[0]:
                    try:
                        data = os.read(master, 65536)
                        if not data:
                            return
                        self.client_output.extend(data)
                    except OSError:
                        return

        thread = threading.Thread(target=drain, daemon=True)
        thread.start()

        def cleanup():
            stop.set()
            client.terminate()
            client.wait(timeout=5)
            thread.join(timeout=2)
            os.close(master)

        self.addCleanup(cleanup)

    def fake_tasks_bin(self, status_line):
        """tmux-agent-tasks の代わり。--status には status_line を返し、それ以外(ポップアップでの起動)は、受け取った引数を [ ] で囲んでログへ書く。"""
        fake = os.path.join(self.dir, "fake-tasks")
        log = os.path.join(self.dir, "popup-args.log")
        with open(fake, "w") as f:
            f.write(f'#!/bin/bash\nif [ "$1" = --status ]; then echo "{status_line}"; exit 0; fi\n'
                    f'for a in "$@"; do printf "[%s]" "$a"; done > {log}\n')
        os.chmod(fake, 0o755)
        return fake, log

    def test_tasks_t_で_ポップアップを_タスクのディレクトリつきで開く(self):
        directory = os.path.join(self.dir, "my tasks")  # 空白を含むパスでも引数が壊れない
        fake, log = self.fake_tasks_bin(f"3 1 0 {directory}")
        self.render(extra_env={"AGENT_SIDEBAR_TASKS_BIN": fake})
        self.attach_client()
        self.press("t")
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while not os.path.exists(log) and time.time() < deadline:
            time.sleep(0.1)
        self.assertTrue(os.path.exists(log), "t でポップアップが開かれませんでした")
        with open(log) as f:
            self.assertEqual(f.read(), f"[--dir][{directory}]")

    def test_tasks_ディレクトリが決まらないときの_t_は_ポップアップを開かない(self):
        fake, log = self.fake_tasks_bin("")  # --status が何も返さない = 決まらない
        self.render(extra_env={"AGENT_SIDEBAR_TASKS_BIN": fake})
        self.attach_client()
        self.press("t")
        time.sleep(1.5)
        self.assertFalse(os.path.exists(log))

    # --- Dock のバウンス用ベル(WAITING / DONE になったとき、クライアントの端末へ BEL を 1 回書く) ---

    def set_codex_thread(self, **kw):
        with open(self.threads_file, "w") as f:
            f.write(self.thread_line(**kw) + "\n")

    def bells(self):
        return bytes(self.client_output).count(b"\a")

    def wait_bells(self, expected):
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while time.time() < deadline and self.bells() < expected:
            time.sleep(0.2)
        self.assertEqual(self.bells(), expected)

    def start_bell_session(self, extra_env=None):
        """idle の Codex が 1 つ居て、クライアントがつながり、基準(記録)が書かれた状態にする。いまの BEL の数を返す。"""
        self.render(codex_threads=[self.thread_line()], extra_env=extra_env)
        self.start_codex_pane()
        self.wait_screen(lambda scr: "IDLE" in scr)
        self.attach_client()
        time.sleep(1.5)  # 接続直後の描画が落ち着くまで
        return self.bells()

    def test_ベル_WAITING_になったら_1回だけ鳴らす(self):
        base = self.start_bell_session()
        self.set_codex_thread(status="active", flags="waitingOnApproval")
        self.wait_screen(lambda scr: "WAITING" in scr)
        self.wait_bells(base + 1)
        time.sleep(5)  # 収集が何度か回っても、同じ WAITING では鳴らさない
        self.assertEqual(self.bells(), base + 1)

    def test_ベル_待ちから戻って_また待ちになったら_もう一度鳴らす(self):
        base = self.start_bell_session()
        self.set_codex_thread(status="active", flags="waitingOnApproval")
        self.wait_bells(base + 1)
        self.wait_screen(lambda scr: "WAITING" in scr)  # 古い IDLE の表示を、待ちが解けた印と取り違えない
        self.set_codex_thread(status="idle")
        self.wait_screen(lambda scr: "IDLE" in scr and "WAITING" not in scr)
        self.assertEqual(self.bells(), base + 1)  # 待ちが解けたときは鳴らさない
        self.set_codex_thread(status="active", flags="waitingOnUserInput")
        self.wait_bells(base + 2)

    def test_ベル_作業中は鳴らさない(self):
        base = self.start_bell_session()
        self.set_codex_thread(status="active", flags="")
        self.wait_screen(lambda scr: "WORKING" in scr)
        time.sleep(3)
        self.assertEqual(self.bells(), base)

    # --- 状態ごとの音(afplay)。BEL と同じ契機で、WAITING = Sosumi、DONE = Glass が既定 ---

    def fake_sound_cmd(self):
        """afplay の代わり。受け取ったファイルのパスを 1 行ずつログへ書く。"""
        fake = os.path.join(self.dir, "fake-sound")
        log = os.path.join(self.dir, "sounds.log")
        with open(fake, "w") as f:
            f.write(f'#!/bin/bash\necho "$1" >> {log}\n')
        os.chmod(fake, 0o755)
        return fake, log

    def sounds(self, log):
        if not os.path.exists(log):
            return []
        with open(log) as f:
            return f.read().split()

    def wait_sounds(self, log, expected):
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while time.time() < deadline and self.sounds(log) != expected:
            time.sleep(0.2)
        self.assertEqual(self.sounds(log), expected)

    def test_音_WAITING_は_Sosumi_を_1回だけ鳴らす(self):
        fake, log = self.fake_sound_cmd()
        self.start_bell_session(extra_env={"AGENT_SIDEBAR_SOUND_CMD": fake})
        self.set_codex_thread(status="active", flags="waitingOnApproval")
        self.wait_sounds(log, ["/System/Library/Sounds/Sosumi.aiff"])
        time.sleep(5)  # 同じ WAITING のままでは、何度も鳴らさない
        self.assertEqual(self.sounds(log), ["/System/Library/Sounds/Sosumi.aiff"])

    def test_音_作業中は鳴らさない(self):
        fake, log = self.fake_sound_cmd()
        self.start_bell_session(extra_env={"AGENT_SIDEBAR_SOUND_CMD": fake})
        self.set_codex_thread(status="active", flags="")
        self.wait_screen(lambda scr: "WORKING" in scr)
        time.sleep(3)
        self.assertEqual(self.sounds(log), [])

    def test_音_音だけ_off_にしても_BEL_は鳴る(self):
        fake, log = self.fake_sound_cmd()
        base = self.start_bell_session(extra_env={"AGENT_SIDEBAR_SOUND_CMD": fake, "AGENT_SIDEBAR_BELL_SOUND": "off"})
        self.set_codex_thread(status="active", flags="waitingOnApproval")
        self.wait_bells(base + 1)
        time.sleep(1)
        self.assertEqual(self.sounds(log), [])

    def test_音_状態ごとに音を変えられて_off_にもできる(self):
        fake, log = self.fake_sound_cmd()
        self.start_bell_session(extra_env={"AGENT_SIDEBAR_SOUND_CMD": fake, "AGENT_SIDEBAR_SOUND_WAITING": "Ping"})
        self.set_codex_thread(status="active", flags="waitingOnApproval")
        self.wait_sounds(log, ["/System/Library/Sounds/Ping.aiff"])

    def test_音_その状態だけ_off_ならその状態は鳴らさない(self):
        fake, log = self.fake_sound_cmd()
        base = self.start_bell_session(extra_env={"AGENT_SIDEBAR_SOUND_CMD": fake, "AGENT_SIDEBAR_SOUND_WAITING": "off"})
        self.set_codex_thread(status="active", flags="waitingOnApproval")
        self.wait_bells(base + 1)
        time.sleep(1)
        self.assertEqual(self.sounds(log), [])

    def test_音_tmux_の_option_で音を選べる(self):
        fake, log = self.fake_sound_cmd()
        self.start_bell_session(extra_env={"AGENT_SIDEBAR_SOUND_CMD": fake})
        self.tmux("set-option", "-g", "@agent_sidebar_sound_waiting", "Funk")
        time.sleep(2.5)  # option は収集のたびに読まれる
        self.set_codex_thread(status="active", flags="waitingOnApproval")
        self.wait_sounds(log, ["/System/Library/Sounds/Funk.aiff"])

    def test_音_ファイルのパスも指定できる(self):
        fake, log = self.fake_sound_cmd()
        custom = os.path.join(self.dir, "my sound.aiff")  # 空白を含むパスでも壊れない
        with open(custom, "wb") as f:
            f.write(b"x")
        self.start_bell_session(extra_env={"AGENT_SIDEBAR_SOUND_CMD": fake})
        self.tmux("set-option", "-g", "@agent_sidebar_sound_waiting", custom)  # 環境変数は空白で分かれてしまうので、option で渡す
        time.sleep(2.5)  # option は収集のたびに読まれる
        self.set_codex_thread(status="active", flags="waitingOnApproval")
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while time.time() < deadline and not os.path.exists(log):
            time.sleep(0.2)
        with open(log) as f:
            self.assertEqual(f.read().strip(), custom)

    def test_音_存在しない音の名前なら鳴らさない(self):
        fake, log = self.fake_sound_cmd()
        base = self.start_bell_session(extra_env={"AGENT_SIDEBAR_SOUND_CMD": fake, "AGENT_SIDEBAR_SOUND_WAITING": "NoSuchSound"})
        self.set_codex_thread(status="active", flags="waitingOnApproval")
        self.wait_bells(base + 1)
        time.sleep(1)
        self.assertEqual(self.sounds(log), [])

    def start_claude_pane(self):
        """Claude 風のプロセスを pane で動かし、claude agents のキャッシュに idle で載せる。tmux の親 pid(DONE の判定のキー)を返す。"""
        cwd = os.path.realpath(self.dir)
        main = self.codex_panes()[0]
        self.tmux("respawn-pane", "-k", "-t", main, "-c", cwd, "exec -a claude sleep 600")
        pid = self.tmux("display-message", "-p", "-t", main, "#{pane_pid}").stdout.strip()
        parent = subprocess.run(["ps", "-o", "ppid=", "-p", pid], capture_output=True, text=True).stdout.strip()
        with open(os.path.join(self.dir, "claude-cache"), "w") as f:
            f.write(f"C|{pid}|idle||{cwd}|名前|sid-test-0001\n")
        return parent

    def test_音_DONE_は_Glass_を鳴らす(self):
        fake, log = self.fake_sound_cmd()
        self.render(extra_env={"AGENT_SIDEBAR_SOUND_CMD": fake})
        parent = self.start_claude_pane()
        self.wait_screen(lambda scr: "IDLE" in scr)
        self.attach_client()
        time.sleep(1.5)
        base = self.bells()
        with open(os.path.join(self.dir, "none"), "w") as f:  # 完了して未読 = DONE
            f.write(f"{parent}:idle:1\n")
        self.wait_screen(lambda scr: "DONE" in scr)
        self.wait_bells(base + 1)
        self.wait_sounds(log, ["/System/Library/Sounds/Glass.aiff"])

    def test_音_bell_が_waiting_なら_DONE_では鳴らさない(self):
        fake, log = self.fake_sound_cmd()
        self.render(extra_env={"AGENT_SIDEBAR_SOUND_CMD": fake, "AGENT_SIDEBAR_BELL": "waiting"})
        parent = self.start_claude_pane()
        self.wait_screen(lambda scr: "IDLE" in scr)
        self.attach_client()
        time.sleep(1.5)
        base = self.bells()
        with open(os.path.join(self.dir, "none"), "w") as f:
            f.write(f"{parent}:idle:1\n")
        self.wait_screen(lambda scr: "DONE" in scr)
        time.sleep(3)
        self.assertEqual(self.bells(), base)
        self.assertEqual(self.sounds(log), [])

    def test_ベル_off_なら鳴らさない(self):
        base = self.start_bell_session(extra_env={"AGENT_SIDEBAR_BELL": "off"})
        self.set_codex_thread(status="active", flags="waitingOnApproval")
        self.wait_screen(lambda scr: "WAITING" in scr)
        time.sleep(3)
        self.assertEqual(self.bells(), base)

    def test_ベル_tmux_の_option_でも_off_にできる(self):
        base = self.start_bell_session()
        self.tmux("set-option", "-g", "@agent_sidebar_bell", "off")
        time.sleep(2.5)  # option は収集のたびに読まれる
        self.set_codex_thread(status="active", flags="waitingOnApproval")
        self.wait_screen(lambda scr: "WAITING" in scr)
        time.sleep(3)
        self.assertEqual(self.bells(), base)

    # --- カードのブランチ(cwd の git。判定は git を呼んで長めにキャッシュし、ブランチは HEAD ファイルを毎回読む) ---

    def git(self, repo, *args):
        return subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "-C", repo, *args], capture_output=True, text=True, check=True).stdout

    def make_repo(self, name="myrepo", branch="feat-a"):
        repo = os.path.realpath(os.path.join(self.dir, name))
        os.makedirs(repo)
        self.git(repo, "init", "-q", "-b", branch)
        self.git(repo, "commit", "-q", "--allow-empty", "-m", "first")
        return repo

    def test_git_ブランチをカードに出す(self):
        repo = self.make_repo()
        self.render()
        self.start_codex_pane(cwd=repo)
        screen = self.wait_screen(lambda scr: "feat-a" in scr)
        self.assertIn("myrepo", screen)  # 見出し

    def test_git_checkout_にすぐ追従する(self):
        repo = self.make_repo()
        self.render()
        self.start_codex_pane(cwd=repo)
        self.wait_screen(lambda scr: "feat-a" in scr)
        self.git(repo, "checkout", "-q", "-b", "feat-b")
        screen = self.wait_screen(lambda scr: "feat-b" in scr)  # 判定のキャッシュ(60 秒)を待たない
        self.assertNotIn("feat-a", screen)

    def test_git_detached_HEAD_は短縮_SHA(self):
        repo = self.make_repo()
        self.render()
        self.start_codex_pane(cwd=repo)
        self.wait_screen(lambda scr: "feat-a" in scr)
        self.git(repo, "checkout", "-q", "--detach")
        sha = self.git(repo, "rev-parse", "--short=7", "HEAD").strip()
        self.wait_screen(lambda scr: sha in scr)

    def test_git_worktree_は本体と同じリポジトリにまとまり_ブランチは各自(self):
        repo = self.make_repo()
        wt = os.path.join(self.dir, "myrepo_worktree_wt")
        self.git(repo, "worktree", "add", "-q", wt, "-b", "wt-branch")
        self.render()
        self.start_codex_pane(cwd=repo)
        self.start_codex_pane(cwd=os.path.realpath(wt), first=False)
        screen = self.wait_screen(lambda scr: "feat-a" in scr and "wt-branch" in scr)
        self.assertEqual(screen.count("── myrepo"), 1)  # 見出しは 1 つ(worktree の名前では分かれない)

    def test_git_管理外のディレクトリは_ブランチの代わりに親ディレクトリ(self):
        plain = os.path.realpath(os.path.join(self.dir, "plain"))
        os.makedirs(plain)
        self.render()
        self.start_codex_pane(cwd=plain)
        screen = self.wait_screen(lambda scr: "── plain" in scr)
        self.assertNotIn("feat-a", screen)

    # ---- cockpit: Agent の行のクリックは、右の枠へ切り替えてフォーカスも移す(Enter と同じ) ----

    def sidebar_pane(self):
        for line in self.tmux("list-panes", "-t", "t:0", "-F", "#{pane_id} #{@agent_sidebar}").stdout.splitlines():
            pane, mark = line.split()[0], line.split()[-1]
            if mark == "1":
                return pane
        self.fail("sidebar の pane が見つかりません")

    def active_pane(self):
        return self.tmux("display-message", "-p", "-t", "t:0", "#{pane_id}").stdout.strip()

    def click_row(self, row):
        """sidebar の画面の row 行目(0 始まり)を、SGR マウス報告の押下 + 解放でクリックする。"""
        y = row + 1
        self.tmux("send-keys", "-t", self.sidebar_pane(), "-l", f"\033[<0;5;{y}M\033[<0;5;{y}m")

    def test_cockpit_Agent_の行をクリックすると_右の枠へ切り替わってフォーカスも移る(self):
        self.render(cockpit="early", windows=self.two_windows())
        first = self.wait_shown(bool, "枠に最初の Agent が入りません")
        sidebar = self.sidebar_pane()
        self.tmux("select-pane", "-t", sidebar)
        self.assertEqual(self.active_pane(), sidebar)
        screen = self.wait_screen(lambda scr: scr.count("New agent") >= 2)
        rows = [i for i, l in enumerate(screen.splitlines()) if "New agent" in l]
        self.click_row(rows[-1])  # 先頭が選ばれているので、もう一方をクリックする
        self.wait_shown(lambda v: v and v != first, "クリックした Agent が枠に入りません")
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while time.time() < deadline and self.active_pane() == sidebar:
            time.sleep(0.2)
        self.assertNotEqual(self.active_pane(), sidebar, "クリックしても右の枠へフォーカスが移りません")

    def test_cockpit_j_k_では_フォーカスは_sidebar_のまま(self):
        self.render(cockpit="early", windows=self.two_windows())
        first = self.wait_shown(bool, "枠に最初の Agent が入りません")
        sidebar = self.sidebar_pane()
        self.tmux("select-pane", "-t", sidebar)
        self.press("j")
        self.wait_shown(lambda v: v and v != first, "j で別の Agent に切り替わりません")
        time.sleep(1)
        self.assertEqual(self.active_pane(), sidebar)

    # --- WEB 欄: モード(auto / on / off)と、w(モード切り替え)・H(自宅の登録)・auto の判定の呼び出し ---

    def fake_web_bin(self):
        """tmux-agent-web-toggle の代わり。受け取った引数を 1 行ずつログへ書く。"""
        fake = os.path.join(self.dir, "fake-web-toggle")
        log = os.path.join(self.dir, "web-calls.log")
        with open(fake, "w") as f:
            f.write(f'#!/bin/bash\necho "$*" >> {log}\n')
        os.chmod(fake, 0o755)
        return fake, log

    def web_calls(self, log):
        if not os.path.exists(log):
            return []
        with open(log) as f:
            return f.read().splitlines()

    def web_env(self, mode=None, registered=False, running=False, extra=None):
        """WEB 欄の確認用の環境。mode は mode ファイル、registered は自宅の登録の有無、running は動いているサーバーの状態ファイル。"""
        if mode:
            with open(os.path.join(self.dir, "mode"), "w") as f:
                f.write(mode + "\n")
        if registered:
            with open(os.path.join(self.dir, "home-networks"), "w") as f:
                f.write("4c:85:8a:4a:25:80  # test\n")
        env = dict(extra or {})
        if running:
            state = os.path.join(self.dir, "web-state.json")
            with open(state, "w") as f:
                json.dump({"pid": os.getpid(), "port": 8765, "readOnly": False}, f)
            env["TMUX_AGENT_WEB_STATE"] = state
        return env

    def web_row(self, screen):
        return screen.splitlines()[-1]

    def test_web_既定は_auto_で_自宅が未登録なら_H_を案内する(self):
        row = self.web_row(self.render(extra_env=self.web_env()))
        self.assertIn("WEB auto off", row)
        self.assertIn("H home", row)

    def test_web_auto_で自宅が登録済みなら_w_を案内する(self):
        row = self.web_row(self.render(extra_env=self.web_env(registered=True)))
        self.assertIn("WEB auto off", row)
        self.assertIn("w mode", row)

    def test_web_auto_で動いていれば_ON_とポートと_URL_のコピーを出す(self):
        row = self.web_row(self.render(extra_env=self.web_env(registered=True, running=True)))
        self.assertIn("WEB auto ON :8765", row)
        self.assertIn("W copy", row)

    def test_web_on_と_off_のモードを出す(self):
        self.assertIn("WEB on", self.web_row(self.render(extra_env=self.web_env(mode="on", registered=True))))
        self.assertIn("WEB off", self.web_row(self.render(extra_env=self.web_env(mode="off", registered=True))))
        row = self.web_row(self.render(extra_env=self.web_env(mode="on", registered=True, running=True)))
        self.assertIn("WEB ON :8765", row)
        self.assertNotIn("auto", row)
        self.assertIn("W copy", row)
        self.assertIn("w mode", row)  # on のときは、幅に収まるので両方出る

    def test_web_どの状態でも_最下行で幅に収まる(self):
        for mode in ("auto", "on", "off"):
            for registered in (False, True):
                for running in (False, True):
                    screen = self.render(extra_env=self.web_env(mode=mode, registered=registered, running=running))
                    row = self.web_row(screen)
                    self.assertIn("WEB", row)
                    self.assertLessEqual(display_width(row), 31, (mode, registered, running, row))

    def test_web_w_でモードを切り替える(self):
        fake, log = self.fake_web_bin()
        self.render(extra_env=self.web_env(mode="off", extra={"AGENT_SIDEBAR_WEB_BIN": fake}))
        self.press("w")
        self.wait_screen(lambda _: "mode next --notify" in self.web_calls(log))
        self.assertIn("mode next --notify", self.web_calls(log))

    def test_web_H_で自宅を登録_解除する(self):
        fake, log = self.fake_web_bin()
        self.render(extra_env=self.web_env(mode="off", extra={"AGENT_SIDEBAR_WEB_BIN": fake}))
        self.press("H")
        self.wait_screen(lambda _: "home toggle --notify" in self.web_calls(log))
        self.assertIn("home toggle --notify", self.web_calls(log))

    def test_web_W_は_URL_をコピーする(self):
        fake, log = self.fake_web_bin()
        self.render(extra_env=self.web_env(mode="off", extra={"AGENT_SIDEBAR_WEB_BIN": fake}))
        self.press("W")
        self.wait_screen(lambda _: "copy --notify" in self.web_calls(log))

    def test_web_auto_のときだけ_自宅の判定を裏で呼ぶ(self):
        fake, log = self.fake_web_bin()
        self.render(extra_env=self.web_env(registered=True, extra={"AGENT_SIDEBAR_WEB_BIN": fake}))
        self.wait_screen(lambda _: "auto --notify" in self.web_calls(log))
        self.assertEqual(self.web_calls(log)[0], "auto --notify")

    def test_web_on_と_off_では_判定を呼ばない(self):
        for mode in ("on", "off"):
            fake, log = self.fake_web_bin()
            if os.path.exists(log):
                os.remove(log)
            self.render(extra_env=self.web_env(mode=mode, registered=True, extra={"AGENT_SIDEBAR_WEB_BIN": fake}))
            time.sleep(3)
            self.assertEqual(self.web_calls(log), [], mode)

    def test_web_判定は_15_秒おきで_毎回は呼ばない(self):
        fake, log = self.fake_web_bin()
        self.render(extra_env=self.web_env(registered=True, extra={"AGENT_SIDEBAR_WEB_BIN": fake}))
        time.sleep(6)
        self.assertEqual(len([c for c in self.web_calls(log) if c.startswith("auto")]), 1)

    def test_取得を裏で起動する(self):
        marker = os.path.join(self.dir, "fetched")
        fake = os.path.join(self.dir, "fake-fetch")
        with open(fake, "w") as f:
            f.write(f"#!/bin/bash\ntouch {marker}\n")
        os.chmod(fake, 0o755)
        self.render(extra_env={"AGENT_SIDEBAR_CODEX_USAGE_BIN": fake})
        self.wait_screen(lambda _: os.path.exists(marker))
        self.assertTrue(os.path.exists(marker))


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
