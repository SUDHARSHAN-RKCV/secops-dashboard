// app/static/js/scripts.js
"use strict";

// ── Sidebar toggle ─────────────────────────────────────────────────────
// (Sidebar toggle is also handled inline in base.html for robustness.
//  This block is kept as a no-op guard so removing one doesn't break things.)
document.addEventListener("DOMContentLoaded", function () {
  const btn     = document.getElementById("toggleBtn");
  const sidebar = document.getElementById("sidebar");
  if (!btn || !sidebar) return;

  // The inline handler in base.html already covers the toggle; nothing extra needed.
});

// ── File download modal ────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("downloadForm");
  if (!form) return;

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    const formData = new FormData(form);

    fetch("/api/download", { method: "POST", body: formData })
      .then(function (res) {
        if (!res.ok) throw new Error("Download failed: " + res.status);
        return res.blob();
      })
      .then(function (blob) {
        const url = URL.createObjectURL(blob);
        const a   = document.createElement("a");
        a.href     = url;
        a.download = "data.csv";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url); // free memory
      })
      .catch(function (err) {
        console.error("Download error:", err);
      });
  });
});