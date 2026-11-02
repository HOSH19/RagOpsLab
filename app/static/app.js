const form = document.getElementById("ask-form");
const questionEl = document.getElementById("question");
const useCacheEl = document.getElementById("use-cache");
const askBtn = document.getElementById("ask-btn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const cacheBadge = document.getElementById("cache-badge");
const cacheDetail = document.getElementById("cache-detail");
const answerEl = document.getElementById("answer");
const timingsEl = document.getElementById("timings");
const docsEl = document.getElementById("docs");
const metaEl = document.getElementById("meta");
const rawJsonEl = document.getElementById("raw-json");
const hintEl = document.getElementById("hint");

function fmtMs(value) {
  if (value == null || Number.isNaN(value)) return "—";
  if (value < 10) return `${value.toFixed(1)} ms`;
  return `${Math.round(value)} ms`;
}

function setStatus(message, isError = false) {
  if (!message) {
    statusEl.hidden = true;
    statusEl.textContent = "";
    statusEl.classList.remove("error");
    return;
  }
  statusEl.hidden = false;
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

function highlightPillars(cache) {
  document.querySelectorAll(".pillars li").forEach((li) => li.classList.remove("active"));
  const map = {
    HIT: ["caching", "latency", "monitoring"],
    SEMANTIC: ["caching", "latency", "evals"],
    MISS: ["latency", "tracing", "evals"],
  };
  for (const key of map[cache] || ["latency"]) {
    const el = document.querySelector(`.pillars li[data-pillar="${key}"]`);
    if (el) el.classList.add("active");
  }
}

function updateHint(data) {
  const { cache, timings, request_id: requestId, semantic_similarity: sim } = data;
  if (cache === "HIT") {
    hintEl.textContent = `Exact cache hit in ${fmtMs(timings.e2e_ms)}. Ask a paraphrase next, or open Grafana and watch cache hit ratio climb.`;
    return;
  }
  if (cache === "SEMANTIC") {
    const simText = sim == null ? "" : ` Similarity ${sim.toFixed(3)}.`;
    hintEl.textContent = `Semantic reuse — skipped LLM.${simText} Lower SEMANTIC_CACHE_THRESHOLD to get more of these (and risk worse answers). Check faithfulness with evals.`;
    return;
  }
  hintEl.textContent = `Full RAG path (e2e ${fmtMs(timings.e2e_ms)}, TTFT ${fmtMs(timings.llm_ttft_ms)}). Open Langfuse and find request ${requestId}. Ask the same question again for a HIT.`;
}

function renderTimings(timings, cache) {
  const stages = [
    { key: "e2e_ms", label: "E2E" },
    { key: "llm_ttft_ms", label: "TTFT" },
    { key: "embed_ms", label: "Embed" },
    { key: "retrieve_ms", label: "Retrieve" },
    { key: "cache_ms", label: "Cache" },
    { key: "llm_total_ms", label: "LLM total" },
  ];

  timingsEl.innerHTML = "";
  for (const stage of stages) {
    const value = timings[stage.key] ?? 0;
    // On HIT, hide empty LLM/retrieve/embed stages so the strip stays readable.
    if (cache === "HIT" && ["embed_ms", "retrieve_ms", "llm_ttft_ms", "llm_total_ms"].includes(stage.key) && value <= 0) {
      continue;
    }
    const node = document.createElement("div");
    node.className = "timing";
    node.innerHTML = `<span class="label">${stage.label}</span><span class="value">${fmtMs(value)}</span>`;
    timingsEl.appendChild(node);
  }
}

function renderDocs(docIds) {
  docsEl.innerHTML = "";
  if (!docIds || docIds.length === 0) {
    const empty = document.createElement("span");
    empty.className = "doc empty";
    empty.textContent = "None retrieved";
    docsEl.appendChild(empty);
    return;
  }
  for (const id of docIds) {
    const chip = document.createElement("span");
    chip.className = "doc";
    chip.textContent = id;
    docsEl.appendChild(chip);
  }
}

function renderResult(data) {
  resultEl.hidden = false;
  // Restart enter animation
  resultEl.style.animation = "none";
  // force reflow
  void resultEl.offsetWidth;
  resultEl.style.animation = "";

  cacheBadge.textContent = data.cache;
  cacheBadge.className = `cache-badge ${data.cache}`;

  if (data.cache === "SEMANTIC" && data.semantic_similarity != null) {
    cacheDetail.textContent = `similarity ${data.semantic_similarity.toFixed(3)}`;
  } else if (data.cache === "HIT") {
    cacheDetail.textContent = "exact key match — skipped embed / retrieve / LLM";
  } else {
    cacheDetail.textContent = data.cache_enabled
      ? "full path ran"
      : "cache disabled for this request";
  }

  answerEl.textContent = data.answer;
  renderTimings(data.timings, data.cache);
  renderDocs(data.doc_ids);

  const tokens =
    data.prompt_tokens || data.completion_tokens
      ? `${data.prompt_tokens} prompt + ${data.completion_tokens} completion tokens`
      : "no token usage (cached)";
  metaEl.textContent = [
    data.model,
    data.prompt_version,
    tokens,
    `request ${data.request_id}`,
  ].join(" · ");

  rawJsonEl.textContent = JSON.stringify(data, null, 2);
  highlightPillars(data.cache);
  updateHint(data);
}

async function askQuestion(question) {
  setStatus("Asking…");
  resultEl.hidden = true;
  askBtn.disabled = true;

  try {
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        use_cache: useCacheEl.checked,
      }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || `Request failed (${res.status})`);
    }

    setStatus("");
    renderResult(data);
  } catch (err) {
    setStatus(err.message || String(err), true);
  } finally {
    askBtn.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = questionEl.value.trim();
  if (!question) return;
  askQuestion(question);
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    questionEl.value = chip.dataset.q || "";
    questionEl.focus();
  });
});
