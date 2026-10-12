"""usage credits（今月の支出）の取得スクリプトと statusline 表示のテスト。

本物の claude は呼ばない。偽の claude が固定の応答を返し、呼び出し回数を記録する。
"""
import json
import os
import stat
import subprocess
import tempfile
import time
import unittest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..")
FETCH = os.path.join(SCRIPTS, "fetch-usage-credits.sh")
STATUSLINE = os.path.join(SCRIPTS, "statusline.sh")


def control_response(extra_usage=None, spend=None, subtype="success"):
    """claude -p の get_usage 応答（control_response）の 1 行を作る。実機の形に合わせる。"""
    rate_limits = {"five_hour": None, "seven_day": None, "limits": []}
    if extra_usage is not None:
        rate_limits["extra_usage"] = extra_usage
    if spend is not None:
        rate_limits["spend"] = spend
    return json.dumps(
        {
            "type": "control_response",
            "response": {
                "subtype": subtype,
                "request_id": "u1",
                "response": {
                    "session": {"total_cost_usd": 0},
                    "subscription_type": "enterprise",
                    "rate_limits_available": True,
                    "rate_limits": rate_limits,
                },
            },
        }
    )


# 実機で取得した応答（2026-10-11）と同じ構造
ENTERPRISE_EXTRA_USAGE = {
    "is_enabled": True,
    "monthly_limit": 130000,
    "used_credits": 2842,
    "utilization": 2.186153846153846,
    "currency": "USD",
    "decimal_places": 2,
}
ENTERPRISE_SPEND = {
    "used": {"amount_minor": 2842, "currency": "USD", "exponent": 2},
    "limit": {"amount_minor": 130000, "currency": "USD", "exponent": 2},
    "percent": 2,
    "enabled": True,
}


class Env:
    """一時ディレクトリに偽の claude・キャッシュ・呼び出し記録を用意する。"""

    def __init__(self, stdout_lines, exit_code=0):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.cache = os.path.join(t, "credits.json")
        self.calls = os.path.join(t, "calls.log")
        self.fake_claude = os.path.join(t, "claude")
        body = "\n".join(stdout_lines)
        with open(self.fake_claude, "w") as f:
            f.write(
                "#!/bin/bash\n"
                f'echo "$@" >> "{self.calls}"\n'
                "cat > /dev/null\n"
                f"cat <<'EOF'\n{body}\nEOF\n"
                f"exit {exit_code}\n"
            )
        os.chmod(self.fake_claude, os.stat(self.fake_claude).st_mode | stat.S_IEXEC)

    def env(self, **extra):
        env = dict(os.environ)
        env.update(
            CLAUDE_CREDITS_CACHE=self.cache,
            CLAUDE_CREDITS_CLAUDE_BIN=self.fake_claude,
            CLAUDE_CREDITS_TTL="300",
            CLAUDE_DISABLE_AI_TITLE="1",
        )
        env.update(extra)
        return env

    def fetch(self, **extra):
        return subprocess.run(
            ["bash", FETCH], env=self.env(**extra), capture_output=True, text=True, timeout=60
        )

    def call_count(self):
        if not os.path.exists(self.calls):
            return 0
        with open(self.calls) as f:
            return len(f.read().splitlines())

    def cached(self):
        with open(self.cache) as f:
            return json.load(f)

    def write_cache(self, **fields):
        data = {
            "enabled": True,
            "used": 28.42,
            "limit": 1300.0,
            "percent": 2.186,
            "currency": "USD",
            "fetched_at": int(time.time()),
        }
        data.update(fields)
        with open(self.cache, "w") as f:
            json.dump(data, f)

    def cleanup(self):
        self.tmp.cleanup()


class FetchUsageCreditsTest(unittest.TestCase):
    def make(self, lines, **kw):
        e = Env(lines, **kw)
        self.addCleanup(e.cleanup)
        return e

    def test_extra_usage_だけでも_最小単位から通貨単位へ変換して保存する(self):
        e = self.make(["junk line", control_response(extra_usage=ENTERPRISE_EXTRA_USAGE)])
        e.fetch()
        c = e.cached()
        self.assertAlmostEqual(c["used"], 28.42)
        self.assertAlmostEqual(c["limit"], 1300.0)
        self.assertEqual(c["currency"], "USD")
        self.assertTrue(c["enabled"])

    def test_spend_があれば_exponent_を使って変換する(self):
        spend = {
            "used": {"amount_minor": 12345, "currency": "USD", "exponent": 2},
            "limit": {"amount_minor": 50000, "currency": "USD", "exponent": 2},
        }
        e = self.make([control_response(extra_usage=ENTERPRISE_EXTRA_USAGE, spend=spend)])
        e.fetch()
        c = e.cached()
        self.assertAlmostEqual(c["used"], 123.45)
        self.assertAlmostEqual(c["limit"], 500.0)

    def test_使用率は_使用額と上限から計算する(self):
        e = self.make([control_response(extra_usage=ENTERPRISE_EXTRA_USAGE, spend=ENTERPRISE_SPEND)])
        e.fetch()
        self.assertAlmostEqual(e.cached()["percent"], 2.186, places=2)

    def test_取得時刻を記録する(self):
        e = self.make([control_response(extra_usage=ENTERPRISE_EXTRA_USAGE)])
        before = int(time.time())
        e.fetch()
        self.assertGreaterEqual(e.cached()["fetched_at"], before)

    def test_上限なしなら_limit_は_null_で保存する(self):
        extra = dict(ENTERPRISE_EXTRA_USAGE, monthly_limit=None, utilization=None)
        e = self.make([control_response(extra_usage=extra)])
        e.fetch()
        c = e.cached()
        self.assertIsNone(c["limit"])
        self.assertIsNone(c["percent"])
        self.assertAlmostEqual(c["used"], 28.42)

    def test_credits_が無効なら_enabled_false_で保存する(self):
        extra = {"is_enabled": False, "monthly_limit": None, "used_credits": None}
        e = self.make([control_response(extra_usage=extra)])
        e.fetch()
        self.assertFalse(e.cached()["enabled"])

    def test_TTL_内ならclaudeを呼ばない(self):
        e = self.make([control_response(extra_usage=ENTERPRISE_EXTRA_USAGE)])
        e.write_cache()
        e.fetch()
        self.assertEqual(e.call_count(), 0)

    def test_TTL_を過ぎたら再取得する(self):
        e = self.make([control_response(extra_usage=ENTERPRISE_EXTRA_USAGE)])
        e.write_cache(fetched_at=int(time.time()) - 1000, used=1.0)
        e.fetch()
        self.assertEqual(e.call_count(), 1)
        self.assertAlmostEqual(e.cached()["used"], 28.42)

    def test_取得に失敗しても_前回の値と時刻を残す(self):
        e = self.make(["not json at all"], exit_code=1)
        old = int(time.time()) - 1000
        e.write_cache(fetched_at=old, used=5.0)
        e.fetch()
        c = e.cached()
        self.assertAlmostEqual(c["used"], 5.0)
        self.assertEqual(c["fetched_at"], old)

    def test_失敗しても_キャッシュが無ければ作らない(self):
        e = self.make(["not json at all"], exit_code=1)
        e.fetch()
        self.assertFalse(os.path.exists(e.cache))

    def test_失敗直後は_TTL_の間_再試行しない(self):
        e = self.make(["not json at all"], exit_code=1)
        e.fetch()
        e.fetch()
        self.assertEqual(e.call_count(), 1)

    def test_error_応答はキャッシュを壊さない(self):
        e = self.make([control_response(subtype="error")])
        e.write_cache(fetched_at=int(time.time()) - 1000, used=5.0)
        e.fetch()
        self.assertAlmostEqual(e.cached()["used"], 5.0)

    def test_金額のフィールドが欠けた応答は採用しない(self):
        e = self.make([control_response()])
        e.write_cache(fetched_at=int(time.time()) - 1000, used=5.0)
        e.fetch()
        self.assertAlmostEqual(e.cached()["used"], 5.0)

    def test_ロック中は取得しない(self):
        e = self.make([control_response(extra_usage=ENTERPRISE_EXTRA_USAGE)])
        os.makedirs(e.cache + ".lock")
        e.fetch()
        self.assertEqual(e.call_count(), 0)

    def test_古いロックは破棄して取得する(self):
        e = self.make([control_response(extra_usage=ENTERPRISE_EXTRA_USAGE)])
        lock = e.cache + ".lock"
        os.makedirs(lock)
        old = time.time() - 3600
        os.utime(lock, (old, old))
        e.fetch()
        self.assertEqual(e.call_count(), 1)

    def test_get_usage_のリクエストを標準入力へ渡す(self):
        e = self.make([control_response(extra_usage=ENTERPRISE_EXTRA_USAGE)])
        e.fetch()
        with open(e.calls) as f:
            args = f.read()
        self.assertIn("-p", args)
        self.assertIn("--verbose", args)
        self.assertIn("stream-json", args)


class StatuslineRefreshTest(unittest.TestCase):
    """statusline.sh は 💳 を表示しない（表示は tmux sidebar）。取得を裏で起動する役だけ持つ。"""

    def setUp(self):
        self.e = Env([control_response(extra_usage=ENTERPRISE_EXTRA_USAGE)])
        self.addCleanup(self.e.cleanup)
        # 起動されたことを印で残す偽の取得コマンド
        self.marker = os.path.join(self.e.tmp.name, "fetch-started")
        self.fake_fetch = os.path.join(self.e.tmp.name, "fake-fetch")
        with open(self.fake_fetch, "w") as f:
            f.write(f"#!/bin/bash\ntouch '{self.marker}'\n")
        os.chmod(self.fake_fetch, 0o755)

    def run_statusline(self, **env_extra):
        env = self.e.env(CLAUDE_CREDITS_FETCH_CMD=self.fake_fetch, **env_extra)
        payload = json.dumps({"session_id": "s", "cost": {"total_cost_usd": 0}})
        return subprocess.run(
            ["bash", STATUSLINE], input=payload, env=env, capture_output=True, text=True, timeout=60
        ).stdout

    def started(self, wait=2.0):
        deadline = time.time() + wait
        while time.time() < deadline:
            if os.path.exists(self.marker):
                return True
            time.sleep(0.1)
        return False

    def test_credits_を表示しない(self):
        self.e.write_cache()
        out = self.run_statusline()
        self.assertNotIn("💳", out)
        self.assertNotIn("今月", out)

    def test_キャッシュが無ければ取得を起動する(self):
        self.run_statusline()
        self.assertTrue(self.started())

    def test_キャッシュが古ければ取得を起動する(self):
        self.e.write_cache()
        old = time.time() - 1000
        os.utime(self.e.cache, (old, old))
        self.run_statusline()
        self.assertTrue(self.started())

    def test_キャッシュが新しければ取得を起動しない(self):
        self.e.write_cache()
        self.run_statusline()
        self.assertFalse(self.started(wait=1.0))

    def test_直近に試行していれば取得を起動しない(self):
        with open(self.e.cache + ".attempt", "w"):
            pass
        self.run_statusline()
        self.assertFalse(self.started(wait=1.0))

    def test_取得プロセスの中からは取得を起動しない(self):
        self.run_statusline(CLAUDE_CREDITS_FETCHING="1")
        self.assertFalse(self.started(wait=1.0))


if __name__ == "__main__":
    unittest.main()
