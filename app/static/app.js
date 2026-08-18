/* ──────────────────────────────────────────────────────────────
   DeepLens  —  Frontend Logic
   ────────────────────────────────────────────────────────────── */

(() => {
  "use strict";

  // ── DOM refs ──────────────────────────────────────────────
  const $ = (s) => document.querySelector(s);
  const dropZone     = $("#drop-zone");
  const fileInput    = $("#file-input");
  const previewCont  = $("#preview-container");
  const previewImg   = $("#preview-img");
  const previewVid   = $("#preview-vid");
  const previewName  = $("#preview-name");
  const previewSize  = $("#preview-size");
  const btnChange    = $("#btn-change");
  const actionSec    = $("#action-section");
  const btnAnalyse   = $("#btn-analyse");
  const progressSec  = $("#progress-section");
  const progressBar  = $("#progress-bar");
  const progressText = $("#progress-text");
  const resultsSec   = $("#results-section");
  const verdictIcon  = $("#verdict-icon");
  const verdictText  = $("#verdict-text");
  const verdictSub   = $("#verdict-sub");
  const ringFill     = $("#ring-fill");
  const ringLabel    = $("#ring-label");
  const infoBar      = $("#info-bar");
  const resultPrevW  = $("#result-preview-wrap");
  const resultPrevImg= $("#result-preview-img");
  const resultPrevVid= $("#result-preview-vid");
  const cardsGrid    = $("#cards-grid");

  let selectedFile = null;

  // ── Helpers ───────────────────────────────────────────────
  function formatBytes(b) {
    if (b < 1024) return b + " B";
    if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
    return (b / 1048576).toFixed(1) + " MB";
  }

  function scoreClass(s) {
    if (s >= 0.65) return "high";
    if (s >= 0.4) return "medium";
    return "low";
  }

  // ── File selection ────────────────────────────────────────
  function selectFile(file) {
    if (!file) return;
    selectedFile = file;

    // show preview
    const isVideo = file.type.startsWith("video/");
    previewCont.style.display = "flex";
    actionSec.style.display = "block";
    resultsSec.style.display = "none";

    previewName.textContent = file.name;
    previewSize.textContent = formatBytes(file.size);

    if (isVideo) {
      previewImg.style.display = "none";
      previewVid.style.display = "block";
      previewVid.src = URL.createObjectURL(file);
    } else {
      previewVid.style.display = "none";
      previewImg.style.display = "block";
      previewImg.src = URL.createObjectURL(file);
    }

    dropZone.style.display = "none";
  }

  // ── Drag & drop ──────────────────────────────────────────
  ["dragenter", "dragover"].forEach((evt) =>
    dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.add("drag-over"); })
  );
  ["dragleave", "drop"].forEach((evt) =>
    dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.remove("drag-over"); })
  );
  dropZone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files.length) selectFile(e.dataTransfer.files[0]);
  });

  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => { if (fileInput.files.length) selectFile(fileInput.files[0]); });
  btnChange.addEventListener("click", () => {
    selectedFile = null;
    previewCont.style.display = "none";
    actionSec.style.display = "none";
    resultsSec.style.display = "none";
    dropZone.style.display = "";
    fileInput.value = "";
  });

  // ── Analyse ───────────────────────────────────────────────
  btnAnalyse.addEventListener("click", runAnalysis);

  async function runAnalysis() {
    if (!selectedFile) return;
    btnAnalyse.disabled = true;

    // show progress
    resultsSec.style.display = "none";
    progressSec.style.display = "";
    progressBar.style.width = "0%";
    progressText.textContent = "Uploading…";

    // simulate progress steps
    let pct = 0;
    const steps = [
      { t: 20, msg: "Running Error-Level Analysis…" },
      { t: 40, msg: "Inspecting metadata…" },
      { t: 55, msg: "Analysing colour distribution…" },
      { t: 70, msg: "Measuring noise patterns…" },
      { t: 85, msg: "Checking edge consistency…" },
      { t: 92, msg: "Computing frequency spectrum…" },
    ];
    let stepIdx = 0;
    const timer = setInterval(() => {
      if (stepIdx < steps.length) {
        progressBar.style.width = steps[stepIdx].t + "%";
        progressText.textContent = steps[stepIdx].msg;
        stepIdx++;
      }
    }, 400);

    try {
      const form = new FormData();
      form.append("file", selectedFile);

      const resp = await fetch("/api/analyze", { method: "POST", body: form });

      clearInterval(timer);
      progressBar.style.width = "100%";
      progressText.textContent = "Done!";

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || "Analysis failed");
      }

      const data = await resp.json();
      await new Promise((r) => setTimeout(r, 350));
      progressSec.style.display = "none";
      renderResults(data);

    } catch (ex) {
      clearInterval(timer);
      progressSec.style.display = "none";
      alert("Error: " + ex.message);
    } finally {
      btnAnalyse.disabled = false;
    }
  }

  // ── Render results ────────────────────────────────────────
  function renderResults(data) {
    resultsSec.style.display = "";
    const ov = data.overall;
    const score = ov.overall_score;

    // verdict
    if (ov.verdict === "Likely Real") {
      verdictIcon.textContent = "✅";
      verdictText.textContent = "Likely Real";
      verdictText.style.color = "var(--success)";
    } else if (ov.verdict === "Likely AI-Generated") {
      verdictIcon.textContent = "🤖";
      verdictText.textContent = "Likely AI-Generated";
      verdictText.style.color = "var(--danger)";
    } else {
      verdictIcon.textContent = "⚠️";
      verdictText.textContent = "Inconclusive";
      verdictText.style.color = "var(--warning)";
    }
    verdictSub.textContent = `Confidence: ${ov.confidence} · Score: ${(score * 100).toFixed(0)}%`;

    // ring
    const circ = 2 * Math.PI * 52; // 326.73
    const offset = circ - score * circ;
    ringFill.style.strokeDashoffset = offset;
    ringFill.style.stroke =
      score >= 0.65 ? "var(--success)" : score >= 0.4 ? "var(--warning)" : "var(--danger)";
    ringLabel.textContent = (score * 100).toFixed(0) + "%";

    // info bar
    infoBar.innerHTML = "";
    const addTag = (txt) => { const s = document.createElement("span"); s.textContent = txt; infoBar.appendChild(s); };
    addTag(`Filename: ${data.filename}`);
    addTag(`Type: ${data.type}`);
    addTag(`${data.dimensions.width}×${data.dimensions.height}`);
    if (data.type === "video") {
      addTag(`${data.duration_seconds}s`);
      addTag(`${data.fps} fps`);
      addTag(`${data.frames_analyzed} frames analysed`);
    }

    // preview
    if (data.preview) {
      resultPrevW.style.display = "";
      if (data.type === "video") {
        resultPrevImg.style.display = "none";
        resultPrevVid.style.display = "block";
        resultPrevVid.src = "data:video/mp4;base64," + data.preview;
      } else {
        resultPrevVid.style.display = "none";
        resultPrevImg.style.display = "block";
        resultPrevImg.src = "data:image/jpeg;base64," + data.preview;
      }
    }

    // cards
    cardsGrid.innerHTML = "";
    if (data.type === "image") {
      Object.entries(data.analyses).forEach(([key, a]) => {
        cardsGrid.appendChild(buildCard(key, a));
      });
    } else {
      // video: temporal card + average
      if (data.analyses.temporal) {
        cardsGrid.appendChild(buildCard("temporal", data.analyses.temporal));
      }
      // frame summary
      const fr = data.analyses.frame_results;
      if (fr && fr.length) {
        cardsGrid.appendChild(buildFrameSummaryCard(fr));
      }
    }

    resultsSec.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ── Build a single card ───────────────────────────────────
  function buildCard(key, analysis) {
    const card = document.createElement("div");
    card.className = "card";

    const title = cardTitle(key);
    const sc = analysis.score;
    const badge = `<span class="score-badge ${scoreClass(sc)}">${(sc * 100).toFixed(0)}%</span>`;

    let visHtml = "";
    if (analysis.visualization) {
      visHtml = `<div class="card-vis"><img src="data:image/jpeg;base64,${analysis.visualization}" alt="${title} visualization" /></div>`;
    }
    if (analysis.histogram) {
      visHtml += `<div class="card-vis"><img src="data:image/png;base64,${analysis.histogram}" alt="Colour histogram" /></div>`;
    }
    if (analysis.spectrum) {
      visHtml += `<div class="card-vis"><img src="data:image/jpeg;base64,${analysis.spectrum}" alt="Frequency spectrum" /></div>`;
    }

    let metaHtml = "";
    if (key === "metadata" && analysis.metadata) {
      const entries = Object.entries(analysis.metadata).slice(0, 8);
      if (entries.length) {
        metaHtml = '<ul class="meta-list">' +
          entries.map(([k, v]) => `<li><span class="meta-key">${esc(k)}:</span> ${esc(String(v).slice(0, 80))}</li>`).join("") +
          "</ul>";
      }
      if (analysis.ai_indicators && analysis.ai_indicators.length) {
        metaHtml += `<div style="margin-top:.4rem;font-size:.78rem;color:var(--danger)">` +
          analysis.ai_indicators.map((h) => "⚠ " + esc(h)).join("<br>") + "</div>";
      }
    }

    card.innerHTML = `
      <div class="card-header">
        <span class="card-title">${titleIcon(key)} ${title}</span>
        ${badge}
      </div>
      <p class="card-desc">${esc(analysis.description || "")}</p>
      ${visHtml}
      ${metaHtml}
    `;
    return card;
  }

  function buildFrameSummaryCard(frameResults) {
    const card = document.createElement("div");
    card.className = "card";

    const keys = ["ela", "color", "noise", "edge"];
    const avgs = {};
    keys.forEach((k) => {
      const vals = frameResults.map((f) => f[k]?.score).filter((v) => v !== undefined);
      avgs[k] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0.5;
    });

    const barsHtml = keys.map((k) => {
      const v = avgs[k];
      const pct = (v * 100).toFixed(0);
      return `<div style="margin-bottom:.4rem">
        <div style="display:flex;justify-content:space-between;font-size:.78rem;margin-bottom:2px">
          <span>${cardTitle(k)}</span><span class="score-badge ${scoreClass(v)}" style="font-size:.72rem">${pct}%</span>
        </div>
        <div style="height:5px;background:var(--surface2);border-radius:3px;overflow:hidden">
          <div style="height:100%;width:${pct}%;background:${v >= 0.65 ? "var(--success)" : v >= 0.4 ? "var(--warning)" : "var(--danger)"};border-radius:3px"></div>
        </div>
      </div>`;
    }).join("");

    card.innerHTML = `
      <div class="card-header">
        <span class="card-title">${titleIcon("frames")} Frame Averages</span>
        <span class="score-badge ${scoreClass(frameResults[0]?.ela?.score ?? 0.5)}">${frameResults.length} frames</span>
      </div>
      <p class="card-desc">Average analysis scores across ${frameResults.length} sampled frames.</p>
      <div style="margin-top:.4rem">${barsHtml}</div>
    `;
    return card;
  }

  // ── Card helpers ──────────────────────────────────────────
  function cardTitle(key) {
    const map = {
      ela: "Error-Level Analysis",
      metadata: "Metadata Inspection",
      color: "Colour Distribution",
      noise: "Noise Patterns",
      edge: "Edge Consistency",
      frequency: "Frequency Spectrum",
      temporal: "Temporal Consistency",
      frames: "Frame Analysis",
    };
    return map[key] || key;
  }

  function titleIcon(key) {
    const icons = {
      ela: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>`,
      metadata: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
      color: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="13.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="15.5" r="2.5"/><circle cx="8.5" cy="15.5" r="2.5"/><path d="M12 2C6.49 2 2 6.49 2 12s4.49 10 10 10 10-4.49 10-10S17.51 2 12 2z"/></svg>`,
      noise: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12h2l3-9 4 18 4-12 3 6h4"/></svg>`,
      edge: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 2 22 22 22"/></svg>`,
      frequency: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="12" width="4" height="8"/><rect x="7" y="8" width="4" height="12"/><rect x="12" y="4" width="4" height="16"/><rect x="17" y="10" width="4" height="10"/></svg>`,
      temporal: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
      frames: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="7" x2="7" y2="7"/><line x1="2" y1="17" x2="7" y2="17"/><line x1="17" y1="7" x2="22" y2="7"/><line x1="17" y1="17" x2="22" y2="17"/></svg>`,
    };
    return icons[key] || "";
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }
})();
