// Klik baris tabel untuk membuka detail; tutup popup aksi lain saat satu dibuka; polling chat.
document.addEventListener("click", function (ev) {
  var cp = ev.target.closest("[data-copy]");
  if (cp) {
    var text = cp.dataset.copy, label = cp.textContent;
    var done = function () { cp.textContent = "Tersalin"; setTimeout(function () { cp.textContent = label; }, 1800); };
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () { prompt("Salin pesan:", text); });
    else prompt("Salin pesan:", text);
    return;
  }
  var tr = ev.target.closest("tr[data-href]");
  if (tr && !ev.target.closest("a,button,form,input,select")) location.href = tr.dataset.href;
  var sum = ev.target.closest("details.act > summary");
  document.querySelectorAll("details.act[open]").forEach(function (d) {
    if (!sum || d !== sum.parentElement) { if (!d.contains(ev.target)) d.open = false; }
  });
});

function startChat(box) {
  var url = box.dataset.poll, last = parseInt(box.dataset.last || "0", 10), list = box.querySelector(".msgs");
  function bottom() { list.scrollTop = list.scrollHeight; }
  bottom();
  function tick() {
    fetch(url + "?after=" + last, { headers: { "X-Requested-With": "fetch" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (j && j.html) { list.insertAdjacentHTML("beforeend", j.html); last = j.last; bottom(); }
      })
      .catch(function () {});
  }
  setInterval(tick, 4000);
  var form = box.querySelector("form.composer");
  if (form) {
    var ta = form.querySelector("textarea");
    ta.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
    });
    form.addEventListener("submit", function (e) {
      var file = form.querySelector("input[type=file]");
      if (file && file.files.length) return; // lampiran: kirim biasa
      e.preventDefault();
      if (!ta.value.trim()) return;
      var data = new FormData(form);
      fetch(form.action, { method: "POST", body: data, headers: { "X-Requested-With": "fetch" } })
        .then(function () { ta.value = ""; tick(); });
    });
  }
}
document.querySelectorAll("[data-poll]").forEach(startChat);
