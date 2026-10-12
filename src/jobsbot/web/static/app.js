// Jobsbot admin panel — vanilla JS, no build step, no framework.
// Auth is HTTP Basic: once the browser's native login prompt is answered,
// every fetch() below to the same origin carries the Authorization header
// automatically — no login form or token handling needed here.

const PAGE_TITLES = {
  stats: "Статистика",
  vacancies: "Вакансии",
  subscribers: "Подписчики",
  reports: "Жалобы на вакансии",
  ads: "Реклама",
  channels: "Telegram-каналы",
  "required-channels": "Обязательные каналы",
  "group-topics": "Топики группы",
  staff: "Сотрудники",
  "adapter-health": "Здоровье парсеров",
};

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function toast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

async function api(path, options = {}) {
  const resp = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch (_) {
      // ignore
    }
    toast(`Ошибка: ${detail}`, "error");
    throw new Error(detail);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

function openModal(html) {
  document.getElementById("modal-body").innerHTML = html;
  document.getElementById("modal-backdrop").classList.remove("hidden");
}

function closeModal() {
  document.getElementById("modal-backdrop").classList.add("hidden");
  document.getElementById("modal-body").innerHTML = "";
}

document.getElementById("modal-close").addEventListener("click", closeModal);
document.getElementById("modal-backdrop").addEventListener("click", (e) => {
  if (e.target.id === "modal-backdrop") closeModal();
});

function view() {
  return document.getElementById("view");
}

function spinner() {
  view().innerHTML = '<div class="spinner">Загрузка...</div>';
}

function paginationControls(total, limit, offset, onPage) {
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));
  const div = document.createElement("div");
  div.className = "pagination";
  const prev = document.createElement("button");
  prev.className = "secondary small";
  prev.textContent = "← Назад";
  prev.disabled = offset <= 0;
  prev.onclick = () => onPage(Math.max(0, offset - limit));
  const next = document.createElement("button");
  next.className = "secondary small";
  next.textContent = "Вперёд →";
  next.disabled = offset + limit >= total;
  next.onclick = () => onPage(offset + limit);
  const label = document.createElement("span");
  label.textContent = `Стр. ${page} из ${pages} (всего ${total})`;
  div.append(prev, label, next);
  return div;
}

// ---------- Stats ----------

async function renderStats() {
  spinner();
  const data = await api("/api/stats");
  const byStatus = data.by_status || {};
  const topList = (obj, labelFn) => {
    const entries = Object.entries(obj).sort((a, b) => b[1] - a[1]).slice(0, 12);
    if (!entries.length) return '<div class="empty-state">Пока нет данных</div>';
    const max = entries[0][1];
    return `<div class="top-list">${entries
      .map(
        ([key, count]) => `
        <div class="top-row">
          <span>${escapeHtml(labelFn(key))}</span>
          <span class="bar-track"><span class="bar-fill" style="width:${(count / max) * 100}%"></span></span>
          <span class="count">${count}</span>
        </div>`
      )
      .join("")}</div>`;
  };

  view().innerHTML = `
    <div class="stat-grid">
      <div class="stat-box"><div class="value">${data.total ?? 0}</div><div class="label">Всего</div></div>
      <div class="stat-box"><div class="value">${byStatus.active ?? 0}</div><div class="label">Активных</div></div>
      <div class="stat-box"><div class="value">${byStatus.paused ?? 0}</div><div class="label">На паузе</div></div>
      <div class="stat-box"><div class="value">${byStatus.blocked ?? 0}</div><div class="label">Заблокировано</div></div>
    </div>
    <div class="card">
      <h2>Топ языков / сфер</h2>
      ${topList(data.languages || {}, (k) => k)}
    </div>
    <div class="card">
      <h2>Топ городов</h2>
      ${topList(data.cities || {}, (k) => k)}
    </div>
    <div class="card">
      <h2>Форматы работы</h2>
      ${topList(data.work_formats || {}, (k) => k)}
    </div>
  `;
}

// ---------- Vacancies ----------

let vacanciesState = { q: "", language: "", source_type: "", hidden: "", offset: 0, limit: 20 };

async function renderVacancies() {
  spinner();
  const params = new URLSearchParams();
  if (vacanciesState.q) params.set("q", vacanciesState.q);
  if (vacanciesState.language) params.set("language", vacanciesState.language);
  if (vacanciesState.source_type) params.set("source_type", vacanciesState.source_type);
  if (vacanciesState.hidden) params.set("hidden", vacanciesState.hidden);
  params.set("limit", vacanciesState.limit);
  params.set("offset", vacanciesState.offset);

  const data = await api(`/api/vacancies?${params}`);

  const rows = data.items
    .map(
      (v) => `
      <tr>
        <td>
          <a href="#" data-vac-id="${v.id}" class="vac-link">${escapeHtml(v.title)}</a><br/>
          <span class="muted">${escapeHtml(v.company || "")}</span>
        </td>
        <td>${v.languages.map((l) => `<span class="tag">${escapeHtml(l)}</span>`).join("")}</td>
        <td>${escapeHtml(v.source_type || "—")}</td>
        <td>${escapeHtml(v.salary_text || "—")}</td>
        <td>${escapeHtml(v.location || "—")}</td>
        <td>${v.hidden ? '<span class="badge badge-red">скрыта</span>' : '<span class="badge badge-green">видна</span>'}</td>
        <td>${fmtDate(v.first_seen_at)}</td>
        <td>
          ${
            v.hidden
              ? `<button class="small secondary" data-unhide="${v.id}">Показать</button>`
              : `<button class="small danger" data-hide="${v.id}">Скрыть</button>`
          }
        </td>
      </tr>`
    )
    .join("");

  view().innerHTML = `
    <div class="card">
      <div class="toolbar">
        <div class="form-field">
          <label>Поиск по заголовку</label>
          <input type="text" id="vac-q" placeholder="python developer" value="${escapeHtml(vacanciesState.q)}" />
        </div>
        <div class="form-field">
          <label>Язык</label>
          <input type="text" id="vac-lang" placeholder="python" value="${escapeHtml(vacanciesState.language)}" />
        </div>
        <div class="form-field">
          <label>Источник</label>
          <select id="vac-source">
            <option value="">Все</option>
            ${["hh", "habr", "geekjob", "linkedin", "telegram_channel"]
              .map((s) => `<option value="${s}" ${vacanciesState.source_type === s ? "selected" : ""}>${s}</option>`)
              .join("")}
          </select>
        </div>
        <div class="form-field">
          <label>Видимость</label>
          <select id="vac-hidden">
            <option value="" ${vacanciesState.hidden === "" ? "selected" : ""}>Все</option>
            <option value="false" ${vacanciesState.hidden === "false" ? "selected" : ""}>Видимые</option>
            <option value="true" ${vacanciesState.hidden === "true" ? "selected" : ""}>Скрытые</option>
          </select>
        </div>
        <button id="vac-apply">Применить</button>
      </div>
      <table>
        <thead>
          <tr><th>Вакансия</th><th>Язык</th><th>Источник</th><th>Зарплата</th><th>Город</th><th>Статус</th><th>Найдена</th><th></th></tr>
        </thead>
        <tbody>${rows || ""}</tbody>
      </table>
      ${!data.items.length ? '<div class="empty-state">Ничего не найдено</div>' : ""}
      <div id="vac-pagination"></div>
    </div>
  `;

  document.getElementById("vac-pagination").appendChild(
    paginationControls(data.total, vacanciesState.limit, vacanciesState.offset, (offset) => {
      vacanciesState.offset = offset;
      renderVacancies();
    })
  );

  document.getElementById("vac-apply").onclick = () => {
    vacanciesState.q = document.getElementById("vac-q").value.trim();
    vacanciesState.language = document.getElementById("vac-lang").value.trim();
    vacanciesState.source_type = document.getElementById("vac-source").value;
    vacanciesState.hidden = document.getElementById("vac-hidden").value;
    vacanciesState.offset = 0;
    renderVacancies();
  };

  view().querySelectorAll(".vac-link").forEach((el) => {
    el.onclick = async (e) => {
      e.preventDefault();
      const v = await api(`/api/vacancies/${el.dataset.vacId}`);
      openModal(`
        <h2>${escapeHtml(v.title)}</h2>
        <p class="muted">${escapeHtml(v.company || "")} · ${escapeHtml(v.source_type || "")} · ${escapeHtml(v.location || "—")}</p>
        <p>${v.languages.map((l) => `<span class="tag">${escapeHtml(l)}</span>`).join("")}</p>
        <p><strong>Зарплата:</strong> ${escapeHtml(v.salary_text || "—")}</p>
        <p><strong>Опыт:</strong> ${escapeHtml(v.experience || "—")} · <strong>Формат:</strong> ${escapeHtml(v.work_format || "—")}</p>
        ${v.url ? `<p><a href="${escapeHtml(v.url)}" target="_blank" rel="noopener">Открыть на сайте источника →</a></p>` : ""}
        <div class="description-text">${escapeHtml(v.description || "Описание отсутствует")}</div>
      `);
    };
  });

  view().querySelectorAll("[data-hide]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/vacancies/${btn.dataset.hide}/hide`, { method: "POST" });
      toast("Вакансия скрыта", "success");
      renderVacancies();
    };
  });
  view().querySelectorAll("[data-unhide]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/vacancies/${btn.dataset.unhide}/unhide`, { method: "POST" });
      toast("Вакансия снова видна", "success");
      renderVacancies();
    };
  });
}

// ---------- Subscribers ----------

let subscribersState = { status: "", offset: 0, limit: 20 };

async function renderSubscribers() {
  spinner();
  const params = new URLSearchParams();
  if (subscribersState.status) params.set("status", subscribersState.status);
  params.set("limit", subscribersState.limit);
  params.set("offset", subscribersState.offset);

  const data = await api(`/api/subscribers?${params}`);
  const statusBadge = (s) =>
    s === "active"
      ? '<span class="badge badge-green">active</span>'
      : s === "paused"
      ? '<span class="badge badge-yellow">paused</span>'
      : '<span class="badge badge-red">blocked</span>';

  const rows = data.items
    .map(
      (s) => `
      <tr>
        <td>${s.telegram_user_id}<br/><span class="muted">@${escapeHtml(s.username || "—")}</span></td>
        <td>${statusBadge(s.status)}</td>
        <td>${s.languages.map((l) => `<span class="tag">${escapeHtml(l)}</span>`).join("") || "—"}</td>
        <td>${s.cities.join(", ") || "—"}</td>
        <td>${s.min_salary ? s.min_salary.toLocaleString("ru-RU") + " ₽" : "—"}</td>
        <td>${fmtDate(s.subscribed_at)}</td>
        <td>
          ${
            s.status === "blocked"
              ? `<button class="small secondary" data-unblock="${s.telegram_user_id}">Разблокировать</button>`
              : `<button class="small danger" data-block="${s.telegram_user_id}">Заблокировать</button>`
          }
        </td>
      </tr>`
    )
    .join("");

  view().innerHTML = `
    <div class="card">
      <div class="toolbar">
        <div class="form-field">
          <label>Статус</label>
          <select id="sub-status">
            <option value="" ${subscribersState.status === "" ? "selected" : ""}>Все</option>
            <option value="active" ${subscribersState.status === "active" ? "selected" : ""}>Активные</option>
            <option value="paused" ${subscribersState.status === "paused" ? "selected" : ""}>На паузе</option>
            <option value="blocked" ${subscribersState.status === "blocked" ? "selected" : ""}>Заблокированные</option>
          </select>
        </div>
        <button id="sub-apply">Применить</button>
      </div>
      <table>
        <thead><tr><th>Пользователь</th><th>Статус</th><th>Языки</th><th>Города</th><th>Зарплата от</th><th>Подписан</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${!data.items.length ? '<div class="empty-state">Никого не найдено</div>' : ""}
      <div id="sub-pagination"></div>
    </div>
  `;

  document.getElementById("sub-pagination").appendChild(
    paginationControls(data.total, subscribersState.limit, subscribersState.offset, (offset) => {
      subscribersState.offset = offset;
      renderSubscribers();
    })
  );
  document.getElementById("sub-apply").onclick = () => {
    subscribersState.status = document.getElementById("sub-status").value;
    subscribersState.offset = 0;
    renderSubscribers();
  };
  view().querySelectorAll("[data-block]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/subscribers/${btn.dataset.block}/block`, { method: "POST" });
      toast("Пользователь заблокирован", "success");
      renderSubscribers();
    };
  });
  view().querySelectorAll("[data-unblock]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/subscribers/${btn.dataset.unblock}/unblock`, { method: "POST" });
      toast("Пользователь разблокирован", "success");
      renderSubscribers();
    };
  });
}

// ---------- Reports ----------

async function renderReports() {
  spinner();
  const data = await api("/api/reports?status=pending");
  const rows = data.items
    .map(
      (r) => `
      <tr>
        <td>
          ${escapeHtml(r.vacancy_title || `#${r.vacancy_id}`)}<br/>
          ${r.vacancy_url ? `<a href="${escapeHtml(r.vacancy_url)}" target="_blank" rel="noopener" class="muted">Открыть вакансию →</a>` : ""}
        </td>
        <td>${escapeHtml(r.comment)}</td>
        <td>${fmtDate(r.created_at)}</td>
        <td>
          <button class="small secondary" data-resolve="${r.id}" data-action="keep">Оставить</button>
          <button class="small danger" data-resolve="${r.id}" data-action="remove">Удалить</button>
        </td>
      </tr>`
    )
    .join("");

  view().innerHTML = `
    <div class="card">
      <h2>Ожидают решения</h2>
      <table>
        <thead><tr><th>Вакансия</th><th>Комментарий</th><th>Когда</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${!data.items.length ? '<div class="empty-state">Нет новых жалоб 🎉</div>' : ""}
    </div>
  `;

  view().querySelectorAll("[data-resolve]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/reports/${btn.dataset.resolve}/resolve`, {
        method: "POST",
        body: JSON.stringify({ action: btn.dataset.action }),
      });
      toast("Жалоба обработана", "success");
      renderReports();
    };
  });
}

// ---------- Ads ----------

async function renderAds() {
  spinner();
  const data = await api("/api/ads");
  const statusBadge = (s) =>
    ({
      draft: '<span class="badge badge-gray">draft</span>',
      active: '<span class="badge badge-green">active</span>',
      completed: '<span class="badge badge-gray">completed</span>',
      cancelled: '<span class="badge badge-red">cancelled</span>',
    }[s] || `<span class="badge badge-gray">${s}</span>`);

  const rows = data.items
    .map(
      (c) => `
      <tr>
        <td>${escapeHtml(c.name)}<br/><span class="muted">${escapeHtml(c.message_text.slice(0, 60))}${c.message_text.length > 60 ? "…" : ""}</span></td>
        <td>${statusBadge(c.status)}</td>
        <td>${c.send_interval_hours ? c.send_interval_hours + "ч" : "—"}</td>
        <td>
          ${c.status === "draft" ? `<button class="small" data-activate="${c.id}">Активировать</button>` : ""}
          ${c.status === "active" ? `<button class="small secondary" data-broadcast="${c.id}">Разослать сейчас</button><button class="small danger" data-cancel="${c.id}">Отменить</button>` : ""}
        </td>
      </tr>`
    )
    .join("");

  view().innerHTML = `
    <div class="card">
      <h2>📝 Отправить всем сейчас</h2>
      <div class="form-field">
        <label>Текст / тезисы</label>
        <textarea id="broadcast-text" placeholder="Напиши текст объявления или тезисы для AI..."></textarea>
      </div>
      <div class="toolbar" style="margin-top:10px">
        <button id="ai-draft-btn" class="secondary">🤖 Оформить через AI</button>
        <button id="send-broadcast-btn">✅ Отправить всем</button>
      </div>
      <div id="broadcast-result"></div>
    </div>

    <div class="card">
      <h2>Запланированные кампании</h2>
      <div class="form-row" style="margin-bottom:14px">
        <div class="form-field"><label>Название</label><input type="text" id="new-ad-name" /></div>
        <div class="form-field"><label>Текст</label><input type="text" id="new-ad-text" style="width:280px" /></div>
        <div class="form-field"><label>Интервал (ч)</label><input type="number" id="new-ad-interval" value="24" style="width:80px" /></div>
        <button id="new-ad-btn">Создать (draft)</button>
      </div>
      <table>
        <thead><tr><th>Кампания</th><th>Статус</th><th>Интервал</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${!data.items.length ? '<div class="empty-state">Кампаний пока нет</div>' : ""}
    </div>
  `;

  document.getElementById("ai-draft-btn").onclick = async () => {
    const text = document.getElementById("broadcast-text").value.trim();
    if (!text) return toast("Сначала напиши текст или тезисы", "error");
    const btn = document.getElementById("ai-draft-btn");
    btn.disabled = true;
    btn.textContent = "⏳ Составляю...";
    try {
      const { draft } = await api("/api/ads/draft", { method: "POST", body: JSON.stringify({ text }) });
      document.getElementById("broadcast-text").value = draft;
      toast("Черновик готов", "success");
    } finally {
      btn.disabled = false;
      btn.textContent = "🤖 Оформить через AI";
    }
  };

  document.getElementById("send-broadcast-btn").onclick = async () => {
    const text = document.getElementById("broadcast-text").value.trim();
    if (!text) return toast("Текст не может быть пустым", "error");
    if (!confirm("Отправить это сообщение всем подписчикам?")) return;
    const result = await api("/api/ads/broadcast-now", { method: "POST", body: JSON.stringify({ text }) });
    document.getElementById("broadcast-result").innerHTML = `<p class="muted">Отправлено ${result.sent} из ${result.total}.</p>`;
    toast("Рассылка отправлена", "success");
    renderAds();
  };

  document.getElementById("new-ad-btn").onclick = async () => {
    const name = document.getElementById("new-ad-name").value.trim();
    const message_text = document.getElementById("new-ad-text").value.trim();
    const send_interval_hours = parseInt(document.getElementById("new-ad-interval").value, 10) || 24;
    if (!name || !message_text) return toast("Название и текст обязательны", "error");
    await api("/api/ads", { method: "POST", body: JSON.stringify({ name, message_text, send_interval_hours }) });
    toast("Кампания создана", "success");
    renderAds();
  };

  view().querySelectorAll("[data-activate]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/ads/${btn.dataset.activate}/activate`, { method: "POST" });
      toast("Кампания активирована", "success");
      renderAds();
    };
  });
  view().querySelectorAll("[data-cancel]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/ads/${btn.dataset.cancel}/cancel`, { method: "POST" });
      toast("Кампания отменена", "success");
      renderAds();
    };
  });
  view().querySelectorAll("[data-broadcast]").forEach((btn) => {
    btn.onclick = async () => {
      if (!confirm("Разослать эту кампанию всем сейчас?")) return;
      const result = await api(`/api/ads/${btn.dataset.broadcast}/broadcast`, { method: "POST" });
      toast(`Отправлено ${result.sent} из ${result.total}`, "success");
    };
  });
}

// ---------- Channels ----------

async function renderChannels() {
  spinner();
  const data = await api("/api/channels");
  const rows = data.items
    .map(
      (c) => `
      <tr>
        <td>@${escapeHtml(c.identifier)}</td>
        <td>${c.enabled ? '<span class="badge badge-green">включён</span>' : '<span class="badge badge-gray">выключен</span>'}</td>
        <td><button class="small danger" data-remove="${c.id}">Удалить</button></td>
      </tr>`
    )
    .join("");

  view().innerHTML = `
    ${!data.telegram_enabled ? '<div class="warn-banner">⚠️ Парсинг Telegram-каналов отключён (нет TELEGRAM_API_ID/HASH) — каналы можно настраивать, но опрос не запустится.</div>' : ""}
    <div class="card">
      <div class="form-row" style="margin-bottom:14px">
        <div class="form-field"><label>Юзернейм канала</label><input type="text" id="new-channel" placeholder="channel_username" /></div>
        <button id="add-channel-btn">Добавить</button>
      </div>
      <table>
        <thead><tr><th>Канал</th><th>Статус</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${!data.items.length ? '<div class="empty-state">Каналов пока нет</div>' : ""}
    </div>
  `;

  document.getElementById("add-channel-btn").onclick = async () => {
    const identifier = document.getElementById("new-channel").value.trim();
    if (!identifier) return toast("Укажи юзернейм канала", "error");
    await api("/api/channels", { method: "POST", body: JSON.stringify({ identifier }) });
    toast("Канал добавлен", "success");
    renderChannels();
  };
  view().querySelectorAll("[data-remove]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/channels/${btn.dataset.remove}`, { method: "DELETE" });
      toast("Канал удалён", "success");
      renderChannels();
    };
  });
}

// ---------- Required channels ----------

async function renderRequiredChannels() {
  spinner();
  const data = await api("/api/required-channels");
  const rows = data.items
    .map(
      (c) => `
      <tr>
        <td>${escapeHtml(c.title || c.username)}<br/><span class="muted">@${escapeHtml(c.username)}</span></td>
        <td>${fmtDate(c.added_at)}</td>
        <td><button class="small danger" data-remove="${c.id}">Удалить</button></td>
      </tr>`
    )
    .join("");

  view().innerHTML = `
    <div class="card">
      <p class="muted">Новый пользователь должен подписаться на все эти каналы/группы перед тем, как начать пользоваться ботом. Бот должен сам быть участником каждого канала.</p>
      <div class="form-row" style="margin:14px 0">
        <div class="form-field"><label>Юзернейм</label><input type="text" id="new-gate-username" placeholder="channel_username" /></div>
        <div class="form-field"><label>Название (опц.)</label><input type="text" id="new-gate-title" /></div>
        <button id="add-gate-btn">Добавить</button>
      </div>
      <table>
        <thead><tr><th>Канал</th><th>Добавлен</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${!data.items.length ? '<div class="empty-state">Обязательных каналов нет — новые пользователи проходят без проверки</div>' : ""}
    </div>
  `;

  document.getElementById("add-gate-btn").onclick = async () => {
    const username = document.getElementById("new-gate-username").value.trim();
    const title = document.getElementById("new-gate-title").value.trim();
    if (!username) return toast("Укажи юзернейм", "error");
    await api("/api/required-channels", { method: "POST", body: JSON.stringify({ username, title: title || null }) });
    toast("Канал добавлен", "success");
    renderRequiredChannels();
  };
  view().querySelectorAll("[data-remove]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/required-channels/${btn.dataset.remove}`, { method: "DELETE" });
      toast("Канал удалён", "success");
      renderRequiredChannels();
    };
  });
}

// ---------- Group topics ----------

async function renderGroupTopics() {
  spinner();
  const data = await api("/api/group-topics");
  const rows = data.items
    .map(
      (t) => `
      <tr>
        <td>${escapeHtml(t.language_key)}</td>
        <td>${t.thread_id}</td>
        <td><button class="small danger" data-remove="${escapeHtml(t.language_key)}">Удалить</button></td>
      </tr>`
    )
    .join("");

  view().innerHTML = `
    <div class="card">
      <p class="muted">Группа: <strong>${data.group_chat_id ?? "не настроена (GROUP_CHAT_ID пуст)"}</strong></p>
      <div class="form-row" style="margin:14px 0">
        <div class="form-field"><label>Язык/сфера</label><input type="text" id="new-topic-lang" placeholder="python" /></div>
        <div class="form-field"><label>Thread ID</label><input type="number" id="new-topic-thread" /></div>
        <button id="set-topic-btn">Сохранить</button>
      </div>
      <table>
        <thead><tr><th>Язык/сфера</th><th>Thread ID</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${!data.items.length ? '<div class="empty-state">Маппингов пока нет</div>' : ""}
    </div>
  `;

  document.getElementById("set-topic-btn").onclick = async () => {
    const language_key = document.getElementById("new-topic-lang").value.trim();
    const thread_id = parseInt(document.getElementById("new-topic-thread").value, 10);
    if (!language_key || Number.isNaN(thread_id)) return toast("Укажи язык и thread_id", "error");
    await api(`/api/group-topics/${encodeURIComponent(language_key)}`, {
      method: "PUT",
      body: JSON.stringify({ thread_id }),
    });
    toast("Сохранено", "success");
    renderGroupTopics();
  };
  view().querySelectorAll("[data-remove]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/group-topics/${encodeURIComponent(btn.dataset.remove)}`, { method: "DELETE" });
      toast("Удалено", "success");
      renderGroupTopics();
    };
  });
}

// ---------- Staff ----------

async function renderStaff() {
  spinner();
  const [data, permsData] = await Promise.all([api("/api/staff"), api("/api/staff/permissions")]);
  const permissions = permsData.permissions;

  const rows = data.items
    .map(
      (s) => `
      <tr>
        <td>${s.telegram_user_id}<br/><span class="muted">@${escapeHtml(s.username || "—")}</span></td>
        <td>${s.permissions.map((p) => `<span class="tag">${escapeHtml(permissions[p] || p)}</span>`).join("") || "—"}</td>
        <td>${s.status === "active" ? '<span class="badge badge-green">active</span>' : '<span class="badge badge-gray">removed</span>'}</td>
        <td>${s.status === "active" ? `<button class="small danger" data-remove="${s.id}">Удалить</button>` : ""}</td>
      </tr>`
    )
    .join("");

  view().innerHTML = `
    <div class="card">
      <h2>Добавить сотрудника</h2>
      <div class="form-row">
        <div class="form-field"><label>Telegram ID</label><input type="number" id="new-staff-id" /></div>
        <div class="form-field"><label>Username (опц.)</label><input type="text" id="new-staff-username" /></div>
      </div>
      <div class="form-field" style="margin-top:10px">
        <label>Права</label>
        <div class="checkbox-group">
          ${Object.entries(permissions)
            .map(([key, label]) => `<label><input type="checkbox" value="${key}" class="staff-perm-cb" /> ${escapeHtml(label)}</label>`)
            .join("")}
        </div>
      </div>
      <button id="add-staff-btn" style="margin-top:12px">Добавить</button>
    </div>

    <div class="card">
      <h2>Сотрудники</h2>
      <table>
        <thead><tr><th>Пользователь</th><th>Права</th><th>Статус</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      ${!data.items.length ? '<div class="empty-state">Сотрудников пока нет</div>' : ""}
    </div>
  `;

  document.getElementById("add-staff-btn").onclick = async () => {
    const telegram_user_id = parseInt(document.getElementById("new-staff-id").value, 10);
    const username = document.getElementById("new-staff-username").value.trim() || null;
    const selected = Array.from(view().querySelectorAll(".staff-perm-cb:checked")).map((cb) => cb.value);
    if (Number.isNaN(telegram_user_id)) return toast("Укажи корректный Telegram ID", "error");
    await api("/api/staff", { method: "POST", body: JSON.stringify({ telegram_user_id, username, permissions: selected }) });
    toast("Сотрудник добавлен", "success");
    renderStaff();
  };
  view().querySelectorAll("[data-remove]").forEach((btn) => {
    btn.onclick = async () => {
      await api(`/api/staff/${btn.dataset.remove}`, { method: "DELETE" });
      toast("Сотрудник удалён", "success");
      renderStaff();
    };
  });
}

// ---------- Adapter health ----------

async function renderAdapterHealth() {
  spinner();
  const data = await api("/api/adapter-health");
  if (!data.items.length) {
    view().innerHTML = '<div class="card"><div class="empty-state">Пока нет данных — подождите первого цикла опроса</div></div>';
    return;
  }
  const cards = data.items
    .map((h) => {
      const bad = h.alert_sent;
      return `
      <div class="stat-box" style="text-align:left">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <strong style="font-size:15px">${escapeHtml(h.adapter)}</strong>
          ${bad ? '<span class="badge badge-red">проблема</span>' : '<span class="badge badge-green">ок</span>'}
        </div>
        <div class="muted" style="margin-top:8px">Пустых циклов подряд: ${h.consecutive_empty_polls} / ${h.failure_threshold}</div>
        <div class="muted">Последний опрос: ${fmtDate(h.last_polled_at)}</div>
      </div>`;
    })
    .join("");
  view().innerHTML = `<div class="stat-grid">${cards}</div>`;
}

// ---------- Router ----------

const ROUTES = {
  stats: renderStats,
  vacancies: renderVacancies,
  subscribers: renderSubscribers,
  reports: renderReports,
  ads: renderAds,
  channels: renderChannels,
  "required-channels": renderRequiredChannels,
  "group-topics": renderGroupTopics,
  staff: renderStaff,
  "adapter-health": renderAdapterHealth,
};

async function router() {
  const section = (location.hash.slice(1) || "stats").split("?")[0];
  const renderFn = ROUTES[section] || renderStats;

  document.querySelectorAll("#nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.section === section);
  });
  document.getElementById("page-title").textContent = PAGE_TITLES[section] || "Jobsbot Admin";

  try {
    await renderFn();
  } catch (err) {
    view().innerHTML = `<div class="card"><div class="empty-state">Не удалось загрузить раздел.</div></div>`;
  }
}

window.addEventListener("hashchange", router);
window.addEventListener("DOMContentLoaded", router);
