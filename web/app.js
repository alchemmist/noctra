(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  function setResult(message, isError) {
    const resultEl = $("result");
    resultEl.textContent = message;
    resultEl.style.color = isError ? "var(--bad)" : "";
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function postJson(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(text || url + " failed (" + res.status + ")");
    }
    return text ? JSON.parse(text) : {};
  }

  function renderJob(job, index) {
    const item = document.createElement("div");
    item.className = "job";

    const percent = Math.max(0, Math.min(100, Math.round((job.progress || 0) * 100)));
    const meta = [];
    if (job.text_path) meta.push("txt: " + escapeHtml(job.text_path));
    if (job.error) meta.push("error: " + escapeHtml(job.error));
    if (job.duration) meta.push("duration: " + job.duration.toFixed(1) + " sec");

    item.innerHTML =
      '<div class="job-head">' +
      '<div class="job-index">#' + String(index + 1) + "</div>" +
      '<div class="job-path">' + escapeHtml(job.path) + "</div>" +
      '<div class="badge ' + escapeHtml(job.status) + '">' + escapeHtml(job.status) + "</div>" +
      "</div>" +
      '<div class="meta">' + meta.join("<br>") + "</div>" +
      '<div class="bar"><div class="fill" style="width:' + percent + '%"></div></div>';
    return item;
  }

  function renderState(data) {
    $("pending").textContent = data.pending;
    $("processing").textContent = data.processing;
    $("done").textContent = data.done;
    $("failed").textContent = data.failed;
    const startButton = $("start-queue");
    startButton.disabled = Boolean(data.running);
    startButton.textContent = data.running ? "Запущено" : "Старт";

    const queueEl = $("queue");
    queueEl.innerHTML = "";
    data.jobs.forEach(function (job, index) {
      queueEl.appendChild(renderJob(job, index));
    });
  }

  async function refresh() {
    try {
      const res = await fetch("/api/state", { cache: "no-store" });
      if (!res.ok) {
        throw new Error("state request failed (" + res.status + ")");
      }
      renderState(await res.json());
    } catch (error) {
      setResult("Не удалось обновить состояние: " + error.message, true);
    }
  }

  async function enqueue() {
    const button = $("enqueue");
    const raw = $("paths").value;
    const paths = raw.split(/\r?\n/).map(function (s) {
      return s.trim();
    }).filter(Boolean);

    if (!paths.length) {
      setResult("Добавьте хотя бы один путь.", true);
      return;
    }

    button.disabled = true;
    setResult("Добавляю задачи...");

    try {
      const data = await postJson("/api/enqueue", { paths: paths });
      const parts = ["Добавлено: " + data.added.length];
      if (data.skipped.length) parts.push("дубликаты: " + data.skipped.length);
      if (data.missing.length) parts.push("не найдены: " + data.missing.length);
      setResult(parts.join(", "));
      await refresh();
    } catch (error) {
      setResult("Не удалось добавить задачи: " + error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  async function startQueue() {
    const data = await postJson("/api/control", { action: "start" });
    if (data.state) {
      renderState(data.state);
    } else {
      await refresh();
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("enqueue").addEventListener("click", enqueue);
    $("start-queue").addEventListener("click", function () {
      startQueue().catch(function (error) {
        setResult("Не удалось запустить очередь: " + error.message, true);
      });
    });

    refresh();
    setInterval(refresh, 3000);
  });
}());
