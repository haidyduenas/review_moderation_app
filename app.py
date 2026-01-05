from __future__ import annotations

import os
import uuid
from io import BytesIO
from datetime import datetime
from typing import Dict

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, send_file

from review_moderator import classify_dataframe, guess_review_column
from data_loader import load_reviews_to_dataframe, normalize_column_names, add_correlativo_and_clean_empty_col


import unicodedata
import re as _re

def _norm_col(name: str) -> str:
    s = "" if name is None else str(name)
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("_", " ")
    s = _re.sub(r"\s+", " ", s)
    return s

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_outputs_dir() -> str:
    out_dir = os.path.join(os.path.dirname(__file__), "outputs")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir

def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")
    app.config["RESULT_CACHE"]: Dict[str, bytes] = {}

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/process")
    def process():
        if "file" not in request.files:
            flash("No se encontró archivo en la solicitud.", "error")
            return redirect(url_for("index"))

        f = request.files["file"]
        if f.filename == "":
            flash("Selecciona un archivo CSV o Excel.", "error")
            return redirect(url_for("index"))

        if not allowed_file(f.filename):
            flash("Formato no soportado. Sube .csv, .xlsx o .xls", "error")
            return redirect(url_for("index"))

        try:
            df = load_reviews_to_dataframe(f)
        except Exception as e:
            flash(f"No pude leer el archivo: {e}", "error")
            return redirect(url_for("index"))

        if df.empty:
            flash("El archivo no tiene filas.", "error")
            return redirect(url_for("index"))

        df = normalize_column_names(df)
        df = add_correlativo_and_clean_empty_col(df, correlativo_name="Correlativo")

        chosen_col = (request.form.get("review_column") or "").strip()
        if chosen_col and chosen_col in df.columns:
            review_col = chosen_col
        else:
            review_col = guess_review_column(df)

        if review_col is None:
            flash(
                "No pude identificar la columna de reseñas. "
                "Asegúrate de tener una columna llamada por ejemplo: Reseña, Review, Comentario, Texto.",
                "error",
            )
            return render_template("index.html", columns=list(df.columns))

        out_df = classify_dataframe(df, review_col=review_col)

        # Resumen de distribución (para mostrar % en la UI)
        counts = out_df["clasificacion"].value_counts(dropna=False).to_dict()
        total = int(len(out_df))
        def pct(k: str) -> float:
            return round((counts.get(k, 0) / total * 100.0) if total else 0.0, 2)
        stats = {
            "Aprobar": {"count": int(counts.get("Aprobar", 0)), "pct": pct("Aprobar")},
            "Denegar": {"count": int(counts.get("Denegar", 0)), "pct": pct("Denegar")},
            "Revisión humana requerida": {"count": int(counts.get("Revisión humana requerida", 0)), "pct": pct("Revisión humana requerida")},
            "total": total,
        }


        estado_col = next((c for c in out_df.columns if c.strip().lower() == "estado"), None)
        criterio_col = next((c for c in out_df.columns if c.strip().lower() in {"criterio de moderación", "criterio de moderacion"}), None)

        if estado_col is not None:
            def map_estado(x: str) -> str:
                if x == "Aprobar":
                    return "Aprobada"
                if x == "Denegar":
                    return "Denegada"
                return "Revisión humana"
            out_df[estado_col] = out_df["clasificacion"].map(map_estado)

        if criterio_col is not None:
            out_df[criterio_col] = out_df["factor_revision_humana"].where(
                out_df["factor_revision_humana"].astype(str).str.len() > 0,
                out_df["explicacion"],
            )


        # ✅ Quitar columnas internas (siempre) para que la salida quede limpia
        drop_norm = {
            "explicacion",
            "factor revision humana",
            "factor_revision_humana",
            "clasificacion ia",
            "clasificación ia",
            "explicacion ia",
            "explicación ia",
            "factor ia",
        }
        cols_drop = [c for c in out_df.columns if _norm_col(c) in drop_norm]
        if cols_drop:
            out_df = out_df.drop(columns=cols_drop, errors="ignore")

        out_df = out_df.fillna("")

        output_format = (request.form.get("output_format") or "xlsx").lower()
        token = str(uuid.uuid4())
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_base = os.path.splitext(os.path.basename(f.filename))[0]
        filename = f"{safe_base}_resultado_{stamp}.{ 'xlsx' if output_format=='xlsx' else 'csv' }"

        buf = BytesIO()
        if output_format == "xlsx":
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                out_df.to_excel(writer, index=False, sheet_name="resultado")
        else:
            out_df.to_csv(buf, index=False, encoding="utf-8-sig")

        buf.seek(0)
        data_bytes = buf.getvalue()
        app.config["RESULT_CACHE"][token] = data_bytes

        out_dir = ensure_outputs_dir()
        saved_path = os.path.join(out_dir, filename)
        with open(saved_path, "wb") as fp:
            fp.write(data_bytes)

        preview_df = out_df.head(min(len(out_df), 200))

        return render_template(
            "results.html",
            review_col=review_col,
            rows=preview_df.to_dict(orient="records"),
            columns=list(preview_df.columns),
            total_rows=len(out_df),
            download_token=token,
            download_name=filename,
            saved_path=saved_path,
            stats=stats,
        )

    @app.get("/download/<token>/<name>")
    def download(token: str, name: str):
        data = app.config["RESULT_CACHE"].get(token)
        if data is None:
            flash("El archivo ya no está disponible. Vuelve a procesar el dataset.", "error")
            return redirect(url_for("index"))

        ext = name.rsplit(".", 1)[-1].lower()
        mimetype = "text/csv" if ext == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return send_file(BytesIO(data), mimetype=mimetype, as_attachment=True, download_name=name)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=True)
