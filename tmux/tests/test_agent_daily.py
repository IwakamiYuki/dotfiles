"""tmux-agent-daily のテスト。

実行: cd tmux/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_agent_daily

本物の ~/.claude・~/.codex・vault には触れない（一時ディレクトリに偽のログとノートを作る）。
"""

import datetime as dt
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "tmux-agent-daily"
_loader = importlib.machinery.SourceFileLoader("tmux_agent_daily", str(SCRIPT))
_spec = importlib.util.spec_from_loader("tmux_agent_daily", _loader)
ad = importlib.util.module_from_spec(_spec)
sys.modules["tmux_agent_daily"] = ad  # dataclass が型注釈を解決するのに必要
_loader.exec_module(ad)

NOW = dt.datetime(2026, 10, 15, 16, 57)


def epoch(hour, minute, day=15):
    return dt.datetime(2026, 10, day, hour, minute).timestamp()


def write_jsonl(path, records, mtime):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    os.utime(path, (mtime, mtime))


class TmpCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.claude = self.root / "claude-projects"
        self.codex = self.root / "codex-sessions"
        self.titles = self.root / "titles"
        self.titles.mkdir()

    def claude_session(self, sid, cwd, mtime, title="", last_prompt="", project="p"):
        recs = [{"type": "user", "cwd": cwd, "timestamp": "2026-10-15T01:00:00Z"}]
        if last_prompt:
            recs.append({"type": "last-prompt", "lastPrompt": last_prompt, "sessionId": sid})
        if title:
            recs.append({"type": "ai-title", "aiTitle": title, "sessionId": sid})
        write_jsonl(self.claude / project / f"{sid}.jsonl", recs, mtime)

    def codex_session(self, name, cwd, mtime, first_user, source="cli", day="15"):
        meta = {"type": "session_meta", "payload": {"cwd": cwd, "source": source, "originator": "codex_exec" if source == "exec" else "codex_cli"}}
        msg = lambda role, text: {"type": "response_item", "payload": {"type": "message", "role": role, "content": [{"type": "input_text", "text": text}]}}  # noqa: E731
        recs = [meta, msg("developer", "<skills_instructions>..."), msg("user", "# AGENTS.md instructions for /x\n<INSTRUCTIONS>"), msg("user", first_user)]
        write_jsonl(self.codex / "2026" / "10" / day / f"rollout-{name}.jsonl", recs, mtime)


class FormatTest(unittest.TestCase):
    def test_elapsed_under_an_hour_is_minutes_only(self):
        self.assertEqual(ad.format_elapsed(35 * 60), "35m")

    def test_elapsed_over_an_hour_pads_minutes(self):
        self.assertEqual(ad.format_elapsed(4 * 3600 + 5 * 60), "4h05m")

    def test_elapsed_never_negative(self):
        self.assertEqual(ad.format_elapsed(-30), "0m")

    def test_fit_counts_cjk_as_two_columns(self):
        self.assertEqual(ad.display_width("日本語ab"), 8)

    def test_fit_truncates_with_ellipsis_within_width(self):
        out = ad.fit("日本語のタイトルです", 10)
        self.assertLessEqual(ad.display_width(out), 10)
        self.assertTrue(out.endswith("…"))

    def test_fit_keeps_short_text(self):
        self.assertEqual(ad.fit("abc", 10), "abc")


class NoteTest(TmpCase):
    def test_done_section_extracts_until_next_heading(self):
        text = "## はじめに\n- a\n\n## やったこと\n\n- mimi\n\t- x\n\n## 明日\n- b\n"
        self.assertEqual(ad.done_section(text), ["- mimi", "\t- x"])

    def test_done_section_missing_returns_empty(self):
        self.assertEqual(ad.done_section("## だけ\n- a\n"), [])

    def test_read_note_missing_file(self):
        note = ad.read_note(self.root, NOW.date())
        self.assertFalse(note.exists)
        self.assertIsNone(note.mtime)

    def test_read_note_existing_file(self):
        path = self.root / "2026-10-15.md"
        path.write_text("## やったこと\n- a\n", encoding="utf-8")
        os.utime(path, (epoch(12, 56), epoch(12, 56)))
        note = ad.read_note(self.root, NOW.date())
        self.assertTrue(note.exists)
        self.assertEqual(note.mtime, epoch(12, 56))
        self.assertEqual(note.done, ["- a"])


class ClaudeCollectTest(TmpCase):
    def collect(self, since):
        return ad.collect_claude(self.claude, since, self.titles)

    def test_includes_only_sessions_touched_after_since(self):
        self.claude_session("old", "/w/a", epoch(9, 0), title="古い")
        self.claude_session("new", "/w/a", epoch(14, 0), title="新しい")
        titles = [s.title for s in self.collect(epoch(12, 56))]
        self.assertEqual(titles, ["新しい"])

    def test_title_prefers_statusline_cache_over_ai_title(self):
        self.claude_session("s1", "/w/a", epoch(14, 0), title="AI 題")
        (self.titles / "claude-title-s1.txt").write_text("rename 題\n", encoding="utf-8")
        self.assertEqual(self.collect(0)[0].title, "rename 題")

    def test_title_falls_back_to_last_prompt(self):
        self.claude_session("s1", "/w/a", epoch(14, 0), last_prompt="これを直して\n詳細")
        self.assertEqual(self.collect(0)[0].title, "これを直して")

    def test_session_without_any_title_is_skipped(self):
        self.claude_session("s1", "/w/a", epoch(14, 0))
        self.assertEqual(self.collect(0), [])

    def test_subagent_transcripts_are_ignored(self):
        self.claude_session("s1", "/w/a", epoch(14, 0), title="本体")
        write_jsonl(self.claude / "p" / "s1" / "subagents" / "agent-x.jsonl",
                    [{"type": "ai-title", "aiTitle": "サブ", "cwd": "/w/a"}], epoch(14, 1))
        self.assertEqual([s.title for s in self.collect(0)], ["本体"])

    def test_cwd_and_agent_kind(self):
        self.claude_session("s1", "/w/a", epoch(14, 0), title="t")
        s = self.collect(0)[0]
        self.assertEqual((s.agent, s.cwd, s.mtime), ("Claude", "/w/a", epoch(14, 0)))

    def test_missing_projects_dir_is_empty(self):
        self.assertEqual(ad.collect_claude(self.root / "nope", 0, self.titles), [])


class CodexCollectTest(TmpCase):
    def collect(self, since, now=NOW):
        return ad.collect_codex(self.codex, since, now)

    def test_title_is_first_real_user_message_skipping_agents_md(self):
        self.codex_session("a", "/w/a", epoch(14, 0), "テストを足して\n詳細は…")
        s = self.collect(0)[0]
        self.assertEqual((s.agent, s.title, s.cwd), ("Codex", "テストを足して", "/w/a"))

    def test_non_interactive_exec_sessions_are_skipped(self):
        self.codex_session("a", "/w/a", epoch(14, 0), "次の英語のセッション名を訳して", source="exec")
        self.assertEqual(self.collect(0), [])

    def test_sessions_before_since_are_skipped(self):
        self.codex_session("a", "/w/a", epoch(9, 0), "朝の作業")
        self.assertEqual(self.collect(epoch(12, 56)), [])

    def test_session_started_yesterday_but_active_after_since_is_included(self):
        self.codex_session("a", "/w/a", epoch(14, 0), "日またぎ", day="14")
        self.assertEqual([s.title for s in self.collect(epoch(12, 56))], ["日またぎ"])

    def test_missing_dir_is_empty(self):
        self.assertEqual(ad.collect_codex(self.root / "nope", 0, NOW), [])


class RepoNameTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()

    def git(self, *args, cwd):
        env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                       capture_output=True, env=env)

    def test_repo_name_uses_main_repo_for_worktree(self):
        main = self.root / "myrepo"
        main.mkdir()
        self.git("init", "-q", cwd=main)
        self.git("commit", "--allow-empty", "-q", "-m", "x", cwd=main)
        wt = self.root / "myrepo_worktree_feat"
        self.git("worktree", "add", "-q", str(wt), "-b", "feat", cwd=main)
        self.assertEqual(ad.repo_name(str(main), {}), "myrepo")
        self.assertEqual(ad.repo_name(str(wt), {}), "myrepo")

    def test_non_git_dir_uses_basename_and_strips_worktree_suffix(self):
        d = self.root / "wow_client_worktree_chore_x"
        self.assertEqual(ad.repo_name(str(d), {}), "wow_client")

    def test_home_directory_is_tilde(self):
        self.assertEqual(ad.repo_name(str(Path.home()), {}), "~")

    def test_empty_cwd(self):
        self.assertEqual(ad.repo_name("", {}), "(不明)")


class BuildReportTest(TmpCase):
    def build(self, now=NOW):
        daily = self.root / "daily"
        daily.mkdir(exist_ok=True)
        return ad.build_report(daily, now, self.claude, self.codex, self.titles)

    def write_note(self, hour, minute):
        daily = self.root / "daily"
        daily.mkdir(exist_ok=True)
        path = daily / "2026-10-15.md"
        path.write_text("## やったこと\n\n- mimi\n\t- \n", encoding="utf-8")
        os.utime(path, (epoch(hour, minute), epoch(hour, minute)))

    def test_since_is_note_mtime(self):
        self.write_note(12, 56)
        self.claude_session("a", str(self.root / "repoA"), epoch(9, 0), title="朝")
        self.claude_session("b", str(self.root / "repoA"), epoch(14, 0), title="午後")
        report = self.build()
        self.assertEqual(report.since, epoch(12, 56))
        self.assertEqual([s.title for g in report.groups for s in g.sessions], ["午後"])

    def test_since_is_midnight_when_note_does_not_exist(self):
        self.claude_session("a", str(self.root / "repoA"), epoch(0, 30), title="早朝")
        report = self.build()
        self.assertFalse(report.note.exists)
        self.assertEqual(report.since, epoch(0, 0))
        self.assertEqual(len(report.groups), 1)

    def test_groups_by_repo_in_time_order_mixing_claude_and_codex(self):
        self.write_note(12, 0)
        self.claude_session("a", str(self.root / "repoB"), epoch(15, 0), title="B の作業")
        self.claude_session("b", str(self.root / "repoA"), epoch(13, 0), title="A の作業 1")
        self.codex_session("c", str(self.root / "repoA"), epoch(14, 0), "A の作業 2")
        report = self.build()
        self.assertEqual([g.repo for g in report.groups], ["repoA", "repoB"])
        self.assertEqual([s.title for s in report.groups[0].sessions], ["A の作業 1", "A の作業 2"])


    def test_sessions_with_same_title_in_a_repo_are_merged_keeping_latest_time(self):
        self.write_note(12, 0)
        self.claude_session("a", str(self.root / "repoA"), epoch(13, 0), title="同じ題")
        self.claude_session("b", str(self.root / "repoA"), epoch(15, 0), title="同じ題")
        self.claude_session("c", str(self.root / "repoA"), epoch(14, 0), title="別の題")
        sessions = self.build().groups[0].sessions
        self.assertEqual([(s.title, s.mtime) for s in sessions], [("別の題", epoch(14, 0)), ("同じ題", epoch(15, 0))])


class RenderTest(TmpCase):
    def report(self, with_note=True, with_session=True):
        daily = self.root / "daily"
        daily.mkdir(exist_ok=True)
        if with_note:
            path = daily / "2026-10-15.md"
            path.write_text("## やったこと\n\n- mimi\n\t- \n", encoding="utf-8")
            os.utime(path, (epoch(12, 56), epoch(12, 56)))
        if with_session:
            self.claude_session("a", str(self.root / "repoA"), epoch(14, 5), title="USAGE 欄の改善")
        return ad.build_report(daily, NOW, self.claude, self.codex, self.titles)

    def test_screen_shows_elapsed_since_last_update_and_sessions(self):
        text = "\n".join(ad.render_screen(self.report(), 60, color=False))
        self.assertIn("2026-10-15", text)
        self.assertIn("12:56", text)
        self.assertIn("4h01m", text)
        self.assertIn("repoA", text)
        self.assertIn("USAGE 欄の改善", text)
        self.assertIn("14:05", text)
        self.assertIn("- mimi", text)

    def test_screen_without_note_says_not_created(self):
        text = "\n".join(ad.render_screen(self.report(with_note=False), 60, color=False))
        self.assertIn("未作成", text)

    def test_screen_without_sessions_says_so(self):
        text = "\n".join(ad.render_screen(self.report(with_session=False), 60, color=False))
        self.assertIn("作業の記録はありません", text)

    def test_screen_lines_fit_width(self):
        for width in (30, 44, 80):
            for line in ad.render_screen(self.report(), width, color=False):
                self.assertLessEqual(ad.display_width(line), width, line)

    def test_color_flag_adds_escape_codes_only_when_enabled(self):
        report = self.report()
        self.assertNotIn("\033[", "\n".join(ad.render_screen(report, 60, color=False)))
        self.assertIn("\033[", "\n".join(ad.render_screen(report, 60, color=True)))

    def test_staleness_color_levels(self):
        self.assertEqual(ad.staleness_color(30 * 60), ad.COLOR_FRESH)
        self.assertEqual(ad.staleness_color(2 * 3600 + 1), ad.COLOR_WARN)
        self.assertEqual(ad.staleness_color(3 * 3600 + 1), ad.COLOR_ALERT)

    def test_markdown_nests_titles_under_repo_with_tabs(self):
        md = ad.render_markdown(self.report())
        self.assertEqual(md, "- repoA\n\t- USAGE 欄の改善\n")

    def test_markdown_empty_when_no_sessions(self):
        self.assertEqual(ad.render_markdown(self.report(with_session=False)), "")


class HeightTest(TmpCase):
    """縦に収まらないときの切り詰め。作業の一覧は新しい方（後ろ）を残し、ノートの「やったこと」は上限の行数で切る。"""

    def report_with(self, groups, done=None):
        daily = self.root / "daily"
        daily.mkdir(exist_ok=True)
        path = daily / "2026-10-15.md"
        body = "## やったこと\n" + "".join(f"- {line}\n" for line in (done or []))
        path.write_text(body, encoding="utf-8")
        os.utime(path, (epoch(12, 56), epoch(12, 56)))
        report = ad.build_report(daily, NOW, self.claude, self.codex, self.titles)
        report.groups = [ad.Group(repo, [ad.Session("Claude", t, "/x", epoch(14, 0)) for t in titles]) for repo, titles in groups]
        return report

    def test_without_height_nothing_is_trimmed(self):
        report = self.report_with([("a", [f"t{i}" for i in range(30)])])
        self.assertGreater(len(ad.render_screen(report, 60, color=False)), 30)

    def test_lines_never_exceed_height(self):
        report = self.report_with([("a", [f"t{i}" for i in range(30)]), ("b", ["x", "y"])], done=["m1", "m2"])
        for height in (12, 16, 24):
            lines = ad.render_screen(report, 60, color=False, height=height)
            self.assertLessEqual(len(lines), height, height)

    def test_oldest_groups_are_dropped_first_and_counted(self):
        report = self.report_with([("old", ["o1", "o2"]), ("mid", ["m1"]), ("new", ["n1"])])
        text = "\n".join(ad.render_screen(report, 60, color=False, height=12))
        self.assertIn("new", text)
        self.assertNotIn("old", text)
        self.assertRegex(text, r"他 \d+ 件")

    def test_all_fit_shows_no_omission_line(self):
        report = self.report_with([("a", ["x"])])
        self.assertNotIn("他", "\n".join(ad.render_screen(report, 60, color=False, height=40)))

    def test_single_huge_group_keeps_its_newest_sessions(self):
        report = self.report_with([("a", [f"t{i}" for i in range(30)])])
        text = "\n".join(ad.render_screen(report, 60, color=False, height=14))
        self.assertIn("t29", text)
        self.assertNotIn("t0\n", text + "\n")

    def test_done_section_is_capped(self):
        report = self.report_with([("a", ["x"])], done=[f"memo{i}" for i in range(40)])
        lines = ad.render_screen(report, 60, color=False, height=30)
        self.assertLessEqual(len(lines), 30)
        self.assertIn("memo0", "\n".join(lines))

    def test_cli_height_option(self):
        daily = self.root / "daily"
        daily.mkdir()
        for i in range(30):
            self.claude_session(f"s{i}", str(self.root / "repoA"), epoch(14, 5), title=f"作業 {i}")
        r = CliTest.run_cli(self, "--dir", str(daily), "--color", "never", "--width", "50", "--height", "14")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLessEqual(len(r.stdout.splitlines()), 14)


class ObsidianDetectTest(TmpCase):
    """Obsidian の設定（obsidian.json と、vault の .obsidian/daily-notes.json）から Daily Note のディレクトリを求める。"""

    def vault(self, name="vault", folder="10-Daily/team", extra=None, daily_settings=True):
        v = self.root / name
        (v / ".obsidian").mkdir(parents=True)
        if daily_settings:
            settings = {"folder": folder, "template": "templates/Daily Note"}
            settings.update(extra or {})
            (v / ".obsidian" / "daily-notes.json").write_text(json.dumps(settings), encoding="utf-8")
        return v

    def config(self, vaults):
        """vaults: [(path, open)]。obsidian.json を書いて、そのパスを返す。"""
        data = {"vaults": {f"id{i}": ({"path": str(p), "ts": 1} | ({"open": True} if o else {})) for i, (p, o) in enumerate(vaults)}}
        path = self.root / "obsidian.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_joins_open_vault_and_daily_notes_folder(self):
        v = self.vault()
        self.assertEqual(ad.detect_obsidian_daily_dir(self.config([(v, True)])), v / "10-Daily" / "team")

    def test_follows_folder_change_in_obsidian_settings(self):
        v = self.vault(folder="10-Daily/next-project")
        self.assertEqual(ad.detect_obsidian_daily_dir(self.config([(v, True)])), v / "10-Daily" / "next-project")

    def test_prefers_open_vault_among_several(self):
        a, b = self.vault("a", folder="A"), self.vault("b", folder="B")
        self.assertEqual(ad.detect_obsidian_daily_dir(self.config([(a, False), (b, True)])), b / "B")

    def test_single_vault_is_used_even_if_not_open(self):
        v = self.vault()
        self.assertEqual(ad.detect_obsidian_daily_dir(self.config([(v, False)])), v / "10-Daily" / "team")

    def test_several_vaults_none_open_is_ambiguous(self):
        a, b = self.vault("a"), self.vault("b")
        self.assertIsNone(ad.detect_obsidian_daily_dir(self.config([(a, False), (b, False)])))

    def test_empty_folder_means_vault_root(self):
        v = self.vault(folder="")
        self.assertEqual(ad.detect_obsidian_daily_dir(self.config([(v, True)])), v)

    def test_slashes_around_folder_are_ignored(self):
        v = self.vault(folder="/10-Daily/team/")
        self.assertEqual(ad.detect_obsidian_daily_dir(self.config([(v, True)])), v / "10-Daily" / "team")

    def test_unsupported_file_name_format_is_not_guessed(self):
        v = self.vault(extra={"format": "YYYY/MM/DD"})
        self.assertIsNone(ad.detect_obsidian_daily_dir(self.config([(v, True)])))

    def test_default_file_name_format_is_accepted(self):
        v = self.vault(extra={"format": "YYYY-MM-DD"})
        self.assertEqual(ad.detect_obsidian_daily_dir(self.config([(v, True)])), v / "10-Daily" / "team")

    def test_empty_settings_object_means_all_defaults(self):
        v = self.vault(folder="")
        (v / ".obsidian" / "daily-notes.json").write_text("{}", encoding="utf-8")
        self.assertEqual(ad.detect_obsidian_daily_dir(self.config([(v, True)])), v)

    def test_vault_without_daily_notes_settings_is_none(self):
        v = self.vault(daily_settings=False)
        self.assertIsNone(ad.detect_obsidian_daily_dir(self.config([(v, True)])))

    def test_missing_or_broken_config_is_none(self):
        self.assertIsNone(ad.detect_obsidian_daily_dir(self.root / "nope.json"))
        broken = self.root / "obsidian.json"
        broken.write_text("{not json", encoding="utf-8")
        self.assertIsNone(ad.detect_obsidian_daily_dir(broken))


class CliTest(TmpCase):
    def run_cli(self, *args, env=None):
        base = dict(os.environ, AGENT_DAILY_NOW="2026-10-15 16:57", AGENT_DAILY_CLAUDE_PROJECTS=str(self.claude),
                    AGENT_DAILY_CODEX_SESSIONS=str(self.codex), AGENT_DAILY_TITLE_DIR=str(self.titles),
                    PYTHONDONTWRITEBYTECODE="1")
        base.pop("AGENT_DAILY_DIR", None)
        base.update(env or {})
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=base)

    def test_markdown_output_via_env_dir(self):
        daily = self.root / "daily"
        daily.mkdir()
        self.claude_session("a", str(self.root / "repoA"), epoch(14, 5), title="作業 X")
        r = self.run_cli("--markdown", env={"AGENT_DAILY_DIR": str(daily)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "- repoA\n\t- 作業 X\n")

    def test_dir_option_overrides_env(self):
        daily = self.root / "daily"
        daily.mkdir()
        r = self.run_cli("--dir", str(daily), "--color", "never", "--width", "50",
                         env={"AGENT_DAILY_DIR": "/nonexistent"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Daily Note", r.stdout)

    def test_print_dir_resolves_from_obsidian_settings(self):
        v = self.root / "vault"
        (v / ".obsidian").mkdir(parents=True)
        (v / ".obsidian" / "daily-notes.json").write_text(json.dumps({"folder": "daily/x"}), encoding="utf-8")
        cfg = self.root / "obsidian.json"
        cfg.write_text(json.dumps({"vaults": {"a": {"path": str(v), "open": True}}}), encoding="utf-8")
        r = self.run_cli("--print-dir", env={"AGENT_DAILY_OBSIDIAN_CONFIG": str(cfg), "AGENT_DAILY_NO_TMUX": "1"})
        self.assertEqual((r.returncode, r.stdout.strip()), (0, str(v / "daily" / "x")))

    def test_explicit_dir_wins_over_obsidian_settings(self):
        r = self.run_cli("--print-dir", env={"AGENT_DAILY_DIR": "/explicit", "AGENT_DAILY_OBSIDIAN_CONFIG": "/nonexistent"})
        self.assertEqual(r.stdout.strip(), "/explicit")

    def test_print_dir_fails_when_nothing_resolves(self):
        r = self.run_cli("--print-dir", env={"AGENT_DAILY_NO_TMUX": "1", "AGENT_DAILY_OBSIDIAN_CONFIG": "/nonexistent"})
        self.assertEqual(r.returncode, 2)

    def test_missing_dir_setting_is_an_error_with_hint(self):
        r = self.run_cli(env={"AGENT_DAILY_NO_TMUX": "1", "AGENT_DAILY_OBSIDIAN_CONFIG": "/nonexistent"})
        self.assertEqual(r.returncode, 2)
        self.assertIn("AGENT_DAILY_DIR", r.stderr)


if __name__ == "__main__":
    unittest.main()
