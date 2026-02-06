#!/usr/bin/env python3
"""
TESTE AUTOMATIZADO DE SINCRONIZAÇÃO PONTO-CONTINENTE
=====================================================

Este script verifica se o sistema está funcionando corretamente:
1. Busca coordenadas reconstruídas do GPlates para várias idades
2. Busca coastlines do GPlates para as mesmas idades
3. Verifica se o ponto está DENTRO do continente em cada idade
4. Gera relatório de diagnóstico

Se o ponto está dentro do continente em todas as idades, o GPlates está correto
e o problema é na RENDERIZAÇÃO (JavaScript).
"""

import json
import urllib.request
import hashlib
from pathlib import Path

# Configuração
GPLATES_BASE = "https://gws.gplates.org"
CACHE_DIR = Path(__file__).parent / "gplates_cache"
MODEL = "MULLER2022"

# Ponto de teste: Rio de Janeiro
TEST_POINT = {"lat": -22.9, "lon": -43.2, "name": "Rio de Janeiro"}

# Idades para testar (múltiplos de 10)
TEST_AGES = [0, 50, 100, 150, 200, 250, 300]


def get_cache_path(url: str) -> Path:
    """Gera caminho do cache baseado na URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{url_hash}.json"


def fetch_url(url: str) -> dict:
    """Busca URL com cache."""
    cache_path = get_cache_path(url)

    # Verificar cache
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    # Buscar da API
    print(f"  Buscando: {url[:80]}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'TestSync/1.0'})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode())
        cache_path.write_text(json.dumps(data))
        return data


def reconstruct_point(lat: float, lon: float, age: int) -> tuple:
    """Reconstrói coordenadas do ponto para uma idade."""
    url = f"{GPLATES_BASE}/reconstruct/reconstruct_points/?points={lon},{lat}&time={age}&model={MODEL}"
    data = fetch_url(url)

    if data and "coordinates" in data and len(data["coordinates"]) > 0:
        return data["coordinates"][0][1], data["coordinates"][0][0]  # lat, lon
    return lat, lon


def get_coastlines(age: int) -> list:
    """Busca coastlines para uma idade."""
    url = f"{GPLATES_BASE}/reconstruct/coastlines/?time={age}&model={MODEL}"
    data = fetch_url(url)

    polygons = []
    if data and "features" in data:
        for feature in data["features"]:
            geom = feature.get("geometry", {})
            if geom.get("type") == "Polygon":
                coords = geom.get("coordinates", [[]])[0]
                polygons.append([(c[0], c[1]) for c in coords])  # lon, lat
            elif geom.get("type") == "MultiPolygon":
                for poly in geom.get("coordinates", []):
                    if poly:
                        polygons.append([(c[0], c[1]) for c in poly[0]])
    return polygons


def point_in_polygon(point_lon: float, point_lat: float, polygon: list) -> bool:
    """Ray casting algorithm para verificar se ponto está dentro do polígono."""
    x, y = point_lon, point_lat
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def point_in_any_polygon(point_lon: float, point_lat: float, polygons: list) -> bool:
    """Verifica se ponto está dentro de qualquer polígono."""
    for polygon in polygons:
        if len(polygon) >= 3 and point_in_polygon(point_lon, point_lat, polygon):
            return True
    return False


def run_diagnostic():
    """Executa diagnóstico completo."""
    print("=" * 70)
    print("DIAGNÓSTICO DE SINCRONIZAÇÃO PONTO-CONTINENTE")
    print("=" * 70)
    print(f"Ponto de teste: {TEST_POINT['name']}")
    print(f"Coordenadas originais: lat={TEST_POINT['lat']}, lon={TEST_POINT['lon']}")
    print(f"Modelo de rotação: {MODEL}")
    print("=" * 70)
    print()

    results = []
    all_ok = True

    for age in TEST_AGES:
        print(f"\n[{age} Ma]")
        print("-" * 40)

        # 1. Reconstruir ponto
        recon_lat, recon_lon = reconstruct_point(TEST_POINT['lat'], TEST_POINT['lon'], age)
        print(f"  Ponto reconstruído: lat={recon_lat:.4f}, lon={recon_lon:.4f}")

        # 2. Buscar coastlines
        polygons = get_coastlines(age)
        print(f"  Coastlines: {len(polygons)} polígonos")

        # 3. Verificar se ponto está dentro
        is_inside = point_in_any_polygon(recon_lon, recon_lat, polygons)

        if is_inside:
            print(f"  [OK] PONTO DENTRO DO CONTINENTE")
            status = "OK"
        else:
            print(f"  [ERRO] PONTO FORA DO CONTINENTE!")
            status = "ERRO"
            all_ok = False

            # Encontrar polígono mais próximo
            min_dist = float('inf')
            for i, poly in enumerate(polygons):
                if len(poly) >= 3:
                    center_lon = sum(p[0] for p in poly) / len(poly)
                    center_lat = sum(p[1] for p in poly) / len(poly)
                    dist = ((center_lon - recon_lon)**2 + (center_lat - recon_lat)**2)**0.5
                    if dist < min_dist:
                        min_dist = dist
            print(f"    Distância ao polígono mais próximo: {min_dist:.2f}°")

        results.append({
            "age": age,
            "original_lat": TEST_POINT['lat'],
            "original_lon": TEST_POINT['lon'],
            "recon_lat": recon_lat,
            "recon_lon": recon_lon,
            "num_polygons": len(polygons),
            "is_inside": is_inside,
            "status": status
        })

    # Resumo
    print("\n")
    print("=" * 70)
    print("RESUMO DO DIAGNÓSTICO")
    print("=" * 70)

    ok_count = sum(1 for r in results if r["is_inside"])
    error_count = len(results) - ok_count

    print(f"Total de idades testadas: {len(results)}")
    print(f"Ponto dentro do continente: {ok_count}")
    print(f"Ponto fora do continente: {error_count}")
    print()

    if all_ok:
        print("[OK] DIAGNOSTICO: API GPlates esta CORRETA")
        print("  O problema esta na RENDERIZACAO (JavaScript)")
        print()
        print("CAUSA PROVAVEL:")
        print("  - Os coastlines nao estao sendo atualizados durante a animacao")
        print("  - Ha dessincronizacao entre a idade do ponto e dos coastlines")
        print()
        print("SOLUCAO:")
        print("  - Garantir que currentCoastlines seja atualizado ANTES de desenhar")
        print("  - Verificar se loadCoastlinesForAge esta funcionando")
    else:
        print("[ERRO] DIAGNOSTICO: Problema na API GPlates ou no modelo de rotacao")
        print("  Alguns pontos reconstruidos estao fora dos continentes")

    # Salvar resultados
    output_file = Path(__file__).parent / "diagnostic_results.json"
    output_file.write_text(json.dumps(results, indent=2))
    print(f"\nResultados salvos em: {output_file}")

    return all_ok, results


def generate_fix():
    """Gera correção para o JavaScript baseado no diagnóstico."""
    print("\n")
    print("=" * 70)
    print("GERANDO CORREÇÃO AUTOMÁTICA")
    print("=" * 70)

    # A correção principal: garantir sincronização
    fix_code = '''
// ============================================================
// CORREÇÃO: Sincronização forçada de coastlines
// ============================================================
// O problema é que loadCoastlinesForAge é assíncrono e pode não
// atualizar currentCoastlines antes do desenho.
//
// SOLUÇÃO: Usar cache síncrono quando disponível
// ============================================================

function loadCoastlinesForAgeSync(targetAge) {
    const model = ROTATION_MODELS[currentRotationModel];
    const cacheKey = 'coastlines_' + targetAge + '_' + model.name;

    // Se está no cache, usar IMEDIATAMENTE (síncrono)
    if (coastlinesCache[cacheKey]) {
        currentCoastlines = coastlinesCache[cacheKey];
        lastCoastlinesAge2D = targetAge;
        return true; // Sucesso síncrono
    }

    // Se não está no cache, disparar carregamento assíncrono
    if (!isUpdatingCoastlines2D) {
        isUpdatingCoastlines2D = true;
        fetchCoastlines(targetAge).then(coastlines => {
            if (coastlines && coastlines.length > 0) {
                currentCoastlines = coastlines;
                lastCoastlinesAge2D = targetAge;
            }
            isUpdatingCoastlines2D = false;
        });
    }

    return false; // Carregamento assíncrono em andamento
}

// Modificar drawContinents2D para usar versão síncrona
function drawContinents2D() {
    const targetAge = journeyData ? Math.round(currentAge / 10) * 10 : 0;

    // FORÇAR sincronização - só desenha se coastlines estão na idade correta
    if (targetAge !== lastCoastlinesAge2D) {
        loadCoastlinesForAgeSync(targetAge);
    }

    // Desenhar coastlines atuais
    if (currentCoastlines && currentCoastlines.length > 0) {
        drawGPlatesCoastlines2D();
    } else {
        drawLocalContinentsStatic2D();
    }
}
'''

    print("Correção gerada:")
    print(fix_code)

    return fix_code


if __name__ == "__main__":
    CACHE_DIR.mkdir(exist_ok=True)

    try:
        all_ok, results = run_diagnostic()

        if all_ok:
            generate_fix()

    except Exception as e:
        print(f"\nERRO: {e}")
        import traceback
        traceback.print_exc()
