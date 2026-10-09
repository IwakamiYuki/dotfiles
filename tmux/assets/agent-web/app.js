// tmux-agent-web のブラウザ側。Agent 一覧（メニュー）・pane の表示・入力・クイックキー。
"use strict";
(() => {
  const { parse, toHtml, maxCells } = window.AnsiView;
  const $ = (sel) => document.querySelector(sel);
  const els = {
    menu: $("#menu"), close: $("#close"), scrim: $("#scrim"), list: $("#list"), view: $("#view"), screen: $("#screen"),
    pill: $("#pill"), name: $("#name"), sub: $("#sub"), text: $("#text"), composer: $("#composer"), send: $("#send"), sendEnter: $("#sendEnter"),
    keys: $("#keys"), login: $("#login"), loginForm: $("#loginForm"), loginToken: $("#loginToken"), loginMsg: $("#loginMsg"),
    toast: $("#toast"), hist: $("#hist"), fit: $("#fit"), zoomIn: $("#zoomIn"), zoomOut: $("#zoomOut"),
    bottom: $("#bottom"), logout: $("#logout"),
    newSheet: $("#newSheet"), newTitle: $("#newTitle"), newCancel: $("#newCancel"),
  };

  // localStorage は使えない環境（プライベートブラウズ等）がある。無くても動く
  const store = {
    get(key, fallback) {
      try {
        const v = localStorage.getItem("taw." + key);
        return v === null ? fallback : v;
      } catch (e) {
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem("taw." + key, String(value));
      } catch (e) { /* 保存できなくても動く */ }
    },
  };

  const HISTORY_LINES = 500;
  const state = {
    agents: [], selected: null, rev: "", history: 0, readOnly: false, running: false, stick: true,
    fit: store.get("fit", "1") === "1", size: Number(store.get("size", "11")) || 11, cells: 0, ratio: 0.6,
    paneTimer: 0, listTimer: 0, newAnchor: null, pendingPane: null, pendingUntil: 0,
  };

  // --- 通信 ---
  async function api(path, body) {
    const init = { credentials: "same-origin", cache: "no-store" };
    if (body !== undefined) {
      init.method = "POST";
      init.headers = { "Content-Type": "application/json", "X-Requested-With": "tmux-agent-web" };
      init.body = JSON.stringify(body);
    }
    let res;
    try {
      res = await fetch(path, init);
    } catch (e) {
      return { ok: false, status: 0, data: null };
    }
    let data = null;
    if (res.status !== 204) {
      try { data = await res.json(); } catch (e) { /* 本文なし */ }
    }
    if (res.status === 401 && path !== "/api/login") showLogin();
    return { ok: res.ok, status: res.status, data };
  }

  const MESSAGES = {
    0: "Mac に接続できません", 400: "送れない入力です", 403: "閲覧のみのモードです", 404: "この Agent は見つかりません",
    429: "試行が多すぎます。しばらく待ってください",
  };
  let toastTimer = 0;
  function toast(message) {
    els.toast.textContent = message;
    els.toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => els.toast.classList.remove("show"), 2200);
  }

  // --- ログイン ---
  function showLogin() {
    els.login.hidden = false;
    state.running = false;
    clearTimeout(state.paneTimer);
    clearTimeout(state.listTimer);
  }

  async function login(token) {
    const r = await api("/api/login", { token });
    if (!r.ok) {
      els.loginMsg.textContent = r.status === 429 ? MESSAGES[429] : r.status === 401 ? "トークンが違います" : MESSAGES[r.status] || "ログインできません";
      return false;
    }
    els.login.hidden = true;
    els.loginToken.value = "";
    els.loginMsg.textContent = "";
    start();
    return true;
  }

  els.loginForm.addEventListener("submit", (e) => {
    e.preventDefault();
    login(els.loginToken.value.trim());
  });
  els.logout.addEventListener("click", async () => {
    await api("/api/logout", {});
    location.reload();
  });

  // --- 一覧 ---
  const fmtElapsed = (s) => {
    if (s === null || s === undefined) return "";
    if (s < 60) return s + "s";
    if (s < 3600) return Math.floor(s / 60) + "m";
    if (s < 86400) return Math.floor(s / 3600) + "h" + String(Math.floor((s % 3600) / 60)).padStart(2, "0") + "m";
    return Math.floor(s / 86400) + "d";
  };
  const shortPath = (p) => p.replace(/^\/Users\/[^/]+/, "~");

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function renderList() {
    const counts = {};
    for (const a of state.agents) counts[a.repoKey] = (counts[a.repoKey] || 0) + 1;
    const frag = document.createDocumentFragment();
    let last = null;
    for (const a of state.agents) {
      if (a.repoKey !== last) {
        last = a.repoKey;
        const g = el("div", "group");
        const add = el("button", "add", "＋");
        add.type = "button";
        add.dataset.id = String(a.id); // そのリポジトリの先頭の Agent（足がかりにする）
        add.dataset.repo = a.repo;
        add.title = a.repo + " で、新しい Agent を起動";
        add.setAttribute("aria-label", a.repo + " で、新しい Agent を起動");
        add.hidden = state.readOnly;
        g.append(el("span", "name", a.repo), el("span", "count", String(counts[a.repoKey])), add);
        frag.append(g);
      }
      const card = el("button", "card st-" + a.status + (a.id === state.selected ? " sel" : ""));
      card.type = "button";
      card.dataset.id = String(a.id);
      const r1 = el("div", "row1");
      r1.append(el("span", "nm", a.name), el("span", "kind", a.type));
      const r3 = el("div", "row3");
      r3.append(el("span", "pill " + a.status, a.status.toUpperCase()), el("span", "det", a.detail), el("span", "el", fmtElapsed(a.elapsed)));
      card.append(r1, el("div", "row2", a.branch ? "⎇ " + a.branch : shortPath(a.cwd)), r3);
      frag.append(card);
    }
    if (!state.agents.length) frag.append(el("p", "empty", "Agent が見つかりません"));
    els.list.replaceChildren(frag);
  }

  els.list.addEventListener("click", (e) => {
    const add = e.target.closest(".add");
    if (add) return openNewSheet(Number(add.dataset.id), add.dataset.repo);
    const card = e.target.closest(".card");
    if (card) select(Number(card.dataset.id), true);
  });

  // --- 新しい Agent を起動（sidebar の n と同じ。リポジトリの見出しの「＋」から、Claude / Codex を選ぶ） ---
  function openNewSheet(anchorId, repo) {
    state.newAnchor = anchorId;
    els.newTitle.textContent = repo + " で、新しい Agent を起動";
    els.newSheet.hidden = false;
  }
  const closeNewSheet = () => {
    els.newSheet.hidden = true;
    state.newAnchor = null;
  };
  els.newCancel.addEventListener("click", closeNewSheet);
  els.newSheet.addEventListener("click", (e) => {
    if (e.target === els.newSheet) closeNewSheet(); // 外側のタップで閉じる
  });
  els.newSheet.addEventListener("click", async (e) => {
    const button = e.target.closest("button[data-kind]");
    if (!button || state.newAnchor === null) return;
    const buttons = els.newSheet.querySelectorAll("button");
    buttons.forEach((b) => (b.disabled = true));
    const r = await api("/api/new", { id: state.newAnchor, kind: button.dataset.kind });
    buttons.forEach((b) => (b.disabled = false));
    if (!r.ok) return toast((r.data && r.data.error) || MESSAGES[r.status] || "起動できませんでした");
    closeNewSheet();
    setDrawer(false);
    // Agent として検出されるまで（Claude は数秒かかる）待ち、検出されたら、その Agent を選ぶ
    state.pendingPane = r.data.pane;
    state.pendingUntil = Date.now() + 60000;
    toast("起動しました。検出されたら、自動で選びます");
    pollAgents();
  });

  function current() {
    return state.agents.find((a) => a.id === state.selected) || null;
  }

  function renderHeader() {
    const a = current();
    els.pill.className = "pill " + (a ? a.status : "unknown");
    els.pill.textContent = a ? a.status.toUpperCase() : "—";
    els.name.textContent = a ? a.name : "Agent を選択";
    els.sub.textContent = a ? [a.repo, a.branch, a.window].filter(Boolean).join(" · ") : "☰ から選びます";
    const waiting = state.agents.filter((x) => x.status === "waiting").length;
    document.title = (waiting ? "(" + waiting + ") " : "") + "tmux agents";
  }

  async function refreshAgents() {
    const r = await api("/api/agents");
    if (!r.ok) return false;
    state.agents = r.data.agents;
    state.readOnly = r.data.readOnly;
    document.body.classList.toggle("ro", state.readOnly);
    if (state.selected === null) {
      const stored = Number(store.get("selected", ""));
      const pick = state.agents.find((a) => a.id === stored) || state.agents.find((a) => a.status === "waiting") || state.agents[0];
      if (pick) select(pick.id, false);
    }
    if (state.pendingPane) {
      const started = state.agents.find((a) => a.pane === state.pendingPane);
      if (started) {
        state.pendingPane = null;
        select(started.id, false);
        return true;
      }
      if (Date.now() > state.pendingUntil) state.pendingPane = null;
    }
    renderList();
    renderHeader();
    return true;
  }

  // --- メニュー ---
  const setDrawer = (open) => document.body.classList.toggle("drawer", open);
  els.menu.addEventListener("click", () => {
    setDrawer(true);
    refreshAgents();
  });
  els.close.addEventListener("click", () => setDrawer(false));
  els.scrim.addEventListener("click", () => setDrawer(false));

  function select(id, closeDrawer) {
    state.selected = id;
    state.rev = "";
    state.stick = true;
    store.set("selected", id);
    if (closeDrawer) setDrawer(false);
    renderList();
    renderHeader();
    pollPane();
  }

  // --- pane の表示 ---
  function charRatio() {
    const probe = document.createElement("span");
    probe.style.cssText = "position:absolute;visibility:hidden;white-space:pre;font:100px " + getComputedStyle(els.screen).fontFamily;
    probe.textContent = "0".repeat(20);
    document.body.appendChild(probe);
    const ratio = probe.getBoundingClientRect().width / 20 / 100;
    probe.remove();
    return ratio || 0.6;
  }

  function applyFont() {
    let px = state.size;
    if (state.fit && state.cells > 0) {
      const room = els.view.clientWidth - 24;
      px = Math.max(7, Math.min(14, room / (state.cells * state.ratio)));
    }
    els.screen.style.fontSize = px.toFixed(2) + "px";
    els.fit.classList.toggle("on", state.fit);
  }

  function renderScreen(text) {
    const lines = parse(text);
    const nearBottom = els.view.scrollHeight - els.view.scrollTop - els.view.clientHeight < 80;
    const pinned = state.stick || nearBottom;
    state.cells = maxCells(lines);
    els.screen.innerHTML = toHtml(lines); // 内容は ansi.js が HTML エスケープ済み
    applyFont();
    if (pinned) els.view.scrollTop = els.view.scrollHeight;
    state.stick = false;
  }

  async function pollPane() {
    clearTimeout(state.paneTimer);
    const id = state.selected;
    if (id !== null && !document.hidden && els.login.hidden) {
      const q = new URLSearchParams({ id: String(id), lines: String(state.history), rev: state.rev });
      const r = await api("/api/pane?" + q);
      if (id === state.selected) {
        if (r.status === 404) {
          state.rev = "";
          els.screen.textContent = "この Agent は見つかりません（終了した可能性があります）";
        } else if (r.ok && !r.data.same) {
          state.rev = r.data.rev;
          renderScreen(r.data.text);
        }
      }
    }
    if (state.running) state.paneTimer = setTimeout(pollPane, 1000);
  }

  async function pollAgents() {
    clearTimeout(state.listTimer);
    if (!document.hidden) {
      await refreshAgents();
    }
    if (state.running) state.listTimer = setTimeout(pollAgents, state.pendingPane ? 1000 : 3000);
  }

  function start() {
    if (state.running) return;
    state.running = true;
    state.ratio = charRatio();
    pollAgents();
    pollPane();
  }

  // --- 表示の操作 ---
  els.hist.addEventListener("click", () => {
    state.history = state.history ? 0 : HISTORY_LINES;
    els.hist.classList.toggle("on", state.history > 0);
    state.rev = "";
    state.stick = true;
    pollPane();
  });
  els.fit.addEventListener("click", () => {
    state.fit = !state.fit;
    store.set("fit", state.fit ? "1" : "0");
    applyFont();
  });
  const zoom = (delta) => {
    if (state.fit) {
      state.size = parseFloat(els.screen.style.fontSize) || state.size;
      state.fit = false;
      store.set("fit", "0");
    }
    state.size = Math.max(6, Math.min(24, state.size + delta));
    store.set("size", state.size);
    applyFont();
  };
  els.zoomIn.addEventListener("click", () => zoom(1));
  els.zoomOut.addEventListener("click", () => zoom(-1));
  els.bottom.addEventListener("click", () => {
    els.view.scrollTo({ top: els.view.scrollHeight, behavior: "smooth" });
  });
  window.addEventListener("resize", applyFont);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && state.running) {
      pollAgents();
      pollPane();
    }
  });

  // --- 入力 ---
  async function sendKey(key) {
    if (state.selected === null) return;
    const r = await api("/api/key", { id: state.selected, key });
    if (!r.ok) toast(MESSAGES[r.status] || "送れませんでした");
    setTimeout(pollPane, 150);
  }

  els.keys.addEventListener("mousedown", (e) => e.preventDefault()); // 入力欄のキーボードを閉じない
  els.keys.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-key]");
    if (b) sendKey(b.dataset.key);
  });

  const autosize = () => {
    els.text.style.height = "auto";
    els.text.style.height = Math.min(els.text.scrollHeight, 140) + "px";
  };

  // 送信ボタンは、入力欄に文字があるときは「文字を入れるだけ（Enter は押さない）」、空のときは「Enter を押す」。
  // Enter まで一度に押してしまうと、/ やスキルの補完（Tab・↑↓で選ぶ）を使えないため。文字を入れたあと、補完を選んで、⏎ で確定する。
  // 従来どおり「文字を入れて Enter まで」を 1 回で済ませたいときは、文字があるときだけ出る「入力+⏎」を使う
  const syncComposer = () => {
    const has = els.text.value.length > 0;
    els.send.textContent = has ? "入力" : "⏎";
    els.send.setAttribute("aria-label", has ? "文字を入れる（Enter は押さない）" : "Enter を押す");
    els.sendEnter.hidden = !has;
  };
  els.text.addEventListener("input", () => {
    autosize();
    syncComposer();
  });

  async function sendText(enter) {
    const text = els.text.value;
    if (state.selected === null || !text) return;
    els.send.disabled = els.sendEnter.disabled = true;
    const r = await api("/api/send", { id: state.selected, text, enter });
    els.send.disabled = els.sendEnter.disabled = false;
    if (r.ok) {
      els.text.value = "";
      autosize();
      syncComposer(); // 空になるので、ボタンは「⏎」に戻る（続けて押せば、Enter になる）
      state.stick = true;
      setTimeout(pollPane, 250);
    } else {
      toast(MESSAGES[r.status] || "送れませんでした");
    }
  }

  els.text.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (els.text.value) sendText(true);
      else sendKey("Enter");
    }
  });
  els.composer.addEventListener("submit", (e) => {
    e.preventDefault();
    if (els.text.value) sendText(false);
    else sendKey("Enter");
  });
  els.sendEnter.addEventListener("click", () => sendText(true));
  els.sendEnter.addEventListener("mousedown", (e) => e.preventDefault()); // 入力欄のキーボードを閉じない
  els.send.addEventListener("mousedown", (e) => e.preventDefault());

  // ソフトキーボードが入力欄を隠さないようにする。Android の Chrome は、viewport の interactive-widget=resizes-content で
  // レイアウトごと縮む。縮まない端末（iOS Safari 等）のために、visual viewport の高さをページの高さにも反映する。
  // ピンチズーム中（scale が 1 でない）は visual viewport も縮むので、反映しない（レイアウトが潰れないように）
  const vv = window.visualViewport;
  if (vv) {
    const fitViewport = () => {
      const root = document.documentElement.style;
      if (Math.abs(vv.scale - 1) < 0.01) root.setProperty("--vvh", vv.height + "px");
      else root.removeProperty("--vvh");
      if (vv.offsetTop && Math.abs(vv.scale - 1) < 0.01) window.scrollTo(0, 0); // iOS: キーボードでページごとずれるのを戻す
      if (document.activeElement === els.text) els.text.scrollIntoView({ block: "nearest" });
    };
    vv.addEventListener("resize", fitViewport);
    vv.addEventListener("scroll", fitViewport);
    fitViewport();
  }

  // 「アプリとして追加」用の Service Worker（何も溜めない）。https / localhost 以外では navigator.serviceWorker が無く、何もしない
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});

  // --- 起動 ---
  async function boot() {
    els.hist.classList.toggle("on", false);
    const m = /(?:^|[#&])token=([^&]+)/.exec(location.hash);
    if (m) {
      history.replaceState(null, "", location.pathname + location.search); // トークンをアドレスバー・履歴から消す
      if (!(await login(decodeURIComponent(m[1])))) showLogin();
      return;
    }
    if (await refreshAgents()) start();
  }
  boot();
})();
