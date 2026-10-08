"""
Serverless function Python (FastAPI) untuk Vercel.

Endpoint:
    GET /api/proses_ai?input=<data_teks>

Menjalankan dua model (simulasi) secara bersamaan dengan asyncio.gather():
    - Random Forest  (delay 0.3 detik)
    - SVM            (delay 0.5 detik)

Karena berjalan paralel, total durasi ≈ 0.5 detik (model terlama),
bukan 0.8 detik (0.3 + 0.5) seperti kalau dijalankan berurutan.
"""

import asyncio
import re
import time

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Proses AI",
    docs_url="/api/proses_ai/docs",
    openapi_url="/api/proses_ai/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ganti dengan domain frontend untuk produksi
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Kata kunci indikasi ancaman (dipakai oleh model simulasi).
KATA_BAHAYA = {
    "serangan", "hack", "hacker", "malware", "virus", "exploit", "phishing",
    "ransomware", "ddos", "bocor", "ancaman", "bom", "senjata", "penyusup",
    "injeksi", "injection", "script", "drop", "trojan", "backdoor", "curi",
}


def _rasio_bahaya(teks: str) -> float:
    """Proporsi kata berbahaya dalam teks (0.0 - 1.0)."""
    kata = re.findall(r"\w+", teks.lower())
    if not kata:
        return 0.0
    return sum(k in KATA_BAHAYA for k in kata) / len(kata)


def _hasil(model: str, skor_bahaya: float) -> dict:
    """Ubah skor bahaya (0.0 - 1.0) jadi prediksi + confidence."""
    skor_bahaya = max(0.0, min(1.0, skor_bahaya))
    if skor_bahaya >= 0.5:
        prediction, confidence = "BAHAYA", skor_bahaya
    else:
        prediction, confidence = "AMAN", 1.0 - skor_bahaya
    return {"model": model, "prediction": prediction, "confidence": round(confidence, 4)}


# --- Fungsi A: Random Forest (simulasi, delay 0.3 detik) ---
async def model_random_forest(teks: str) -> dict:
    await asyncio.sleep(0.3)
    rasio = _rasio_bahaya(teks)
    # Satu kata bahaya saja sudah cukup mendorong skor ke atas ambang.
    skor = 0.1 + rasio * 4
    return _hasil("Random Forest", skor)


# --- Fungsi B: SVM (simulasi, delay 0.5 detik) ---
async def model_svm(teks: str) -> dict:
    await asyncio.sleep(0.5)
    rasio = _rasio_bahaya(teks)
    # SVM sedikit lebih konservatif dibanding RF.
    skor = 0.05 + rasio * 3.5
    return _hasil("SVM", skor)


@app.get("/api/proses_ai")
async def proses_ai(
    input: str = Query(..., min_length=1, max_length=5000, description="Teks yang akan diproses"),
):
    teks = input.strip()
    try:
        start = time.time()
        rf, svm = await asyncio.gather(
            model_random_forest(teks),
            model_svm(teks),
        )
        end = time.time()

        return {
            "status": "success",
            "duration_seconds": round(end - start, 4),
            "result": {
                "rf": rf,
                "svm": svm,
            },
        }
    except Exception as exc:  # error saat menjalankan model
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "duration_seconds": 0.0,
                "message": f"Gagal memproses: {exc}",
                "result": None,
            },
        )


# Error validasi (mis. parameter ?input tidak ada / kosong) juga dikembalikan
# dalam format JSON yang sama, bukan format default FastAPI.
@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "duration_seconds": 0.0,
            "message": "Parameter query 'input' wajib diisi (1-5000 karakter).",
            "result": None,
        },
    )