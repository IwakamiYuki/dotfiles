"""tmux-agent-tasks（Obsidian のタスクの一覧・完了）のテスト。

タスクは一時ディレクトリに作る（本物の vault には触れない）。対話の画面は、専用ソケット（tmux -S <一時ソケット>）の
別 tmux サーバーで本物のスクリプトを動かし、send-keys と capture-pane で読む。普段使っている tmux には触れない
（kill-server も一時ソケットを明示する）。ソケットのパスは長いと接続できない（sun_path の上限）ので、短い /tmp 直下に置く。
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "tmux-agent-tasks")
TODAY = "2026-10-17"
RENDER_TIMEOUT_SEC = 8

_loader = importlib.machinery.SourceFileLoader("tmux_agent_tasks", SCRIPT)
_spec = importlib.util.spec_from_loader("tmux_agent_tasks", _loader)
tasks_mod = importlib.util.module_from_spec(_spec)
sys.modules["tmux_agent_tasks"] = tasks_mod  # dataclass が自分のモジュールを引くために要る
_loader.exec_module(tasks_mod)


def task_text(done="false", tags=("mimi", "bug"), body="タスクの詳細説明\n\n## 関連情報\n- 元の Daily Note: [[x]]\n\n## 詳細\n背景のメモ\n"):
    tag_lines = "".join(f"  - {t}\n" for t in tags)
    return f"---\ndone: {done}\ntags:\n{tag_lines}---\n{body}"


class TasksTestBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="tsk.", dir="/tmp")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.tasks = Path(self.dir, "tasks")
        self.tasks.mkdir()

    def write(self, name, text=None, **kw):
        path = self.tasks / name
        path.write_text(text if text is not None else task_text(**kw), encoding="utf-8")
        return path

    def run_cli(self, *args, env=None):
        full = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": self.dir, "AGENT_TASKS_NO_TMUX": "1",
                "AGENT_TASKS_TODAY": TODAY, **(env or {})}
        return subprocess.run(["python3", "-I", SCRIPT, *args], env=full, capture_output=True, text=True, timeout=30)


class ParseTest(TasksTestBase):
    def test_frontmatter_とファイル名を読む(self):
        path = self.write("2026-10-16-mimi-おでかけ動画-キャッシュ削除.md", tags=("mimi", "feature"))
        task = tasks_mod.parse_task(path)
        self.assertEqual(task.title, "mimi-おでかけ動画-キャッシュ削除")
        self.assertEqual(str(task.created), "2026-10-16")
        self.assertEqual((task.project, task.category), ("mimi", "feature"))
        self.assertFalse(task.done)
        self.assertEqual(task.body[0], "タスクの詳細説明")

    def test_done_true_は_完了(self):
        task = tasks_mod.parse_task(self.write("2026-10-16-a.md", done="true"))
        self.assertTrue(task.done)

    def test_インラインのタグも読む(self):
        path = self.write("2026-10-16-a.md", "---\ndone: false\ntags: [wow, release]\n---\n本文\n")
        task = tasks_mod.parse_task(path)
        self.assertEqual(task.tags, ["wow", "release"])

    def test_タグが無ければ_プロジェクトは_ハイフン(self):
        task = tasks_mod.parse_task(self.write("2026-10-16-a.md", "---\ndone: false\n---\n本文\n"))
        self.assertEqual((task.project, task.category), ("-", ""))

    def test_frontmatter_が無いファイルも_落ちずに未完了で読む(self):
        task = tasks_mod.parse_task(self.write("2026-10-16-a.md", "ただのメモ\n"))
        self.assertFalse(task.done)
        self.assertEqual(task.tags, [])

    def test_日付で始まらないファイル名は_更新日を作成日にする(self):
        task = tasks_mod.parse_task(self.write("memo.md"))
        self.assertEqual(task.title, "memo")
        self.assertIsNotNone(task.created)

    def test_md_以外と隠しファイルは読まない(self):
        self.write("2026-10-16-a.md")
        (self.tasks / "note.txt").write_text("x")
        (self.tasks / ".2026-10-16-b.md.1.tmp").write_text("x")
        (self.tasks / ".hidden.md").write_text(task_text())
        self.assertEqual([t.path.name for t in tasks_mod.load_tasks(self.tasks)], ["2026-10-16-a.md"])


class SetDoneTest(TasksTestBase):
    def test_done_を_ちょうど_CI_の_grep_に合う書式にする(self):
        path = self.write("2026-10-16-a.md", done="false")
        task = tasks_mod.parse_task(path)
        ok, _ = tasks_mod.set_done(task, True)
        self.assertTrue(ok)
        lines = path.read_text(encoding="utf-8").split("\n")
        self.assertIn("done: true", lines)  # CI は ^done: true$ で消す
        self.assertNotIn("done: false", lines)

    def test_本文とタグは変えない(self):
        path = self.write("2026-10-16-a.md", tags=("wow", "release"))
        before = path.read_text(encoding="utf-8")
        tasks_mod.set_done(tasks_mod.parse_task(path), True)
        self.assertEqual(path.read_text(encoding="utf-8"), before.replace("done: false", "done: true", 1))

    def test_戻せる(self):
        path = self.write("2026-10-16-a.md")
        task = tasks_mod.parse_task(path)
        tasks_mod.set_done(task, True)
        ok, _ = tasks_mod.set_done(task, False)
        self.assertTrue(ok)
        self.assertIn("done: false", path.read_text(encoding="utf-8").split("\n"))
        self.assertFalse(task.done)

    def test_done_行が無ければ_足す(self):
        path = self.write("2026-10-16-a.md", "---\ntags:\n  - mimi\n---\n本文\n")
        ok, _ = tasks_mod.set_done(tasks_mod.parse_task(path), True)
        self.assertTrue(ok)
        self.assertEqual(path.read_text(encoding="utf-8"), "---\ndone: true\ntags:\n  - mimi\n---\n本文\n")

    def test_本文の_done_は_書き換えない(self):
        path = self.write("2026-10-16-a.md", "---\ndone: false\n---\ndone: false と書いた本文\n")
        tasks_mod.set_done(tasks_mod.parse_task(path), True)
        self.assertEqual(path.read_text(encoding="utf-8"), "---\ndone: true\n---\ndone: false と書いた本文\n")

    def test_読み込み後に変わっていたら_上書きしない(self):
        path = self.write("2026-10-16-a.md")
        task = tasks_mod.parse_task(path)
        path.write_text(task_text(body="別の場所で書き換えられた本文\n"), encoding="utf-8")
        os.utime(path, (task.mtime + 5, task.mtime + 5))
        ok, why = tasks_mod.set_done(task, True)
        self.assertFalse(ok)
        self.assertIn("変わっていました", why)
        self.assertIn("別の場所で", path.read_text(encoding="utf-8"))
        self.assertIn("done: false", path.read_text(encoding="utf-8"))

    def test_frontmatter_が無ければ_書き換えない(self):
        path = self.write("2026-10-16-a.md", "ただのメモ\n")
        ok, _ = tasks_mod.set_done(tasks_mod.parse_task(path), True)
        self.assertFalse(ok)
        self.assertEqual(path.read_text(encoding="utf-8"), "ただのメモ\n")

    def test_一時ファイルを残さない_権限を保つ(self):
        path = self.write("2026-10-16-a.md")
        path.chmod(0o640)
        tasks_mod.set_done(tasks_mod.parse_task(path), True)
        self.assertEqual(sorted(p.name for p in self.tasks.iterdir()), ["2026-10-16-a.md"])
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)


class CliTest(TasksTestBase):
    def test_status_は_未完了と古いものと完了待ちを数える(self):
        self.write("2026-10-16-new.md")                     # 1 日前
        self.write("2026-09-01-old.md")                     # 46 日前 → 30 日超
        self.write("2026-01-01-older.md")                   # 289 日前
        self.write("2026-10-10-done.md", done="true")       # 完了待ち
        proc = self.run_cli("--status", "--dir", str(self.tasks))
        self.assertEqual(proc.stdout.strip(), f"3 2 1 {self.tasks}")

    def test_30_日ちょうどは古くない(self):
        self.write("2026-09-17-x.md")  # 30 日前
        self.assertEqual(self.run_cli("--status", "--dir", str(self.tasks)).stdout.split()[:3], ["1", "0", "0"])

    def test_ディレクトリが決まらなければ_終了コード_2(self):
        proc = self.run_cli("--status", env={"AGENT_DAILY_OBSIDIAN_CONFIG": os.path.join(self.dir, "none.json")})
        self.assertEqual(proc.returncode, 2)

    def test_存在しないディレクトリは_終了コード_2(self):
        self.assertEqual(self.run_cli("--status", "--dir", os.path.join(self.dir, "missing")).returncode, 2)

    def test_環境変数でディレクトリを指定できる(self):
        self.write("2026-10-16-a.md")
        proc = self.run_cli("--print-dir", env={"AGENT_TASKS_DIR": str(self.tasks)})
        self.assertEqual(proc.stdout.strip(), str(self.tasks))

    def test_Obsidian_の設定から_vault_のタスクのディレクトリを求める(self):
        vault = Path(self.dir, "vault")
        (vault / "12-task" / "12-01-tasks").mkdir(parents=True)
        (vault / "12-task" / "12-01-tasks" / "2026-10-16-a.md").write_text(task_text())
        config = Path(self.dir, "obsidian.json")
        config.write_text(json.dumps({"vaults": {"a": {"path": str(vault), "open": True}, "b": {"path": "/other"}}}))
        proc = self.run_cli("--status", env={"AGENT_DAILY_OBSIDIAN_CONFIG": str(config)})
        self.assertEqual(proc.stdout.split()[0], "1")
        self.assertTrue(proc.stdout.strip().endswith("12-task/12-01-tasks"))

    def test_開いている_vault_が無く_複数あれば_決めない(self):
        for name in ("a", "b"):
            (Path(self.dir, name, "12-task", "12-01-tasks")).mkdir(parents=True)
        config = Path(self.dir, "obsidian.json")
        config.write_text(json.dumps({"vaults": {n: {"path": str(Path(self.dir, n))} for n in ("a", "b")}}))
        self.assertEqual(self.run_cli("--status", env={"AGENT_DAILY_OBSIDIAN_CONFIG": str(config)}).returncode, 2)

    def test_list_は_古い順で_完了待ちは最後(self):
        self.write("2026-10-16-b-new.md", tags=("wow", "release"))
        self.write("2026-09-01-a-old.md", tags=("mimi", "bug"))
        self.write("2026-08-01-z-done.md", done="true")
        lines = self.run_cli("--list", "--dir", str(self.tasks)).stdout.splitlines()
        self.assertEqual([l.split()[-1] for l in lines], ["a-old", "b-new", "z-done"])
        self.assertRegex(lines[0], r"^\s+46d\s+mimi\s+bug\s+a-old$")
        self.assertTrue(lines[2].startswith("x "))

    def test_端末が無ければ対話は始めない(self):
        self.write("2026-10-16-a.md")
        proc = self.run_cli("--dir", str(self.tasks))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("端末", proc.stderr)


class DisplayTest(unittest.TestCase):
    def test_fit_は_表示幅で収める(self):
        self.assertEqual(tasks_mod.fit("abcdef", 4), "abc…")
        self.assertEqual(tasks_mod.fit("日本語のタイトル", 7), "日本語…")  # 2 桁 × 3 + … = 7
        self.assertEqual(tasks_mod.fit("abc", 5), "abc")
        self.assertEqual(tasks_mod.fit("abc", 0), "")

    def test_一覧のタイトルから_先頭のプロジェクト名を省く(self):
        def t(title, tags):
            return tasks_mod.Task(Path(title), title, None, tags, False, [], 0.0)

        self.assertEqual(t("mimi-オフライン対応", ["mimi"]).short_title, "オフライン対応")
        self.assertEqual(t("mimi-オフライン対応", ["wow"]).short_title, "mimi-オフライン対応")  # 別のプロジェクトなら省かない
        self.assertEqual(t("mimi-", ["mimi"]).short_title, "mimi-")                              # 全部消えるなら省かない
        self.assertEqual(t("mimi-x", []).short_title, "mimi-x")                                  # タグが無ければ省かない

    def test_並び替え(self):
        def t(name, created, tags, done=False):
            return tasks_mod.Task(Path(name), name, tasks_mod.dt.date.fromisoformat(created), tags, done, [], 0.0)

        items = [t("b", "2026-10-01", ["wow"]), t("a", "2026-09-01", ["mimi"]), t("c", "2026-08-01", ["mimi"], done=True)]
        names = lambda mode: [x.title for x in tasks_mod.sort_tasks(items, mode)]  # noqa: E731
        self.assertEqual(names(0), ["a", "b", "c"])   # 古い順。完了待ちは最後
        self.assertEqual(names(1), ["b", "a", "c"])   # 新しい順
        self.assertEqual(names(2), ["a", "b", "c"])   # プロジェクト別(mimi → wow)
        self.assertEqual(names(3), ["a", "b", "c"])   # 名前順


class InteractiveTest(TasksTestBase):
    """専用ソケットの別 tmux で、本物の対話画面を動かす。"""

    def setUp(self):
        super().setUp()
        self.sock = os.path.join(self.dir, "s")
        self.addCleanup(self.stop)
        self.write("2026-10-16-mimi-新しいタスク.md", tags=("mimi", "feature"), body="新しいタスクの説明\n")
        self.write("2026-08-01-wow-古いタスク.md", tags=("wow", "bug"), body="古いタスクの説明\n\n## 詳細\n長引いている\n")
        self.write("2026-09-20-mimi-中くらい.md", tags=("mimi", "refactor"))

    def stop(self):
        subprocess.run(["tmux", "-S", self.sock, "kill-server"], capture_output=True)  # 一時ソケットのサーバーだけ

    def tmux(self, *args):
        return subprocess.run(["tmux", "-S", self.sock, *args], capture_output=True, text=True)

    def start(self, extra_env="", width=100, height=30):
        cmd = (f"env AGENT_TASKS_NO_TMUX=1 AGENT_TASKS_TODAY={TODAY} AGENT_TASKS_OPEN_CMD='{self.dir}/fake-open' "
               f"EDITOR='{self.dir}/fake-editor' {extra_env} python3 -I {SCRIPT} --dir {self.tasks}")
        subprocess.run(["tmux", "-S", self.sock, "-f", "/dev/null", "new-session", "-d", "-s", "t", "-x", str(width), "-y", str(height), cmd], check=True)
        return self.wait(lambda s: "TASKS" in s)

    def screen(self):
        return self.tmux("capture-pane", "-p", "-t", "t").stdout

    def wait(self, predicate):
        deadline = time.time() + RENDER_TIMEOUT_SEC
        screen = ""
        while time.time() < deadline:
            screen = self.screen()
            if predicate(screen):
                return screen
            time.sleep(0.1)
        self.fail(f"期待した画面になりませんでした:\n{screen}")

    def keys(self, *keys):
        self.tmux("send-keys", "-t", "t", *keys)

    def selected_title(self, screen):
        """詳細欄の見出し(選択中のタスク)。罫線の次の行。"""
        lines = screen.splitlines()
        rule = next(i for i, l in enumerate(lines) if l.startswith("─"))
        return lines[rule + 1].strip()

    def test_古い順に並び_先頭が選ばれ_詳細に本文が出る(self):
        screen = self.start()
        rows = [l for l in screen.splitlines() if "d  " in l and ("mimi" in l or "wow" in l)]
        self.assertEqual([r.split()[-1] for r in rows], ["古いタスク", "中くらい", "新しいタスク"])
        self.assertEqual(self.selected_title(screen), "wow-古いタスク")
        self.assertIn("古いタスクの説明", screen)
        self.assertIn("長引いている", screen)
        self.assertNotIn("関連情報", screen)  # 見出しは出さない
        self.assertIn("3 件", screen)
        self.assertIn("30日超 1", screen)  # 77 日前だけ。27 日前の「中くらい」は古くない

    def test_jk_で選択が動き_詳細が追従する(self):
        self.start()
        self.keys("j")
        self.assertEqual(self.selected_title(self.wait(lambda s: "mimi-中くらい" in s)), "mimi-中くらい")
        self.keys("G")
        self.wait(lambda s: self.selected_title(s) == "mimi-新しいタスク")
        self.keys("k", "k")
        self.wait(lambda s: self.selected_title(s) == "wow-古いタスク")

    def test_x_で_done_true_になり_戻せる(self):
        self.start()
        self.keys("x")
        screen = self.wait(lambda s: "CI が削除" in s)
        self.assertIn("完了待ち 1", screen)
        target = self.tasks / "2026-08-01-wow-古いタスク.md"
        self.assertIn("done: true", target.read_text(encoding="utf-8").split("\n"))
        self.keys("x")
        screen = self.wait(lambda s: "未完了に戻しました" in s)
        self.assertIn("done: false", target.read_text(encoding="utf-8").split("\n"))
        self.assertNotIn("完了待ち", screen)

    def test_完了にしたタスクは_最後へ移り_選択は同じタスクのまま(self):
        self.start()
        self.keys("x")
        screen = self.wait(lambda s: "CI が削除" in s)
        rows = [l for l in screen.splitlines() if "d  " in l and ("mimi" in l or "wow" in l)]
        self.assertEqual(rows[-1].split()[-1], "古いタスク")
        self.assertIn("✓", rows[-1])
        self.assertEqual(self.selected_title(screen), "wow-古いタスク")

    def test_s_で並びが変わる(self):
        self.start()
        self.keys("s")
        screen = self.wait(lambda s: "新しい順" in s)
        rows = [l for l in screen.splitlines() if "d  " in l and ("mimi" in l or "wow" in l)]
        self.assertEqual(rows[0].split()[-1], "新しいタスク")
        self.keys("s")
        screen = self.wait(lambda s: "プロジェクト別" in s)
        rows = [l for l in screen.splitlines() if "d  " in l and ("mimi" in l or "wow" in l)]
        self.assertEqual([r.split()[-1] for r in rows], ["中くらい", "新しいタスク", "古いタスク"])  # mimi(古い順) → wow

    def test_f_でプロジェクトを絞り込む(self):
        self.start()
        self.keys("f")  # タスクが多い順: mimi(2) → wow(1)
        screen = self.wait(lambda s: "絞り込み: mimi" in s)
        self.assertNotIn("古いタスク", [l.split()[-1] for l in screen.splitlines() if "d  " in l])
        self.keys("f")
        self.wait(lambda s: "絞り込み: wow" in s)
        self.keys("f")
        self.wait(lambda s: "絞り込み: すべて" in s)

    def test_Enter_で_Obsidian_のパス指定の_URL_を開く(self):
        log = os.path.join(self.dir, "open.log")
        fake = os.path.join(self.dir, "fake-open")
        Path(fake).write_text(f'#!/bin/bash\nprintf "%s\\n" "$@" >> {log}\n')
        os.chmod(fake, 0o755)
        self.start()
        self.keys("Enter")
        self.wait(lambda s: "Obsidian で開きました" in s)
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while not os.path.exists(log) and time.time() < deadline:
            time.sleep(0.1)
        url = Path(log).read_text().strip()
        self.assertTrue(url.startswith("obsidian://open?path=%2F"), url)
        self.assertIn("2026-08-01-wow-", url)
        self.assertTrue(url.endswith(".md") or ".md" in url)

    def test_e_でエディタを開き_戻ったら読み直す(self):
        fake = os.path.join(self.dir, "fake-editor")
        # エディタの代わりに、受け取ったファイルのタグを書き換える(Obsidian 側などで変更された状況の再現)
        Path(fake).write_text('#!/bin/bash\nsed -i "" "s/  - wow/  - 書き換えた/" "$1"\n')
        os.chmod(fake, 0o755)
        self.start()
        self.keys("e")
        self.wait(lambda s: "書き換えた" in s)

    def test_q_で終了する(self):
        self.start()
        self.keys("q")
        deadline = time.time() + RENDER_TIMEOUT_SEC
        while time.time() < deadline:
            if self.tmux("list-sessions").returncode != 0:
                return
            time.sleep(0.1)
        self.fail("q で終了しませんでした")

    def test_タスクが無ければ_空と表示して落ちない(self):
        for p in self.tasks.iterdir():
            p.unlink()
        screen = self.start()
        self.assertIn("タスクはありません", screen)
        self.keys("j", "x", "Enter")
        self.assertIn("タスクはありません", self.wait(lambda s: "TASKS" in s))

    def test_狭い幅でも右端を越えない(self):
        screen = self.start(width=40, height=20)
        for line in screen.splitlines():
            self.assertLessEqual(tasks_mod.display_width(line), 40, line)


if __name__ == "__main__":
    unittest.main()
