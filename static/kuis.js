(function () {
  const el = (id) => document.getElementById(id);
  const WARNA = { A: "pa", B: "pb", C: "pc", D: "pd" };

  let waktuTotal = 20;
  let sisa = 20;
  let interval = null;
  let terkunci = false;
  let terakhir = false;

  function mulaiTimer() {
    clearInterval(interval);
    const mulai = performance.now();
    interval = setInterval(() => {
      sisa = Math.max(0, waktuTotal - (performance.now() - mulai) / 1000);
      el("timer").textContent = Math.ceil(sisa);
      el("bar-isi").style.width = (sisa / waktuTotal) * 100 + "%";
      if (sisa <= 0) {
        clearInterval(interval);
        kirim("");
      }
    }, 100);
  }

  async function muatSoal() {
    const r = await fetch("/api/soal");
    const d = await r.json();
    if (d.selesai) {
      window.location = "/selesai";
      return;
    }
    terkunci = false;
    waktuTotal = d.waktu;
    sisa = d.waktu;
    el("nomor").textContent = "Soal " + d.nomor + "/" + d.total;
    el("skor").textContent = d.skor;
    el("teks").textContent = d.teks;
    el("timer").textContent = d.waktu;
    el("bar-isi").style.width = "100%";
    el("umpanbalik").classList.add("hidden");
    el("lanjut").classList.add("hidden");

    const wadah = el("pilihan");
    wadah.innerHTML = "";
    Object.keys(d.pilihan).forEach((huruf) => {
      const b = document.createElement("button");
      b.className = "opsi " + WARNA[huruf];
      b.dataset.huruf = huruf;
      b.textContent = huruf + ". " + d.pilihan[huruf];
      b.addEventListener("click", () => kirim(huruf));
      wadah.appendChild(b);
    });
    mulaiTimer();
  }

  async function kirim(huruf) {
    if (terkunci) return;
    terkunci = true;
    clearInterval(interval);
    const r = await fetch("/api/jawab", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pilihan: huruf, sisa: sisa }),
    });
    const d = await r.json();
    if (d.error) {
      window.location = "/";
      return;
    }
    terakhir = d.terakhir;
    document.querySelectorAll(".opsi").forEach((b) => {
      b.disabled = true;
      if (b.dataset.huruf === d.kunci) b.classList.add("kunci");
      else if (b.dataset.huruf === huruf) b.classList.add("salah");
    });
    el("skor").textContent = d.skor;
    const fb = el("umpanbalik");
    fb.className = "umpanbalik " + (d.benar ? "ok" : "no");
    fb.textContent = d.benar
      ? "Benar! +" + d.poin + " poin"
      : huruf === "" ? "Waktu habis!" : "Kurang tepat.";
    el("lanjut").textContent = terakhir ? "Lihat hasil" : "Lanjut";
    el("lanjut").classList.remove("hidden");
  }

  el("lanjut").addEventListener("click", () => {
    if (terakhir) window.location = "/selesai";
    else muatSoal();
  });

  muatSoal();
})();
