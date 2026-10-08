"""
Pengujian lokal: membuktikan model RF dan SVM berjalan bersamaan.

    Random Forest : delay 0.3 detik
    SVM           : delay 0.5 detik

    Berurutan (await satu per satu) → ±0.8 detik  (0.3 + 0.5)
    Bersamaan (asyncio.gather)      → ±0.5 detik  (model terlama)

Cara menjalankan (dari root proyek):
    python test_async_ai.py
"""

import asyncio
import os
import sys
import time

# Supaya folder api/ di root proyek bisa di-import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.proses_ai import model_random_forest, model_svm  # noqa: E402

TEKS_UJI = "Terdeteksi serangan malware dan phishing dari hacker"
TOLERANSI = 0.1  # detik, untuk overhead event loop


def cetak_hasil(rf: dict, svm: dict) -> None:
    for h in (rf, svm):
        print(f"    {h['model']:<14} → {h['prediction']:<7} (confidence {h['confidence']:.2f})")


async def uji_berurutan() -> float:
    print("\n[1] BERURUTAN (await satu per satu)")
    start = time.time()
    rf = await model_random_forest(TEKS_UJI)
    svm = await model_svm(TEKS_UJI)
    durasi = time.time() - start
    cetak_hasil(rf, svm)
    print(f"    Total waktu: {durasi:.4f} detik")
    return durasi


async def uji_bersamaan() -> float:
    print("\n[2] BERSAMAAN (asyncio.gather)")
    start = time.time()
    rf, svm = await asyncio.gather(
        model_random_forest(TEKS_UJI),
        model_svm(TEKS_UJI),
    )
    durasi = time.time() - start
    cetak_hasil(rf, svm)
    print(f"    Total waktu: {durasi:.4f} detik")
    return durasi


async def main() -> None:
    print("=" * 56)
    print(" PENGUJIAN ASYNC: Random Forest (0.3s) + SVM (0.5s)")
    print("=" * 56)
    print(f' Input: "{TEKS_UJI}"')

    durasi_seq = await uji_berurutan()
    durasi_par = await uji_bersamaan()

    print("\n" + "=" * 56)
    print(" KESIMPULAN")
    print("=" * 56)
    print(f"  Berurutan : {durasi_seq:.4f} detik  (≈ 0.3 + 0.5 = 0.8)")
    print(f"  Bersamaan : {durasi_par:.4f} detik  (≈ max(0.3, 0.5) = 0.5)")
    print(f"  Lebih cepat {durasi_seq - durasi_par:.4f} detik "
          f"({durasi_seq / durasi_par:.2f}x)")

    # Verifikasi
    lulus = True
    if abs(durasi_par - 0.5) <= TOLERANSI:
        print("\n  ✅ LULUS: gather ≈ 0.5 detik (waktu model terlama)")
    else:
        print(f"\n  ❌ GAGAL: gather {durasi_par:.4f} detik, seharusnya ≈ 0.5")
        lulus = False

    if durasi_par < 0.8 - TOLERANSI:
        print("  ✅ LULUS: gather jelas di bawah 0.8 detik (bukan dijumlahkan)")
    else:
        print(f"  ❌ GAGAL: gather {durasi_par:.4f} detik mendekati 0.8 → tidak paralel")
        lulus = False

    sys.exit(0 if lulus else 1)


if __name__ == "__main__":
    asyncio.run(main())