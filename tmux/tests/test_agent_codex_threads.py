"""tmux-agent-codex-threads（Codex のスレッドの状態・名前・モデルの取得）のテスト。

偽の常駐デーモン（unix ソケット上の WebSocket。initialize / thread/loaded/list / thread/read だけ話す）を立てて、
本物と同じ手順で問い合わせさせる。本物のデーモンやスレッドには触れない。
ソケットのパスは長いと接続できない（sun_path の上限）ので、短い /tmp 直下の一時ディレクトリに置く。
"""
import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "tmux-agent-codex-threads")
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def thread(thread_id, cwd, status=None, **extra):
    data = {
        "id": thread_id,
        "cwd": cwd,
        "name": "設計書の確認",
        "model": "gpt-6-astra",
        "reasoningEffort": "low",
        "updatedAt": 1790000000,
        "status": status or {"type": "idle"},
        "parentThreadId": None,
        "ephemeral": False,
    }
    data.update(extra)
    return data


class FakeDaemon:
    """app-server の常駐デーモンの真似。threads は {id: thread dict}。"""

    def __init__(self, path, threads):
        self.threads = threads
        self.read_errors = set()
        self.pongs = 0
        self.server = socket.socket(socket.AF_UNIX)
        self.server.bind(path)
        self.server.listen(8)
        self.stopped = False
        threading.Thread(target=self.serve, daemon=True).start()

    def stop(self):
        self.stopped = True
        self.server.close()

    def serve(self):
        while not self.stopped:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self.handle, args=(conn,), daemon=True).start()

    def recv_exact(self, conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise OSError("closed")
            buf += chunk
        return buf

    def read_frame(self, conn):
        b0, b1 = self.recv_exact(conn, 2)
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack(">H", self.recv_exact(conn, 2))[0]
        elif n == 127:
            n = struct.unpack(">Q", self.recv_exact(conn, 8))[0]
        mask = self.recv_exact(conn, 4)
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(self.recv_exact(conn, n)))
        return b0 & 0x0F, payload

    def send_frame(self, conn, opcode, payload):
        n = len(payload)
        if n < 126:
            head = bytes([0x80 | opcode, n])
        else:
            head = bytes([0x80 | opcode, 126]) + struct.pack(">H", n)
        conn.sendall(head + payload)

    def send(self, conn, obj):
        self.send_frame(conn, 1, json.dumps(obj).encode())

    def handle(self, conn):
        try:
            request = b""
            while b"\r\n\r\n" not in request:
                request += conn.recv(4096)
            key = [l.split(b": ", 1)[1] for l in request.split(b"\r\n") if l.lower().startswith(b"sec-websocket-key")][0]
            accept = base64.b64encode(hashlib.sha1(key + GUID.encode()).digest()).decode()
            conn.sendall(
                ("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                 f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode()
            )
            while True:
                opcode, payload = self.read_frame(conn)
                if opcode == 8:
                    return
                if opcode in (9, 10):  # ping / pong(クライアントが ping に pong を返せているか)
                    if opcode == 10:
                        self.pongs += 1
                    continue
                message = json.loads(payload)
                if "id" not in message:
                    continue
                # 応答の前に、無関係な通知と ping を挟む(読み捨てられること、pong を返せることの確認)
                self.send(conn, {"method": "thread/status/changed", "params": {}})
                self.send_frame(conn, 9, b"hi")
                self.send(conn, self.respond(message))
        except OSError:
            return
        finally:
            conn.close()

    def respond(self, message):
        method, params = message["method"], message.get("params") or {}
        if method == "initialize":
            return {"id": message["id"], "result": {"userAgent": "fake"}}
        if method == "thread/loaded/list":
            return {"id": message["id"], "result": {"data": list(self.threads), "nextCursor": None}}
        if method == "thread/read":
            if params["threadId"] in self.read_errors:
                return {"id": message["id"], "error": {"code": -1, "message": "no"}}
            return {"id": message["id"], "result": {"thread": self.threads[params["threadId"]]}}
        return {"id": message["id"], "error": {"code": -32601, "message": "unknown"}}


class CodexThreadsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="cxt.", dir="/tmp")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.sock = os.path.join(self.dir, "s")
        self.cache = os.path.join(self.dir, "threads.txt")
        self.work = os.path.realpath(os.path.join(self.dir, "work"))
        os.mkdir(self.work)
        self.daemon = None

    def tearDown(self):
        if self.daemon:
            self.daemon.stop()

    def start_daemon(self, threads):
        self.daemon = FakeDaemon(self.sock, threads)
        return self.daemon

    def run_script(self, *args):
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": self.dir,
            "AGENT_CODEX_SOCK": self.sock,
            "AGENT_CODEX_THREADS_CACHE": self.cache,
        }
        return subprocess.run(["python3", "-I", SCRIPT, *args], env=env, capture_output=True, text=True, timeout=30)

    def rows(self):
        with open(self.cache, encoding="utf-8") as f:
            return [line.rstrip("\n").split("|") for line in f if line.strip()]

    def test_ping_には_pong_を返す(self):
        daemon = self.start_daemon({"t1": thread("t1", self.work)})
        self.run_script()
        self.assertGreater(daemon.pongs, 0)

    def test_状態と名前とモデルを書く(self):
        self.start_daemon({"t1": thread("t1", self.work)})
        proc = self.run_script()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            self.rows(),
            [["X", "t1", self.work, "idle", "", "設計書の確認", "gpt-6-astra", "low", "1790000000", "1790000000"]],
        )

    def test_作業中と待ちは_active_と_フラグで書く(self):
        self.start_daemon(
            {
                "w": thread("w", self.work, {"type": "active", "activeFlags": []}),
                "a": thread("a", self.work, {"type": "active", "activeFlags": ["waitingOnApproval", "waitingOnUserInput"]}),
            }
        )
        self.run_script()
        by_id = {r[1]: r for r in self.rows()}
        self.assertEqual((by_id["w"][3], by_id["w"][4]), ("active", ""))
        self.assertEqual((by_id["a"][3], by_id["a"][4]), ("active", "waitingOnApproval,waitingOnUserInput"))

    def test_cwd_は実体のパスにする(self):
        link = os.path.join(self.dir, "link")
        os.symlink(self.work, link)
        self.start_daemon({"t1": thread("t1", link)})
        self.run_script()
        self.assertEqual(self.rows()[0][2], self.work)

    def test_サブエージェントと一時スレッドは含めない(self):
        self.start_daemon(
            {
                "main": thread("main", self.work),
                "sub": thread("sub", self.work, parentThreadId="main"),
                "tmp": thread("tmp", self.work, ephemeral=True),
            }
        )
        self.run_script()
        self.assertEqual([r[1] for r in self.rows()], ["main"])

    def test_区切りと改行を含む名前は空白にする(self):
        self.start_daemon({"t1": thread("t1", self.work, name="a|b\nc\td")})
        self.run_script()
        rows = self.rows()
        self.assertEqual(len(rows[0]), 10)
        self.assertEqual(rows[0][5], "a b c d")

    def test_読めないスレッドは飛ばして_他は出す(self):
        daemon = self.start_daemon({"ok": thread("ok", self.work), "bad": thread("bad", self.work)})
        daemon.read_errors.add("bad")
        self.run_script()
        self.assertEqual([r[1] for r in self.rows()], ["ok"])

    def test_同じ状態が続けば_since_を保ち_変われば更新する(self):
        daemon = self.start_daemon({"t1": thread("t1", self.work, {"type": "active", "activeFlags": []})})
        before = int(time.time())
        self.run_script()
        first = int(self.rows()[0][8])
        self.assertGreaterEqual(first, before)  # 初めて見た active は「今」
        # 少し待って同じ状態: since は変わらない
        with open(self.cache) as f:
            text = f.read().replace(f"|{first}|", f"|{first - 100}|", 1)
        with open(self.cache, "w") as f:
            f.write(text)
        self.run_script()
        self.assertEqual(int(self.rows()[0][8]), first - 100)
        # 状態が変わる(承認待ち): since は今に更新される
        daemon.threads["t1"]["status"] = {"type": "active", "activeFlags": ["waitingOnApproval"]}
        self.run_script()
        self.assertGreaterEqual(int(self.rows()[0][8]), before)

    def test_初めて見た_idle_は_最後の更新から数える(self):
        self.start_daemon({"t1": thread("t1", self.work, updatedAt=1700000000)})
        self.run_script()
        self.assertEqual(self.rows()[0][8], "1700000000")

    def test_デーモンに届かなければ_空のキャッシュで古い状態を残さない(self):
        daemon = self.start_daemon({"t1": thread("t1", self.work)})
        self.run_script()
        self.assertEqual(len(self.rows()), 1)
        daemon.stop()
        os.unlink(self.sock)
        proc = self.run_script()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.rows(), [])

    def test_ソケットが無くても正常終了して空を書く(self):
        proc = self.run_script()
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.rows(), [])

    def test_stdout_ならキャッシュを書かない(self):
        self.start_daemon({"t1": thread("t1", self.work)})
        proc = self.run_script("--stdout")
        self.assertFalse(os.path.exists(self.cache))
        self.assertTrue(proc.stdout.startswith("X|t1|"))

    def test_WebSocket_でない応答なら_空にする(self):
        server = socket.socket(socket.AF_UNIX)
        server.bind(self.sock)
        server.listen(1)

        def refuse():
            conn, _ = server.accept()
            conn.recv(4096)
            conn.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            conn.close()

        threading.Thread(target=refuse, daemon=True).start()
        self.addCleanup(server.close)
        self.run_script()
        self.assertEqual(self.rows(), [])


if __name__ == "__main__":
    unittest.main()
