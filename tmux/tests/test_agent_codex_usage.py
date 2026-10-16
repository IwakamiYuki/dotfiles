"""tmux-agent-codex-usage（Codex の今月の使用量の取得）のテスト。

偽の codex（app-server の JSON-RPC を話す小さなスクリプト）を使うので、本物の API は呼ばない。
キャッシュは一時ディレクトリに書く（普段の /tmp/codex-usage.json には触れない）。
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "tmux-agent-codex-usage")

FAKE_CODEX = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_CODEX_LOG"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
mode = open(os.environ["FAKE_CODEX_MODE"]).read().strip()
for line in sys.stdin:
    msg = json.loads(line)
    if msg.get("id") == 1:
        print(json.dumps({"id": 1, "result": {}}), flush=True)
    elif msg.get("id") == 2:
        if mode == "silent":
            continue
        if mode == "error":
            print(json.dumps({"id": 2, "error": {"code": -1, "message": "no"}}), flush=True)
        else:
            print(json.dumps({"id": 2, "result": json.load(open(os.environ["FAKE_CODEX_RESULT"]))}), flush=True)
        break
"""


def rate_limits_result(individual="default"):
    if individual == "default":
        individual = {"limit": "20000", "used": "2533.5", "remainingPercent": 87, "resetsAt": 1793491200}
    return {
        "rateLimits": {
            "limitId": "codex",
            "primary": None,
            "secondary": None,
            "credits": {"hasCredits": True, "unlimited": False, "balance": None},
            "individualLimit": individual,
            "planType": "business",
        }
    }


class CodexUsageTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cxu.")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.cache = os.path.join(self.dir, "usage.json")
        self.log = os.path.join(self.dir, "codex.log")
        self.mode_file = os.path.join(self.dir, "mode")
        self.result_file = os.path.join(self.dir, "result.json")
        self.fake = os.path.join(self.dir, "codex")
        with open(self.fake, "w") as f:
            f.write(FAKE_CODEX)
        os.chmod(self.fake, 0o755)
        self.set_response(rate_limits_result())

    def set_response(self, result, mode="ok"):
        with open(self.result_file, "w") as f:
            json.dump(result, f)
        with open(self.mode_file, "w") as f:
            f.write(mode)

    def run_script(self, *args, ttl=300, codex=None):
        env = {
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "HOME": self.dir,
            "AGENT_CODEX_USAGE_CACHE": self.cache,
            "AGENT_CODEX_BIN": codex or self.fake,
            "AGENT_CODEX_USAGE_TTL": str(ttl),
            "FAKE_CODEX_LOG": self.log,
            "FAKE_CODEX_MODE": self.mode_file,
            "FAKE_CODEX_RESULT": self.result_file,
        }
        return subprocess.run(["python3", "-I", SCRIPT, *args], env=env, capture_output=True, text=True, timeout=60)

    def read_cache(self):
        with open(self.cache) as f:
            return json.load(f)

    def calls(self):
        if not os.path.exists(self.log):
            return 0
        with open(self.log) as f:
            return len(f.read().splitlines())

    def test_月間上限の使用量と上限と使用率をキャッシュへ書く(self):
        proc = self.run_script()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        cache = self.read_cache()
        self.assertTrue(cache["enabled"])
        self.assertEqual(cache["used"], 2533.5)
        self.assertEqual(cache["limit"], 20000)
        self.assertAlmostEqual(cache["percent"], 12.6675)
        self.assertEqual(cache["unit"], "credits")
        self.assertEqual(cache["resets_at"], 1793491200)
        self.assertAlmostEqual(cache["fetched_at"], time.time(), delta=60)

    def test_app_server_を起動して問い合わせる(self):
        self.run_script()
        with open(self.log) as f:
            self.assertEqual(f.read().strip(), "app-server")

    def test_個人の上限が無ければ_enabled_false(self):
        self.set_response(rate_limits_result(individual=None))
        self.run_script()
        cache = self.read_cache()
        self.assertFalse(cache["enabled"])
        self.assertNotIn("used", cache)

    def test_TTL_内なら_codex_を起動しない(self):
        self.run_script()
        self.assertEqual(self.calls(), 1)
        self.run_script()
        self.assertEqual(self.calls(), 1)

    def test_force_なら_TTL_を無視して取得する(self):
        self.run_script()
        self.run_script("--force")
        self.assertEqual(self.calls(), 2)

    def test_TTL_を過ぎたら_取り直す(self):
        self.run_script()
        old = time.time() - 600
        for path in (self.cache, self.cache + ".attempt"):
            os.utime(path, (old, old))
        self.set_response(rate_limits_result({"limit": "20000", "used": "3000", "remainingPercent": 85, "resetsAt": 1793491200}))
        self.run_script()
        self.assertEqual(self.read_cache()["used"], 3000)

    def test_エラー応答なら_前回の値を消さない(self):
        self.run_script()
        old = time.time() - 600
        for path in (self.cache, self.cache + ".attempt"):
            os.utime(path, (old, old))
        before = self.read_cache()
        self.set_response({}, mode="error")
        proc = self.run_script()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.read_cache(), before)

    def test_形が想定外なら_書かない(self):
        self.set_response({"unexpected": True})
        self.run_script()
        self.assertFalse(os.path.exists(self.cache))

    def test_上限が数値でなければ_書かない(self):
        self.set_response(rate_limits_result({"limit": "n/a", "used": "1"}))
        self.run_script()
        self.assertFalse(os.path.exists(self.cache))

    def test_失敗しても_TTL_の間は再試行しない(self):
        self.set_response({}, mode="error")
        self.run_script()
        self.run_script()
        self.assertEqual(self.calls(), 1)

    def test_codex_が無ければ_何もせず正常終了する(self):
        proc = self.run_script(codex="no-such-codex-binary")
        self.assertEqual(proc.returncode, 0)
        self.assertFalse(os.path.exists(self.cache))

    def test_取得中は_別の取得を始めない(self):
        os.mkdir(self.cache + ".lock")
        self.run_script()
        self.assertEqual(self.calls(), 0)

    def test_古いロックは無視して取得する(self):
        os.mkdir(self.cache + ".lock")
        old = time.time() - 600
        os.utime(self.cache + ".lock", (old, old))
        self.run_script()
        self.assertEqual(self.calls(), 1)
        self.assertFalse(os.path.exists(self.cache + ".lock"))

    def test_取得が済んだらロックを消す(self):
        self.run_script()
        self.assertFalse(os.path.exists(self.cache + ".lock"))


if __name__ == "__main__":
    unittest.main()
