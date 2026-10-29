"""tmux-agent-calendar（Mac のカレンダーの予定の取得・キャッシュ・今日の予定の画面）のテスト。

偽の icalBuddy（決まった出力を返すスクリプト）を使うので、本物のカレンダーには触れない。
偽の icalBuddy は、受け取った引数も記録する（終日の予定を除く -ea などが渡っているかの確認用）。
"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "tmux-agent-calendar")


def stamp(day_offset, hhmm):
    """今日から day_offset 日後の hhmm の、icalBuddy の日時表記と epoch を返す。"""
    t = time.localtime(time.time() + day_offset * 86400)
    date = time.strftime("%Y-%m-%d", t)
    epoch = int(time.mktime(time.strptime(f"{date} {hhmm}", "%Y-%m-%d %H:%M")))
    return date, epoch


class CalendarTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cal.", dir="/tmp")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.cache = os.path.join(self.dir, "cache.txt")
        self.args_log = os.path.join(self.dir, "args.log")

    def fake_icalbuddy(self, output, code=0):
        path = os.path.join(self.dir, "fake-icalbuddy")
        out = os.path.join(self.dir, "out.txt")
        with open(out, "w") as f:
            f.write(output)
        with open(path, "w") as f:
            f.write(f'#!/bin/sh\necho "$@" > {self.args_log}\ncat {out}\nexit {code}\n')
        os.chmod(path, 0o755)
        return path

    def run_script(self, icalbuddy, *args, env=None):
        e = dict(os.environ, AGENT_CALENDAR_ICALBUDDY=icalbuddy, AGENT_CALENDAR_CACHE=self.cache, PYTHONDONTWRITEBYTECODE="1")
        e.update(env or {})
        return subprocess.run([SCRIPT, *args], capture_output=True, text=True, env=e)

    @staticmethod
    def read(path):
        with open(path) as f:
            return f.read()

    def events(self):
        lines = self.read(self.cache).splitlines()
        self.assertTrue(lines[0].startswith("F|"), lines)
        return [l.split("|") for l in lines[1:]]

    def block(self, day, start, end, title, extra=""):
        date, _ = stamp(day, start)
        return f"{date} at {start} - {end} ¦ {title}\n{extra}"

    def test_予定を_開始と終了の_epoch_とタイトルでキャッシュへ書く(self):
        _, s1 = stamp(1, "10:30")
        _, e1 = stamp(1, "11:00")
        out = self.block(1, "10:30", "11:00", "朝会", "       [参加者]A,B\n")
        # 今日の予定は、いまより後に終わるものだけ残る(23:59 までの予定なら、いつ実行しても残る)
        out += self.block(0, "00:00", "23:59", "終日に近い予定")
        self.assertEqual(self.run_script(self.fake_icalbuddy(out)).returncode, 0)
        rows = self.events()
        self.assertEqual([r[3] for r in rows], ["終日に近い予定", "朝会"])
        self.assertEqual(rows[1][:3], ["E", str(s1), str(e1)])

    def test_終わった予定は書かない(self):
        out = self.block(-1, "10:00", "11:00", "昨日の予定")
        self.assertEqual(self.run_script(self.fake_icalbuddy(out)).returncode, 0)
        self.assertEqual(self.events(), [])

    def test_日をまたぐ予定は_終了にも日付がつく(self):
        d0, s = stamp(0, "23:00")
        d1, e = stamp(1, "01:00")
        out = f"{d0} at 23:00 - {d1} at 01:00 ¦ 夜間作業\n"
        proc = self.run_script(self.fake_icalbuddy(out), "--stdout")
        row = [l.split("|") for l in proc.stdout.splitlines() if l.startswith("E|")][0]
        self.assertEqual(row[1:3], [str(s), str(e)])

    def test_終了時刻が無い予定は_開始と同じ時刻にする(self):
        date, s = stamp(1, "09:00")
        proc = self.run_script(self.fake_icalbuddy(f"{date} at 09:00 ¦ リマインド\n"), "--stdout")
        row = [l.split("|") for l in proc.stdout.splitlines() if l.startswith("E|")][0]
        self.assertEqual(row[1:3], [str(s), str(s)])

    def test_同じ開始_終了_タイトルの重複は_1つにする(self):
        out = self.block(1, "10:00", "11:00", "同じ予定") + self.block(1, "10:00", "11:00", "同じ予定")
        self.run_script(self.fake_icalbuddy(out))
        self.assertEqual(len(self.events()), 1)

    def test_会議の_URL_は本文から拾う_社内ツールの_URL_は拾わない(self):
        extra = "       [NASCA URL]https://nasca.example.jp/schedule/1\n       https://cyberagent.zoom.us/j/3100233677\n       PW：1234\n"
        self.run_script(self.fake_icalbuddy(self.block(1, "10:00", "11:00", "共有会", extra)))
        self.assertEqual(self.events()[0][4], "https://cyberagent.zoom.us/j/3100233677")

    def test_会議の_URL_が無ければ空(self):
        extra = "       [NASCA URL]https://nasca.example.jp/schedule/1\n"
        self.run_script(self.fake_icalbuddy(self.block(1, "10:00", "11:00", "対面", extra)))
        self.assertEqual(self.events()[0][4], "")

    def test_Google_Meet_と_Teams_も拾う(self):
        out = self.block(1, "10:00", "11:00", "a", "       https://meet.google.com/abc-defg-hij\n")
        out += self.block(1, "12:00", "13:00", "b", "       https://teams.microsoft.com/l/meetup-join/x\n")
        self.run_script(self.fake_icalbuddy(out))
        self.assertEqual([r[4] for r in self.events()], ["https://meet.google.com/abc-defg-hij", "https://teams.microsoft.com/l/meetup-join/x"])

    def test_タイトルの縦棒は全角にして_キャッシュの区切りと混ざらないようにする(self):
        self.run_script(self.fake_icalbuddy(self.block(1, "10:00", "11:00", "A|B")))
        self.assertEqual(self.events()[0][3], "A｜B")

    def test_icalBuddy_には_終日の予定を除く引数と_今日と明日を渡す(self):
        self.run_script(self.fake_icalbuddy(""))
        args = self.read(self.args_log)
        self.assertIn("-ea", args)
        self.assertIn("eventsToday+1", args)

    def test_除くカレンダーと対象のカレンダーを環境変数で渡せる(self):
        self.run_script(self.fake_icalbuddy(""), env={"AGENT_CALENDAR_EXCLUDE": "誕生日", "AGENT_CALENDAR_INCLUDE": "仕事"})
        args = self.read(self.args_log)
        self.assertIn("-ec 誕生日", args)
        self.assertIn("-ic 仕事", args)

    def test_予定が無ければ_取得時刻だけのキャッシュを書く(self):
        self.assertEqual(self.run_script(self.fake_icalbuddy("")).returncode, 0)
        self.assertEqual(self.events(), [])

    def test_icalBuddy_が失敗したら_キャッシュを書き換えない(self):
        with open(self.cache, "w") as f:
            f.write("F|1\nE|1|2|古い|\n")
        proc = self.run_script(self.fake_icalbuddy("", code=1))
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.read(self.cache), "F|1\nE|1|2|古い|\n")

    def test_icalBuddy_が無い_Mac_では_何も書かずに終わる(self):
        proc = self.run_script("/nonexistent/icalBuddy")
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(os.path.exists(self.cache))

    def test_stdout_は_キャッシュへ書かない(self):
        proc = self.run_script(self.fake_icalbuddy(self.block(1, "10:00", "11:00", "朝会")), "--stdout")
        self.assertIn("E|", proc.stdout)
        self.assertFalse(os.path.exists(self.cache))

    # ---- 今日の予定の画面(--agenda): cockpit の右の枠 ----

    def agenda(self, out, now, width=50, height=24, color="never"):
        """一覧と横棒の画面(--list)。"""
        return self.run_script(self.fake_icalbuddy(out), "--agenda", "--list", "--color", color, "--width", str(width), "--height", str(height),
                               env={"AGENT_CALENDAR_NOW": now}).stdout

    def grid(self, out, now, width=50, height=44, color="never"):
        """日表示(縦の時間軸に予定のブロックを置く)。"""
        return self.run_script(self.fake_icalbuddy(out), "--agenda", "--color", color, "--width", str(width), "--height", str(height),
                               env={"AGENT_CALENDAR_NOW": now}).stdout

    def row(self, screen, text):
        """text を含む行(時刻の欄を除いた部分は、そのまま見える)。"""
        return next(l for l in screen.splitlines() if text in l)

    def test_agenda_終わった予定は薄く_進行中には印_これからの予定は時間つき(self):
        today = stamp(0, "00:00")[0]
        out = "".join(f"{today} at {a} - {b} ¦ {t}\n" for a, b, t in (("09:00", "10:00", "朝会"), ("13:00", "14:00", "進行中の会議"), ("16:00", "17:00", "夕会")))
        screen = self.agenda(out, f"{today} 13:30")
        self.assertIn("  09:00-10:00 朝会", screen)
        self.assertIn("▶ 13:00-14:00 進行中の会議", screen)
        self.assertIn("  16:00-17:00 夕会", screen)

    def test_agenda_明日の予定は見出しで分ける(self):
        today = stamp(0, "00:00")[0]
        tomorrow = stamp(1, "00:00")[0]
        out = f"{today} at 15:00 - 16:00 ¦ 今日の予定\n{tomorrow} at 10:00 - 11:00 ¦ 明日の予定\n"
        screen = self.agenda(out, f"{today} 09:00")
        self.assertLess(screen.index("今日の予定"), screen.index("明日"))
        self.assertLess(screen.index("明日"), screen.index("明日の予定"))

    def test_agenda_会議の_URL_は予定の下に出す(self):
        today = stamp(0, "00:00")[0]
        out = f"{today} at 15:00 - 16:00 ¦ 共有会\n       https://example.zoom.us/j/1\n"
        screen = self.agenda(out, f"{today} 09:00")
        self.assertLess(screen.index("共有会"), screen.index("https://example.zoom.us/j/1"))

    def test_agenda_予定が無ければ_その旨を出す(self):
        self.assertIn("予定はありません", self.agenda("", f"{stamp(0, '00:00')[0]} 09:00"))

    def test_agenda_幅と高さに収める(self):
        today = stamp(0, "00:00")[0]
        out = "".join(f"{today} at {h:02d}:00 - {h:02d}:30 ¦ {'長いタイトル' * 10}{h}\n" for h in range(8, 22))
        screen = self.agenda(out, f"{today} 07:00", width=30, height=10)
        lines = screen.splitlines()
        self.assertLessEqual(len(lines), 10)
        import unicodedata
        for line in lines:
            self.assertLessEqual(sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in line), 30, line)

    # ---- 埋まり具合の横棒と空き時間 ----

    def day_events(self, *rows, day=None):
        day = day or stamp(0, "00:00")[0]
        return "".join(f"{day} at {a} - {b} ¦ {t}\n" for a, b, t in rows)

    def bar(self, screen):
        """今日の横棒の行(█ と ░ だけでできた最初の行)。"""
        return next(l.strip() for l in screen.splitlines() if l.strip() and set(l.strip()) <= {"█", "░"})

    def test_agenda_予定のある時間は_埋まり_無い時間は空きとして横棒に出る(self):
        today = stamp(0, "00:00")[0]
        # 9:00-19:00 を 15 分ごと(40 マス)で描く。9:30-10:00 と 13:00-14:00 が埋まる
        screen = self.agenda(self.day_events(("09:30", "10:00", "朝会"), ("13:00", "14:00", "共有会")), f"{today} 08:00")
        bar = self.bar(screen)
        self.assertEqual(len(bar), 40)
        self.assertEqual(bar[:2], "░░")
        self.assertEqual(bar[2:4], "██")
        self.assertEqual(bar[16:20], "████")
        self.assertEqual(bar.count("█"), 6)

    def test_agenda_空き時間を一覧する_30分に満たない隙間は数えない(self):
        today = stamp(0, "00:00")[0]
        out = self.day_events(("09:00", "10:00", "a"), ("10:20", "12:00", "b"), ("13:00", "19:00", "c"))
        screen = self.agenda(out, f"{today} 08:00", width=80)
        self.assertIn("空き 12:00-13:00", screen)
        self.assertNotIn("10:00-10:20", screen)

    def test_agenda_今日の空きは_いま以降だけ(self):
        today = stamp(0, "00:00")[0]
        screen = self.agenda(self.day_events(("13:00", "14:00", "共有会")), f"{today} 11:10", width=80)
        self.assertIn("空き 11:10-13:00 14:00-19:00", screen)

    def test_agenda_いまの位置に印と時刻を出す(self):
        today = stamp(0, "00:00")[0]
        self.assertIn("▲ 11:10", self.agenda("", f"{today} 11:10"))

    def test_agenda_勤務時間の外の予定があれば_時間帯が広がる(self):
        today = stamp(0, "00:00")[0]
        screen = self.agenda(self.day_events(("07:30", "08:30", "早朝"), ("20:00", "21:30", "夜")), f"{today} 06:00", width=100)
        self.assertEqual(len(self.bar(screen)), (22 - 7) * 4)

    def test_agenda_重なる予定は_1つの埋まりとして空きを数える(self):
        today = stamp(0, "00:00")[0]
        out = self.day_events(("09:00", "12:00", "長い会議"), ("10:00", "11:00", "重なる"), ("12:00", "19:00", "続き"))
        self.assertIn("空きなし", self.agenda(out, f"{today} 08:00"))

    def test_agenda_明日の棒は全部が空きで_空きは朝から(self):
        today = stamp(0, "00:00")[0]
        screen = self.agenda("", f"{today} 08:00", width=80)
        self.assertEqual(screen.count("空き 10:00-19:00"), 2)

    def test_agenda_幅が狭ければ_粗い棒にする(self):
        today = stamp(0, "00:00")[0]
        self.assertEqual(len(self.bar(self.agenda("", f"{today} 08:00", width=30))), 18)

    # ---- 日表示(既定): Google カレンダーの「日」のように縦の時間軸へ置く ----

    def test_日表示_予定は開始の時刻の行に出て_時間の長さだけ縦に伸びる(self):
        today = stamp(0, "00:00")[0]
        screen = self.grid(self.day_events(("10:00", "11:00", "定例")), f"{today} 08:00")
        lines = screen.splitlines()
        i = next(i for i, l in enumerate(lines) if "▌ 定例" in l)
        self.assertTrue(lines[i].startswith("10:00"), lines[i])
        # タイトルの次の行に時間が出て、1 時間ぶん(15 分刻みなら 4 行)が ▌ でつながる
        self.assertIn("▌ 10:00-11:00", lines[i + 1])
        self.assertEqual(sum(1 for l in lines if l[6:].startswith("▌")), 4)

    def test_日表示_左の欄には_1時間ごとの時刻が出る(self):
        today = stamp(0, "00:00")[0]
        screen = self.grid("", f"{today} 08:00")
        for h in ("10:00", "12:00", "18:00"):
            self.assertIn(h, screen)

    def test_日表示_予定の無い時間は空白_予定のある行だけにブロックが出る(self):
        today = stamp(0, "00:00")[0]
        screen = self.grid(self.day_events(("13:00", "14:00", "共有会")), f"{today} 08:00")
        self.assertEqual(sum(1 for l in screen.splitlines() if "▌" in l), 4)

    def test_日表示_重なる予定は横に並ぶ(self):
        today = stamp(0, "00:00")[0]
        out = self.day_events(("10:00", "11:00", "A予定"), ("10:00", "11:00", "B予定"))
        line = self.row(self.grid(out, f"{today} 08:00"), "A予定")
        self.assertIn("B予定", line)
        self.assertLess(line.index("A予定"), line.index("B予定"))

    def test_日表示_いまの行には現在時刻が出る(self):
        today = stamp(0, "00:00")[0]
        screen = self.grid("", f"{today} 11:10")
        self.assertIn("11:10", screen)

    def test_日表示_空き時間の行がある(self):
        today = stamp(0, "00:00")[0]
        screen = self.grid(self.day_events(("13:00", "14:00", "共有会")), f"{today} 11:10", width=70)
        self.assertIn("空き 11:10-13:00 14:00-19:00", screen)

    def test_日表示_幅が広ければ_明日を右に並べる_狭ければ今日だけ(self):
        today = stamp(0, "00:00")[0]
        tomorrow = stamp(1, "00:00")[0]
        out = self.day_events(("10:00", "11:00", "今日の予定")) + self.day_events(("10:00", "11:00", "明日の予定"), day=tomorrow)
        wide = self.grid(out, f"{today} 08:00", width=100)
        self.assertIn("明日の予定", self.row(wide, "今日の予定"))
        narrow = self.grid(out, f"{today} 08:00", width=50)
        self.assertNotIn("明日の予定", narrow)

    def test_日表示_狭い列では_今日の時間帯が終わっていれば明日を出す(self):
        today = stamp(0, "00:00")[0]
        tomorrow = stamp(1, "00:00")[0]
        out = self.day_events(("10:00", "11:00", "明日の予定"), day=tomorrow)
        self.assertIn("明日の予定", self.grid(out, f"{today} 20:00", width=50))

    def test_日表示_行数が足りなければ_いまの付近の時間帯だけを出す(self):
        today = stamp(0, "00:00")[0]
        screen = self.grid("", f"{today} 15:30", width=50, height=8)
        lines = screen.splitlines()
        self.assertLessEqual(len(lines), 8)
        self.assertIn("15:30", screen)

    def test_日表示_幅と高さに収まる(self):
        import unicodedata
        today = stamp(0, "00:00")[0]
        out = "".join(f"{today} at {h:02d}:00 - {h:02d}:45 ¦ {'長いタイトル' * 10}{h}\n" for h in range(8, 22))
        for width in (30, 50, 100):
            lines = self.grid(out, f"{today} 07:00", width=width, height=12).splitlines()
            self.assertLessEqual(len(lines), 12)
            for line in lines:
                self.assertLessEqual(sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in line), width, line)

    def test_日表示_色ありでも_行の幅は同じ(self):
        import re
        today = stamp(0, "00:00")[0]
        out = self.day_events(("10:00", "11:00", "定例"), ("10:30", "11:30", "重なり"))
        plain = self.grid(out, f"{today} 08:00", width=100).splitlines()
        colored = [re.sub(r"\x1b\[[0-9;]*m", "", l) for l in self.grid(out, f"{today} 08:00", width=100, color="always").splitlines()]
        self.assertEqual(plain, colored)

    def test_日表示_ブロックの最後の行に下線を引いて_続く予定との境目を示す(self):
        today = stamp(0, "00:00")[0]
        underline = "\x1b[4m\x1b[58;5;16m"  # 黒い下線
        one = self.grid(self.day_events(("10:00", "11:00", "定例")), f"{today} 08:00", color="always")
        self.assertEqual(sum(underline in l for l in one.splitlines()), 1)
        # 連続する 2 つの予定は、それぞれの最後の行に引く(境目が 2 本の下線で分かる)
        two = self.grid(self.day_events(("10:00", "11:00", "前の予定"), ("11:00", "12:00", "後の予定")), f"{today} 08:00", color="always")
        self.assertEqual(sum(underline in l for l in two.splitlines()), 2)

    def test_空き時間は_10時から19時の中だけで数える(self):
        today = stamp(0, "00:00")[0]
        # 9:30-10:00 は勤務時間の外。10:00 からが空き
        out = self.day_events(("09:30", "10:00", "朝会"), ("13:00", "14:00", "共有会"))
        screen = self.grid(out, f"{today} 08:00", width=70)
        self.assertIn("空き 10:00-13:00 14:00-19:00", screen)
        self.assertNotIn("空き 09:", screen)

    def test_見出しに_空きの残りと全体を出す(self):
        today = stamp(0, "00:00")[0]
        # 10:30-11:30 / 13:00-14:00 / 15:00-15:30 が埋まる。空きは 10:00-10:30、11:30-13:00、14:00-15:00、15:30-19:00 の計 6h30m
        out = self.day_events(("10:30", "11:30", "a"), ("13:00", "14:00", "b"), ("15:00", "15:30", "c"))
        self.assertIn("空き 残り 6h30m / 全体 6h30m", self.grid(out, f"{today} 08:00", width=100))
        # 11:10 には 10:00-10:30 が過ぎて、残りは 6h(11:10-11:30 の 20 分は 30 分に満たないので数えない)
        self.assertIn("空き 残り 6h / 全体 6h30m", self.grid(out, f"{today} 11:10", width=100))

    def test_見出しの空きは_勤務時間が終わると残り_0_になる_明日は全体だけ(self):
        today = stamp(0, "00:00")[0]
        screen = self.grid("", f"{today} 19:30", width=100)
        self.assertIn("空き 残り 0m / 全体 9h", screen)
        self.assertIn("空き 9h", screen.splitlines()[0].split("明日")[1])

    def test_check_は_カレンダーの件数を出す(self):
        proc = self.run_script(self.fake_icalbuddy("• 仕事\n  type: CalDAV\n• 個人\n  type: Local\n"), "--check")
        self.assertIn("2 件", proc.stdout)


if __name__ == "__main__":
    unittest.main()
