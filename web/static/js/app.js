/* Facebook Scraper — frontend logic */
const $ = (sel) => document.querySelector(sel);

const state = {
  mode: "simple_post",
  jobStatus: "idle",
  logCount: 0,
  eventSource: null,
};

/* ---------------- Navigation ---------------- */
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    $(`#view-${btn.dataset.view}`).classList.add("active");
    if (btn.dataset.view === "posts") loadPosts();
    if (btn.dataset.view === "settings") loadSession();
  });
});

/* ---------------- Scrape view ---------------- */
const urlPlaceholders = {
  simple_post: ["Post URLs (one per line)", "https://www.facebook.com/share/p/...\nhttps://www.facebook.com/groups/123/posts/456/"],
  page_posts: ["Page URLs (one per line)", "https://www.facebook.com/profile.php?id=...\nhttps://www.facebook.com/PageName/"],
  group_posts: ["Group URLs (one per line)", "https://www.facebook.com/groups/123456/"],
};

document.querySelectorAll(".mode-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".mode-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    state.mode = tab.dataset.mode;
    const [label, placeholder] = urlPlaceholders[state.mode];
    $("#urlLabel").innerHTML = `${label} <small>(one per line)</small>`;
    $("#urls").placeholder = placeholder;
    $("#pageOptions").hidden = state.mode === "simple_post";
    $("#fetchCommentsField").hidden = state.mode === "simple_post";
  });
});

$("#startBtn").addEventListener("click", async () => {
  const urls = $("#urls").value.split("\n").map((u) => u.trim()).filter(Boolean);
  if (!urls.length) return toast("Enter at least one URL", true);

  const body = {
    type: state.mode,
    urls,
    download_images: $("#downloadImages").checked,
  };
  if (state.mode !== "simple_post") {
    body.limit = parseInt($("#limit").value) || 10;
    body.min_comments = parseInt($("#minComments").value) || 0;
    body.fetch_comments = $("#fetchComments").checked;
    if ($("#startDate").value) body.start_date = $("#startDate").value;
    if ($("#endDate").value) body.end_date = $("#endDate").value;
  }

  const res = await fetch("/api/scrape", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) return toast(data.error || "Failed to start", true);

  clearLogs();
  setJobStatus("running");
  toast("Scrape started");
  streamLogs();
});

$("#stopBtn").addEventListener("click", async () => {
  await fetch("/api/job/stop", { method: "POST" });
  toast("Stop requested — finishing current step...");
});

$("#clearLogsBtn").addEventListener("click", clearLogs);

function clearLogs() {
  $("#logPanel").innerHTML = "";
  state.logCount = 0;
}

function setJobStatus(status) {
  state.jobStatus = status;
  const badge = $("#jobStatus");
  badge.textContent = status;
  badge.className = `badge ${status}`;
  $("#startBtn").disabled = status === "running";
  $("#stopBtn").hidden = status !== "running";
}

/* ---------------- Live logs (SSE) ---------------- */
function streamLogs() {
  if (state.eventSource) state.eventSource.close();
  const es = new EventSource("/api/job/logs/stream");
  state.eventSource = es;

  es.addEventListener("log", (e) => {
    const { logs } = JSON.parse(e.data);
    logs.forEach(appendLog);
  });
  es.addEventListener("end", (e) => {
    const { status } = JSON.parse(e.data);
    setJobStatus(status);
    es.close();
    state.eventSource = null;
    loadSession();
  });
  es.onerror = () => { /* keep the browser's auto-reconnect */ };
}

function classify(line) {
  if (/error|failed|❌|job failed/i.test(line)) return "err";
  if (/✓|✅|saved|downloaded/i.test(line)) return "ok";
  if (/⚠|retry|skipping/i.test(line)) return "warn";
  return "";
}

function appendLog(message) {
  const panel = $("#logPanel");
  const div = document.createElement("div");
  const t = new Date().toLocaleTimeString();
  div.className = `log-line ${classify(message)}`.trim();
  div.innerHTML = `<span class="t">${t}</span>`;
  div.appendChild(document.createTextNode(message));
  panel.appendChild(div);
  panel.scrollTop = panel.scrollHeight;
}

/* ---------------- Posts view ---------------- */
$("#refreshPostsBtn").addEventListener("click", loadPosts);
$("#filterType").addEventListener("change", loadPosts);
$("#filterSource").addEventListener("change", loadPosts);
$("#filterQuery").addEventListener("input", debounce(loadPosts, 300));
$("#filterMinComments").addEventListener("input", debounce(loadPosts, 300));

async function loadPosts() {
  const params = new URLSearchParams();
  if ($("#filterType").value) params.set("type", $("#filterType").value);
  if ($("#filterSource").value) params.set("source", $("#filterSource").value);
  if ($("#filterQuery").value) params.set("q", $("#filterQuery").value);
  if (parseInt($("#filterMinComments").value)) params.set("min_comments", $("#filterMinComments").value);

  const res = await fetch(`/api/posts?${params}`);
  const data = await res.json();

  const sourceSelect = $("#filterSource");
  const current = sourceSelect.value;
  sourceSelect.innerHTML = '<option value="">All sources</option>' +
    data.sources.map((s) => `<option value="${esc(s.name)}">${esc(s.name)}</option>`).join("");
  sourceSelect.value = current;

  const grid = $("#postsGrid");
  grid.innerHTML = "";
  $("#postsEmpty").hidden = data.posts.length > 0;

  data.posts.forEach((p) => grid.appendChild(renderPostCard(p)));
}

function renderPostCard(p) {
  const card = document.createElement("div");
  card.className = "post-card";

  const typeLabel = { simple_post: "Single", page_post: "Page", group_post: "Group" }[p.post_type];
  const meta = document.createElement("div");
  meta.className = "post-meta";
  meta.innerHTML = `<span class="tag">${typeLabel}</span>` +
    (p.source ? `<span class="tag source">${esc(p.source)}</span>` : "") +
    `<span class="tag">${esc(p.post_id)}</span>`;

  const text = document.createElement("div");
  text.className = "post-text";
  text.textContent = p.text || "(no text)";

  const stats = document.createElement("div");
  stats.className = "post-stats";
  stats.innerHTML =
    `<span>&#128172; ${p.scraped_comments} comments${p.comment_count ? ` (${p.comment_count})` : ""}</span>` +
    (p.reaction_count != null ? `<span>&#128077; ${esc(p.reaction_count)}</span>` : "") +
    `<span>&#128444; ${p.image_count}</span>`;

  const actions = document.createElement("div");
  actions.className = "post-actions";
  actions.append(
    btn("View", "secondary", () => viewPost(p)),
    btn("JSON", "secondary", () => window.open(`/api/posts/download?type=${p.post_type}&source=${encodeURIComponent(p.source || "")}&id=${p.post_id}`)),
  );
  if (p.image_count > 0) {
    actions.append(btn("Images", "secondary", () => window.open(`/api/posts/images?type=${p.post_type}&source=${encodeURIComponent(p.source || "")}&id=${p.post_id}`)));
  }
  actions.append(btn("Delete", "danger", () => deletePost(p)));

  card.append(meta, text, stats, actions);
  return card;
}

function btn(label, cls, onClick) {
  const b = document.createElement("button");
  b.className = `btn ${cls} small`;
  b.textContent = label;
  b.addEventListener("click", onClick);
  return b;
}

async function viewPost(p) {
  const res = await fetch(`/api/posts/view?type=${p.post_type}&source=${encodeURIComponent(p.source || "")}&id=${p.post_id}`);
  const data = await res.json();
  if (!res.ok) return toast(data.error || "Failed to load", true);

  const post = data.post;
  $("#modalTitle").textContent = `Post ${p.post_id}`;

  const body = $("#modalBody");
  body.innerHTML = "";

  if (post.text) {
    const txt = document.createElement("p");
    txt.style.marginBottom = "12px";
    txt.textContent = post.text;
    body.appendChild(txt);
  }

  const stats = document.createElement("p");
  stats.className = "muted";
  stats.textContent = `Comments scraped: ${(post.comments || []).length}` +
    (post.reaction_count != null ? ` · Reactions: ${post.reaction_count}` : "") +
    (post.comment_count != null ? ` · Comment count: ${post.comment_count}` : "");
  body.appendChild(stats);

  (post.media || []).forEach((m) => {
    if (m.type === "photo" && m.url) {
      const img = document.createElement("img");
      img.src = m.url;
      img.loading = "lazy";
      body.appendChild(img);
    }
  });

  const list = document.createElement("div");
  (post.comments || []).forEach((c) => list.appendChild(renderComment(c)));
  if (!(post.comments || []).length) {
    list.innerHTML = '<p class="muted">No comments stored.</p>';
  }
  body.appendChild(list);

  $("#postModal").hidden = false;
}

function renderComment(c) {
  const div = document.createElement("div");
  div.className = "comment";
  div.innerHTML = `<div class="who">${esc(c.author || "Unknown")}</div>`;
  const text = document.createElement("div");
  text.textContent = c.text || "";
  div.appendChild(text);
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `👍 ${c.reaction_count ?? 0}`;
  div.appendChild(meta);

  if ((c.replies || []).length) {
    const replies = document.createElement("div");
    replies.className = "replies";
    c.replies.forEach((r) => replies.appendChild(renderComment(r)));
    div.appendChild(replies);
  }
  return div;
}

async function deletePost(p) {
  if (!confirm(`Delete post ${p.post_id} and its files?`)) return;
  const res = await fetch("/api/posts/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: p.post_type, source: p.source, id: p.post_id }),
  });
  if (res.ok) { toast("Deleted"); loadPosts(); }
  else toast("Delete failed", true);
}

$("#modalCloseBtn").addEventListener("click", () => { $("#postModal").hidden = true; });
$("#postModal").addEventListener("click", (e) => {
  if (e.target === $("#postModal")) $("#postModal").hidden = true;
});

/* ---------------- Settings view ---------------- */
$("#saveSessionBtn").addEventListener("click", async () => {
  const body = {};
  if ($("#cookieInput").value.trim()) body.cookies = $("#cookieInput").value.trim();
  if ($("#curlInput").value.trim()) body.curl = $("#curlInput").value.trim();

  const res = await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) return toast(data.error || "Failed to save", true);
  toast("Session saved");
  $("#cookieInput").value = "";
  $("#curlInput").value = "";
  loadSession();
});

$("#clearSessionBtn").addEventListener("click", async () => {
  await fetch("/api/settings", { method: "DELETE" });
  toast("Session cleared");
  loadSession();
});

/* ---------------- Proxy settings ---------------- */
$("#saveProxyBtn").addEventListener("click", async () => {
  const body = {};
  const rotating = $("#rotatingProxyInput").value.trim();
  const stat = $("#staticProxyInput").value.trim();
  if (rotating && !rotating.includes("***")) body.rotating = rotating;
  if (stat && !stat.includes("***")) body.static = stat;

  const res = await fetch("/api/settings/proxy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) return toast(data.error || "Failed to save proxy", true);
  toast("Proxy saved");
  loadSession();
});

async function loadSession() {
  const res = await fetch("/api/settings");
  const s = await res.json();
  const active = s.has_cookies || s.has_dtsg;

  const badge = $("#sessionBadge");
  badge.classList.toggle("active", active);
  $("#sessionText").textContent = active
    ? `Session active (${s.cookie_count} cookies${s.has_dtsg ? " + dtsg" : ""})`
    : "No session";

  $("#sessionDetail").textContent = active
    ? `Authenticated session active — ${s.cookie_count} cookies, fb_dtsg ${s.has_dtsg ? "set" : "not set"}.`
    : "No session configured. Scraping works without it for public content.";

  if (s.proxies) {
    $("#rotatingProxyInput").value = s.proxies.rotating || "";
    $("#staticProxyInput").value = s.proxies.static || "";
  }
}

/* ---------------- Helpers ---------------- */
function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

function toast(msg, isError = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = isError ? "toast error" : "toast";
  t.hidden = false;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.hidden = true; }, 3500);
}

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

/* ---------------- Init ---------------- */
(async function init() {
  loadSession();
  const res = await fetch("/api/job");
  const job = await res.json();
  if (job.status === "running") {
    setJobStatus("running");
    streamLogs();
  } else {
    setJobStatus(job.status || "idle");
  }
})();
