const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const state = { cfg: null, styles: [], styleId: "apple-minimal", p: null, saveTimer: null, pollTimer: null };

// ---------- 工具 ----------

async function api(method, url, body) {
  const r = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : JSON.stringify(d || r.statusText));
  }
  return data;
}

let toastTimer;
function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (isErr ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), isErr ? 6000 : 2500);
}

function overlay(msg) {
  const el = document.createElement("div");
  el.className = "loading-overlay";
  el.innerHTML = `<div class="spinner"></div><div>${esc(msg)}</div>`;
  document.body.appendChild(el);
  return () => el.remove();
}

// ---------- 首页 ----------

function renderStyleGrid() {
  const grid = $("#style-grid");
  const cards = state.styles.map((s) => `
    <div class="style-card ${s.id === state.styleId ? "active" : ""}" data-id="${s.id}">
      <div class="swatch">${s.swatch.map((c) => `<i style="background:${c}"></i>`).join("")}</div>
      <b>${esc(s.name)}</b><small>${esc(s.tagline)}</small>
    </div>`);
  cards.push(`
    <div class="style-card none ${state.styleId === "" ? "active" : ""}" data-id="">
      <div class="swatch"></div><b>仅自定义</b><small>完全按下方的文字描述</small>
    </div>`);
  grid.innerHTML = cards.join("");
  grid.querySelectorAll(".style-card").forEach((el) =>
    el.addEventListener("click", () => { state.styleId = el.dataset.id; renderStyleGrid(); }));
}

async function renderRecent() {
  const list = await api("GET", "/api/projects");
  $("#recent").classList.toggle("hidden", !list.length);
  $("#recent-list").innerHTML = list.slice(0, 8).map((p) =>
    `<li data-id="${esc(p.id)}">${esc(p.topic)}<span>${p.pages} 页 · ${esc(p.id.slice(0, 13))}</span></li>`).join("");
  $("#recent-list").querySelectorAll("li").forEach((li) =>
    li.addEventListener("click", () => (location.hash = `#/p/${li.dataset.id}`)));
}

$("#create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  if (state.styleId === "" && !f.get("custom_style").trim()) {
    return toast("选择“仅自定义”时，请填写自定义风格描述", true);
  }
  const done = overlay("正在构思发布会的叙事和每一页画面，大约需要 4～6 分钟，请不要关闭页面…");
  try {
    const p = await api("POST", "/api/projects", {
      topic: f.get("topic"),
      notes: f.get("notes"),
      style_id: state.styleId,
      custom_style: f.get("custom_style"),
      page_count: Number(f.get("page_count")),
    });
    location.hash = `#/p/${p.id}`;
  } catch (err) {
    toast(err.message, true);
  } finally {
    done();
  }
});

// ---------- 工作台 ----------

const cover = () => state.p.slides[0];
const others = () => state.p.slides.slice(1);
const busy = (s) => s.status === "queued" || s.status === "generating";

function frameHTML(s) {
  const img = s.image ? `<img src="/files/${state.p.id}/${s.image}" data-zoom alt="">` : "";
  const ph = !s.image && !busy(s) && s.status !== "error" ? `<div class="placeholder">尚未生成</div>` : "";
  let st = "";
  if (busy(s)) {
    st = `<div class="status"><div class="shimmer"></div><div class="spinner"></div>${s.status === "queued" ? "排队中" : "生成中，约 20–60 秒"}</div>`;
  } else if (s.status === "error") {
    st = `<div class="status err">生成失败<br>${esc(s.error)}</div>`;
  }
  const badge = s.version > 1 ? `<span class="badge">第 ${s.version} 版</span>` : "";
  return img + ph + st + badge;
}

function updateFrame(s) {
  const el = document.querySelector(`[data-frame="${s.uid}"]`);
  if (el) el.innerHTML = frameHTML(s);
}

function fieldsHTML(s) {
  return `
    <input class="title-in" data-f="title" value="${esc(s.title)}" placeholder="主标题（建议 ≤12 字）">
    <input data-f="subtitle" value="${esc(s.subtitle)}" placeholder="副文案（可空，建议 ≤20 字）">
    <textarea data-f="visual" rows="3" placeholder="画面描述">${esc(s.visual)}</textarea>`;
}

function bindFields(root, s) {
  root.querySelectorAll("[data-f]").forEach((el) =>
    el.addEventListener("input", () => { s[el.dataset.f] = el.value; scheduleSave(); }));
}

function renderCover() {
  const s = cover();
  $("#cover-frame").innerHTML = `<div class="frame" data-frame="${s.uid}">${frameHTML(s)}</div>`;
  $("#cover-fields").innerHTML = fieldsHTML(s);
  bindFields($("#cover-fields"), s);
}

function renderSlides() {
  const types = state.cfg.slide_types;
  const grid = $("#slide-grid");
  grid.innerHTML = "";
  others().forEach((s, j) => {
    const i = j + 1;
    const card = document.createElement("div");
    card.className = "slide-card";
    card.innerHTML = `
      <div class="frame" data-frame="${s.uid}">${frameHTML(s)}</div>
      <div class="card-head">
        <span class="num">${String(i + 1).padStart(2, "0")}</span>
        <select data-f="type">${Object.keys(types).map((t) =>
          `<option value="${t}" ${t === s.type ? "selected" : ""}>${esc(types[t].split("：")[0])}</option>`).join("")}</select>
        <div class="tools">
          <button class="btn ghost" data-act="up" ${i === 1 ? "disabled" : ""} title="上移">↑</button>
          <button class="btn ghost" data-act="down" ${i === state.p.slides.length - 1 ? "disabled" : ""} title="下移">↓</button>
          <button class="btn ghost danger" data-act="del" title="删除">✕</button>
        </div>
      </div>
      ${fieldsHTML(s)}
      <div class="gen-row">
        <input data-feedback placeholder="修改意见（可选）">
        <button class="btn" data-act="gen">${s.image ? "重抽" : "生成"}</button>
      </div>`;
    bindFields(card, s);
    card.querySelector("[data-act=up]").onclick = () => moveSlide(i, -1);
    card.querySelector("[data-act=down]").onclick = () => moveSlide(i, 1);
    card.querySelector("[data-act=del]").onclick = () => deleteSlide(i);
    card.querySelector("[data-act=gen]").onclick = () =>
      generateSlide(s, card.querySelector("[data-feedback]").value);
    grid.appendChild(card);
  });
  updateControls();
}

function updateControls() {
  const p = state.p;
  const c = cover();
  const rest = others();
  const doneCount = p.slides.filter((s) => s.image).length;

  $("#cover-gen").textContent = c.image ? "重抽封面" : "生成封面";
  $("#cover-gen").disabled = busy(c);
  const lock = $("#cover-lock");
  lock.disabled = !c.image || busy(c);
  lock.textContent = p.cover_locked ? "✓ 已锁定（点击解锁）" : "锁定风格";
  lock.classList.toggle("primary", !p.cover_locked);

  $("#gen-all").disabled = !p.cover_locked || !rest.some((s) => s.status === "idle" || s.status === "error");
  document.querySelectorAll("#slide-grid [data-act=gen]").forEach((b, j) => {
    b.disabled = !p.cover_locked || busy(rest[j]);
    b.title = p.cover_locked ? "" : "请先锁定封面风格";
    b.textContent = rest[j].image ? "重抽" : "生成";
  });
  $("#export-btn").disabled = doneCount === 0;
  const running = p.slides.filter(busy).length;
  $("#progress-text").textContent = `已生成 ${doneCount} / ${p.slides.length} 页` + (running ? ` · ${running} 页进行中` : "");

  const step = !c.image ? 1 : !p.cover_locked ? 2 : 3;
  const allDone = doneCount === p.slides.length;
  document.querySelectorAll("#steps li").forEach((li) => {
    const n = Number(li.dataset.step);
    li.className = n < step || (n === 3 && allDone) ? "done" : n === step ? "current" : "";
  });
}

function renderWork() {
  const p = state.p;
  const style = state.styles.find((s) => s.id === p.style_id);
  $("#work-style").textContent = style ? style.name + (p.custom_style ? " + 自定义" : "") : "自定义风格";
  $("#work-topic").textContent = p.topic;
  $("#style-guide").value = p.style_guide;
  renderCover();
  renderSlides();
  ensurePolling();
}

// ---------- 保存 ----------

function outlinePayload() {
  return {
    style_guide: state.p.style_guide,
    slides: state.p.slides.map(({ uid, type, title, subtitle, visual }) => ({ uid, type, title, subtitle, visual })),
  };
}

function scheduleSave() {
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(() => saveNow().catch((e) => toast(e.message, true)), 600);
}

async function saveNow() {
  clearTimeout(state.saveTimer);
  const res = await api("PUT", `/api/projects/${state.p.id}/outline`, outlinePayload());
  state.p.cover_locked = res.cover_locked;
  return res;
}

$("#style-guide").addEventListener("input", (e) => { state.p.style_guide = e.target.value; scheduleSave(); });

// 结构变化（增删、排序）后用服务器返回的数据重新渲染，拿到新页面的 uid
async function structural(mutate) {
  mutate(state.p.slides);
  try {
    const res = await saveNow();
    state.p.slides = res.slides;
  } catch (e) {
    toast(e.message, true);
  }
  renderSlides();
}

function moveSlide(i, d) {
  structural((sl) => { const [s] = sl.splice(i, 1); sl.splice(i + d, 0, s); });
}

function deleteSlide(i) {
  if (!confirm(`删除第 ${i + 1} 页？`)) return;
  structural((sl) => sl.splice(i, 1));
}

$("#add-slide").addEventListener("click", () =>
  structural((sl) => sl.splice(sl.length - 1, 0, { uid: null, type: "feature", title: "新卖点", subtitle: "", visual: "" })));

// ---------- 生成 ----------

async function generateSlide(s, feedback = "") {
  try {
    await saveNow();
    const res = await api("POST", `/api/projects/${state.p.id}/slides/${s.uid}/generate`, { feedback });
    Object.assign(s, { status: res.status, error: null });
    if (s === cover()) state.p.cover_locked = false;
    updateFrame(s);
    updateControls();
    ensurePolling();
  } catch (e) {
    toast(e.message, true);
  }
}

$("#cover-gen").addEventListener("click", () => {
  if (state.p.cover_locked && others().some((s) => s.image) &&
      !confirm("重抽封面会解除风格锁定，已生成的其他页面不会自动更新。继续？")) return;
  generateSlide(cover(), $("#cover-feedback").value);
});

$("#cover-lock").addEventListener("click", async () => {
  try {
    const res = await api("POST", `/api/projects/${state.p.id}/lock`, { locked: !state.p.cover_locked });
    state.p.cover_locked = res.cover_locked;
    updateControls();
    if (res.cover_locked) toast("风格已锁定，其余页面会参考这张封面");
  } catch (e) {
    toast(e.message, true);
  }
});

$("#gen-all").addEventListener("click", async () => {
  try {
    await saveNow();
    const res = await api("POST", `/api/projects/${state.p.id}/generate-all`);
    toast(`已加入 ${res.queued} 页到生成队列`);
    await poll();
    ensurePolling();
  } catch (e) {
    toast(e.message, true);
  }
});

$("#export-btn").addEventListener("click", () => {
  const missing = state.p.slides.filter((s) => !s.image).length;
  if (missing && !confirm(`还有 ${missing} 页未生成，导出时会跳过这些页面。继续？`)) return;
  window.location = `/api/projects/${state.p.id}/export`;
});

// 只合并生成状态相关字段，不覆盖用户正在编辑的文字
async function poll() {
  const res = await api("GET", `/api/projects/${state.p.id}`);
  const byUid = Object.fromEntries(res.slides.map((s) => [s.uid, s]));
  for (const s of state.p.slides) {
    const r = byUid[s.uid];
    if (!r) continue;
    const changed = r.status !== s.status || r.image !== s.image;
    Object.assign(s, { status: r.status, image: r.image, error: r.error, version: r.version });
    if (changed) {
      updateFrame(s);
      if (r.status === "error") toast(`第 ${state.p.slides.indexOf(s) + 1} 页生成失败`, true);
    }
  }
  state.p.cover_locked = res.cover_locked;
  updateControls();
}

function ensurePolling() {
  if (state.pollTimer || !state.p.slides.some(busy)) return;
  state.pollTimer = setInterval(async () => {
    try { await poll(); } catch (e) { console.error(e); }
    if (!state.p || !state.p.slides.some(busy)) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }, 2000);
}

// ---------- 灯箱 ----------

document.addEventListener("click", (e) => {
  if (e.target.matches("[data-zoom]")) {
    $("#lightbox img").src = e.target.src;
    $("#lightbox").classList.remove("hidden");
  }
});
$("#lightbox").addEventListener("click", () => $("#lightbox").classList.add("hidden"));
document.addEventListener("keydown", (e) => e.key === "Escape" && $("#lightbox").classList.add("hidden"));

// ---------- 主题 ----------

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("theme", theme);
  document.querySelectorAll("#theme-toggle button").forEach((b) =>
    b.classList.toggle("active", b.dataset.theme === theme));
}

document.querySelectorAll("#theme-toggle button").forEach((b) =>
  b.addEventListener("click", () => setTheme(b.dataset.theme)));
setTheme(document.documentElement.dataset.theme);

// ---------- 路由 ----------

async function route() {
  clearInterval(state.pollTimer);
  state.pollTimer = null;
  const m = location.hash.match(/^#\/p\/(.+)$/);
  $("#view-home").classList.toggle("hidden", !!m);
  $("#view-work").classList.toggle("hidden", !m);
  if (m) {
    try {
      state.p = await api("GET", `/api/projects/${m[1]}`);
      renderWork();
    } catch (e) {
      toast(e.message, true);
      location.hash = "";
    }
  } else {
    state.p = null;
    renderStyleGrid();
    renderRecent();
  }
}

$("#home-link").addEventListener("click", (e) => { e.preventDefault(); location.hash = ""; });
window.addEventListener("hashchange", route);

(async function init() {
  [state.cfg, state.styles] = await Promise.all([api("GET", "/api/config"), api("GET", "/api/styles")]);
  const b = $("#banner");
  if (state.cfg.mock) {
    b.textContent = "MOCK 模式：不调用百炼 API，文案和图片均为占位内容，仅用于演示流程。";
    b.classList.remove("hidden");
  } else if (!state.cfg.has_key) {
    b.textContent = "未配置 DASHSCOPE_API_KEY：请复制 .env.example 为 .env 并填入百炼 API Key，然后重启服务。";
    b.classList.remove("hidden");
  }
  route();
})();
