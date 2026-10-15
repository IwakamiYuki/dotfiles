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

    def render(self, limits=None, cred=None, today=None, colors=False, daily_dir=None, open_cmd=None, obsidian_config=None, extra_env=None, cockpit=False):
        """sidebar を起動して、描画が出そろった画面を返す。None のファイルは作らない。
        today: 「今日」の日付(YYYY-MM-DD)。着地予想の色が日付で変わるので、固定して確認する。
        colors: True なら色の制御文字つき(capture-pane -e)で返す。
        daily_dir: Daily Note のディレクトリ(AGENT_SIDEBAR_DAILY_DIR)。None なら未設定。
        open_cmd: o キーで呼ぶコマンド(AGENT_SIDEBAR_OPEN_CMD)。実際の open は呼ばない。
        obsidian_config: Obsidian の obsidian.json のパス(AGENT_DAILY_OBSIDIAN_CONFIG)。None なら存在しないパスにして、本物の設定を読まない。
        extra_env: sidebar に足す環境変数({名前: 値})。
        cockpit: True なら、描画のあとで window を cockpit にして(@agent_cockpit=1)、cockpit の欄(d のヒント)が出るまで待つ。"""
        rl_file = os.path.join(self.dir, "rate-limits.json")
        cr_file = os.path.join(self.dir, "credits.json")
        for path, data in ((rl_file, limits), (cr_file, cred)):
            if data is not None:
                with open(path, "w") as f:
                    json.dump(data, f)
        env = " ".join(
            [
                "env",  # TMUX は外さない: pane に設定される専用ソケットの値を引き継ぎ、sidebar が普段の tmux ではなく一時サーバーを見るようにする
                f"AGENT_SIDEBAR_RATE_LIMITS={rl_file}",
                f"AGENT_SIDEBAR_CREDITS={cr_file}",
                "AGENT_SIDEBAR_CLAUDE_BIN=true",
                f"AGENT_SIDEBAR_ALERT_STATE={self.dir}/none",
                f"AGENT_SIDEBAR_TITLE_CACHE={self.dir}/titles",
                f"AGENT_SIDEBAR_CLAUDE_CACHE={self.dir}/claude-cache",
                f"AGENT_SIDEBAR_SESSIONS_DIR={self.dir}/sessions",
                f"AGENT_SIDEBAR_TODAY={today}" if today else "AGENT_SIDEBAR_TODAY=",
                f"AGENT_SIDEBAR_DAILY_DIR={daily_dir}" if daily_dir else "AGENT_SIDEBAR_DAILY_DIR=",
                f"AGENT_SIDEBAR_OPEN_CMD={open_cmd}" if open_cmd else "AGENT_SIDEBAR_OPEN_CMD=true",
                f"AGENT_DAILY_OBSIDIAN_CONFIG={obsidian_config or self.dir + '/no-obsidian.json'}",
                f"TMUX_AGENT_WEB_STATE={self.dir}/no-web-state.json",  # 普段の WEB サーバーの状態を読まない
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
        self.assertIn("🚄", lines[-2])

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

    def daily_note(self, age_sec):
        """今日の Daily Note を、age_sec 秒前に更新されたことにして作る。ディレクトリを返す。"""
        d = os.path.join(self.dir, "daily")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, time.strftime("%Y-%m-%d") + ".md")
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
