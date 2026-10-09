"""tmux-agent-web のテスト。

実行: cd tmux/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v

結合テストは専用ソケット（tmux -S <一時ファイル>）の別 tmux サーバーだけを使う。
普段使っている tmux のサーバーには触れない（kill-server も、その一時ソケットを明示して呼ぶ）。
"""

import http.client
import importlib.machinery
import importlib.util
import json
import os
import shutil
import socket
import ssl
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "tmux-agent-web"
_loader = importlib.machinery.SourceFileLoader("tmux_agent_web", str(SCRIPT))
_spec = importlib.util.spec_from_loader("tmux_agent_web", _loader)
aw = importlib.util.module_from_spec(_spec)
sys.modules["tmux_agent_web"] = aw  # dataclass が型注釈を解決するのに必要
_loader.exec_module(aw)


def pane(**kw):
    base = dict(
        session="default", window_id="@1", window=1, index=0, pane_id="%1", pid=100,
        sidebar=False, window_active=True, active=False, window_name="w",
        origin_window=None, origin_name="", origin_index=None, slot=False,
        command="zsh", cols=100, rows=30, path="/work/repo",
    )
    base.update(kw)
    return aw.Pane(**base)


GIT = lambda cwd: aw.GitInfo(repo_key="/work/repo", repo="repo", worktree=cwd, branch="main")  # noqa: E731


class ParseTest(unittest.TestCase):
    def test_parse_panes_reads_fields_and_keeps_pipe_in_path(self):
        line = "default|@1|2|1|%26|99175||1|1|name|||||2.1.295|514|137|/tmp/a|b"
        # sidebar, origin_*, slot は空。最後の path に '|' が入っていても壊れない
        panes = aw.parse_panes(line + "\n\n")
        self.assertEqual(len(panes), 1)
        p = panes[0]
        self.assertEqual((p.session, p.window, p.index, p.pane_id, p.pid), ("default", 2, 1, "%26", 99175))
        self.assertEqual((p.cols, p.rows, p.command), (514, 137, "2.1.295"))
        self.assertEqual(p.path, "/tmp/a|b")
        self.assertFalse(p.sidebar)
        self.assertIsNone(p.origin_window)

    def test_parse_panes_reads_cockpit_origin(self):
        line = "default|@3|9|0|%5|200|1|1|1|cockpit|4|origin|2|%7|zsh|80|24|/x"
        p = aw.parse_panes(line)[0]
        self.assertTrue(p.sidebar)
        self.assertEqual((p.origin_window, p.origin_name, p.origin_index), (4, "origin", 2))
        self.assertTrue(p.slot)

    def test_parse_panes_skips_malformed_lines(self):
        self.assertEqual(aw.parse_panes("garbage\nfoo|bar"), [])

    def test_parse_ps(self):
        procs = aw.parse_ps("  10     1 /sbin/launchd\n 20 10 node /opt/x/codex --flag\nbad line\n")
        self.assertEqual(procs[20], (10, "node /opt/x/codex --flag"))
        self.assertNotIn("bad", procs)


class DetectTest(unittest.TestCase):
    def setUp(self):
        self.panes = [
            pane(pane_id="%1", pid=100, window=1, index=0),
            pane(pane_id="%2", pid=200, window=1, index=1),
            pane(pane_id="%3", pid=300, window=2, index=0, sidebar=True),
            pane(pane_id="%4", pid=400, window=2, index=1, slot=True),
        ]
        self.procs = {
            100: (1, "-zsh"),
            110: (100, "claude"),
            200: (1, "-zsh"),
            210: (200, "node /opt/homebrew/bin/codex"),
            300: (1, "bash tmux-agent-sidebar"),
            310: (300, "claude"),  # sidebar の下の process は拾わない
        }

    def agents(self, claude, alerts=None, **kw):
        return aw.build_agents(
            self.panes, self.procs, claude, alerts or {}, now=1000,
            title_of=kw.get("title_of", lambda sid: ""), meta_of=kw.get("meta_of", lambda pid: (None, "")),
            git_of=GIT,
        )

    def test_pane_of_walks_up_ancestors(self):
        by_pid = {100: self.panes[0]}
        self.assertEqual(aw.pane_of(110, by_pid, self.procs).pane_id, "%1")
        self.assertIsNone(aw.pane_of(999, by_pid, self.procs))

    def test_claude_and_codex_are_mapped_to_panes(self):
        out = self.agents([{"pid": 110, "status": "busy", "cwd": "/work/repo", "name": "n", "sessionId": "s"}])
        by_type = {a["type"]: a for a in out}
        self.assertEqual(by_type["Claude"]["pane"], "%1")
        self.assertEqual(by_type["Claude"]["status"], "working")
        self.assertEqual(by_type["Codex"]["pane"], "%2")
        self.assertEqual(by_type["Codex"]["status"], "unknown")

    def test_sidebar_panes_are_not_agents(self):
        out = self.agents([{"pid": 310, "status": "idle", "cwd": "/w", "name": "", "sessionId": ""}])
        self.assertNotIn("%3", [a["pane"] for a in out])

    def test_status_mapping(self):
        f = aw.claude_status
        self.assertEqual(f("busy", False), "working")
        self.assertEqual(f("waiting", False), "waiting")
        self.assertEqual(f("idle", False), "idle")
        self.assertEqual(f("idle", True), "done")
        self.assertEqual(f("???", False), "unknown")

    def test_done_comes_from_alerting_parent_pid(self):
        # 状態ファイルは claude の親 pid(シェル) をキーにする（sidebar と同じ）
        out = self.agents([{"pid": 110, "status": "idle", "cwd": "/w", "name": "", "sessionId": ""}], {100: True})
        self.assertEqual([a["status"] for a in out if a["type"] == "Claude"], ["done"])

    def test_name_falls_back_to_title_then_session_name_then_project(self):
        c = {"pid": 110, "status": "idle", "cwd": "/work/proj", "name": "sess", "sessionId": "abc"}
        titled = self.agents([c], title_of=lambda sid: "会話タイトル")
        self.assertEqual(titled[0]["name"], "会話タイトル")
        named = self.agents([c], meta_of=lambda pid: (None, "user"))
        self.assertEqual(named[0]["name"], "sess")
        derived = self.agents([c], meta_of=lambda pid: (None, "derived"))
        self.assertEqual(derived[0]["name"], "proj")

    def test_elapsed_uses_status_updated_at(self):
        c = {"pid": 110, "status": "busy", "cwd": "/w", "name": "", "sessionId": ""}
        out = self.agents([c], meta_of=lambda pid: (990_000, ""))
        self.assertEqual(out[0]["elapsed"], 10)

    def test_ordering_groups_by_repo_then_window_and_uses_cockpit_origin(self):
        panes = [
            pane(pane_id="%1", pid=100, window=5, index=0),
            pane(pane_id="%2", pid=200, window=1, index=0),
            # cockpit 内(window 9)に入っているが、元は window 2
            pane(pane_id="%3", pid=300, window=9, index=0, origin_window=2, origin_index=0),
        ]
        procs = {p.pid + 1: (p.pid, "claude") for p in panes}
        procs.update({p.pid: (1, "zsh") for p in panes})
        repos = {"/a": ("/r/a", "a"), "/b": ("/r/b", "b")}

        def git_of(cwd):
            key, name = repos[cwd]
            return aw.GitInfo(repo_key=key, repo=name, worktree=cwd, branch="")

        claude = [
            {"pid": 101, "status": "idle", "cwd": "/a", "name": "", "sessionId": ""},  # window 5 / repo a
            {"pid": 201, "status": "idle", "cwd": "/b", "name": "", "sessionId": ""},  # window 1 / repo b
            {"pid": 301, "status": "idle", "cwd": "/a", "name": "", "sessionId": ""},  # 元 window 2 / repo a
        ]
        out = aw.build_agents(panes, procs, claude, {}, now=0, title_of=lambda s: "",
                              meta_of=lambda p: (None, ""), git_of=git_of)
        # repo b が最も若い window(1) → 先。repo a の中は元の window 順(2 → 5)
        self.assertEqual([a["pane"] for a in out], ["%2", "%3", "%1"])


class TitleTest(unittest.TestCase):
    def test_title_priority_and_ai_title_from_transcript(self):
        with tempfile.TemporaryDirectory() as d:
            titles, projects = Path(d, "titles"), Path(d, "projects", "p1")
            titles.mkdir()
            projects.mkdir(parents=True)
            sid = "0123abcd-0000-4000-8000-000000000001"
            cfg = aw.Config(title_dir=str(titles), projects_dir=str(Path(d, "projects")))
            res = aw.TitleResolver(cfg)
            self.assertEqual(res.title_of(sid), "")
            Path(projects, f"{sid}.jsonl").write_text(
                '{"type":"user"}\n{"type":"ai-title","aiTitle":"古いタイトル"}\n{"type":"ai-title","aiTitle":"新しいタイトル"}\n'
            )
            res = aw.TitleResolver(cfg)
            self.assertEqual(res.title_of(sid), "新しいタイトル")
            Path(titles, f"claude-title-{sid}.txt").write_text("statusline のタイトル\n")
            res = aw.TitleResolver(cfg)
            self.assertEqual(res.title_of(sid), "statusline のタイトル")

    def test_title_of_rejects_unsafe_session_id(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "claude-title-x.txt").write_text("secret")
            res = aw.TitleResolver(aw.Config(title_dir=d, projects_dir=d))
            self.assertEqual(res.title_of("../x"), "")


class SecurityTest(unittest.TestCase):
    def test_bind_address_accepts_only_specific_private_ipv4(self):
        ok = aw.validate_bind_host
        for host in ("192.168.11.10", "10.0.0.5", "172.16.3.4", "127.0.0.1", "100.101.102.103", "169.254.1.1"):
            self.assertIsNone(ok(host), host)
        for host in ("0.0.0.0", "::", "::1", "8.8.8.8", "203.0.113.5", "example.com", "", "192.168.11.0/24"):
            self.assertIsNotNone(ok(host), host)

    def test_client_ip_allowlist(self):
        ok = aw.client_ip_allowed
        for ip in ("192.168.1.2", "10.1.2.3", "127.0.0.1", "100.64.0.9", "::ffff:192.168.1.2", "fe80::1"):
            self.assertTrue(ok(ip), ip)
        for ip in ("8.8.8.8", "203.0.113.9", "::ffff:8.8.8.8", "2001:db8::1", "bogus"):
            self.assertFalse(ok(ip), ip)

    def test_host_header_must_be_an_allowed_name(self):
        allowed = frozenset({"192.168.11.10", "localhost", "ca-1.local"})
        self.assertTrue(aw.host_allowed("192.168.11.10:8765", allowed))
        self.assertTrue(aw.host_allowed("CA-1.local:8765", allowed))
        self.assertTrue(aw.host_allowed("localhost", allowed))
        for bad in (None, "", "evil.example.com", "evil.example.com:8765", "192.168.11.11:8765", "[::1]:8765"):
            self.assertFalse(aw.host_allowed(bad, allowed), bad)

    def test_origin_must_match_host(self):
        self.assertTrue(aw.origin_ok("http://192.168.11.10:8765", "192.168.11.10:8765"))
        self.assertFalse(aw.origin_ok("http://evil.example.com", "192.168.11.10:8765"))
        self.assertFalse(aw.origin_ok("https://192.168.11.10:8765", "192.168.11.10:8765"))
        self.assertFalse(aw.origin_ok("null", "192.168.11.10:8765"))

    def test_token_compare_and_sessions(self):
        auth = aw.Auth("secret-token-0123456789")
        self.assertTrue(auth.check_token("secret-token-0123456789"))
        self.assertFalse(auth.check_token("secret-token-012345678"))
        self.assertFalse(auth.check_token(""))
        self.assertFalse(auth.check_token(None))
        sid = auth.new_session()
        self.assertTrue(auth.valid_session(sid))
        self.assertFalse(auth.valid_session("nope"))
        self.assertFalse(auth.valid_session(None))

    def test_session_expires(self):
        auth = aw.Auth("secret-token-0123456789", session_ttl=-1)
        self.assertFalse(auth.valid_session(auth.new_session()))

    def test_rate_limiter_blocks_after_repeated_failures_and_resets(self):
        rl = aw.RateLimiter(max_failures=3)
        for _ in range(2):
            rl.fail("1.2.3.4")
        self.assertEqual(rl.blocked("1.2.3.4"), 0)
        rl.fail("1.2.3.4")
        self.assertGreater(rl.blocked("1.2.3.4"), 0)
        self.assertEqual(rl.blocked("5.6.7.8"), 0)
        rl.reset("1.2.3.4")
        self.assertEqual(rl.blocked("1.2.3.4"), 0)

    def test_key_whitelist(self):
        self.assertEqual(aw.tmux_key("Enter"), ("Enter", False))
        self.assertEqual(aw.tmux_key("C-c"), ("C-c", False))
        self.assertEqual(aw.tmux_key("y"), ("y", True))
        self.assertEqual(aw.tmux_key("1"), ("1", True))
        self.assertEqual(aw.tmux_key("/"), ("/", True))  # Claude Code のスラッシュコマンドのメニューを開く
        for bad in ("rm", "C-x", "; kill-server", "", "ab", None, 5, "-l"):
            self.assertIsNone(aw.tmux_key(bad), bad)

    def test_pane_number_validation(self):
        self.assertEqual(aw.pane_number("26"), 26)
        self.assertEqual(aw.pane_number(26), 26)
        for bad in ("", "-1", "%26", "1;2", "x", None, True, 10**9, "1 "):
            self.assertIsNone(aw.pane_number(bad), bad)

    def test_token_min_length(self):
        self.assertIsNotNone(aw.validate_token("short"))
        self.assertIsNone(aw.validate_token("x" * 20))


def http_call(port, method, path, body=None, cookie=None, host=None, origin=True, xrw=True, context=None):
    """ブラウザ相当のリクエストを送り、(status, JSON, response) を返す。context を渡すと HTTPS で繋ぐ。"""
    if context is not None:
        conn = http.client.HTTPSConnection("127.0.0.1", port, timeout=10, context=context)
    else:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Host": host or f"127.0.0.1:{port}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if method == "POST":
        if origin is True:
            headers["Origin"] = f"{'https' if context is not None else 'http'}://{headers['Host']}"
        elif origin:
            headers["Origin"] = origin
        if xrw:
            headers["X-Requested-With"] = "tmux-agent-web"
    if cookie:
        headers["Cookie"] = cookie
    conn.request(method, path, json.dumps(body) if body is not None else None, headers)
    res = conn.getresponse()
    raw = res.read()
    conn.close()
    try:
        data = json.loads(raw) if raw else None
    except ValueError:
        data = raw
    return res.status, data, res


@unittest.skipUnless(shutil.which("tmux"), "tmux が必要")
class ServerIntegrationTest(unittest.TestCase):
    """専用ソケットの別 tmux サーバー + 偽の claude で、HTTP の入口から出口までを通す。"""

    TOKEN = "integration-token-0123456789"

    @classmethod
    def tmux(cls, *args):
        return subprocess.run(["tmux", "-S", cls.sock, *args], capture_output=True, text=True, check=True).stdout

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="taw-")
        cls.sock = os.path.join(cls.tmp, "sock")
        env = {k: v for k, v in os.environ.items() if k != "TMUX"}
        subprocess.run(["tmux", "-S", cls.sock, "-f", "/dev/null", "new-session", "-d", "-s", "t",
                        "-x", "100", "-y", "30", "cat"], check=True, env=env)
        cls.tmux("split-window", "-t", "t", "cat")  # 2 つ目の pane（Agent ではない）
        panes = cls.tmux("list-panes", "-t", "t", "-F", "#{pane_id} #{pane_pid}").split("\n")
        (cls.agent_pane, cls.agent_pid), (cls.other_pane, _) = [p.split() for p in panes if p][:2]
        fake = Path(cls.tmp, "claude")
        fake.write_text("#!/bin/sh\n" + "cat <<'EOF'\n" + json.dumps([
            {"pid": int(cls.agent_pid), "status": "waiting", "waitingFor": "permission", "cwd": cls.tmp,
             "name": "fake", "sessionId": "0123abcd-0000-4000-8000-0000000000aa"}]) + "\nEOF\n")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        cls.cfg = aw.Config(
            tmux_socket=cls.sock, claude_bin=str(fake), sessions_dir=cls.tmp, projects_dir=cls.tmp,
            alert_state=os.path.join(cls.tmp, "none"), title_dir=cls.tmp, token=cls.TOKEN, quiet=True,
        )
        cls.start_server(read_only=False)

    @classmethod
    def start_server(cls, read_only):
        cls.cfg.read_only = read_only
        cls.srv = aw.make_server("127.0.0.1", 0, cls.cfg, frozenset({"127.0.0.1", "localhost"}))
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def stop_server(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    @classmethod
    def tearDownClass(cls):
        cls.stop_server()
        subprocess.run(["tmux", "-S", cls.sock, "kill-server"], capture_output=True)  # 一時ソケットのサーバーだけ
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def request(self, method, path, body=None, cookie=None, host=None, origin=True, xrw=True):
        return http_call(self.port, method, path, body, cookie, host, origin, xrw)

    def login(self):
        status, _, res = self.request("POST", "/api/login", {"token": self.TOKEN})
        self.assertEqual(status, 204)
        return res.getheader("Set-Cookie").split(";")[0]

    def pane_id(self, pane):
        return int(pane.lstrip("%"))

    def capture(self, cookie, pane=None):
        pane = pane or self.agent_pane
        return self.request("GET", f"/api/pane?id={self.pane_id(pane)}", cookie=cookie)

    def test_healthz_and_static_need_no_login_and_carry_security_headers(self):
        status, data, _ = self.request("GET", "/healthz")
        self.assertEqual((status, data["ok"]), (200, True))
        status, _, res = self.request("GET", "/")
        self.assertEqual(status, 200)
        csp = res.getheader("Content-Security-Policy")
        self.assertIn("default-src 'none'", csp)
        # manifest の取得は manifest-src で制御され、未指定だと default-src 'none' に従って Chrome 自身に止められる
        # （そうなると「アプリをインストール」が出ない）。実機のログで、manifest が一度も取得されなかったことで発覚した
        self.assertIn("manifest-src 'self'", csp)
        self.assertIn("worker-src 'self'", csp)  # Service Worker（child-src → script-src の fallback に頼らず明示）
        self.assertEqual(res.getheader("Cache-Control"), "no-store")
        self.assertEqual(res.getheader("X-Content-Type-Options"), "nosniff")

    def test_manifest_and_icons_are_served_without_login(self):
        status, manifest, res = self.request("GET", "/manifest.webmanifest")
        self.assertEqual(status, 200)
        self.assertEqual(res.getheader("Content-Type"), "application/manifest+json")
        self.assertEqual((manifest["start_url"], manifest["display"]), ("/", "standalone"))
        self.assertTrue(manifest["name"] and manifest["short_name"])
        by_purpose = {}
        for icon in manifest["icons"]:
            by_purpose.setdefault(icon["purpose"], set()).add(icon["sizes"])
            status, png, res = self.request("GET", icon["src"])
            self.assertEqual(status, 200, icon["src"])
            self.assertEqual(res.getheader("Content-Type"), "image/png")
            width, height = struct.unpack(">II", png[16:24])  # PNG の IHDR（幅・高さ）
            self.assertEqual(f"{width}x{height}", icon["sizes"], icon["src"])
        # Chrome の installability の最低条件(192 と 512)と、Android のホーム画面向けの maskable
        self.assertTrue({"192x192", "512x512"} <= by_purpose["any"])
        self.assertIn("512x512", by_purpose["maskable"])

    def test_index_links_manifest_and_touch_icons(self):
        status, html, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        text = html.decode()
        for needle in ('rel="manifest"', 'rel="apple-touch-icon"', 'rel="icon"', 'name="theme-color"', "apple-mobile-web-app-title"):
            self.assertIn(needle, text)
        # Android の Chrome は、ソフトキーボードが画面に重なるだけでページが縮まず、入力欄が隠れる。縮めるよう宣言する
        self.assertIn("interactive-widget=resizes-content", text)
        status, css, _ = self.request("GET", "/app.css")
        self.assertIn("var(--vvh", css.decode())  # 縮まない端末（iOS Safari）用に visual viewport の高さを使う
        status, png, res = self.request("GET", "/apple-touch-icon.png")
        self.assertEqual((status, struct.unpack(">II", png[16:24])), (200, (180, 180)))
        self.assertEqual(self.request("GET", "/favicon.ico")[2].getheader("Content-Type"), "image/png")

    def test_service_worker_is_javascript_and_never_caches(self):
        status, body, res = self.request("GET", "/sw.js")
        self.assertEqual(status, 200)
        self.assertEqual(res.getheader("Content-Type"), "text/javascript; charset=utf-8")
        text = body.decode()
        self.assertIn("fetch", text)
        self.assertNotIn("caches", text)  # 画面や API の応答を端末に溜めない（認証済みの内容を残さない）

    def test_api_requires_login(self):
        self.assertEqual(self.request("GET", "/api/agents")[0], 401)
        self.assertEqual(self.request("GET", "/api/agents", cookie="tmux_agent_web=bogus")[0], 401)
        self.assertEqual(self.request("GET", f"/api/pane?id={self.pane_id(self.agent_pane)}")[0], 401)

    def test_login_cookie_is_httponly_samesite_strict(self):
        _, _, res = self.request("POST", "/api/login", {"token": self.TOKEN})
        cookie = res.getheader("Set-Cookie")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertNotIn(self.TOKEN, cookie)

    def test_rejects_unexpected_host_origin_and_missing_csrf_header(self):
        body = {"token": self.TOKEN}
        self.assertEqual(self.request("POST", "/api/login", body, host="evil.example.com")[0], 403)
        self.assertEqual(self.request("GET", "/api/agents", host="evil.example.com")[0], 403)
        self.assertEqual(self.request("POST", "/api/login", body, origin="http://evil.example.com")[0], 403)
        self.assertEqual(self.request("POST", "/api/login", body, origin=False)[0], 403)
        self.assertEqual(self.request("POST", "/api/login", body, xrw=False)[0], 403)

    def test_agents_lists_detected_agent_only(self):
        cookie = self.login()
        status, data, _ = self.request("GET", "/api/agents", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual([a["pane"] for a in data["agents"]], [self.agent_pane])
        agent = data["agents"][0]
        self.assertEqual((agent["type"], agent["status"], agent["detail"]), ("Claude", "waiting", "permission"))
        self.assertFalse(data["readOnly"])

    def test_send_text_and_keys_reach_the_pane_and_capture_shows_them(self):
        cookie = self.login()
        n = self.pane_id(self.agent_pane)
        status, _, _ = self.request("POST", "/api/send", {"id": n, "text": "こんにちは hello", "enter": True}, cookie)
        self.assertEqual(status, 204)
        self.assertEqual(self.request("POST", "/api/key", {"id": n, "key": "y"}, cookie)[0], 204)
        deadline, text = time.time() + 3, ""
        while time.time() < deadline and "こんにちは hello" not in text:
            time.sleep(0.1)
            text = self.capture(cookie)[1]["text"]
        self.assertIn("こんにちは hello", text)
        # 同じ内容なら rev 一致で本文を返さない
        rev = self.capture(cookie)[1]["rev"]
        status, data, _ = self.request("GET", f"/api/pane?id={n}&rev={rev}", cookie=cookie)
        self.assertEqual((status, data.get("same")), (200, True))

    def pane_text_with(self, cookie, needle, count=1, timeout=3.0):
        deadline, text = time.time() + timeout, ""
        while time.time() < deadline:
            text = self.capture(cookie)[1]["text"]
            if text.count(needle) >= count:
                break
            time.sleep(0.1)
        return text

    def test_text_without_enter_is_typed_and_enter_is_a_separate_key(self):
        """補完（/ やスキル）を使えるよう、文字だけを入れて、Enter は別に押せる。"""
        cookie = self.login()
        n = self.pane_id(self.agent_pane)
        marker = "typed-only-7f3a"
        self.assertEqual(self.request("POST", "/api/send", {"id": n, "text": marker, "enter": False}, cookie)[0], 204)
        text = self.pane_text_with(cookie, marker)
        self.assertEqual(text.count(marker), 1)  # 端末のエコーだけ。まだ Enter されていない（cat の出力は無い）
        time.sleep(0.4)
        self.assertEqual(self.capture(cookie)[1]["text"].count(marker), 1)
        self.assertEqual(self.request("POST", "/api/key", {"id": n, "key": "Enter"}, cookie)[0], 204)
        self.assertEqual(self.pane_text_with(cookie, marker, count=2).count(marker), 2)  # Enter で cat が出力した

    def test_typed_text_is_not_mangled_by_tmux_argument_parsing(self):
        """行末の「;」は tmux の引数の区切りと解釈されうる。先頭の「-」はオプションに見える。どちらも、そのまま届く。"""
        cookie = self.login()
        n = self.pane_id(self.agent_pane)
        for text in ("semi-end-1c9d;", "-dash-start-2e4b --x", "back-end-3a7f\\;"):
            self.assertEqual(self.request("POST", "/api/send", {"id": n, "text": text, "enter": False}, cookie)[0], 204)
            self.assertIn(text, self.pane_text_with(cookie, text))
            self.request("POST", "/api/key", {"id": n, "key": "BSpace"}, cookie)

    def test_multiline_text_is_pasted_as_one_block(self):
        cookie = self.login()
        n = self.pane_id(self.agent_pane)
        self.assertEqual(self.request("POST", "/api/send", {"id": n, "text": "ml-one-5b2c\nml-two-5b2c", "enter": False}, cookie)[0], 204)
        text = self.pane_text_with(cookie, "ml-two-5b2c")
        self.assertIn("ml-one-5b2c", text)
        self.assertIn("ml-two-5b2c", text)

    def test_single_line_is_typed_but_multiline_is_a_bracketed_paste(self):
        """1 行の文字は「打った」形で届ける（Claude Code の / やスキルの補完メニューは、貼り付けでは出ないため）。
        改行を含む文字だけ、貼り付け（bracketed paste）の形にする。"""
        script = Path(self.tmp, "bracketed.sh")
        script.write_text("#!/bin/sh\nprintf '\\033[?2004h'\nexec cat -v\n")  # 貼り付けモードを有効にして、届いたものをそのまま見せる
        script.chmod(0o755)
        pane = self.tmux("new-window", "-d", "-P", "-F", "#{pane_id}", "-t", "t", str(script)).strip()
        time.sleep(0.5)
        collector = aw.Collector(self.cfg)
        number = self.pane_id(pane)

        collector.paste(number, "typed-line-8d1e", False)
        text = self.pane_text_for(collector, number, "typed-line-8d1e")
        self.assertIn("typed-line-8d1e", text)
        self.assertNotIn("[200~", text)  # 貼り付けの目印が付いていない = 打った形

        collector.paste(number, "pasted-a-8d1e\npasted-b-8d1e", False)
        text = self.pane_text_for(collector, number, "pasted-b-8d1e")
        self.assertIn("[200~", text)  # 貼り付けの開始の目印
        self.assertIn("[201~", text)  # 終了の目印

    @staticmethod
    def pane_text_for(collector, number, needle, timeout=3.0):
        deadline, text = time.time() + timeout, ""
        while time.time() < deadline:
            text = collector.capture(number, 0)
            if needle in text:
                break
            time.sleep(0.1)
        return text

    def test_composer_has_a_text_button_and_a_separate_enter_button(self):
        html = self.request("GET", "/")[1].decode()
        self.assertIn('id="send"', html)
        self.assertIn('id="sendEnter"', html)  # 文字を入れて Enter まで押す、従来どおりの 1 回の操作

    def test_slash_key_reaches_the_pane_as_a_typed_character(self):
        cookie = self.login()
        n = self.pane_id(self.agent_pane)
        self.assertEqual(self.request("POST", "/api/key", {"id": n, "key": "/"}, cookie)[0], 204)
        text = ""
        deadline = time.time() + 3
        while time.time() < deadline and "/" not in text:
            time.sleep(0.1)
            text = self.capture(cookie)[1]["text"]
        self.assertIn("/", text)

    def test_non_agent_pane_cannot_be_read_or_driven(self):
        cookie = self.login()
        n = self.pane_id(self.other_pane)
        self.assertEqual(self.capture(cookie, self.other_pane)[0], 404)
        self.assertEqual(self.request("POST", "/api/send", {"id": n, "text": "x", "enter": True}, cookie)[0], 404)
        self.assertEqual(self.request("POST", "/api/key", {"id": n, "key": "Enter"}, cookie)[0], 404)

    def test_invalid_input_is_rejected(self):
        cookie = self.login()
        n = self.pane_id(self.agent_pane)
        self.assertEqual(self.request("POST", "/api/key", {"id": n, "key": "; kill-server"}, cookie)[0], 400)
        self.assertEqual(self.request("POST", "/api/send", {"id": n, "text": "a" * 9000}, cookie)[0], 400)
        self.assertEqual(self.request("POST", "/api/send", {"id": "%1;x", "text": "a"}, cookie)[0], 400)
        self.assertEqual(self.request("GET", "/api/pane?id=abc", cookie=cookie)[0], 400)
        self.assertEqual(self.request("GET", "/api/nothing", cookie=cookie)[0], 404)

    def test_wrong_tokens_are_rate_limited(self):
        self.stop_server()
        self.start_server(read_only=False)
        try:
            statuses = [self.request("POST", "/api/login", {"token": "wrong"})[0] for _ in range(8)]
            self.assertEqual(statuses[0], 401)
            self.assertEqual(statuses[-1], 429)
            # ロック中は正しいトークンでも通らない
            self.assertEqual(self.request("POST", "/api/login", {"token": self.TOKEN})[0], 429)
        finally:
            self.stop_server()
            self.start_server(read_only=False)

    def test_read_only_mode_blocks_input_but_allows_viewing(self):
        self.stop_server()
        self.start_server(read_only=True)
        try:
            cookie = self.login()
            n = self.pane_id(self.agent_pane)
            self.assertEqual(self.request("POST", "/api/send", {"id": n, "text": "x"}, cookie)[0], 403)
            self.assertEqual(self.request("POST", "/api/key", {"id": n, "key": "Enter"}, cookie)[0], 403)
            self.assertEqual(self.capture(cookie)[0], 200)
            self.assertTrue(self.request("GET", "/api/agents", cookie=cookie)[1]["readOnly"])
        finally:
            self.stop_server()
            self.start_server(read_only=False)


class AuthStoreTest(unittest.TestCase):
    """ログイン済みの記録（Cookie のハッシュ）をファイルに残し、サーバーを起動し直しても有効にする。"""

    TOKEN = "store-token-0123456789"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="taw-auth-")
        self.path = os.path.join(self.tmp, "sub", "sessions.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_session_survives_a_new_auth_instance(self):
        sid = aw.Auth(self.TOKEN, store_path=self.path).new_session()
        self.assertTrue(aw.Auth("another-token-0123456789", store_path=self.path).valid_session(sid))

    def test_store_holds_only_hashes_and_is_private(self):
        sid = aw.Auth(self.TOKEN, store_path=self.path).new_session()
        self.assertNotIn(sid, Path(self.path).read_text())
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(self.path)).st_mode), 0o700)

    def test_expired_sessions_are_not_restored(self):
        auth = aw.Auth(self.TOKEN, session_ttl=-1, store_path=self.path)
        sid = auth.new_session()
        self.assertFalse(aw.Auth(self.TOKEN, store_path=self.path).valid_session(sid))

    def test_corrupt_store_is_treated_as_empty(self):
        os.makedirs(os.path.dirname(self.path))
        Path(self.path).write_text("{broken")
        auth = aw.Auth(self.TOKEN, store_path=self.path)
        self.assertFalse(auth.valid_session("anything"))
        self.assertTrue(auth.valid_session(auth.new_session()))  # 壊れていても、新しいログインは保存できる

    def test_revoke_removes_the_store_and_a_running_auth_notices(self):
        running = aw.Auth(self.TOKEN, store_path=self.path)
        sid = running.new_session()
        self.assertTrue(running.valid_session(sid))
        aw.revoke_sessions(self.path)
        self.assertFalse(os.path.exists(self.path))
        self.assertFalse(running.valid_session(sid))
        self.assertFalse(aw.Auth(self.TOKEN, store_path=self.path).valid_session(sid))

    def test_drop_session_is_persisted(self):
        auth = aw.Auth(self.TOKEN, store_path=self.path)
        sid = auth.new_session()
        auth.drop_session(sid)
        self.assertFalse(aw.Auth(self.TOKEN, store_path=self.path).valid_session(sid))

    def test_oldest_sessions_are_evicted_beyond_the_limit(self):
        auth = aw.Auth(self.TOKEN, store_path=self.path)
        first = auth.new_session()
        for _ in range(aw.Auth.MAX_SESSIONS):
            auth.new_session()
        self.assertFalse(auth.valid_session(first))

    def test_revoke_without_a_store_is_harmless(self):
        aw.revoke_sessions(self.path)  # ファイルが無くてもエラーにしない

    def test_default_session_lifetime_is_30_days_and_configurable(self):
        self.assertEqual(aw.parse_args([]).session_days, 30)
        self.assertEqual(aw.parse_args(["--session-days", "7"]).session_days, 7)
        self.assertTrue(aw.parse_args(["--revoke-sessions"]).revoke_sessions)
        self.assertEqual(aw.SESSION_TTL, 30 * 86400)


class PersistentLoginTest(unittest.TestCase):
    """サーバーを止めて起動し直しても、ログイン済みの端末は再認証なしで使える（トークンは変わる）。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="taw-login-")
        self.sessions = os.path.join(self.tmp, "sessions.json")
        self.servers = []

    def tearDown(self):
        for srv in self.servers:
            srv.shutdown()
            srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def serve(self, token):
        cfg = aw.Config(
            tmux_socket=os.path.join(self.tmp, "no-such-socket"), claude_bin="true", sessions_dir=self.tmp,
            projects_dir=self.tmp, alert_state=os.path.join(self.tmp, "none"), title_dir=self.tmp,
            token=token, quiet=True, sessions_path=self.sessions,
        )
        srv = aw.make_server("127.0.0.1", 0, cfg, frozenset({"127.0.0.1"}))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.servers.append(srv)
        return srv

    def stop(self, srv):
        srv.shutdown()
        srv.server_close()
        self.servers.remove(srv)

    def login(self, srv, token):
        status, _, res = http_call(srv.server_address[1], "POST", "/api/login", {"token": token})
        return status, res.getheader("Set-Cookie")

    def agents_status(self, srv, cookie):
        return http_call(srv.server_address[1], "GET", "/api/agents", cookie=cookie)[0]

    def test_login_survives_a_server_restart_with_a_new_token(self):
        first = self.serve("first-token-0123456789")
        status, set_cookie = self.login(first, "first-token-0123456789")
        self.assertEqual(status, 204)
        cookie = set_cookie.split(";")[0]
        self.assertEqual(self.agents_status(first, cookie), 200)
        self.stop(first)

        second = self.serve("second-token-0123456789")
        self.assertEqual(self.agents_status(second, cookie), 200)  # 再認証なし
        self.assertEqual(self.login(second, "first-token-0123456789")[0], 401)  # 古いトークンは使えない

    def test_cookie_lifetime_is_30_days(self):
        srv = self.serve("lifetime-token-0123456789")
        _, set_cookie = self.login(srv, "lifetime-token-0123456789")
        self.assertIn(f"Max-Age={30 * 86400}", set_cookie)

    def test_revoke_logs_out_a_running_server(self):
        srv = self.serve("revoke-token-0123456789")
        cookie = self.login(srv, "revoke-token-0123456789")[1].split(";")[0]
        self.assertEqual(self.agents_status(srv, cookie), 200)
        aw.revoke_sessions(self.sessions)
        self.assertEqual(self.agents_status(srv, cookie), 401)

    def test_logout_ends_the_session_for_good(self):
        first = self.serve("logout-token-0123456789")
        cookie = self.login(first, "logout-token-0123456789")[1].split(";")[0]
        self.assertEqual(http_call(first.server_address[1], "POST", "/api/logout", {}, cookie=cookie)[0], 204)
        self.stop(first)
        second = self.serve("logout-token-9876543210")
        self.assertEqual(self.agents_status(second, cookie), 401)


OPENSSL = shutil.which("openssl")


def openssl(*args):
    return subprocess.run([OPENSSL, *args], capture_output=True, text=True)


@unittest.skipUnless(OPENSSL, "openssl が必要")
class SelfSignedCertTest(unittest.TestCase):
    """HTTPS 用の自己署名の証明書（CA は作らない）。起動時に無ければ自動で作る。"""

    HOST = "ca-test.local"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="taw-cert-")
        self.dir = os.path.join(self.tmp, "tls")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ensure(self, **kw):
        return aw.ensure_self_signed_cert(self.dir, [self.HOST, "localhost"], ["127.0.0.1", "192.168.11.40"], **kw)

    def text(self, path):
        return openssl("x509", "-in", path, "-noout", "-text").stdout

    def test_creates_a_private_self_signed_cert_and_nothing_else(self):
        files = self.ensure()
        self.assertEqual(stat.S_IMODE(os.stat(files["server_key"]).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.dir).st_mode), 0o700)
        self.assertEqual(sorted(os.listdir(self.dir)), ["server.crt", "server.key"])  # CA も作業用ファイルも残さない
        names = openssl("x509", "-in", files["server_crt"], "-noout", "-subject", "-issuer").stdout.splitlines()
        subject, issuer = (line.split("=", 1)[1].strip() for line in names)
        self.assertEqual(subject, issuer)  # 自己署名

    def test_cert_covers_the_names_and_is_long_lived(self):
        files = self.ensure()
        text = self.text(files["server_crt"])
        for name in (f"DNS:{self.HOST}", "DNS:localhost", "IP Address:127.0.0.1", "IP Address:192.168.11.40"):
            self.assertIn(name, text)
        self.assertIn("TLS Web Server Authentication", text)
        # 作り直すと証明書が変わり、ブラウザの「続行」の記憶（証明書ごと）が無効になるので、長く使えるようにする
        self.assertEqual(openssl("x509", "-in", files["server_crt"], "-noout", "-checkend", str(3000 * 86400)).returncode, 0)

    def test_existing_cert_is_kept_so_the_browsers_continue_choice_stays_valid(self):
        before = Path(self.ensure()["server_crt"]).read_text()
        self.assertEqual(Path(self.ensure()["server_crt"]).read_text(), before)

    def test_cert_about_to_expire_is_replaced(self):
        before = Path(self.ensure(days=10)["server_crt"]).read_text()
        self.assertNotEqual(Path(self.ensure()["server_crt"]).read_text(), before)

    def test_python_ssl_can_serve_it(self):
        files = self.ensure()
        ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(files["server_crt"], files["server_key"])

    def test_tls_ready_needs_both_files(self):
        self.assertFalse(aw.tls_ready(self.dir))
        self.ensure()
        self.assertTrue(aw.tls_ready(self.dir))

    def test_without_openssl_it_fails_with_a_clear_error(self):
        with mock.patch.object(aw.shutil, "which", return_value=None):
            with self.assertRaises(RuntimeError):
                self.ensure()


@unittest.skipUnless(OPENSSL, "openssl が必要")
class DualProtocolServerTest(unittest.TestCase):
    """同じポートで、HTTP と HTTPS の両方を受け付ける（最初の 1 バイトで見分ける）。"""

    TOKEN = "dual-token-0123456789"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="taw-dual-")
        self.files = aw.ensure_self_signed_cert(os.path.join(self.tmp, "tls"), ["ca-test.local", "localhost"], ["127.0.0.1"])
        self.servers = []

    def tearDown(self):
        for srv in self.servers:
            srv.shutdown()
            srv.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def serve(self, tls=True):
        cfg = aw.Config(
            tmux_socket=os.path.join(self.tmp, "none"), claude_bin="true", sessions_dir=self.tmp, projects_dir=self.tmp,
            alert_state=os.path.join(self.tmp, "none"), title_dir=self.tmp, token=self.TOKEN, quiet=True,
            tls_cert=self.files["server_crt"] if tls else "", tls_key=self.files["server_key"] if tls else "",
        )
        srv = aw.make_server("127.0.0.1", 0, cfg, frozenset({"127.0.0.1"}))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.servers.append(srv)
        return srv.server_address[1]

    @staticmethod
    def browser_after_continue():
        """証明書の警告で「続行」したブラウザ（検証しない）。"""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def test_the_same_port_serves_plain_http_and_https(self):
        port = self.serve()
        self.assertEqual(http_call(port, "GET", "/healthz")[0], 200)
        self.assertEqual(http_call(port, "GET", "/healthz", context=self.browser_after_continue())[0], 200)

    def test_https_presents_the_generated_certificate(self):
        port = self.serve()
        with socket.create_connection(("127.0.0.1", port), timeout=5) as raw:
            with self.browser_after_continue().wrap_socket(raw, server_hostname="ca-test.local") as tls:
                presented = ssl.DER_cert_to_PEM_cert(tls.getpeercert(binary_form=True))
        self.assertEqual(presented.strip(), Path(self.files["server_crt"]).read_text().strip())

    def test_a_client_that_verifies_refuses_the_untrusted_cert(self):
        port = self.serve()
        with self.assertRaises(ssl.SSLCertVerificationError):
            http_call(port, "GET", "/healthz", context=ssl.create_default_context())

    def test_cookie_is_secure_only_on_https_connections(self):
        port = self.serve()
        body = {"token": self.TOKEN}
        _, _, over_https = http_call(port, "POST", "/api/login", body, context=self.browser_after_continue())
        _, _, over_http = http_call(port, "POST", "/api/login", body)
        self.assertIn("Secure", over_https.getheader("Set-Cookie"))
        self.assertNotIn("Secure", over_http.getheader("Set-Cookie"))

    def test_origin_must_match_the_scheme_of_the_connection(self):
        port = self.serve()
        body, ctx = {"token": self.TOKEN}, self.browser_after_continue()
        self.assertEqual(http_call(port, "POST", "/api/login", body, origin=f"http://127.0.0.1:{port}", context=ctx)[0], 403)
        self.assertEqual(http_call(port, "POST", "/api/login", body, origin=f"https://127.0.0.1:{port}")[0], 403)
        self.assertEqual(http_call(port, "POST", "/api/login", body, context=ctx)[0], 204)
        self.assertEqual(http_call(port, "POST", "/api/login", body)[0], 204)

    def test_a_silent_connection_does_not_block_other_clients(self):
        """ブラウザは、何も送らない予備の接続を張ることがある。それで他の接続が待たされてはいけない。"""
        port = self.serve()
        with socket.create_connection(("127.0.0.1", port), timeout=5):
            started = time.time()
            self.assertEqual(http_call(port, "GET", "/healthz", context=self.browser_after_continue())[0], 200)
            self.assertEqual(http_call(port, "GET", "/healthz")[0], 200)
            self.assertLess(time.time() - started, 3)

    def test_garbage_bytes_do_not_break_the_server(self):
        port = self.serve()
        with socket.create_connection(("127.0.0.1", port), timeout=5) as raw:
            raw.sendall(b"\x00\x01garbage\r\n\r\n")
            raw.settimeout(5)
            try:
                raw.recv(4096)
            except OSError:
                pass
        self.assertEqual(http_call(port, "GET", "/healthz")[0], 200)

    def test_http_only_server_refuses_https(self):
        port = self.serve(tls=False)
        self.assertEqual(http_call(port, "GET", "/healthz")[0], 200)
        with self.assertRaises(OSError):
            http_call(port, "GET", "/healthz", context=self.browser_after_continue())

    def test_there_is_no_ca_download_any_more(self):
        port = self.serve()
        self.assertEqual(http_call(port, "GET", "/ca.crt")[0], 404)


@unittest.skipUnless(OPENSSL, "openssl が必要")
class TlsCommandLineTest(unittest.TestCase):
    """プロセスとして起動したときの、HTTPS の自動選択と URL。"""

    TOKEN = "cli-token-0123456789"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="taw-cli-")
        self.state = os.path.join(self.tmp, "state.json")
        self.tls_dir = os.path.join(self.tmp, "tls")
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.terminate()
                p.wait(5)
            p.stderr.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def start(self, *extra):
        cmd = [sys.executable, str(SCRIPT), "--host", "127.0.0.1", "--port", "0", "--state-file", self.state,
               "--tls-dir", self.tls_dir, *extra]
        p = subprocess.Popen(cmd, env=dict(os.environ, TMUX_AGENT_WEB_TOKEN=self.TOKEN),
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.procs.append(p)
        state = wait_for(lambda: (aw.read_state(self.state) or {}).get("pid") == p.pid and aw.read_state(self.state))
        self.assertTrue(state, "状態ファイルが書かれませんでした")
        return p, state

    def test_https_is_on_by_default_with_an_automatic_certificate(self):
        _, state = self.start()
        self.assertEqual(state["scheme"], "https")
        self.assertTrue(aw.tls_ready(self.tls_dir))

    def test_the_main_url_uses_the_local_name_and_the_ip_url_is_kept_separately(self):
        _, state = self.start()
        self.assertRegex(state["url"], r"^https://[^/:]+\.local:\d+/#token=")  # w でコピーされるのは、この .local の URL
        self.assertTrue(state["ipUrl"].startswith(f"https://127.0.0.1:{state['port']}/#token="))

    def test_no_tls_means_plain_http_and_creates_no_certificate(self):
        _, state = self.start("--no-tls")
        self.assertEqual(state["scheme"], "http")
        self.assertTrue(state["url"].startswith("http://"))
        self.assertFalse(aw.tls_ready(self.tls_dir))

    def test_the_certificate_is_reused_across_restarts(self):
        p, _ = self.start()
        first = Path(aw.tls_paths(self.tls_dir)["server_crt"]).read_text()
        p.terminate()
        p.wait(10)
        self.start()
        self.assertEqual(Path(aw.tls_paths(self.tls_dir)["server_crt"]).read_text(), first)

    def test_the_ca_commands_are_gone(self):
        for flag in ("--make-cert", "--cert-ip", "--no-name-constraints"):
            with self.assertRaises(SystemExit):
                aw.parse_args([flag])


def wait_for(predicate, timeout=8.0, step=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return None


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class StateFileTest(unittest.TestCase):
    """sidebar が読む状態ファイル（pid・ポート・URL）。トークンを含むので本人だけが読めること。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="taw-state-")
        self.path = os.path.join(self.tmp, "sub", "state.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_state_is_private(self):
        aw.write_state(self.path, {"pid": 1234, "port": 8765, "url": "http://x/#token=t"})
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(self.path)).st_mode), 0o700)
        self.assertEqual(aw.read_state(self.path)["port"], 8765)

    def test_read_state_returns_none_for_missing_or_broken_file(self):
        self.assertIsNone(aw.read_state(self.path))
        os.makedirs(os.path.dirname(self.path))
        Path(self.path).write_text("{broken")
        self.assertIsNone(aw.read_state(self.path))
        Path(self.path).write_text("[1, 2]")
        self.assertIsNone(aw.read_state(self.path))

    def test_instance_running_needs_a_live_process_that_is_ours(self):
        state = {"pid": 4242}
        self.assertTrue(aw.instance_running(state, is_ours=lambda pid: True))
        self.assertFalse(aw.instance_running(state, is_ours=lambda pid: False))
        self.assertFalse(aw.instance_running(None, is_ours=lambda pid: True))
        self.assertFalse(aw.instance_running({"pid": "x"}, is_ours=lambda pid: True))

    def test_process_is_ours_rejects_other_and_dead_processes(self):
        self.assertFalse(aw.process_is_ours(os.getpid()))  # このテストの実行プロセスは tmux-agent-web ではない
        done = subprocess.Popen(["true"])
        done.wait()
        self.assertFalse(aw.process_is_ours(done.pid))

    def test_remove_state_only_removes_the_owners_file(self):
        aw.write_state(self.path, {"pid": 1234})
        aw.remove_state(self.path, 9999)
        self.assertIsNotNone(aw.read_state(self.path))
        aw.remove_state(self.path, 1234)
        self.assertIsNone(aw.read_state(self.path))


class RunningServerTest(unittest.TestCase):
    """実際にプロセスとして起動し、状態ファイル・二重起動の拒否・SIGTERM での後片付けを確かめる。"""

    TOKEN = "process-token-0123456789"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="taw-proc-")
        self.state = os.path.join(self.tmp, "state.json")
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.terminate()
                p.wait(5)
            p.stderr.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def command(self, *extra):
        return [sys.executable, str(SCRIPT), "--host", "127.0.0.1", "--port", "0", "--state-file", self.state, *extra]

    def env(self):
        return dict(os.environ, TMUX_AGENT_WEB_TOKEN=self.TOKEN)

    def start(self, *extra):
        p = subprocess.Popen(self.command(*extra), env=self.env(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.procs.append(p)
        state = wait_for(lambda: (aw.read_state(self.state) or {}).get("pid") == p.pid and aw.read_state(self.state))
        self.assertTrue(state, "状態ファイルが書かれませんでした")
        return p, state

    def test_writes_state_serves_and_cleans_up_on_sigterm(self):
        p, state = self.start("--read-only")
        self.assertEqual((state["host"], state["readOnly"]), ("127.0.0.1", True))
        self.assertIn(f"#token={self.TOKEN}", state["url"])
        conn = http.client.HTTPConnection("127.0.0.1", state["port"], timeout=5)
        conn.request("GET", "/healthz", headers={"Host": f"127.0.0.1:{state['port']}"})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 200)
        p.send_signal(15)  # SIGTERM（toggle の OFF と同じ）
        self.assertEqual(p.wait(10), 0)
        self.assertIsNone(aw.read_state(self.state))

    def test_second_instance_is_refused_and_first_keeps_running(self):
        first, _ = self.start()
        second = subprocess.run(self.command(), env=self.env(), capture_output=True, text=True, timeout=20)
        self.assertEqual(second.returncode, 1)
        self.assertIn("すでに起動", second.stderr)
        self.assertIsNone(first.poll())
        self.assertEqual(aw.read_state(self.state)["pid"], first.pid)

    def test_state_left_by_a_dead_process_is_replaced(self):
        done = subprocess.Popen(["true"])
        done.wait()
        aw.write_state(self.state, {"pid": done.pid, "port": 1, "host": "127.0.0.1", "url": "x"})
        p, state = self.start()
        self.assertEqual(state["pid"], p.pid)


TOGGLE = SCRIPT.with_name("tmux-agent-web-toggle")


@unittest.skipUnless(shutil.which("jq"), "jq が必要")
class ToggleScriptTest(unittest.TestCase):
    """sidebar の w から呼ばれる入り切りスクリプト。--notify を付けないので tmux にもクリップボードにも触れない。"""

    TOKEN = "toggle-token-0123456789"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="taw-toggle-")
        self.state = os.path.join(self.tmp, "state.json")
        self.env = dict(
            os.environ, TMUX_AGENT_WEB_STATE=self.state, AGENT_WEB_BIN=str(SCRIPT),
            AGENT_WEB_ARGS="--host 127.0.0.1 --port 0 --read-only", TMUX_AGENT_WEB_TOKEN=self.TOKEN,
        )
        self.env.pop("TMUX", None)

    def tearDown(self):
        self.toggle("stop")
        shutil.rmtree(self.tmp, ignore_errors=True)

    def toggle(self, *args):
        return subprocess.run([str(TOGGLE), *args], env=self.env, capture_output=True, text=True, timeout=30)

    def test_toggle_starts_then_stops(self):
        on = self.toggle("toggle")
        self.assertEqual(on.returncode, 0, on.stderr)
        self.assertIn("ON", on.stdout)
        state = aw.read_state(self.state)
        self.assertTrue(pid_alive(state["pid"]))
        status = self.toggle("status")
        self.assertEqual(status.returncode, 0)
        self.assertIn("ON", status.stdout)
        self.assertIn(str(state["port"]), status.stdout)
        self.assertNotIn(self.TOKEN, status.stdout)  # status にトークンは出さない

        off = self.toggle("toggle")
        self.assertEqual(off.returncode, 0, off.stderr)
        self.assertIn("OFF", off.stdout)
        self.assertTrue(wait_for(lambda: not pid_alive(state["pid"])))
        self.assertIsNone(aw.read_state(self.state))
        self.assertEqual(self.toggle("status").returncode, 1)

    def test_url_prints_the_tokenized_url_only_when_running(self):
        self.assertNotEqual(self.toggle("url").returncode, 0)
        self.toggle("start")
        url = self.toggle("url")
        self.assertEqual(url.returncode, 0)
        self.assertIn(f"#token={self.TOKEN}", url.stdout)

    def test_start_twice_does_not_start_a_second_server(self):
        self.toggle("start")
        pid = aw.read_state(self.state)["pid"]
        again = self.toggle("start")
        self.assertEqual(again.returncode, 0)
        self.assertEqual(aw.read_state(self.state)["pid"], pid)

    def test_copy_with_notify_puts_the_url_on_the_clipboard_command(self):
        clip_out = os.path.join(self.tmp, "clip.txt")
        fake = Path(self.tmp, "fakeclip")
        fake.write_text(f'#!/bin/sh\ncat > "{clip_out}"\n')
        fake.chmod(0o755)
        self.env.update(AGENT_WEB_CLIP_CMD=str(fake), TMUX_TMPDIR=self.tmp)  # tmux のサーバーも本物には繋がらない
        self.assertEqual(self.toggle("copy", "--notify").returncode, 1)  # 止まっているので何もコピーしない
        self.assertFalse(os.path.exists(clip_out))
        self.toggle("start")
        self.assertEqual(self.toggle("copy", "--notify").returncode, 0)
        self.assertIn(f"#token={self.TOKEN}", Path(clip_out).read_text())
        self.assertEqual(self.toggle("copy").returncode, 2)  # --notify なしではクリップボードに触れない

    @unittest.skipUnless(OPENSSL, "openssl が必要")
    def test_status_says_https_and_url_is_the_local_name_when_the_server_runs_with_tls(self):
        self.assertEqual(self.toggle("start").returncode, 0)
        self.assertIn("https", self.toggle("status").stdout)
        url = self.toggle("url").stdout.strip()
        self.assertRegex(url, r"^https://[^/:]+\.local:\d+/#token=")  # w でコピーされるのは .local の URL

    def test_revoke_subcommand_removes_the_session_store(self):
        sessions = os.path.join(self.tmp, "sessions.json")  # 状態ファイルと同じディレクトリ
        Path(sessions).write_text('{"sessions": {"abc": 9999999999}}')
        res = self.toggle("revoke")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertFalse(os.path.exists(sessions))

    def test_stale_state_counts_as_off(self):
        done = subprocess.Popen(["true"])
        done.wait()
        aw.write_state(self.state, {"pid": done.pid, "port": 1, "host": "127.0.0.1", "url": "x"})
        self.assertEqual(self.toggle("status").returncode, 1)
        self.assertIn("ON", self.toggle("toggle").stdout)  # 古い状態は無視して起動する


if __name__ == "__main__":
    unittest.main()
