#!/usr/bin/env python3
"""
Script para baixar TODOS os dados do GPlates Web Service para o mundo inteiro.
Grid completo de coordenadas para funcionamento 100% offline em qualquer ponto.

AVISO: Este download é MUITO grande e pode demorar várias horas!
"""

import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse

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


def generate_grid_coordinates(step=5):
    """
    Gera grid de coordenadas cobrindo o mundo todo.
    step=5 significa pontos a cada 5 graus (72 x 37 = 2664 pontos)
    step=2 significa pontos a cada 2 graus (180 x 91 = 16380 pontos)
    step=1 significa pontos a cada 1 grau (360 x 181 = 65160 pontos)
    """
    coords = []
    for lat in range(-90, 91, step):
        for lon in range(-180, 180, step):
            # Limitar latitude para evitar problemas nos polos
            if lat < -85:
                lat = -85
            elif lat > 85:
                lat = 85
            coords.append((lat, lon))
    return coords


def get_ages_for_model(max_age, step=10):
    """Gera lista de idades para um modelo."""
    ages = []
    for age in range(0, max_age + 1, step):
        ages.append(age)
    return ages


def generate_urls(coord_step=5, age_step=10, models=None):
    """Gera todas as URLs necessarias para download."""
    urls = []

    if models is None:
        models = ROTATION_MODELS

    coordinates = generate_grid_coordinates(coord_step)
    print(f"Grid de coordenadas: {len(coordinates)} pontos (passo: {coord_step}°)")

    for model_name, max_age in models.items():
        ages = get_ages_for_model(max_age, age_step)
        print(f"Modelo {model_name}: {len(ages)} idades (0-{max_age} Ma, passo: {age_step} Ma)")

        # Coastlines para cada idade (uma vez por modelo)
        for age in ages:
            url = f"{GPLATES_BASE_URL}/reconstruct/coastlines/?time={age}&model={model_name}"
            urls.append(("coastlines", model_name, age, None, url))

        # Reconstruct points para cada coordenada e idade
        for lat, lon in coordinates:
            for age in ages:
                url = f"{GPLATES_BASE_URL}/reconstruct/reconstruct_points/?points={lon},{lat}&time={age}&model={model_name}"
                urls.append(("points", model_name, age, (lat, lon), url))

    return urls


def estimate_download(coord_step, age_step):
    """Estima o tamanho e tempo do download."""
    coords = generate_grid_coordinates(coord_step)
    n_coords = len(coords)

    total_points = 0
    total_coastlines = 0

    for model_name, max_age in ROTATION_MODELS.items():
        n_ages = len(get_ages_for_model(max_age, age_step))
        total_coastlines += n_ages
        total_points += n_coords * n_ages

    total_files = total_points + total_coastlines

    # Estimativas
    avg_size_kb = 2  # tamanho medio por arquivo em KB
    total_size_mb = (total_files * avg_size_kb) / 1024
    total_size_gb = total_size_mb / 1024

    # Tempo estimado (10 downloads por segundo com 10 threads)
    downloads_per_sec = 10
    time_seconds = total_files / downloads_per_sec
    time_minutes = time_seconds / 60
    time_hours = time_minutes / 60

    return {
        "n_coords": n_coords,
        "total_files": total_files,
        "total_coastlines": total_coastlines,
        "total_points": total_points,
        "size_mb": total_size_mb,
        "size_gb": total_size_gb,
        "time_minutes": time_minutes,
        "time_hours": time_hours,
    }


def main():
    parser = argparse.ArgumentParser(description='Download GPlates cache for offline use')
    parser.add_argument('--coord-step', type=int, default=5,
                        help='Grid step in degrees (default: 5). Lower = more points.')
    parser.add_argument('--age-step', type=int, default=10,
                        help='Age step in Ma (default: 10). Lower = more ages.')
    parser.add_argument('--model', type=str, default=None,
                        help='Download only this model (MULLER2022, MERDITH2021, SETON2012)')
    parser.add_argument('--estimate', action='store_true',
                        help='Only show estimate, do not download')
    parser.add_argument('--threads', type=int, default=10,
                        help='Number of parallel downloads (default: 10)')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompt')

    args = parser.parse_args()

    print("=" * 70)
    print("GPLATES FULL CACHE DOWNLOADER")
    print("Download completo para funcionamento 100% offline")
    print("=" * 70)

    # Estimativa
    est = estimate_download(args.coord_step, args.age_step)

    print(f"\nConfiguracao:")
    print(f"  - Grid de coordenadas: {est['n_coords']} pontos (passo: {args.coord_step}°)")
    print(f"  - Passo de idade: {args.age_step} Ma")
    print(f"  - Threads: {args.threads}")

    print(f"\nEstimativa:")
    print(f"  - Total de arquivos: {est['total_files']:,}")
    print(f"    - Coastlines: {est['total_coastlines']:,}")
    print(f"    - Reconstruct points: {est['total_points']:,}")
    print(f"  - Tamanho estimado: {est['size_mb']:.0f} MB ({est['size_gb']:.1f} GB)")
    print(f"  - Tempo estimado: {est['time_minutes']:.0f} min ({est['time_hours']:.1f} horas)")

    if args.estimate:
        print("\n[Modo estimativa - download nao iniciado]")
        return

    # Confirmar
    if not args.yes:
        print("\n" + "=" * 70)
        resp = input("Deseja continuar com o download? (s/N): ").strip().lower()
        if resp != 's':
            print("Download cancelado.")
            return

    # Selecionar modelos
    models = ROTATION_MODELS
    if args.model:
        if args.model in ROTATION_MODELS:
            models = {args.model: ROTATION_MODELS[args.model]}
        else:
            print(f"Modelo invalido: {args.model}")
            return

    # Gerar URLs
    print("\nGerando lista de URLs...")
    url_list = generate_urls(args.coord_step, args.age_step, models)
    total_urls = len(url_list)
    print(f"Total de URLs: {total_urls:,}")

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

    print(f"  - Ja em cache: {cached:,}")
    print(f"  - A baixar: {len(to_download):,}")

    if not to_download:
        print("\n" + "=" * 70)
        print("TODOS OS DADOS JA ESTAO EM CACHE!")
        print("=" * 70)
        return

    # Download
    print(f"\nIniciando download de {len(to_download):,} arquivos...")
    print("(Pressione Ctrl+C para cancelar)\n")

    downloaded = 0
    failed = 0
    failed_urls = []

    start_time = time.time()
    last_report_time = start_time

    try:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            futures = {executor.submit(download_and_cache, item[4]): item for item in to_download}

            for i, future in enumerate(as_completed(futures), 1):
                item = futures[future]
                url, success, message = future.result()

                if success:
                    if message == "downloaded":
                        downloaded += 1
                else:
                    failed += 1
                    if len(failed_urls) < 100:
                        failed_urls.append((url, message))

                # Progresso a cada 5 segundos ou 100 arquivos
                current_time = time.time()
                if current_time - last_report_time >= 5 or i % 100 == 0:
                    last_report_time = current_time
                    pct = (i / len(to_download)) * 100
                    elapsed = current_time - start_time
                    rate = i / elapsed if elapsed > 0 else 0
                    eta = (len(to_download) - i) / rate if rate > 0 else 0

                    print(f"[{i:,}/{len(to_download):,}] {pct:5.1f}% | "
                          f"{rate:.1f}/s | ETA: {eta/60:.0f}min | "
                          f"OK: {downloaded:,} | Falhas: {failed}")

    except KeyboardInterrupt:
        print("\n\nDownload interrompido pelo usuario!")

    # Resumo final
    elapsed_total = time.time() - start_time
    print()
    print("=" * 70)
    print("DOWNLOAD CONCLUIDO!")
    print("=" * 70)
    print(f"Tempo total: {elapsed_total/60:.1f} minutos")
    print(f"Arquivos baixados: {downloaded:,}")
    print(f"Ja em cache: {cached:,}")
    print(f"Falhas: {failed}")

    if failed_urls:
        print(f"\nPrimeiras {min(10, len(failed_urls))} URLs com falha:")
        for url, error in failed_urls[:10]:
            print(f"  - Erro: {error[:50]}")

    # Status do cache
    total_cached = cached + downloaded
    total_expected = len(url_list)
    pct_cached = (total_cached / total_expected) * 100
    print(f"\nStatus do cache: {total_cached:,}/{total_expected:,} ({pct_cached:.1f}%)")

    if pct_cached >= 99:
        print("O sistema pode funcionar 100% offline!")
    elif pct_cached >= 90:
        print("A maioria dos dados esta em cache.")
    else:
        print("ATENCAO: Dados incompletos. Execute novamente para completar.")


if __name__ == "__main__":
    main()
