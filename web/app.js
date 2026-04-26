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

  function actionButton(label, action, jobId, className) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "action " + (className || "");
    button.textContent = label;
    button.addEventListener("click", async function () {
      button.disabled = true;
      try {
        const data = await postJson("/api/job", { id: jobId, action: action });
        setResult("Готово: " + label.toLowerCase());
        if (data.state) {
          renderState(data.state);
        } else {
          await refresh();
        }
      } catch (error) {
        setResult("Не удалось выполнить действие: " + error.message, true);
      } finally {
        button.disabled = false;
      }
    });
    return button;
  }

  function renderJob(job, index) {
    const item = document.createElement("div");
    item.className = "job";

    const percent = Math.max(0, Math.min(100, Math.round((job.progress || 0) * 100)));
    const meta = [];
    if (job.text_path) meta.push("txt: " + escapeHtml(job.text_path));
    if (job.error) meta.push("error: " + escapeHtml(job.error));
    if (job.duration) meta.push("duration: " + job.duration.toFixed(1) + " sec");

    const head = document.createElement("div");
    head.className = "job-head";
    head.innerHTML =
      '<div class="job-index">#' + String(index + 1) + "</div>" +
      '<div class="job-path">' + escapeHtml(job.path) + "</div>" +
      '<div class="badge ' + escapeHtml(job.status) + '">' + escapeHtml(job.status) + "</div>";

    const metaEl = document.createElement("div");
    metaEl.className = "meta";
    metaEl.innerHTML = meta.join("<br>");

    const bar = document.createElement("div");
    bar.className = "bar";
    const fill = document.createElement("div");
    fill.className = "fill";
    fill.style.width = percent + "%";
    bar.appendChild(fill);

    const actions = document.createElement("div");
    actions.className = "actions";

    if (job.status === "processing") {
      actions.appendChild(actionButton("Остановить", "cancel", job.id, "danger"));
      actions.appendChild(actionButton("Удалить", "delete", job.id, "danger"));
    } else if (job.status === "paused") {
      actions.appendChild(actionButton("Продолжить", "resume", job.id, "primaryish"));
      actions.appendChild(actionButton("Удалить", "delete", job.id, "danger"));
      actions.appendChild(actionButton("Вверх", "move_up", job.id, "primaryish"));
      actions.appendChild(actionButton("Вниз", "move_down", job.id, "primaryish"));
    } else {
      actions.appendChild(actionButton("Удалить", "delete", job.id, "danger"));
      if (job.status === "pending") {
        actions.appendChild(actionButton("Вверх", "move_up", job.id, "primaryish"));
        actions.appendChild(actionButton("Вниз", "move_down", job.id, "primaryish"));
      }
    }

    item.appendChild(head);
    item.appendChild(metaEl);
    item.appendChild(bar);
    item.appendChild(actions);
    return item;
  }

  async function refresh() {
    try {
      const res = await fetch("/api/state", { cache: "no-store" });
      if (!res.ok) {
        throw new Error("state request failed (" + res.status + ")");
      }

      const data = await res.json();
      renderState(data);
    } catch (error) {
      setResult("Не удалось обновить состояние: " + error.message, true);
    }
  }

  function renderState(data) {
    $("pending").textContent = data.pending;
    $("paused").textContent = data.paused;
    $("processing").textContent = data.processing;
    $("done").textContent = data.done;
    $("failed").textContent = data.failed;
    $("canceled").textContent = data.canceled;

    const queueEl = $("queue");
    queueEl.innerHTML = "";
    data.jobs.forEach(function (job, index) {
      queueEl.appendChild(renderJob(job, index));
    });
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

  document.addEventListener("DOMContentLoaded", function () {
    $("enqueue").addEventListener("click", enqueue);
    $("clear").addEventListener("click", function () {
      $("paths").value = "";
      $("paths").focus();
    });

    refresh();
    setInterval(refresh, 3000);
  });
}());
