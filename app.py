import os
import random
import string
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_sqlalchemy import SQLAlchemy

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
# Ganti kedua nilai ini lewat environment variable di PythonAnywhere (jangan ditulis di GitHub)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "ganti-kunci-rahasia-ini")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "kuis.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

db = SQLAlchemy(app)


@app.template_filter("wib")
def format_wib(dt):
    """Ubah waktu UTC di database menjadi tanggal dan jam WIB (UTC+7)."""
    if not dt:
        return "-"
    return (dt + timedelta(hours=7)).strftime("%d/%m/%Y %H:%M")


# ---------- Model ----------
class Kuis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(150), nullable=False)
    kode = db.Column(db.String(8), unique=True, nullable=False)
    kelas = db.Column(db.String(5), nullable=False, default="A")  # rombel: A atau B
    dibuat = db.Column(db.DateTime, default=datetime.utcnow)
    soal = db.relationship("Soal", backref="kuis", cascade="all, delete-orphan",
                           order_by="Soal.id")
    skor = db.relationship("Skor", backref="kuis", cascade="all, delete-orphan")


class Soal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kuis_id = db.Column(db.Integer, db.ForeignKey("kuis.id"), nullable=False)
    teks = db.Column(db.Text, nullable=False)
    a = db.Column(db.String(200), nullable=False)
    b = db.Column(db.String(200), nullable=False)
    c = db.Column(db.String(200), nullable=False)
    d = db.Column(db.String(200), nullable=False)
    benar = db.Column(db.String(1), nullable=False)  # A/B/C/D
    waktu = db.Column(db.Integer, default=20)  # detik

    def pilihan(self):
        return {"A": self.a, "B": self.b, "C": self.c, "D": self.d}


class Skor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kuis_id = db.Column(db.Integer, db.ForeignKey("kuis.id"), nullable=False)
    nama = db.Column(db.String(60), nullable=False)
    nilai = db.Column(db.Integer, default=0)
    jumlah_benar = db.Column(db.Integer, default=0)
    waktu = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()
    # Migrasi otomatis: tambah kolom `kelas` jika database lama belum punya
    kolom = [r[1] for r in db.session.execute(db.text("PRAGMA table_info(kuis)"))]
    if "kelas" not in kolom:
        db.session.execute(db.text("ALTER TABLE kuis ADD COLUMN kelas VARCHAR(5) NOT NULL DEFAULT 'A'"))
    else:
        # Data versi sebelumnya memakai angka 10/11 -> ubah jadi A/B
        db.session.execute(db.text("UPDATE kuis SET kelas='A' WHERE CAST(kelas AS TEXT)='10'"))
        db.session.execute(db.text("UPDATE kuis SET kelas='B' WHERE CAST(kelas AS TEXT)='11'"))
    db.session.commit()

DAFTAR_KELAS = ("A", "B")
TINGKAT = "11"  # semua rombel ada di kelas 11 (ubah di sini bila perlu)


@app.template_filter("namakelas")
def nama_kelas(k):
    """A -> 11-A"""
    return f"{TINGKAT}-{k}"


# ---------- Util ----------
def buat_kode():
    while True:
        kode = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Kuis.query.filter_by(kode=kode).first():
            return kode


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


def hitung_poin(waktu_total, sisa):
    sisa = max(0, min(sisa, waktu_total))
    return 500 + int(500 * sisa / waktu_total)


# ---------- Halaman pemain ----------
@app.route("/")
def index():
    jumlah = {k: Kuis.query.filter_by(kelas=k).count() for k in DAFTAR_KELAS}
    return render_template("index.html", kelas_list=DAFTAR_KELAS, jumlah=jumlah)


@app.route("/kelas/<kelas>")
def daftar_kuis(kelas):
    kelas = kelas.upper()
    if kelas not in DAFTAR_KELAS:
        abort(404)
    daftar = (Kuis.query.filter_by(kelas=kelas)
              .order_by(Kuis.dibuat.desc()).all())
    return render_template("kelas.html", kelas=kelas, daftar=daftar)


@app.route("/kuis/<kode>")
def kuis_detail(kode):
    kuis = Kuis.query.filter_by(kode=kode.upper()).first_or_404()
    return render_template("kuis_mulai.html", kuis=kuis)


@app.route("/mulai", methods=["POST"])
def mulai():
    kode = request.form.get("kode", "").strip().upper()
    nama = request.form.get("nama", "").strip()[:60]
    kuis = Kuis.query.filter_by(kode=kode).first()
    if not kuis:
        flash("Kuis tidak ditemukan.")
        return redirect(url_for("index"))
    if not nama:
        flash("Nama harus diisi.")
        return redirect(url_for("kuis_detail", kode=kuis.kode))
    if not kuis.soal:
        flash("Kuis ini belum punya soal.")
        return redirect(url_for("daftar_kuis", kelas=kuis.kelas))
    session["main"] = {"kuis_id": kuis.id, "nama": nama, "idx": 0, "skor": 0,
                       "benar": 0, "sudah_jawab": False}
    return redirect(url_for("main"))


@app.route("/main")
def main():
    state = session.get("main")
    if not state:
        return redirect(url_for("index"))
    kuis = db.session.get(Kuis, state["kuis_id"])
    return render_template("main.html", kuis=kuis, nama=state["nama"],
                           total=len(kuis.soal))


@app.route("/api/soal")
def api_soal():
    """Kirim soal saat ini TANPA kunci jawaban."""
    state = session.get("main")
    if not state:
        return jsonify({"error": "sesi habis"}), 400
    kuis = db.session.get(Kuis, state["kuis_id"])
    if state["idx"] >= len(kuis.soal):
        return jsonify({"selesai": True})
    s = kuis.soal[state["idx"]]
    state["sudah_jawab"] = False
    session["main"] = state
    return jsonify({"selesai": False, "nomor": state["idx"] + 1,
                    "total": len(kuis.soal), "teks": s.teks,
                    "pilihan": s.pilihan(), "waktu": s.waktu,
                    "skor": state["skor"]})


@app.route("/api/jawab", methods=["POST"])
def api_jawab():
    state = session.get("main")
    if not state:
        return jsonify({"error": "sesi habis"}), 400
    if state["sudah_jawab"]:
        return jsonify({"error": "sudah dijawab"}), 400
    kuis = db.session.get(Kuis, state["kuis_id"])
    if state["idx"] >= len(kuis.soal):
        return jsonify({"error": "kuis selesai"}), 400
    s = kuis.soal[state["idx"]]
    data = request.get_json(silent=True) or {}
    pilihan = str(data.get("pilihan", "")).upper()  # kosong = waktu habis
    try:
        sisa = float(data.get("sisa", 0))
    except (TypeError, ValueError):
        sisa = 0
    benar = pilihan == s.benar
    poin = hitung_poin(s.waktu, sisa) if benar else 0
    state["skor"] += poin
    state["benar"] += 1 if benar else 0
    state["sudah_jawab"] = True
    state["idx"] += 1
    session["main"] = state
    return jsonify({"benar": benar, "kunci": s.benar, "poin": poin,
                    "skor": state["skor"], "terakhir": state["idx"] >= len(kuis.soal)})


@app.route("/selesai")
def selesai():
    state = session.get("main")
    if not state:
        return redirect(url_for("index"))
    kuis = db.session.get(Kuis, state["kuis_id"])
    if state["idx"] < len(kuis.soal):
        return redirect(url_for("main"))
    skor = Skor(kuis_id=kuis.id, nama=state["nama"], nilai=state["skor"],
                jumlah_benar=state["benar"])
    db.session.add(skor)
    db.session.commit()
    session.pop("main", None)
    session["skor_terakhir"] = skor.id
    return redirect(url_for("hasil", kode=kuis.kode))


@app.route("/hasil/<kode>")
def hasil(kode):
    kuis = Kuis.query.filter_by(kode=kode.upper()).first_or_404()
    papan = (Skor.query.filter_by(kuis_id=kuis.id)
             .order_by(Skor.nilai.desc(), Skor.waktu.asc()).limit(20).all())
    return render_template("hasil.html", kuis=kuis, papan=papan,
                           skor_id=session.get("skor_terakhir"),
                           total=len(kuis.soal))


# ---------- Admin ----------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Password salah.")
    return render_template("login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin():
    daftar = Kuis.query.order_by(Kuis.dibuat.desc()).all()
    return render_template("admin.html", daftar=daftar)


@app.route("/admin/kuis/baru", methods=["POST"])
@admin_required
def kuis_baru():
    judul = request.form.get("judul", "").strip()
    kelas = request.form.get("kelas", "").strip().upper()
    if not judul or kelas not in DAFTAR_KELAS:
        flash("Judul dan kelas kuis harus diisi.")
        return redirect(url_for("admin"))
    kuis = Kuis(judul=judul[:150], kode=buat_kode(), kelas=kelas)
    db.session.add(kuis)
    db.session.commit()
    return redirect(url_for("kuis_edit", kuis_id=kuis.id))


@app.route("/admin/kuis/<int:kuis_id>")
@admin_required
def kuis_edit(kuis_id):
    kuis = db.session.get(Kuis, kuis_id) or abort(404)
    return render_template("kuis_edit.html", kuis=kuis)


@app.route("/admin/kuis/<int:kuis_id>/soal", methods=["POST"])
@admin_required
def soal_tambah(kuis_id):
    kuis = db.session.get(Kuis, kuis_id) or abort(404)
    f = request.form
    benar = f.get("benar", "").upper()
    kolom = [f.get(k, "").strip() for k in ("teks", "a", "b", "c", "d")]
    if not all(kolom) or benar not in "ABCD" or benar == "":
        flash("Semua kolom dan kunci jawaban harus diisi.")
        return redirect(url_for("kuis_edit", kuis_id=kuis.id))
    try:
        waktu = max(5, min(120, int(f.get("waktu", 20))))
    except ValueError:
        waktu = 20
    db.session.add(Soal(kuis_id=kuis.id, teks=kolom[0], a=kolom[1], b=kolom[2],
                        c=kolom[3], d=kolom[4], benar=benar, waktu=waktu))
    db.session.commit()
    return redirect(url_for("kuis_edit", kuis_id=kuis.id))


@app.route("/admin/soal/<int:soal_id>/hapus", methods=["POST"])
@admin_required
def soal_hapus(soal_id):
    s = db.session.get(Soal, soal_id) or abort(404)
    kuis_id = s.kuis_id
    db.session.delete(s)
    db.session.commit()
    return redirect(url_for("kuis_edit", kuis_id=kuis_id))


@app.route("/admin/kuis/<int:kuis_id>/hapus", methods=["POST"])
@admin_required
def kuis_hapus(kuis_id):
    kuis = db.session.get(Kuis, kuis_id) or abort(404)
    db.session.delete(kuis)
    db.session.commit()
    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(debug=True)
