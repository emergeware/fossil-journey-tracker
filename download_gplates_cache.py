#!/usr/bin/env python3
"""
Script para baixar todos os dados do GPlates Web Service e salvar no cache local.
Isso permite que o Fossil Journey Tracker funcione 100% offline.
"""

import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuracao
GPLATES_BASE_URL = "https://gws.gplates.org"
CACHE_DIR = Path(__file__).parent / "gplates_cache"
CACHE_DIR.mkdir(exist_ok=True)

# Modelos de rotacao e seus limites de idade
ROTATION_MODELS = {
    "MULLER2022": 1000,
    "MERDITH2021": 1000,
    "SETON2012": 200,
}

# Coordenadas dos presets de especimes (lat, lon)
PRESET_COORDINATES = [
    (-23.55, -46.63),   # Sao Paulo - Pleistoceno
    (-29.75, -51.15),   # RS - Mioceno
    (-22.90, -43.17),   # Rio de Janeiro - Oligoceno
    (-8.05, -34.88),    # PE - Eoceno
    (-5.20, -36.50),    # Bacia Potiguar - Paleoceno
    (-19.92, -43.94),   # Espirito Santo - Mioceno
    (-13.00, -38.50),   # Reconcavo - Eoceno
    (-25.43, -49.27),   # Pelotas - Mioceno
    (-22.50, -41.90),   # Campos - Cretaceo
    (-4.50, -37.50),    # Potiguar - Cretaceo
    (-3.71, -38.52),    # CE - Jurassico
    (-21.20, -41.80),   # Parana - Jurassico
    (-29.00, -51.00),   # RS - Triassico
    (-15.50, -47.50),   # GO - Jurassico
    (-26.00, -49.00),   # SC - Triassico
    (-5.00, -42.00),    # Parnaiba - Devoniano
    (-7.50, -46.00),    # Amazonas - Siluriano
    (-3.00, -60.00),    # Amazonas - Ordoviciano
    (-28.00, -50.00),   # RS - Permiano
    (-6.00, -44.00),    # MA - Carbonifero
    (-4.00, -43.00),    # Parnaiba - Devoniano
    (-30.00, -51.50),   # RS - Triassico
    (-24.00, -50.00),   # Parana - Permiano
    (-8.00, -45.00),    # PI - Carbonifero
    (-6.50, -43.50),    # Parnaiba - Devoniano
    (-2.50, -55.00),    # Amazonas - Siluriano
    (-4.00, -63.00),    # Solimoes - Ordoviciano
    (-10.00, -48.00),   # Sao Francisco - Cambriano
    (-1.50, -56.00),    # Amazonas - Ordoviciano
    (-5.50, -47.00),    # Parnaiba - Siluriano
    (-2.00, -58.00),    # Amazonas - Ordoviciano
    (-7.00, -44.50),    # MA - Devoniano
    # Coordenadas adicionais para pontos no mapa (grid)
    (-22.9, -43.2),     # Rio aproximado
    (-23.0, -43.0),     # Rio grid
    (-30.0, -51.0),     # RS grid
    (-25.0, -50.0),     # Parana grid
    (-20.0, -45.0),     # MG grid
    (-15.0, -47.0),     # GO grid
    (-10.0, -40.0),     # BA grid
    (-5.0, -45.0),      # MA grid
    (0.0, -50.0),       # Equador/PA
    (-35.0, -55.0),     # Uruguai
    (-40.0, -65.0),     # Argentina
    (-33.0, -70.0),     # Chile
    (10.0, -70.0),      # Venezuela
    (-10.0, -75.0),     # Peru
    (5.0, -55.0),       # Guiana
]

# Idades para baixar (em Ma)
def get_ages_for_model(max_age):
    """Gera lista de idades para um modelo."""
    ages = [0]
    # Passo de 10 Ma ate 100, depois 20 Ma
    for age in range(10, min(101, max_age + 1), 10):
        ages.append(age)
    for age in range(120, min(201, max_age + 1), 20):
        ages.append(age)
    for age in range(250, max_age + 1, 50):
        ages.append(age)
    return ages


def get_cache_path(url: str) -> Path:
    """Retorna o caminho do cache para uma URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{url_hash}.json"


def download_and_cache(url: str) -> tuple[str, bool, str]:
    """Baixa uma URL e salva no cache. Retorna (url, sucesso, mensagem)."""
    cache_path = get_cache_path(url)

    # Verificar se ja existe no cache
    if cache_path.exists():
        return (url, True, "cached")

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read().decode('utf-8')
            # Validar JSON
            json.loads(data)
            # Salvar no cache
            cache_path.write_text(data, encoding='utf-8')
            return (url, True, "downloaded")
    except Exception as e:
        return (url, False, str(e))


def generate_urls():
    """Gera todas as URLs necessarias para download."""
    urls = []

    for model_name, max_age in ROTATION_MODELS.items():
        ages = get_ages_for_model(max_age)

        # Coastlines para cada idade
        for age in ages:
            url = f"{GPLATES_BASE_URL}/reconstruct/coastlines/?time={age}&model={model_name}"
            urls.append(("coastlines", model_name, age, None, url))

        # Reconstruct points para cada coordenada e idade
        for lat, lon in PRESET_COORDINATES:
            for age in ages:
                if age <= max_age:
                    url = f"{GPLATES_BASE_URL}/reconstruct/reconstruct_points/?points={lon},{lat}&time={age}&model={model_name}"
                    urls.append(("points", model_name, age, (lat, lon), url))

    return urls


def main():
    print("=" * 70)
    print("GPLATES CACHE DOWNLOADER")
    print("Baixando dados para funcionamento 100% offline")
    print("=" * 70)

    # Gerar URLs
    print("\nGerando lista de URLs...")
    url_list = generate_urls()
    total_urls = len(url_list)
    print(f"Total de URLs a processar: {total_urls}")

    # Contar coastlines vs points
    coastlines_count = sum(1 for u in url_list if u[0] == "coastlines")
    points_count = sum(1 for u in url_list if u[0] == "points")
    print(f"  - Coastlines: {coastlines_count}")
    print(f"  - Reconstruct points: {points_count}")

    # Verificar cache existente
    print("\nVerificando cache existente...")
    cached = 0
    to_download = []
    for item in url_list:
        url = item[4]
        if get_cache_path(url).exists():
            cached += 1
        else:
            to_download.append(item)

    print(f"  - Ja em cache: {cached}")
    print(f"  - A baixar: {len(to_download)}")

    if not to_download:
        print("\n" + "=" * 70)
        print("TODOS OS DADOS JA ESTAO EM CACHE!")
        print("O sistema pode funcionar 100% offline.")
        print("=" * 70)
        return

    # Download paralelo
    print(f"\nIniciando download de {len(to_download)} arquivos...")
    print("(Isso pode demorar alguns minutos)")
    print()

    downloaded = 0
    failed = 0
    failed_urls = []

    start_time = time.time()

    # Usar ThreadPoolExecutor para downloads paralelos
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(download_and_cache, item[4]): item for item in to_download}

        for i, future in enumerate(as_completed(futures), 1):
            item = futures[future]
            url, success, message = future.result()

            if success:
                if message == "downloaded":
                    downloaded += 1
                status = "OK"
            else:
                failed += 1
                failed_urls.append((url, message))
                status = "ERRO"

            # Progresso
            pct = (i / len(to_download)) * 100
            elapsed = time.time() - start_time
            eta = (elapsed / i) * (len(to_download) - i) if i > 0 else 0

            tipo, model, age, coords, _ = item
            if coords:
                desc = f"{tipo} {model} {age}Ma ({coords[0]:.1f},{coords[1]:.1f})"
            else:
                desc = f"{tipo} {model} {age}Ma"

            print(f"[{i}/{len(to_download)}] {pct:5.1f}% | ETA: {eta:5.0f}s | {status:4s} | {desc}")

    # Resumo final
    elapsed_total = time.time() - start_time
    print()
    print("=" * 70)
    print("DOWNLOAD CONCLUIDO!")
    print("=" * 70)
    print(f"Tempo total: {elapsed_total:.1f} segundos")
    print(f"Arquivos baixados: {downloaded}")
    print(f"Ja em cache: {cached}")
    print(f"Falhas: {failed}")

    if failed_urls:
        print("\nURLs com falha:")
        for url, error in failed_urls[:10]:
            print(f"  - {url[:80]}...")
            print(f"    Erro: {error}")
        if len(failed_urls) > 10:
            print(f"  ... e mais {len(failed_urls) - 10} falhas")

    # Verificar se pode funcionar offline
    total_cached = cached + downloaded
    pct_cached = (total_cached / total_urls) * 100
    print()
    if pct_cached >= 95:
        print("O sistema pode funcionar 100% offline!")
    else:
        print(f"ATENCAO: Apenas {pct_cached:.1f}% dos dados estao em cache.")
        print("Algumas funcionalidades podem nao funcionar offline.")


if __name__ == "__main__":
    main()
