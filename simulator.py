#!/usr/bin/env python3
"""
Fossil Journey Tracker - Simulador v9.1
========================================
Visualizacao com toggle 2D/3D usando GPlates Web Service REAL:
- Reconstrucao de paleocoordenadas via API GPlates (gws.gplates.org)
- Coastlines reais reconstruidas para cada idade
- Multiplos modelos de rotacao calibrados cientificamente
- CACHE PERSISTENTE EM DISCO para funcionamento offline

Usage:
    python simulator.py              # Executa normalmente
    python simulator.py --download   # Baixa TODOS os dados do GPlates para cache local

Author: ITT Oceaneon / UNISINOS
Version: 9.1.0
"""

import sys
import os
import json
import threading
import time
import hashlib
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import urllib.request
import urllib.error

# ============================================================================
# CACHE PERSISTENTE EM DISCO - Para funcionamento offline
# ============================================================================

CACHE_DIR = Path(__file__).parent / "gplates_cache"
CACHE_DIR.mkdir(exist_ok=True)

def get_cache_path(url: str) -> Path:
    """Gera caminho do cache baseado na URL."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{url_hash}.json"

def load_from_disk_cache(url: str) -> str | None:
    """Carrega dados do cache em disco."""
    cache_path = get_cache_path(url)
    if cache_path.exists():
        try:
            return cache_path.read_text(encoding='utf-8')
        except Exception:
            pass
    return None

def save_to_disk_cache(url: str, data: str):
    """Salva dados no cache em disco."""
    cache_path = get_cache_path(url)
    try:
        cache_path.write_text(data, encoding='utf-8')
    except Exception as e:
        print(f"Erro ao salvar cache: {e}")

# ============================================================================
# GPLATES PROXY SERVER - Evita CORS e usa cache persistente
# ============================================================================

GPLATES_BASE_URL = "https://gws.gplates.org"
GPLATES_MEMORY_CACHE = {}  # Cache em memoria para sessao atual
PROXY_PORT = 8089

class GPlatesProxyHandler(BaseHTTPRequestHandler):
    """Handler para proxy do GPlates Web Service."""

    def log_message(self, format, *args):
        """Silencia logs do servidor."""
        pass

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Proxy GET requests - usa cache local primeiro, depois internet se necessario."""
        try:
            parsed = urlparse(self.path)

            # Construir URL do GPlates (para lookup no cache)
            gplates_url = f"{GPLATES_BASE_URL}{parsed.path}"
            if parsed.query:
                gplates_url += f"?{parsed.query}"

            # 1. Verificar cache em memoria (mais rapido)
            if gplates_url in GPLATES_MEMORY_CACHE:
                self._send_json_response(GPLATES_MEMORY_CACHE[gplates_url])
                return

            # 2. Verificar cache em disco (persistente)
            disk_data = load_from_disk_cache(gplates_url)
            if disk_data:
                GPLATES_MEMORY_CACHE[gplates_url] = disk_data
                self._send_json_response(disk_data)
                return

            # 3. NAO ENCONTRADO NO CACHE - buscar da internet e salvar no cache
            import urllib.request
            try:
                with urllib.request.urlopen(gplates_url, timeout=30) as response:
                    data = response.read().decode('utf-8')
                    # Salvar no cache para proximas vezes
                    save_to_disk_cache(gplates_url, data)
                    GPLATES_MEMORY_CACHE[gplates_url] = data
                    self._send_json_response(data)
            except Exception as e:
                self.send_error(404, f"Dados nao encontrados: {str(e)}")

        except Exception as e:
            self.send_error(500, str(e))

    def _send_json_response(self, data):
        """Send JSON response with CORS headers."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'max-age=3600')
        self.end_headers()
        self.wfile.write(data.encode('utf-8'))


def start_gplates_proxy():
    """Inicia o servidor proxy em uma thread separada."""
    server = HTTPServer(('127.0.0.1', PROXY_PORT), GPlatesProxyHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"GPlates proxy server running on http://127.0.0.1:{PROXY_PORT}")
    return server


# ============================================================================
# PRE-DOWNLOAD DE TODOS OS DADOS PARA FUNCIONAMENTO 100% OFFLINE
# ============================================================================

LIB_DIR_DOWNLOAD = Path(__file__).parent / "lib"

def download_js_libraries():
    """Baixa Three.js e OrbitControls para funcionamento offline."""
    LIB_DIR_DOWNLOAD.mkdir(exist_ok=True)

    libs = [
        ("three.min.js", "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"),
        ("OrbitControls.js", "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"),
    ]

    print("\n[DOWNLOAD] Bibliotecas JavaScript")
    print("-" * 40)

    for filename, url in libs:
        filepath = LIB_DIR_DOWNLOAD / filename
        if filepath.exists():
            print(f"  [OK] {filename} - Ja existe")
            continue

        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'FossilJourneyTracker/9.1'})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
                filepath.write_bytes(data)
                print(f"  [DL] {filename} - Baixado ({len(data)//1024} KB)")
        except Exception as e:
            print(f"  [ER] {filename} - ERRO: {e}")


def download_all_gplates_data():
    """
    Baixa TODOS os dados necessarios para funcionamento 100% offline:
    - Bibliotecas JavaScript (Three.js, OrbitControls)
    - Coastlines para idades de 0 a 540 Ma (a cada 10 Ma)
    - Para cada modelo de rotacao disponivel
    """
    print("=" * 60)
    print("DOWNLOAD COMPLETO PARA FUNCIONAMENTO 100% OFFLINE")
    print("=" * 60)
    print(f"Cache GPlates: {CACHE_DIR}")
    print(f"Bibliotecas JS: {LIB_DIR_DOWNLOAD}")
    print()

    # 1. Baixar bibliotecas JavaScript
    download_js_libraries()

    # 2. Baixar dados do GPlates
    print("\n[DOWNLOAD] Dados geologicos do GPlates Web Service")
    print("-" * 40)

    models = ["MULLER2022", "SETON2012", "MERDITH2021"]
    ages = list(range(0, 550, 10))  # 0, 10, 20, ..., 540 Ma

    total_requests = len(models) * len(ages)
    completed = 0
    cached = 0
    downloaded = 0
    errors = 0

    for model in models:
        print(f"\n[DOWNLOAD] Baixando dados para modelo: {model}")
        print("-" * 40)

        for age in ages:
            # URL dos coastlines
            url = f"{GPLATES_BASE_URL}/reconstruct/coastlines/?time={age}&model={model}"

            # Verificar se ja esta em cache
            if load_from_disk_cache(url):
                cached += 1
                completed += 1
                progress = (completed / total_requests) * 100
                print(f"  [OK] {age:3d} Ma - Cache existente [{progress:5.1f}%]")
                continue

            # Baixar do GPlates
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        'User-Agent': 'FossilJourneyTracker/9.1-Downloader',
                        'Accept': 'application/json'
                    }
                )

                with urllib.request.urlopen(req, timeout=60) as response:
                    data = response.read().decode('utf-8')
                    save_to_disk_cache(url, data)
                    downloaded += 1
                    completed += 1
                    progress = (completed / total_requests) * 100
                    print(f"  [DL] {age:3d} Ma - Baixado [{progress:5.1f}%]")

                # Pausa para nao sobrecarregar o servidor
                time.sleep(0.3)

            except Exception as e:
                errors += 1
                completed += 1
                print(f"  [ER] {age:3d} Ma - ERRO: {e}")

    print()
    print("=" * 60)
    print("DOWNLOAD COMPLETO!")
    print("=" * 60)
    print(f"  Total de requisicoes: {total_requests}")
    print(f"  Ja em cache:          {cached}")
    print(f"  Baixados agora:       {downloaded}")
    print(f"  Erros:                {errors}")
    print(f"  Tamanho do cache:     {sum(f.stat().st_size for f in CACHE_DIR.glob('*.json')) / 1024 / 1024:.1f} MB")
    print()
    print("NOTA: Os coastlines estao em cache. As reconstrucoes de pontos")
    print("      especificos serao cacheadas na primeira utilizacao.")
    print()
    print("O sistema pode funcionar OFFLINE para visualizacao de coastlines!")
    print("=" * 60)


# ============================================================================
# QT SETUP
# ============================================================================

# Configurar Qt plugins
def _setup_qt_environment():
    try:
        import PyQt5
        pyqt5_path = Path(PyQt5.__file__).parent
        plugins_path = pyqt5_path / "Qt5" / "plugins"
        if plugins_path.exists():
            os.environ["QT_PLUGIN_PATH"] = str(plugins_path)
        platforms_path = plugins_path / "platforms"
        if platforms_path.exists():
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms_path)
    except ImportError:
        pass

_setup_qt_environment()

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QDoubleSpinBox, QCheckBox,
    QGroupBox, QFormLayout, QSplitter, QButtonGroup, QRadioButton
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage


# ============================================================================
# SPECIMEN DATA
# ============================================================================

SPECIMEN_EXAMPLES = [
    # ============ CENOZOICO (66 Ma - Presente) ============
    # Foraminiferos planctonicos - surgem no Jurassico (~170 Ma), diversificam no Cretaceo
    {"name": "Foraminifero - Pleistoceno (1.5 Ma)", "specimen_type": "FOR", "era_code": "CEN", "period_code": "PLE", "fad_ma": 1.5, "confidence": 98.0, "latitude": -23.55, "longitude": -46.63, "description": "Globigerina bulloides - Pleistoceno, Bacia de Santos, Brasil"},
    {"name": "Foraminifero - Mioceno (15 Ma)", "specimen_type": "FOR", "era_code": "CEN", "period_code": "MIO", "fad_ma": 15.0, "confidence": 95.0, "latitude": -29.75, "longitude": -51.15, "description": "Orbulina universa - Mioceno Medio, RS, Brasil"},
    {"name": "Foraminifero - Oligoceno (28 Ma)", "specimen_type": "FOR", "era_code": "CEN", "period_code": "OLI", "fad_ma": 28.0, "confidence": 92.0, "latitude": -22.90, "longitude": -43.17, "description": "Catapsydrax dissimilis - Oligoceno, Bacia de Campos, Brasil"},
    {"name": "Foraminifero - Eoceno (45 Ma)", "specimen_type": "FOR", "era_code": "CEN", "period_code": "EOC", "fad_ma": 45.0, "confidence": 91.0, "latitude": -8.05, "longitude": -34.88, "description": "Morozovella aragonensis - Eoceno Medio, PE, Brasil"},
    {"name": "Foraminifero - Paleoceno (60 Ma)", "specimen_type": "FOR", "era_code": "CEN", "period_code": "PAL", "fad_ma": 60.0, "confidence": 88.0, "latitude": -5.20, "longitude": -36.50, "description": "Subbotina triloculinoides - Paleoceno, Bacia Potiguar, Brasil"},
    # Ostracoda - surgem no Ordoviciano (~485 Ma)
    {"name": "Ostracoda - Mioceno (18 Ma)", "specimen_type": "OST", "era_code": "CEN", "period_code": "MIO", "fad_ma": 18.0, "confidence": 94.0, "latitude": -19.92, "longitude": -43.94, "description": "Krithe spp. - Mioceno, Bacia do Espirito Santo, Brasil"},
    {"name": "Ostracoda - Eoceno (50 Ma)", "specimen_type": "OST", "era_code": "CEN", "period_code": "EOC", "fad_ma": 50.0, "confidence": 90.0, "latitude": -13.00, "longitude": -38.50, "description": "Cytherella spp. - Eoceno, Bacia de Reconcavo, Brasil"},
    # Diatomaceas - surgem no Jurassico (~185 Ma)
    {"name": "Diatomacea - Mioceno (12 Ma)", "specimen_type": "DIA", "era_code": "CEN", "period_code": "MIO", "fad_ma": 12.0, "confidence": 93.0, "latitude": -25.43, "longitude": -49.27, "description": "Coscinodiscus spp. - Mioceno Superior, Bacia de Pelotas, Brasil"},
    # ============ MESOZOICO (252 - 66 Ma) ============
    {"name": "Foraminifero - Cretaceo Sup. (75 Ma)", "specimen_type": "FOR", "era_code": "MES", "period_code": "CRE", "fad_ma": 75.0, "confidence": 87.0, "latitude": -22.50, "longitude": -41.90, "description": "Globotruncana spp. - Maastrichtiano, Bacia de Campos, Brasil"},
    {"name": "Foraminifero - Cretaceo Inf. (120 Ma)", "specimen_type": "FOR", "era_code": "MES", "period_code": "CRE", "fad_ma": 120.0, "confidence": 85.0, "latitude": -4.50, "longitude": -37.50, "description": "Hedbergella spp. - Aptiano, Bacia Potiguar, Brasil"},
    {"name": "Foraminifero - Jurassico (160 Ma)", "specimen_type": "FOR", "era_code": "MES", "period_code": "JUR", "fad_ma": 160.0, "confidence": 82.0, "latitude": -3.71, "longitude": -38.52, "description": "Lenticulina spp. - Jurassico Superior, CE, Brasil"},
    {"name": "Ostracoda - Cretaceo (100 Ma)", "specimen_type": "OST", "era_code": "MES", "period_code": "CRE", "fad_ma": 100.0, "confidence": 87.5, "latitude": -22.90, "longitude": -43.17, "description": "Paracypris spp. - Cretaceo Superior, RJ, Brasil"},
    {"name": "Ostracoda - Jurassico (175 Ma)", "specimen_type": "OST", "era_code": "MES", "period_code": "JUR", "fad_ma": 175.0, "confidence": 80.0, "latitude": -21.20, "longitude": -41.80, "description": "Darwinula spp. - Jurassico Medio, Bacia do Parana, Brasil"},
    {"name": "Ostracoda - Triassico (230 Ma)", "specimen_type": "OST", "era_code": "MES", "period_code": "TRI", "fad_ma": 230.0, "confidence": 78.0, "latitude": -29.00, "longitude": -51.00, "description": "Darwinula oblonga - Triassico Superior, RS, Brasil"},
    # Radiolarios - surgem no Cambriano (~540 Ma)
    {"name": "Radiolario - Jurassico (155 Ma)", "specimen_type": "RAD", "era_code": "MES", "period_code": "JUR", "fad_ma": 155.0, "confidence": 83.0, "latitude": -15.50, "longitude": -47.50, "description": "Pantanellium spp. - Jurassico Superior, GO, Brasil"},
    {"name": "Radiolario - Triassico (240 Ma)", "specimen_type": "RAD", "era_code": "MES", "period_code": "TRI", "fad_ma": 240.0, "confidence": 76.0, "latitude": -26.00, "longitude": -49.00, "description": "Muelleritortis spp. - Triassico Medio, SC, Brasil"},
    # ============ PALEOZOICO (541 - 252 Ma) ============
    {"name": "Ostracoda - Permiano (280 Ma)", "specimen_type": "OST", "era_code": "PAL", "period_code": "PER", "fad_ma": 280.0, "confidence": 75.0, "latitude": -25.43, "longitude": -49.27, "description": "Carbonita spp. - Permiano Inferior, Bacia do Parana, Brasil"},
    {"name": "Ostracoda - Carbonifero (320 Ma)", "specimen_type": "OST", "era_code": "PAL", "period_code": "CAR", "fad_ma": 320.0, "confidence": 72.0, "latitude": -23.50, "longitude": -47.50, "description": "Cavellina spp. - Carbonifero Superior, SP, Brasil"},
    {"name": "Ostracoda - Devoniano (385 Ma)", "specimen_type": "OST", "era_code": "PAL", "period_code": "DEV", "fad_ma": 385.0, "confidence": 70.0, "latitude": -5.00, "longitude": -42.00, "description": "Beyrichia spp. - Devoniano Medio, Bacia do Parnaiba, Brasil"},
    {"name": "Ostracoda - Siluriano (430 Ma)", "specimen_type": "OST", "era_code": "PAL", "period_code": "SIL", "fad_ma": 430.0, "confidence": 68.0, "latitude": -7.50, "longitude": -46.00, "description": "Leperditia spp. - Siluriano, Bacia do Amazonas, Brasil"},
    {"name": "Ostracoda - Ordoviciano (470 Ma)", "specimen_type": "OST", "era_code": "PAL", "period_code": "ORD", "fad_ma": 470.0, "confidence": 65.0, "latitude": -3.00, "longitude": -60.00, "description": "Eoleperditia spp. - Ordoviciano Medio, Bacia do Amazonas, Brasil"},
    {"name": "Radiolario - Permiano (265 Ma)", "specimen_type": "RAD", "era_code": "PAL", "period_code": "PER", "fad_ma": 265.0, "confidence": 73.0, "latitude": -28.00, "longitude": -50.00, "description": "Albaillella spp. - Permiano Medio, RS, Brasil"},
    {"name": "Radiolario - Carbonifero (340 Ma)", "specimen_type": "RAD", "era_code": "PAL", "period_code": "CAR", "fad_ma": 340.0, "confidence": 70.0, "latitude": -6.00, "longitude": -44.00, "description": "Entactinia spp. - Carbonifero Inferior, MA, Brasil"},
    {"name": "Radiolario - Devoniano (400 Ma)", "specimen_type": "RAD", "era_code": "PAL", "period_code": "DEV", "fad_ma": 400.0, "confidence": 68.0, "latitude": -4.00, "longitude": -43.00, "description": "Ceratoikiscum spp. - Devoniano Superior, Bacia do Parnaiba, Brasil"},
    # Conodontes - Cambriano ate Triassico (extintos ~200 Ma)
    {"name": "Conodonte - Triassico (220 Ma)", "specimen_type": "CON", "era_code": "MES", "period_code": "TRI", "fad_ma": 220.0, "confidence": 77.0, "latitude": -30.00, "longitude": -51.50, "description": "Neogondolella spp. - Triassico Inferior, RS, Brasil"},
    {"name": "Conodonte - Permiano (270 Ma)", "specimen_type": "CON", "era_code": "PAL", "period_code": "PER", "fad_ma": 270.0, "confidence": 74.0, "latitude": -24.00, "longitude": -50.00, "description": "Mesogondolella spp. - Permiano, Bacia do Parana, Brasil"},
    {"name": "Conodonte - Carbonifero (330 Ma)", "specimen_type": "CON", "era_code": "PAL", "period_code": "CAR", "fad_ma": 330.0, "confidence": 71.0, "latitude": -8.00, "longitude": -45.00, "description": "Idiognathodus spp. - Carbonifero Superior, PI, Brasil"},
    {"name": "Conodonte - Devoniano (375 Ma)", "specimen_type": "CON", "era_code": "PAL", "period_code": "DEV", "fad_ma": 375.0, "confidence": 69.0, "latitude": -6.50, "longitude": -43.50, "description": "Polygnathus spp. - Devoniano, Bacia do Parnaiba, Brasil"},
    {"name": "Conodonte - Siluriano (425 Ma)", "specimen_type": "CON", "era_code": "PAL", "period_code": "SIL", "fad_ma": 425.0, "confidence": 66.0, "latitude": -2.50, "longitude": -55.00, "description": "Ozarkodina spp. - Siluriano, Bacia do Amazonas, Brasil"},
    {"name": "Conodonte - Ordoviciano (465 Ma)", "specimen_type": "CON", "era_code": "PAL", "period_code": "ORD", "fad_ma": 465.0, "confidence": 64.0, "latitude": -4.00, "longitude": -63.00, "description": "Pygodus spp. - Ordoviciano, Bacia do Solimoes, Brasil"},
    # Acritarcos - Proterozoico ate Presente
    {"name": "Acritarco - Cambriano (520 Ma)", "specimen_type": "ACR", "era_code": "PAL", "period_code": "CAM", "fad_ma": 520.0, "confidence": 62.0, "latitude": -10.00, "longitude": -48.00, "description": "Skiagia spp. - Cambriano Inferior, Bacia do Sao Francisco, Brasil"},
    {"name": "Acritarco - Ordoviciano (480 Ma)", "specimen_type": "ACR", "era_code": "PAL", "period_code": "ORD", "fad_ma": 480.0, "confidence": 63.0, "latitude": -1.50, "longitude": -56.00, "description": "Baltisphaeridium spp. - Ordoviciano Inferior, Bacia do Amazonas, Brasil"},
    # Quitinozoarios - Ordoviciano ate Devoniano (extintos ~360 Ma)
    {"name": "Quitinozoario - Siluriano (435 Ma)", "specimen_type": "QUI", "era_code": "PAL", "period_code": "SIL", "fad_ma": 435.0, "confidence": 67.0, "latitude": -5.50, "longitude": -47.00, "description": "Ancyrochitina spp. - Siluriano, Bacia do Parnaiba, Brasil"},
    {"name": "Quitinozoario - Ordoviciano (455 Ma)", "specimen_type": "QUI", "era_code": "PAL", "period_code": "ORD", "fad_ma": 455.0, "confidence": 65.0, "latitude": -2.00, "longitude": -58.00, "description": "Lagenochitina spp. - Ordoviciano Superior, Bacia do Amazonas, Brasil"},
    {"name": "Quitinozoario - Devoniano (395 Ma)", "specimen_type": "QUI", "era_code": "PAL", "period_code": "DEV", "fad_ma": 395.0, "confidence": 69.0, "latitude": -7.00, "longitude": -44.50, "description": "Angochitina spp. - Devoniano Inferior, MA, Brasil"},
]


# ============================================================================
# HTML/JS - VISUALIZACAO INTERATIVA v9.1 - 100% OFFLINE
# ============================================================================

# Carregar bibliotecas JavaScript locais
LIB_DIR = Path(__file__).parent / "lib"

def load_local_js_libs():
    """Carrega Three.js e OrbitControls dos arquivos locais."""
    threejs_path = LIB_DIR / "three.min.js"
    orbit_path = LIB_DIR / "OrbitControls.js"

    threejs_code = ""
    orbit_code = ""

    if threejs_path.exists():
        threejs_code = threejs_path.read_text(encoding='utf-8')
    else:
        print(f"[ERRO] Three.js nao encontrado em {threejs_path}")
        print("       Execute: python simulator.py --download")

    if orbit_path.exists():
        orbit_code = orbit_path.read_text(encoding='utf-8')
    else:
        print(f"[ERRO] OrbitControls.js nao encontrado em {orbit_path}")
        print("       Execute: python simulator.py --download")

    return threejs_code, orbit_code

# Placeholder - sera preenchido em runtime
THREEJS_CODE = ""
ORBIT_CODE = ""

# Marcadores para substituicao no HTML
THREEJS_PLACEHOLDER = "/*__THREEJS_CODE_HERE__*/"
ORBIT_PLACEHOLDER = "/*__ORBIT_CODE_HERE__*/"
GPLATES_DATA_PLACEHOLDER = "/*__GPLATES_CACHE_DATA__*/"

def load_gplates_cache_as_js():
    """Retorna objeto vazio - dados serao servidos pelo proxy local do cache em disco."""
    # NAO embutir dados no HTML (muito grande - 233MB!)
    # O proxy local servira os dados do cache em disco via HTTP localhost
    return "{}"

def get_html_content():
    """Gera o HTML com as bibliotecas JS e dados GPlates embutidos."""
    global THREEJS_CODE, ORBIT_CODE
    if not THREEJS_CODE:
        THREEJS_CODE, ORBIT_CODE = load_local_js_libs()

    # Carregar dados do GPlates
    gplates_cache_js = load_gplates_cache_as_js()

    # Substituir os placeholders no HTML
    html = THREEJS_HTML_TEMPLATE
    html = html.replace(THREEJS_PLACEHOLDER, THREEJS_CODE)
    html = html.replace(ORBIT_PLACEHOLDER, ORBIT_CODE)
    html = html.replace(GPLATES_DATA_PLACEHOLDER, gplates_cache_js)
    return html

# Template HTML com placeholders para as bibliotecas
THREEJS_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fossil Journey Tracker v9.1 - OFFLINE</title>
    <script>
    // THREE.JS EMBUTIDO LOCALMENTE
    /*__THREEJS_CODE_HERE__*/
    </script>
    <script>
    // ORBIT CONTROLS EMBUTIDO LOCALMENTE
    /*__ORBIT_CODE_HERE__*/
    </script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0d1117;
            color: #e6edf3;
            overflow: hidden;
        }

        #main-container {
            width: 100vw;
            height: 100vh;
            position: relative;
        }

        /* View containers - apenas um visivel por vez */
        #view-3d, #view-2d {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }
        #view-3d.hidden, #view-2d.hidden { display: none; }

        #container-3d { width: 100%; height: 100%; cursor: grab; }
        #container-3d:active { cursor: grabbing; }
        #canvas-2d { width: 100%; height: 100%; cursor: crosshair; }

        /* Toggle de vista */
        #view-toggle {
            position: absolute;
            top: 15px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 200;
            display: flex;
            background: rgba(0,0,0,0.9);
            border-radius: 25px;
            padding: 4px;
            border: 1px solid #30363d;
        }
        .toggle-btn {
            padding: 8px 24px;
            border: none;
            background: transparent;
            color: #8b949e;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            border-radius: 20px;
            transition: all 0.2s;
        }
        .toggle-btn.active {
            background: #238636;
            color: white;
        }
        .toggle-btn:hover:not(.active) {
            background: rgba(255,255,255,0.1);
        }

        /* Estilos para paineis minimizaveis */
        .panel {
            transition: all 0.3s ease;
        }
        .panel.minimized {
            padding: 8px 12px !important;
            min-width: auto !important;
        }
        .panel.minimized .panel-content {
            display: none;
        }
        .panel.minimized .panel-header {
            margin-bottom: 0 !important;
            border-bottom: none !important;
        }
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
        }
        .panel-header:hover {
            opacity: 0.8;
        }
        .minimize-btn {
            background: none;
            border: none;
            color: #8b949e;
            font-size: 16px;
            cursor: pointer;
            padding: 0 5px;
            line-height: 1;
        }
        .minimize-btn:hover {
            color: #e6edf3;
        }

        /* Controle de velocidade - sempre visivel acima da timeline */
        #speed-control {
            position: absolute;
            bottom: 140px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.95);
            padding: 8px 15px;
            border-radius: 20px;
            border: 1px solid #4fc3f7;
            z-index: 150;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        #speed-control label {
            color: #8b949e;
            font-size: 11px;
            text-transform: uppercase;
        }
        #speed-slider {
            width: 120px;
            height: 6px;
            -webkit-appearance: none;
            background: #30363d;
            border-radius: 3px;
            outline: none;
        }
        #speed-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 16px;
            height: 16px;
            background: #4fc3f7;
            border-radius: 50%;
            cursor: pointer;
        }
        #speed-value {
            color: #4fc3f7;
            font-weight: bold;
            font-size: 12px;
            min-width: 35px;
        }
        .speed-btn {
            background: none;
            border: 1px solid #30363d;
            color: #8b949e;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
        }
        .speed-btn:hover {
            background: rgba(255,255,255,0.1);
            color: #e6edf3;
        }
        .speed-btn.active {
            background: #238636;
            border-color: #238636;
            color: white;
        }

        /* Painel de modelo */
        #model-panel {
            position: absolute;
            top: 15px;
            right: 15px;
            background: rgba(0,0,0,0.92);
            padding: 12px 18px;
            border-radius: 10px;
            border: 1px solid #30363d;
            z-index: 100;
            min-width: 200px;
        }
        #model-panel h3 {
            color: #4fc3f7;
            font-size: 12px;
            margin: 0 0 8px 0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .model-row {
            display: flex;
            justify-content: space-between;
            margin: 4px 0;
            font-size: 11px;
        }
        .model-label { color: #8b949e; }
        .model-value { color: #e6edf3; font-weight: 500; }
        .model-name {
            color: #58a6ff;
            font-weight: bold;
            font-size: 14px;
            padding: 6px 0;
            border-bottom: 1px solid #30363d;
            margin-bottom: 6px;
        }

        /* Info panel */
        #info-panel {
            position: absolute;
            top: 70px;
            left: 15px;
            background: rgba(0,0,0,0.92);
            padding: 18px;
            border-radius: 12px;
            border: 1px solid rgba(79,195,247,0.3);
            min-width: 320px;
            z-index: 100;
        }
        #info-panel h2 { color: #4fc3f7; margin: 0 0 12px 0; font-size: 16px; }
        #info-panel .row { margin: 6px 0; display: flex; justify-content: space-between; font-size: 12px; }
        #info-panel .label { color: #8b949e; }
        #info-panel .value { color: #e6edf3; font-weight: 500; }

        .age-display {
            text-align: center;
            padding: 15px 0;
            border-top: 1px solid #30363d;
            border-bottom: 1px solid #30363d;
            margin: 12px 0;
        }
        .age-value {
            color: #ffeb3b;
            font-size: 32px;
            font-family: 'Courier New', monospace;
            font-weight: bold;
        }
        .age-unit { color: #8b949e; font-size: 14px; }
        .period-name { color: #4caf50; font-size: 16px; font-weight: bold; margin-top: 5px; }

        /* Envelope de incerteza */
        #uncertainty-section {
            background: rgba(255,152,0,0.1);
            border: 1px solid rgba(255,152,0,0.3);
            border-radius: 8px;
            padding: 12px;
            margin-top: 12px;
        }
        #uncertainty-section h3 {
            color: #ff9800;
            font-size: 13px;
            margin: 0 0 10px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .ellipse-icon {
            width: 20px;
            height: 14px;
            border: 2px solid #ff9800;
            border-radius: 50%;
        }
        .uncertainty-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }
        .uncertainty-item {
            background: rgba(0,0,0,0.3);
            padding: 8px;
            border-radius: 6px;
            text-align: center;
        }
        .uncertainty-item .val {
            font-size: 16px;
            font-weight: bold;
            color: #ff9800;
        }
        .uncertainty-item .lbl {
            font-size: 9px;
            color: #8b949e;
            text-transform: uppercase;
        }

        .quality-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            margin-top: 8px;
        }
        .quality-high { background: #22c55e; color: white; }
        .quality-medium { background: #f59e0b; color: black; }
        .quality-low { background: #ef4444; color: white; }

        /* Trajetoria legenda */
        #trajectory-legend {
            position: absolute;
            bottom: 80px;
            left: 15px;
            background: rgba(0,0,0,0.92);
            padding: 12px;
            border-radius: 8px;
            z-index: 100;
            font-size: 11px;
        }
        #trajectory-legend h4 {
            color: #4fc3f7;
            margin: 0 0 8px 0;
            font-size: 11px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            margin: 4px 0;
            gap: 8px;
        }
        .legend-line {
            width: 30px;
            height: 3px;
        }
        .legend-circle {
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }
        .legend-ellipse {
            width: 24px;
            height: 16px;
            border: 2px solid;
            border-radius: 50%;
            opacity: 0.7;
        }

        /* Timeline - sempre visivel na parte inferior */
        #timeline {
            position: absolute;
            bottom: 10px;
            left: 15px;
            right: 15px;
            background: rgba(0,0,0,0.95);
            padding: 12px 15px;
            border-radius: 10px;
            z-index: 140;
            border: 1px solid #30363d;
        }
        #timeline-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 11px;
            color: #8b949e;
        }
        #timeline-bar {
            height: 50px;
            background: #161b22;
            border-radius: 8px;
            position: relative;
            overflow: visible;
            cursor: pointer;
            display: flex;
            border: 2px solid #30363d;
        }
        .period-segment {
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            font-weight: bold;
            color: rgba(0,0,0,0.85);
            text-shadow: 0 1px 1px rgba(255,255,255,0.3);
            border-right: 1px solid rgba(0,0,0,0.2);
            position: relative;
            overflow: hidden;
        }
        .period-segment:hover {
            filter: brightness(1.2);
        }
        .period-segment:last-child {
            border-right: none;
        }
        /* Cores oficiais ICS (International Commission on Stratigraphy) */
        /* Cenozoico */
        .period-quaternary { background: #F9F97F; color: #333; }
        .period-neogene { background: #FFE619; color: #333; }
        .period-paleogene { background: #FD9A52; color: #333; }
        /* Mesozoico */
        .period-cretaceous { background: #7FC64E; color: #333; }
        .period-jurassic { background: #34B2C9; color: #fff; }
        .period-triassic { background: #812B92; color: #fff; }
        /* Paleozoico */
        .period-permian { background: #F04028; color: #fff; }
        .period-carboniferous { background: #67A599; color: #333; }
        .period-devonian { background: #CB8C37; color: #333; }
        .period-silurian { background: #B3E1B6; color: #333; }
        .period-ordovician { background: #009270; color: #fff; }
        .period-cambrian { background: #7FA056; color: #333; }

        /* Marcador de tempo atual (azul cyan) */
        #timeline-current-marker {
            position: absolute;
            top: -8px;
            bottom: -8px;
            width: 4px;
            background: #00bcd4;
            box-shadow: 0 0 10px #00bcd4;
            border-radius: 2px;
            z-index: 12;
            left: 0%;
        }
        #timeline-current-marker::before {
            content: 'HOJE';
            position: absolute;
            top: -18px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 9px;
            color: #00bcd4;
            font-weight: bold;
            white-space: nowrap;
        }

        /* Marcador de destino (laranja) */
        #timeline-target-marker {
            position: absolute;
            top: -8px;
            bottom: -8px;
            width: 4px;
            background: #ff5722;
            box-shadow: 0 0 10px #ff5722;
            border-radius: 2px;
            z-index: 11;
            display: none;
        }
        #timeline-target-marker::before {
            content: attr(data-age);
            position: absolute;
            bottom: -18px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 9px;
            color: #ff5722;
            font-weight: bold;
            white-space: nowrap;
        }

        /* Marcador de animacao (vermelho) */
        #timeline-marker {
            position: absolute;
            top: -5px;
            bottom: -5px;
            width: 6px;
            background: #f44336;
            box-shadow: 0 0 15px #f44336;
            border-radius: 3px;
            z-index: 13;
            display: none;
        }

        /* Trajetoria desenhada no timeline - oculto por padrao */
        #trajectory-preview {
            display: none;
        }

        .hidden { display: none !important; }

        /* Waiting screen */
        #waiting {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            z-index: 50;
        }
        #waiting h1 { color: #4fc3f7; font-size: 28px; margin-bottom: 10px; }
        #waiting p { color: #8b949e; font-size: 14px; margin: 5px 0; }
        #waiting .instructions {
            margin-top: 25px;
            padding: 20px;
            background: rgba(79,195,247,0.1);
            border-radius: 12px;
            border: 1px solid rgba(79,195,247,0.3);
            text-align: left;
        }
        #waiting .instructions li {
            margin: 8px 0;
            color: #c9d1d9;
        }
        #waiting .instructions strong { color: #4fc3f7; }

        /* LOADING OVERLAY - Indicador de carregamento */
        #loading-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 8, 20, 0.95);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        #loading-overlay.hidden { display: none; }
        #loading-spinner {
            width: 80px;
            height: 80px;
            border: 6px solid #1f6feb;
            border-top-color: #4fc3f7;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        #loading-text {
            color: #4fc3f7;
            font-size: 20px;
            font-weight: bold;
            margin-top: 25px;
        }
        #loading-status {
            color: #8b949e;
            font-size: 14px;
            margin-top: 10px;
        }
        #loading-progress {
            width: 300px;
            height: 8px;
            background: #21262d;
            border-radius: 4px;
            margin-top: 20px;
            overflow: hidden;
        }
        #loading-progress-bar {
            height: 100%;
            background: linear-gradient(90deg, #1f6feb, #4fc3f7);
            border-radius: 4px;
            width: 0%;
            transition: width 0.3s ease;
        }

        /* Tooltip de coordenadas */
        #coord-tooltip {
            position: absolute;
            background: rgba(0,0,0,0.95);
            padding: 8px 14px;
            border-radius: 6px;
            font-size: 12px;
            color: #e6edf3;
            pointer-events: none;
            z-index: 300;
            white-space: nowrap;
            border: 1px solid #30363d;
        }
    </style>
</head>
<body>
    <div id="main-container">
        <!-- View 3D -->
        <div id="view-3d">
            <div id="container-3d"></div>
        </div>

        <!-- View 2D -->
        <div id="view-2d" class="hidden">
            <canvas id="canvas-2d"></canvas>
        </div>

        <!-- Toggle de vista -->
        <div id="view-toggle">
            <button class="toggle-btn active" id="btn-3d" onclick="switchView('3d')">GLOBO 3D</button>
            <button class="toggle-btn" id="btn-2d" onclick="switchView('2d')">MAPA 2D</button>
        </div>

        <!-- Painel do modelo (minimizavel) - inicia minimizado -->
        <div id="model-panel" class="panel minimized">
            <div class="panel-header" onclick="togglePanel('model-panel')">
                <h3 style="margin: 0;">Modelo de Rotacao</h3>
                <button class="minimize-btn" title="Expandir">+</button>
            </div>
            <div class="panel-content">
                <div class="model-name" id="rotation-model-name">MULLER2022</div>
                <div class="model-row">
                    <span class="model-label">Cobertura:</span>
                    <span class="model-value" id="model-coverage">0 - 1000 Ma</span>
                </div>
                <div class="model-row">
                    <span class="model-label">Referencia:</span>
                    <span class="model-value" id="model-reference">Müller et al. 2022</span>
                </div>
                <div class="model-row">
                    <span class="model-label">Fonte:</span>
                    <span class="model-value" id="data-source" style="color: #4caf50;">GPlates Web Service</span>
                </div>
            </div>
        </div>

        <!-- Coordenadas selecionadas por mouse -->
        <div id="mouse-coords-panel" class="hidden" style="position: absolute; bottom: 80px; right: 15px; background: rgba(0,0,0,0.92); padding: 12px; border-radius: 8px; z-index: 100; border: 1px solid #4fc3f7;">
            <div style="font-size: 11px; color: #4fc3f7; margin-bottom: 5px;">PONTO SELECIONADO</div>
            <div style="font-size: 14px; color: #e6edf3;" id="selected-coords">--</div>
            <div style="font-size: 10px; color: #8b949e; margin-top: 5px;">Clique no mapa para selecionar</div>
        </div>

        <!-- Tela de espera (oculta por padrao, instrucoes ja estao no painel lateral) -->
        <div id="waiting" class="hidden"></div>

        <!-- LOADING OVERLAY - Mostrado durante carregamento -->
        <div id="loading-overlay" class="hidden">
            <div id="loading-spinner"></div>
            <div id="loading-text">Preparando Jornada...</div>
            <div id="loading-status">Carregando dados do GPlates</div>
            <div id="loading-progress">
                <div id="loading-progress-bar"></div>
            </div>
        </div>

        <!-- Painel de informacoes (minimizavel) - inicia minimizado -->
        <div id="info-panel" class="panel hidden minimized">
            <div class="panel-header" onclick="togglePanel('info-panel')">
                <h2 style="margin: 0; color: #4fc3f7; font-size: 14px;">Jornada Paleocontinental</h2>
                <button class="minimize-btn" title="Expandir">+</button>
            </div>
            <div class="panel-content">
                <div class="row">
                    <span class="label">Tipo de Especime:</span>
                    <span class="value" id="specimen-type">--</span>
                </div>
                <div class="row">
                    <span class="label">Origem (Hoje):</span>
                    <span class="value" id="current-coords">--</span>
                </div>
                <div class="row">
                    <span class="label">Posicao na Idade:</span>
                    <span class="value" id="paleo-coords" style="color: #ff5722;">--</span>
                </div>
                <div class="row">
                    <span class="label">Deslocamento Total:</span>
                    <span class="value" id="displacement">-- km</span>
                </div>

                <div class="age-display">
                    <div class="age-value" id="current-age">0.0</div>
                    <div class="age-unit">milhoes de anos (Ma)</div>
                    <div class="period-name" id="current-period">Holoceno</div>
                </div>

                <div id="uncertainty-section">
                    <h3><div class="ellipse-icon"></div> Envelope de Incerteza (95%)</h3>
                    <div class="uncertainty-grid">
                        <div class="uncertainty-item">
                            <div class="val" id="unc-major">--</div>
                            <div class="lbl">Eixo Maior (km)</div>
                        </div>
                        <div class="uncertainty-item">
                            <div class="val" id="unc-minor">--</div>
                            <div class="lbl">Eixo Menor (km)</div>
                        </div>
                        <div class="uncertainty-item">
                            <div class="val" id="unc-angle">--</div>
                            <div class="lbl">Orientacao</div>
                        </div>
                        <div class="uncertainty-item">
                            <div class="val" id="unc-chi2">5.99</div>
                            <div class="lbl">Chi-squared</div>
                        </div>
                    </div>
                    <div style="text-align: center;">
                        <span class="quality-badge quality-high" id="quality-badge">ALTA CONFIANCA</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Legenda da trajetoria (minimizavel) - inicia minimizado -->
        <div id="trajectory-legend" class="panel hidden minimized">
            <div class="panel-header" onclick="togglePanel('trajectory-legend')">
                <h4 style="margin: 0; color: #4fc3f7; font-size: 11px;">Legenda</h4>
                <button class="minimize-btn" title="Expandir">+</button>
            </div>
            <div class="panel-content">
                <div class="legend-item">
                    <div class="legend-circle" style="background: #ff5722;"></div>
                    <span>Local do Fossil (move com continente)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-circle" style="background: rgba(79,195,247,0.6); width: 8px; height: 8px;"></div>
                    <span>Origem (posicao atual)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-line" style="background: linear-gradient(90deg, #4fc3f7, #ff5722);"></div>
                    <span>Trajetoria</span>
                </div>
                <div class="legend-item">
                    <div class="legend-ellipse" style="border-color: #ff9800; background: rgba(255,152,0,0.2);"></div>
                    <span>Envelope de Incerteza</span>
                </div>
            </div>
        </div>

        <!-- Controle de velocidade - sempre visivel -->
        <div id="speed-control">
            <label>Velocidade:</label>
            <button class="speed-btn" onclick="setSpeed(10)">10x</button>
            <button class="speed-btn" onclick="setSpeed(25)">25x</button>
            <button class="speed-btn active" onclick="setSpeed(50)">50x</button>
            <button class="speed-btn" onclick="setSpeed(100)">100x</button>
            <button class="speed-btn" onclick="setSpeed(200)">200x</button>
            <input type="range" id="speed-slider" min="10" max="200" step="10" value="50" oninput="setSpeedFromSlider(this.value)">
            <span id="speed-value">50x</span>
            <button class="speed-btn" onclick="togglePause()" id="pause-btn" title="Pausar/Continuar">⏸</button>
        </div>

        <!-- Timeline - Escala de Tempo Geologico Completa -->
        <div id="timeline">
            <div id="timeline-header">
                <span>HOJE (0 Ma)</span>
                <span id="max-age-label">541 Ma</span>
            </div>
            <div id="timeline-bar">
                <!-- Cenozoico: 0-66 Ma (12.2%) -->
                <div class="period-segment period-quaternary" style="width: 0.5%;" title="Quaternario (0-2.6 Ma)"></div>
                <div class="period-segment period-neogene" style="width: 3.9%;" title="Neogeno (2.6-23 Ma)">Ng</div>
                <div class="period-segment period-paleogene" style="width: 7.9%;" title="Paleogeno (23-66 Ma)">Paleog</div>
                <!-- Mesozoico: 66-252 Ma (34.4%) -->
                <div class="period-segment period-cretaceous" style="width: 14.6%;" title="Cretaceo (66-145 Ma)">CRETACEO</div>
                <div class="period-segment period-jurassic" style="width: 10.4%;" title="Jurassico (145-201 Ma)">JURASSICO</div>
                <div class="period-segment period-triassic" style="width: 9.4%;" title="Triassico (201-252 Ma)">TRIASSICO</div>
                <!-- Paleozoico: 252-541 Ma (53.4%) -->
                <div class="period-segment period-permian" style="width: 8.7%;" title="Permiano (252-299 Ma)">PERMIANO</div>
                <div class="period-segment period-carboniferous" style="width: 11.1%;" title="Carbonifero (299-359 Ma)">CARBONIF</div>
                <div class="period-segment period-devonian" style="width: 11.1%;" title="Devoniano (359-419 Ma)">DEVONIANO</div>
                <div class="period-segment period-silurian" style="width: 4.6%;" title="Siluriano (419-444 Ma)">SIL</div>
                <div class="period-segment period-ordovician" style="width: 7.6%;" title="Ordoviciano (444-485 Ma)">ORDOVIC</div>
                <div class="period-segment period-cambrian" style="width: 10.4%;" title="Cambriano (485-541 Ma)">CAMBRIANO</div>
                <!-- Marcadores -->
                <div id="timeline-current-marker"></div>
                <div id="timeline-target-marker" data-age=""></div>
                <div id="timeline-marker"></div>
            </div>
            <!-- Legenda das Eras com idades -->
            <div style="display: flex; justify-content: space-between; margin-top: 8px; font-size: 11px; font-weight: bold;">
                <span style="color: #FFE619;">■ CENOZOICO (0-66 Ma)</span>
                <span style="color: #67C5CA;">■ MESOZOICO (66-252 Ma)</span>
                <span style="color: #99C08D;">■ PALEOZOICO (252-541 Ma)</span>
            </div>
        </div>

        <div id="coord-tooltip" class="hidden"></div>
    </div>

    <script>
        // ================================================================
        // CONFIGURACAO GLOBAL - v9.1 OFFLINE (cache local via proxy)
        // Dados servidos do cache em disco pelo proxy Python local
        // ================================================================

        const EARTH_RADIUS = 6;
        const EARTH_RADIUS_KM = 6371;

        // Proxy local que serve dados do cache em disco (SEM internet)
        const LOCAL_PROXY = 'http://127.0.0.1:8089';

        // Modelos de rotacao disponiveis no GPlates Web Service
        // Estes sao os modelos REAIS calibrados cientificamente
        const ROTATION_MODELS = {
            MULLER2022: {
                name: 'MULLER2022',
                description: 'Müller et al. 2022',
                maxAge: 1000,
                reference: 'GPlates Web Service - Modelo padrao'
            },
            SETON2012: {
                name: 'SETON2012',
                description: 'Seton et al. 2012',
                maxAge: 200,
                reference: 'GPlates Web Service - Alta precisao Mesozoico'
            },
            MERDITH2021: {
                name: 'MERDITH2021',
                description: 'Merdith et al. 2021',
                maxAge: 1000,
                reference: 'GPlates Web Service - Reconstrucao desde 1 Ga'
            },
            MATTHEWS2016: {
                name: 'MATTHEWS2016_pmag_ref',
                description: 'Matthews et al. 2016',
                maxAge: 410,
                reference: 'GPlates Web Service - Paleomag reference'
            }
        };

        let currentRotationModel = 'MULLER2022';

        // ================================================================
        // FEATURE FLAGS - OTIMIZAÇÕES (controladas pelo painel PyQt)
        // ================================================================
        const OPTIMIZATIONS = {
            preloadCoastlines: false,    // Pré-carregar coastlines ao iniciar
            preloadAges: false,          // Pré-carregar próximas idades durante animação
            interpolation: false,        // Usar interpolação bilinear do cache
            fastRender: false            // Renderização otimizada (simplificar coastlines)
        };

        // Cache de coastlines pré-carregadas (para otimização)
        const preloadedCoastlines = {};
        const PRELOAD_AGES = [0, 50, 100, 150, 200, 250, 300, 400, 500];

        // Função para atualizar otimizações via PyQt
        function setOptimizations(opts) {
            console.log('Otimizações recebidas:', opts);
            OPTIMIZATIONS.preloadCoastlines = opts.preload_coastlines || false;
            OPTIMIZATIONS.preloadAges = opts.preload_ages || false;
            OPTIMIZATIONS.interpolation = opts.interpolation || false;
            OPTIMIZATIONS.fastRender = opts.fast_render || false;

            // Se ativar preload de coastlines, iniciar carregamento
            if (OPTIMIZATIONS.preloadCoastlines && Object.keys(preloadedCoastlines).length === 0) {
                preloadAllCoastlines();
            }
        }

        // Pré-carregar coastlines principais
        async function preloadAllCoastlines() {
            console.log('Iniciando pré-carregamento de coastlines...');
            const models = ['MULLER2022'];  // Modelo principal primeiro

            for (const model of models) {
                for (const age of PRELOAD_AGES) {
                    const cacheKey = `${model}_${age}`;
                    if (!preloadedCoastlines[cacheKey]) {
                        try {
                            const url = `${LOCAL_PROXY}/reconstruct/coastlines/?time=${age}&model=${model}`;
                            const response = await fetch(url);
                            if (response.ok) {
                                preloadedCoastlines[cacheKey] = await response.json();
                                console.log(`  Preloaded: ${model} ${age} Ma`);
                            }
                        } catch (e) {
                            console.log(`  Erro preload: ${model} ${age} Ma`);
                        }
                    }
                }
            }
            console.log('Pré-carregamento concluído:', Object.keys(preloadedCoastlines).length, 'coastlines');
        }

        // Controle de velocidade - velocidade inicial 10x para visualização clara
        let simulationSpeed = 10.0;  // Velocidade padrao (viagem completa em ~12 segundos)
        let isPaused = false;

        // Chi-squared para niveis de confianca (2 DOF)
        const CHI2 = { 0.68: 2.30, 0.90: 4.61, 0.95: 5.99, 0.99: 9.21 };

        // ================================================================
        // FUNCOES DE UI - PAINEIS E VELOCIDADE
        // ================================================================

        // Toggle minimizacao de painel
        function togglePanel(panelId) {
            const panel = document.getElementById(panelId);
            if (panel) {
                panel.classList.toggle('minimized');
                const btn = panel.querySelector('.minimize-btn');
                if (btn) {
                    btn.textContent = panel.classList.contains('minimized') ? '+' : '_';
                }
            }
        }

        // Definir velocidade
        function setSpeed(speed) {
            simulationSpeed = speed;
            document.getElementById('speed-value').textContent = speed + 'x';
            document.getElementById('speed-slider').value = Math.min(speed, 200);

            // Atualizar botoes ativos
            document.querySelectorAll('#speed-control .speed-btn:not(#pause-btn)').forEach(btn => {
                btn.classList.remove('active');
                if (btn.textContent === speed + 'x') {
                    btn.classList.add('active');
                }
            });
        }

        // Definir velocidade pelo slider
        function setSpeedFromSlider(value) {
            const speed = parseInt(value);
            simulationSpeed = speed;
            document.getElementById('speed-value').textContent = speed + 'x';

            // Remover classe ativa de todos os botoes (exceto pause)
            document.querySelectorAll('#speed-control .speed-btn:not(#pause-btn)').forEach(btn => {
                btn.classList.remove('active');
            });
        }

        // Toggle pausa
        function togglePause() {
            isPaused = !isPaused;
            const btn = document.getElementById('pause-btn');
            btn.textContent = isPaused ? '▶' : '⏸';
            btn.style.background = isPaused ? '#238636' : '';
        }

        // Idade maxima padrao para a timeline (sera atualizada quando iniciar jornada)
        let previewMaxAge = 541; // Limite do Fanerozoico
        let selectionModeActive = false; // Modo de selecao de pontos

        // Funcao para ativar/desativar modo de selecao
        function setSelectionMode(active) {
            selectionModeActive = active;
            document.body.style.cursor = active ? 'crosshair' : 'default';
        }
        window.setSelectionMode = setSelectionMode;

        // Funcao para atualizar preview na timeline quando seleciona microfossil
        function previewSpecimenAge(age, periodCode, eraCode, specimenName) {
            // Atualizar label de idade maxima
            document.getElementById('max-age-label').textContent = previewMaxAge.toFixed(0) + ' Ma';

            // Marcador atual (tempo presente - cyan) - ja existe no HTML
            const currentMarker = document.getElementById('timeline-current-marker');
            if (currentMarker) {
                currentMarker.style.display = 'block';
            }

            // Marcador de destino (laranja) - ja existe no HTML
            const targetMarker = document.getElementById('timeline-target-marker');
            if (targetMarker) {
                // Calcular posicao do marcador de destino (0% = hoje, 100% = idade maxima)
                const targetPosition = Math.min(age / previewMaxAge, 1.0);
                targetMarker.style.left = (targetPosition * 100) + '%';
                targetMarker.style.display = 'block';
                targetMarker.setAttribute('data-age', age.toFixed(0) + ' Ma');
            }

            // Destacar o periodo correspondente na timeline
            const periodMap = {
                'PLE': '.period-quaternary',
                'PLI': '.period-neogene',
                'MIO': '.period-neogene',
                'OLI': '.period-paleogene',
                'EOC': '.period-paleogene',
                'PAL': '.period-paleogene',
                'CRE': '.period-cretaceous',
                'JUR': '.period-jurassic',
                'TRI': '.period-triassic',
                'PER': '.period-permian',
                'CAR': '.period-carboniferous',
                'DEV': '.period-devonian',
                'SIL': '.period-silurian',
                'ORD': '.period-ordovician',
                'CAM': '.period-cambrian'
            };

            // Remover destaque anterior
            document.querySelectorAll('.period-segment').forEach(el => {
                el.style.outline = 'none';
                el.style.zIndex = '1';
            });

            // Destacar periodo selecionado
            const periodSelector = periodMap[periodCode];
            if (periodSelector) {
                const periodEl = document.querySelector(periodSelector);
                if (periodEl) {
                    periodEl.style.outline = '3px solid #fff';
                    periodEl.style.zIndex = '5';
                }
            }

            // Mostrar tooltip com info do especime
            const tooltip = document.getElementById('coord-tooltip');
            tooltip.classList.remove('hidden');
            tooltip.innerHTML = `<strong>${specimenName}</strong><br>${age} Ma - ${getPeriodName(age)}`;

            // Posicionar tooltip acima do marcador de destino
            const timelineBar = document.getElementById('timeline-bar');
            const rect = timelineBar.getBoundingClientRect();
            const targetPosition = Math.min(age / previewMaxAge, 1.0);
            tooltip.style.left = (rect.left + targetPosition * rect.width - 50) + 'px';
            tooltip.style.top = (rect.top - 55) + 'px';

            // Ocultar tooltip apos 4 segundos
            setTimeout(() => {
                if (!isPlaying) tooltip.classList.add('hidden');
            }, 4000);
        }

        // Expor funcao globalmente para PyQt
        window.previewSpecimenAge = previewSpecimenAge;

        // Contornos continentais DETALHADOS (lat, lon) - alta resolucao
        // Cores distintas para cada placa tectonica
        const PLATE_COLORS = {
            southAmerica: '#00E676',   // Verde brilhante
            africa: '#FF6D00',         // Laranja forte
            australia: '#FFEA00',      // Amarelo
            india: '#E91E63',          // Rosa/Magenta
            europe: '#2979FF',         // Azul
            northAmerica: '#AA00FF',   // Roxo
            antarctica: '#00BCD4',     // Cyan
            asia: '#FF1744'            // Vermelho
        };

        const CONTINENTS = {
            southAmerica: {
                color: PLATE_COLORS.southAmerica,
                outline: [
                    // Costa norte (Venezuela, Guianas)
                    [12.5,-71.5],[12.2,-72.5],[11.8,-71.8],[11.0,-74.2],[10.5,-75.5],
                    [11.2,-73.5],[12.4,-71.3],[12.0,-70.0],[10.7,-67.1],[10.5,-66.9],
                    [10.7,-63.8],[9.3,-60.0],[8.5,-60.0],[7.0,-58.5],[6.0,-57.5],
                    [5.8,-55.5],[4.5,-52.5],[4.2,-51.8],[2.8,-50.0],[1.4,-49.5],
                    // Costa nordeste Brasil
                    [0.0,-50.0],[-1.0,-48.5],[-2.5,-44.2],[-2.8,-41.8],[-5.0,-35.5],
                    [-5.5,-35.2],[-7.0,-34.8],[-8.5,-35.0],[-9.5,-35.5],[-10.5,-36.5],
                    // Costa leste Brasil
                    [-13.0,-38.5],[-15.5,-39.0],[-18.0,-39.5],[-20.0,-40.0],[-21.0,-41.0],
                    [-22.5,-42.0],[-23.0,-44.5],[-23.5,-45.5],[-24.5,-47.0],[-25.5,-48.5],
                    [-26.0,-48.7],[-27.5,-48.6],[-28.5,-49.0],[-29.0,-49.5],
                    // Costa sul Brasil, Uruguai, Argentina
                    [-30.0,-51.0],[-31.5,-51.8],[-33.0,-53.5],[-34.0,-54.0],[-34.9,-56.5],
                    [-36.0,-56.8],[-38.0,-57.5],[-39.5,-62.0],[-41.0,-63.0],[-42.5,-64.5],
                    [-45.0,-65.5],[-47.0,-66.0],[-49.0,-67.5],[-51.5,-69.0],[-52.5,-68.5],
                    // Tierra del Fuego
                    [-53.5,-68.0],[-54.5,-67.0],[-55.0,-66.5],[-55.5,-67.5],[-54.8,-68.5],
                    [-54.5,-70.0],[-54.0,-71.5],[-52.5,-72.5],[-52.0,-73.5],
                    // Costa oeste Chile
                    [-50.0,-75.0],[-47.0,-75.5],[-45.0,-74.0],[-43.5,-73.5],[-42.0,-73.0],
                    [-40.0,-73.5],[-38.5,-73.2],[-37.0,-73.5],[-35.5,-72.5],[-33.5,-71.8],
                    [-32.0,-71.5],[-30.5,-71.5],[-29.0,-71.3],[-27.5,-71.0],[-26.0,-70.5],
                    [-24.5,-70.5],[-23.5,-70.3],[-22.0,-70.0],[-20.0,-70.2],[-18.5,-70.5],
                    // Costa Peru, Ecuador, Colombia
                    [-17.0,-72.0],[-15.0,-75.0],[-13.5,-76.2],[-12.0,-77.0],[-10.0,-78.5],
                    [-7.0,-80.5],[-5.0,-81.0],[-4.0,-81.0],[-2.5,-80.5],[-1.0,-80.0],
                    [0.0,-80.0],[1.0,-79.0],[2.0,-77.8],[4.0,-77.5],[6.5,-77.5],
                    [8.0,-77.0],[9.0,-76.0],[10.0,-75.5],[11.0,-74.5],[12.5,-71.5]
                ],
                drift: { vLat: 0.03, vLon: 0.08 }
            },
            africa: {
                color: PLATE_COLORS.africa,
                outline: [
                    // Costa norte (Marrocos ao Egito)
                    [35.8,-5.9],[35.2,-2.0],[37.0,0.0],[37.5,3.0],[37.0,6.0],
                    [36.8,8.5],[37.3,10.0],[35.5,11.0],[33.0,11.5],[32.0,12.5],
                    [31.5,15.0],[31.0,18.0],[31.5,25.0],[31.0,27.0],[31.5,30.0],
                    [31.2,32.0],[30.0,32.5],[29.5,32.8],
                    // Canal de Suez e Mar Vermelho
                    [30.0,32.5],[29.0,33.0],[27.5,34.0],[26.0,34.5],[24.5,35.0],
                    [22.5,36.5],[20.0,37.5],[18.0,38.5],[15.5,40.0],[14.0,42.5],
                    [12.5,43.5],[11.5,43.0],[11.0,45.0],
                    // Corno de Africa
                    [11.5,47.0],[11.8,49.0],[10.5,51.0],[8.0,50.0],[5.0,48.0],
                    [2.5,45.5],[1.5,44.0],[0.0,42.5],[-1.5,41.5],[-3.0,40.5],
                    // Costa leste Africa
                    [-4.5,39.8],[-6.0,39.5],[-8.0,39.5],[-10.5,40.5],[-15.0,40.5],
                    [-17.5,38.0],[-20.0,35.0],[-23.0,35.5],[-25.5,33.0],
                    // Africa do Sul
                    [-27.0,32.8],[-29.0,32.0],[-31.0,30.0],[-33.0,28.0],[-34.0,26.0],
                    [-34.5,22.0],[-34.8,20.0],[-34.5,18.5],[-33.5,18.0],[-32.5,18.0],
                    [-31.0,17.5],[-29.5,17.0],[-28.5,16.5],
                    // Costa oeste Africa
                    [-26.0,15.0],[-23.0,14.5],[-20.0,13.0],[-17.5,12.0],[-15.5,12.0],
                    [-13.5,12.5],[-11.5,13.5],[-9.0,13.0],[-7.0,12.5],[-5.0,12.0],
                    [-4.0,11.5],[-2.5,10.0],[-1.0,9.5],[0.5,9.5],[2.0,9.0],
                    [3.5,7.0],[4.5,5.5],[5.0,4.0],[4.8,2.5],[5.5,1.0],
                    [6.2,1.0],[6.5,2.5],[4.5,5.5],[5.0,7.0],[6.0,5.0],
                    [6.5,2.5],[7.0,1.5],[7.5,-2.0],[8.0,-5.0],[9.0,-6.0],
                    [10.5,-7.5],[12.0,-8.5],[14.0,-10.0],[15.0,-12.5],[14.8,-13.5],
                    // Golfo da Guine e Senegal
                    [14.0,-15.5],[13.0,-16.5],[12.5,-17.0],[14.5,-17.5],[16.0,-16.5],
                    [18.0,-16.0],[20.5,-17.0],[21.0,-17.0],[23.5,-16.0],[25.5,-15.0],
                    [27.5,-13.0],[29.0,-10.0],[32.0,-9.0],[33.5,-8.0],[35.8,-5.9]
                ],
                drift: { vLat: 0.02, vLon: -0.06 }
            },
            australia: {
                color: PLATE_COLORS.australia,
                outline: [
                    // Norte Australia
                    [-10.5,142.5],[-10.8,141.5],[-12.0,141.8],[-12.5,141.5],
                    [-14.0,141.5],[-14.5,141.8],[-15.0,141.0],[-16.0,139.5],
                    [-16.5,139.0],[-17.0,140.5],[-17.5,141.0],[-16.5,141.5],
                    [-15.5,145.0],[-14.8,145.5],[-14.5,143.5],[-13.5,143.8],
                    [-12.5,143.5],[-11.5,142.5],[-11.0,142.8],[-10.5,142.5],
                    // Costa nordeste
                    [-10.8,142.5],[-12.5,143.2],[-14.0,143.8],[-15.0,145.2],
                    [-16.5,145.8],[-18.0,146.2],[-19.5,147.5],[-21.0,149.0],
                    [-22.5,150.5],[-24.0,152.0],[-25.0,153.0],[-26.5,153.2],
                    // Costa leste
                    [-27.5,153.5],[-28.5,153.8],[-30.0,153.2],[-31.5,152.8],
                    [-33.0,152.0],[-34.5,151.0],[-36.0,150.0],[-37.5,149.8],
                    [-38.0,148.0],[-38.5,147.5],[-39.0,146.5],
                    // Sul e sudeste
                    [-38.8,146.0],[-38.5,145.5],[-38.8,144.5],[-38.2,144.8],
                    [-37.5,140.0],[-36.0,137.0],[-35.5,136.5],[-35.0,136.8],
                    [-34.5,136.0],[-34.8,135.5],[-35.5,134.5],[-34.0,132.5],
                    // Costa sul
                    [-33.5,130.0],[-32.5,128.0],[-32.0,126.0],[-31.5,124.5],
                    [-32.0,122.0],[-33.5,120.0],[-34.5,118.5],[-35.0,117.0],
                    [-34.0,115.5],[-32.0,115.5],[-30.5,115.0],
                    // Costa oeste
                    [-29.0,114.8],[-27.5,113.5],[-26.0,113.2],[-24.5,113.5],
                    [-23.0,114.0],[-22.0,114.0],[-21.0,115.5],[-20.0,118.5],
                    [-19.0,121.0],[-17.5,122.0],[-16.0,123.0],[-15.0,124.5],
                    [-14.5,125.8],[-14.0,126.5],[-13.5,128.0],[-12.5,130.0],
                    [-12.0,131.0],[-11.5,132.0],[-11.2,133.0],[-12.0,135.5],
                    [-12.5,136.5],[-12.0,137.0],[-11.0,138.5],[-10.5,140.0],
                    [-10.5,142.5]
                ],
                drift: { vLat: -0.08, vLon: -0.04 }
            },
            india: {
                color: PLATE_COLORS.india,
                outline: [
                    // Norte (fronteira Himalaia)
                    [35.5,74.0],[35.0,75.5],[34.5,77.0],[34.0,78.5],[33.0,79.0],
                    [32.0,79.5],[30.5,81.0],[29.5,83.0],[28.5,84.5],[28.0,86.0],
                    [27.5,88.0],[27.0,89.5],[27.5,91.5],[28.0,93.5],[28.5,96.0],
                    // Nordeste
                    [27.5,97.0],[26.0,96.5],[25.0,95.0],[24.0,94.5],[23.5,94.0],
                    [22.5,93.5],[22.0,92.5],[21.5,92.0],[21.0,92.5],
                    // Bangladesh e costa leste
                    [22.0,92.0],[22.5,91.5],[23.0,90.5],[23.5,89.0],[22.5,88.5],
                    [22.0,88.5],[21.5,87.5],[20.5,86.5],[19.5,85.0],[18.5,84.0],
                    [17.5,83.0],[16.5,82.5],[15.5,80.5],[14.5,80.0],[13.5,80.5],
                    // Costa sul
                    [12.5,80.0],[11.5,79.8],[10.5,79.5],[9.5,79.0],[8.5,78.5],
                    [8.0,77.8],[8.0,77.0],[8.5,76.5],[9.5,76.0],[10.0,76.5],
                    // Ponta sul e costa oeste
                    [9.0,77.5],[8.2,77.2],[7.5,77.5],[8.0,77.0],[8.5,76.5],
                    [9.5,76.0],[10.5,76.0],[11.5,75.8],[12.5,75.0],[13.5,74.8],
                    [14.5,74.5],[15.5,73.8],[16.5,73.5],[17.5,73.0],[18.5,73.0],
                    [19.5,72.8],[20.5,73.0],[21.5,72.5],[22.0,69.5],[22.5,69.0],
                    [23.0,68.5],[23.5,68.2],[24.0,68.5],[24.5,70.5],[25.0,71.5],
                    [25.5,71.0],[26.5,70.0],[28.0,70.5],[29.5,71.5],[30.5,73.5],
                    [31.5,74.5],[32.5,75.0],[33.5,74.5],[35.0,74.0],[35.5,74.0]
                ],
                drift: { vLat: -0.15, vLon: 0.02 }
            },
            europe: {
                color: PLATE_COLORS.europe,
                outline: [
                    // Peninsula Iberica
                    [36.0,-5.5],[36.5,-6.0],[37.0,-8.5],[38.5,-9.5],[40.0,-8.8],
                    [42.0,-8.8],[43.5,-8.2],[43.8,-7.5],[43.5,-6.0],[43.8,-3.5],
                    [43.5,-1.8],[43.0,0.0],[42.5,3.0],
                    // Costa francesa
                    [42.5,3.2],[43.0,4.5],[43.2,5.0],[43.0,6.5],[43.8,7.5],
                    [44.0,8.0],[44.5,8.5],[44.0,9.5],[43.5,10.0],[42.5,10.5],
                    [42.0,11.5],[41.5,12.5],[41.0,13.0],[40.5,14.0],
                    // Italia
                    [40.8,14.5],[40.5,15.5],[40.0,16.0],[39.0,17.0],[38.0,16.0],
                    [37.5,15.5],[38.0,15.0],[38.5,16.0],[39.5,16.5],[40.0,18.5],
                    [41.0,17.0],[41.5,16.0],[42.0,15.0],[42.5,14.0],[44.0,12.5],
                    [44.5,12.0],[45.5,13.5],[45.8,13.8],
                    // Balcas e Grecia
                    [46.0,14.5],[45.5,15.0],[45.0,15.5],[44.5,16.0],[44.0,17.0],
                    [43.0,17.5],[42.5,18.5],[42.0,19.5],[41.0,19.5],[40.5,20.0],
                    [39.5,20.0],[38.5,21.0],[38.0,23.5],[37.5,24.0],[36.5,23.0],
                    [36.0,23.0],[35.5,24.0],[35.0,25.5],[35.5,27.0],[36.5,28.0],
                    // Turquia costa sul
                    [36.8,29.0],[36.5,30.0],[36.0,32.0],[36.5,34.0],[36.8,35.5],
                    [37.0,36.0],[36.5,36.0],[36.2,35.8],
                    // Mar Negro e norte
                    [41.0,29.0],[41.5,28.5],[42.0,28.0],[43.0,28.0],[43.5,28.5],
                    [44.0,29.0],[45.0,30.0],[45.5,30.5],[46.0,31.0],[46.5,32.0],
                    [46.0,33.5],[46.0,35.0],[47.0,37.5],[47.5,39.5],[48.0,40.0],
                    // Russia costa norte
                    [47.0,42.0],[46.0,43.0],[45.5,47.0],[46.5,50.0],[47.0,52.0],
                    [47.5,53.0],[50.0,54.0],[53.0,55.0],[55.0,55.0],[56.5,54.0],
                    [58.0,53.0],[60.0,50.0],[62.0,52.0],[64.0,55.0],[66.0,57.0],
                    [68.0,55.0],[69.5,60.0],[70.0,58.0],[70.5,55.0],[71.0,52.0],
                    // Escandinavia
                    [70.5,28.0],[71.0,25.0],[70.0,20.0],[68.0,18.0],[66.5,15.0],
                    [64.0,12.0],[62.0,10.0],[60.0,10.5],[59.0,10.0],[58.5,8.0],
                    [58.0,7.0],[57.5,8.0],[56.5,8.5],[55.5,9.5],[55.0,10.5],
                    // Dinamarca e costa norte Europa
                    [54.5,10.0],[54.0,9.0],[54.5,8.5],[55.0,8.2],[55.5,8.0],
                    [54.5,7.5],[53.5,7.0],[53.0,6.5],[52.0,5.0],[51.5,4.0],
                    [51.0,3.5],[51.0,2.5],[51.5,1.5],[52.0,1.8],[52.5,1.5],
                    [53.0,0.5],[53.5,0.0],[54.0,-0.5],[54.5,-1.5],[55.0,-1.8],
                    // Gran Bretanha
                    [55.5,-2.0],[56.0,-3.0],[57.0,-2.0],[58.0,-3.5],[58.5,-5.0],
                    [57.5,-6.5],[56.5,-6.0],[55.5,-5.5],[54.5,-5.0],[54.0,-4.5],
                    [53.0,-4.0],[52.0,-4.5],[51.5,-5.0],[51.0,-4.5],[50.5,-3.5],
                    [50.0,-5.5],[50.0,-5.0],[50.5,-2.5],[51.0,-1.5],[50.8,-0.8],
                    // Canal da Mancha e Bretanha
                    [49.5,-1.0],[48.5,-4.5],[47.5,-2.8],[47.0,-2.0],[46.5,-1.8],
                    [46.0,-1.5],[45.5,-1.0],[44.5,-1.2],[43.5,-1.5],[43.0,-1.8],
                    [42.0,-3.0],[41.5,-3.0],[40.5,-3.5],[39.0,-4.0],[37.0,-5.0],
                    [36.0,-5.5]
                ],
                drift: { vLat: 0.01, vLon: -0.02 }
            },
            northAmerica: {
                color: PLATE_COLORS.northAmerica,
                outline: [
                    // Florida e costa leste
                    [25.0,-80.0],[26.0,-80.2],[27.0,-80.5],[28.5,-80.5],[30.0,-81.5],
                    [31.5,-81.2],[32.5,-79.5],[33.5,-78.0],[34.5,-76.5],[35.5,-75.5],
                    [36.5,-76.0],[37.0,-76.5],[37.5,-76.0],[38.5,-75.0],[39.0,-74.5],
                    [40.0,-74.0],[40.5,-73.8],[41.0,-72.0],[41.5,-70.5],[42.0,-70.0],
                    [43.0,-70.5],[44.0,-68.5],[44.8,-67.0],[45.0,-67.0],[45.5,-64.5],
                    // Canada Atlantico
                    [46.0,-60.0],[45.5,-61.5],[46.0,-63.5],[47.0,-61.0],[47.5,-59.0],
                    [48.5,-59.0],[49.0,-58.0],[49.5,-56.0],[50.0,-57.5],[51.5,-56.0],
                    [52.5,-56.0],[53.5,-57.0],[55.0,-59.5],[56.5,-61.0],[58.0,-62.5],
                    [59.5,-64.0],[60.5,-65.0],[62.0,-66.5],[63.5,-68.0],[65.0,-67.0],
                    [66.5,-62.0],[68.0,-63.5],[69.5,-68.0],[71.0,-72.5],[72.0,-78.0],
                    // Artico canadense
                    [73.0,-80.0],[74.0,-85.0],[75.0,-90.0],[74.5,-95.0],[73.5,-95.0],
                    [73.0,-97.0],[72.0,-96.0],[71.5,-95.0],[70.5,-92.0],[70.0,-90.0],
                    [70.0,-100.0],[71.5,-105.0],[73.0,-110.0],[74.0,-115.0],[75.0,-120.0],
                    [74.5,-125.0],[72.0,-125.0],[71.0,-130.0],[70.0,-140.0],[70.5,-145.0],
                    // Alaska
                    [71.0,-155.0],[70.5,-162.0],[69.5,-165.0],[68.5,-166.0],[67.0,-164.0],
                    [66.0,-165.0],[65.5,-168.0],[64.5,-165.0],[63.5,-162.0],[62.0,-163.0],
                    [60.0,-165.0],[59.0,-162.0],[58.0,-157.0],[56.5,-154.0],[55.5,-160.0],
                    [55.0,-162.0],[54.5,-164.0],[55.5,-161.0],[57.0,-157.0],[58.0,-152.0],
                    [58.5,-152.0],[59.0,-153.5],[59.5,-151.0],[60.0,-149.0],[60.5,-146.0],
                    [60.0,-143.0],[59.5,-140.0],[59.5,-137.0],[59.0,-136.0],[58.5,-135.0],
                    // Costa oeste Canada
                    [57.0,-132.0],[55.5,-130.0],[54.5,-130.5],[54.0,-133.0],[53.0,-132.0],
                    [52.0,-128.5],[51.0,-128.0],[50.5,-127.5],[49.5,-127.0],[49.0,-125.0],
                    [48.5,-124.5],[48.0,-123.5],[47.5,-122.5],
                    // Costa oeste EUA
                    [46.5,-124.0],[45.0,-124.0],[43.0,-124.5],[41.5,-124.2],[40.0,-124.5],
                    [38.5,-123.5],[37.5,-122.5],[36.5,-122.0],[35.0,-121.0],[34.0,-120.5],
                    [33.5,-118.5],[32.5,-117.2],[31.0,-116.0],[29.5,-114.5],[28.0,-114.0],
                    // Baja California e Golfo Mexico
                    [27.0,-113.0],[26.0,-112.0],[24.5,-111.5],[23.5,-110.0],[23.0,-109.5],
                    [22.5,-110.0],[24.0,-111.5],[26.0,-112.5],[28.0,-114.5],[30.0,-115.5],
                    [31.5,-117.0],[32.0,-117.2],[32.5,-115.0],[31.5,-113.0],[30.0,-110.0],
                    [28.0,-106.0],[26.0,-102.0],[24.0,-98.0],[22.0,-97.5],[20.5,-97.0],
                    [19.5,-96.0],[19.0,-95.5],[19.5,-94.5],[20.0,-92.0],[20.5,-90.5],
                    [21.5,-90.0],[21.0,-89.0],[20.0,-87.5],[21.5,-87.0],[23.0,-87.5],
                    // Costa golfo EUA
                    [25.0,-82.0],[26.5,-82.5],[28.0,-82.5],[29.0,-83.5],[30.0,-84.0],
                    [29.5,-85.5],[30.0,-87.0],[30.5,-88.0],[29.5,-89.0],[29.0,-89.5],
                    [29.5,-91.0],[29.0,-93.0],[28.5,-94.5],[29.0,-95.0],[29.5,-94.5],
                    [30.0,-94.0],[29.5,-95.5],[28.5,-96.5],[27.0,-97.5],[26.0,-97.5],
                    [25.5,-97.0],[25.0,-80.0]
                ],
                drift: { vLat: 0.01, vLon: 0.03 }
            },
            asia: {
                color: PLATE_COLORS.asia,
                outline: [
                    // Medio Oriente
                    [36.5,36.0],[35.5,40.0],[37.0,42.0],[38.0,44.0],[39.5,45.0],
                    [41.0,45.0],[42.0,48.0],[44.0,50.0],[46.0,52.0],[47.0,54.0],
                    // Asia Central
                    [48.0,55.0],[50.0,55.0],[52.0,58.0],[55.0,60.0],[57.0,62.0],
                    [60.0,65.0],[63.0,72.0],[66.0,75.0],[68.0,78.0],[70.0,82.0],
                    [72.0,90.0],[73.0,100.0],[74.0,110.0],[75.0,120.0],[76.0,135.0],
                    [75.0,145.0],[73.0,150.0],[72.0,155.0],[70.0,160.0],[68.5,165.0],
                    [67.0,170.0],[66.0,175.0],[65.5,180.0],
                    // Rusia Far East
                    [62.0,180.0],[60.0,170.0],[58.0,165.0],[55.0,162.0],[53.0,158.0],
                    [51.0,155.0],[50.0,155.5],[48.0,154.0],[46.5,153.0],[46.0,150.0],
                    [45.5,148.0],[45.0,145.0],[44.0,142.0],[43.0,140.0],
                    // Japao e Korea (simplificado)
                    [42.0,140.0],[40.0,140.0],[38.0,138.5],[35.5,140.0],[34.0,139.0],
                    [33.0,135.0],[32.5,131.0],[33.5,130.0],[35.0,129.0],[37.0,127.0],
                    [38.0,125.0],[39.0,125.5],[40.0,124.0],[41.0,123.0],
                    // China costa
                    [40.0,122.0],[39.0,121.5],[38.0,121.0],[36.0,120.5],[35.0,119.5],
                    [34.0,120.0],[32.0,122.0],[31.0,122.5],[30.0,122.5],[28.0,121.5],
                    [26.0,120.0],[25.0,119.0],[24.0,118.0],[23.0,117.5],[22.5,114.5],
                    [22.0,114.0],[21.5,110.5],[20.5,110.0],[19.0,109.5],[18.5,108.5],
                    // Sudeste Asiatico
                    [17.0,108.5],[14.0,109.5],[12.0,109.0],[10.5,108.5],[8.5,105.0],
                    [7.0,103.0],[5.5,103.5],[4.0,104.0],[3.0,103.5],[2.0,103.0],
                    [1.5,104.0],[1.0,104.5],[1.5,105.5],[3.0,106.5],[5.0,108.0],
                    [6.0,109.5],[7.0,110.0],[6.5,111.5],[5.5,115.0],[5.0,118.0],
                    [6.0,119.0],[7.0,117.0],[8.0,117.0],[9.5,118.5],[10.5,119.0],
                    // Filipinas e Taiwan (simplificado)
                    [12.0,120.0],[14.0,120.5],[16.0,120.0],[18.5,121.0],[20.0,122.0],
                    [22.0,121.0],[23.5,121.5],[25.0,121.5],[25.5,122.0],
                    // De volta ao continente
                    [8.0,100.0],[9.0,98.5],[10.0,98.0],[12.0,99.5],[13.5,100.5],
                    [16.0,100.5],[18.0,103.0],[20.0,104.0],[21.5,103.0],[23.0,102.5],
                    // Myanmar, Bangladesh
                    [24.0,97.5],[25.0,95.0],[26.0,93.0],[27.0,92.0],[28.0,95.0],
                    [27.5,97.5],[26.0,99.0],[24.0,98.5],[22.0,97.0],[20.0,96.0],
                    [18.0,95.0],[16.0,95.0],[15.0,97.5],[14.0,98.0],[12.0,99.0],
                    [10.0,98.5],[8.0,98.5],[7.0,99.5],[6.0,100.0],[4.0,100.5],
                    [2.5,101.0],[1.5,103.5],[1.0,103.0],[2.0,102.0],[4.0,100.0],
                    [6.0,98.0],[8.0,98.0],[10.0,98.0],[12.0,97.5],[14.0,96.0],
                    [16.0,94.5],[18.0,94.0],[20.0,92.5],[21.5,92.0],[21.0,89.0],
                    // Volta pelo sul da India ao Oriente Medio
                    [12.0,80.0],[8.0,77.0],[6.0,80.0],[5.0,80.0],[7.0,82.0],
                    [9.0,79.5],[11.0,80.0],[15.0,80.0],[18.0,83.5],[19.0,85.0],
                    [20.0,87.0],[21.5,89.0],[22.0,89.5],[23.0,89.0],[24.0,88.5],
                    [25.0,88.0],[26.0,88.5],[27.0,88.0],[27.5,85.5],[28.0,84.0],
                    [28.5,82.0],[29.0,80.0],[30.0,78.0],[31.5,76.0],[33.0,74.0],
                    [35.0,72.0],[36.0,70.0],[35.5,68.0],[33.0,66.0],[30.0,66.0],
                    [27.0,63.5],[25.5,61.5],[25.0,58.5],[25.5,57.0],[26.5,56.5],
                    [27.0,56.0],[26.5,54.0],[25.0,52.0],[24.0,51.5],[24.5,54.0],
                    [23.0,55.5],[22.0,59.0],[20.0,58.0],[18.0,57.0],[16.5,53.0],
                    [14.5,48.5],[13.0,45.0],[12.5,44.0],[13.0,43.5],[15.0,42.5],
                    [19.0,41.0],[21.0,40.0],[24.0,38.0],[26.0,35.5],[28.0,34.5],
                    [30.0,33.0],[32.0,35.0],[34.0,36.0],[36.5,36.0]
                ],
                drift: { vLat: 0.01, vLon: -0.01 }
            },
            antarctica: {
                color: PLATE_COLORS.antarctica,
                outline: [
                    [-65.0,-55.0],[-66.0,-58.0],[-67.5,-60.0],[-68.5,-62.5],[-70.0,-60.0],
                    [-71.5,-58.0],[-72.5,-55.0],[-74.0,-50.0],[-75.0,-45.0],[-74.5,-40.0],
                    [-73.5,-35.0],[-72.0,-30.0],[-71.0,-25.0],[-70.0,-20.0],[-69.5,-15.0],
                    [-69.0,-10.0],[-68.5,-5.0],[-68.0,0.0],[-67.5,5.0],[-67.0,10.0],
                    [-67.0,15.0],[-67.5,20.0],[-68.0,25.0],[-68.5,30.0],[-69.0,35.0],
                    [-69.5,40.0],[-70.0,45.0],[-70.5,50.0],[-71.0,55.0],[-72.0,60.0],
                    [-73.0,65.0],[-74.0,70.0],[-75.0,75.0],[-76.0,80.0],[-77.0,85.0],
                    [-78.0,90.0],[-78.5,95.0],[-78.0,100.0],[-77.0,105.0],[-76.0,110.0],
                    [-75.0,115.0],[-74.5,120.0],[-74.0,125.0],[-73.5,130.0],[-73.0,135.0],
                    [-72.5,140.0],[-72.0,145.0],[-71.5,150.0],[-71.0,155.0],[-70.5,160.0],
                    [-70.0,165.0],[-69.5,170.0],[-69.0,175.0],[-68.5,180.0],
                    [-68.5,-175.0],[-69.0,-170.0],[-69.5,-165.0],[-70.0,-160.0],
                    [-70.5,-155.0],[-71.0,-150.0],[-71.5,-145.0],[-72.0,-140.0],
                    [-72.5,-135.0],[-73.0,-130.0],[-73.5,-125.0],[-74.0,-120.0],
                    [-74.5,-115.0],[-75.0,-110.0],[-75.5,-105.0],[-76.0,-100.0],
                    [-76.5,-95.0],[-77.0,-90.0],[-77.5,-85.0],[-78.0,-80.0],
                    [-77.5,-75.0],[-76.5,-70.0],[-75.0,-65.0],[-73.0,-62.0],
                    [-71.0,-60.0],[-69.0,-58.0],[-67.0,-56.0],[-65.0,-55.0]
                ],
                drift: { vLat: 0.01, vLon: 0 }
            }
        };

        // ================================================================
        // ILHAS IMPORTANTES
        // ================================================================
        const ISLANDS = {
            // Caribe
            cuba: {
                color: '#00E676',
                outline: [
                    [23.2,-84.9],[23.0,-83.5],[22.5,-82.5],[22.0,-81.0],[21.5,-79.5],
                    [21.0,-78.0],[20.5,-77.0],[20.0,-75.5],[20.2,-74.5],[20.7,-74.2],
                    [21.5,-75.5],[22.0,-77.0],[22.5,-78.5],[23.0,-80.0],[23.3,-81.5],
                    [23.5,-82.5],[23.2,-84.0],[23.2,-84.9]
                ]
            },
            hispaniola: {
                color: '#00E676',
                outline: [
                    [19.9,-74.5],[19.5,-73.0],[19.0,-71.5],[18.5,-70.0],[18.2,-69.0],
                    [18.5,-68.5],[19.0,-69.5],[19.5,-70.5],[20.0,-72.0],[20.0,-73.5],
                    [19.9,-74.5]
                ]
            },
            jamaica: {
                color: '#00E676',
                outline: [
                    [18.5,-78.5],[18.2,-77.5],[18.0,-76.5],[18.2,-76.2],[18.5,-77.0],
                    [18.5,-78.0],[18.5,-78.5]
                ]
            },
            puertoRico: {
                color: '#00E676',
                outline: [
                    [18.5,-67.5],[18.3,-66.5],[18.0,-65.8],[18.3,-65.5],[18.5,-66.0],
                    [18.5,-67.0],[18.5,-67.5]
                ]
            },
            // Japao
            japanHonshu: {
                color: '#FF1744',
                outline: [
                    [41.5,140.0],[40.5,140.5],[39.5,140.0],[38.5,139.5],[37.5,139.0],
                    [36.5,139.5],[35.5,140.0],[35.0,139.5],[34.5,138.5],[34.0,137.0],
                    [34.5,135.5],[35.0,135.0],[35.5,134.0],[36.0,133.5],[36.5,133.0],
                    [37.0,134.0],[37.5,135.0],[38.0,136.0],[38.5,137.0],[39.0,138.0],
                    [40.0,139.0],[41.0,140.0],[41.5,140.0]
                ]
            },
            japanHokkaido: {
                color: '#FF1744',
                outline: [
                    [45.5,141.5],[44.5,141.0],[43.5,140.5],[43.0,141.0],[42.5,142.0],
                    [42.0,143.0],[42.5,144.5],[43.5,145.5],[44.5,145.0],[45.5,143.0],
                    [45.5,141.5]
                ]
            },
            japanKyushu: {
                color: '#FF1744',
                outline: [
                    [33.8,130.0],[33.5,130.5],[33.0,131.0],[32.5,131.5],[32.0,131.0],
                    [31.5,130.5],[31.0,130.5],[31.5,129.5],[32.5,129.5],[33.5,129.5],
                    [33.8,130.0]
                ]
            },
            // Indonesia
            sumatra: {
                color: '#FF1744',
                outline: [
                    [5.5,95.5],[4.0,97.0],[2.0,99.0],[0.0,101.0],[-2.0,103.5],
                    [-4.0,104.5],[-5.5,105.5],[-5.5,104.0],[-4.0,102.0],[-2.0,100.0],
                    [0.0,98.5],[2.0,96.5],[4.0,95.5],[5.5,95.5]
                ]
            },
            borneo: {
                color: '#FF1744',
                outline: [
                    [7.0,117.0],[6.0,118.0],[4.5,118.5],[2.5,118.0],[1.0,117.5],
                    [0.0,117.0],[-1.5,116.0],[-3.0,115.0],[-3.5,114.0],[-2.5,111.5],
                    [-1.0,110.0],[1.0,109.5],[3.0,110.0],[5.0,112.0],[6.0,114.0],
                    [7.0,116.0],[7.0,117.0]
                ]
            },
            java: {
                color: '#FF1744',
                outline: [
                    [-6.0,105.5],[-6.5,107.0],[-7.0,108.5],[-7.5,110.0],[-8.0,112.0],
                    [-8.5,114.0],[-8.0,114.5],[-7.5,112.5],[-7.0,110.5],[-6.5,108.5],
                    [-6.0,106.5],[-5.8,105.5],[-6.0,105.5]
                ]
            },
            // Filipinas
            luzon: {
                color: '#FF1744',
                outline: [
                    [18.5,120.5],[17.5,121.5],[16.0,121.0],[15.0,120.5],[14.0,121.0],
                    [13.5,122.0],[14.0,123.0],[15.0,122.5],[16.5,121.5],[18.0,121.0],
                    [18.5,120.5]
                ]
            },
            mindanao: {
                color: '#FF1744',
                outline: [
                    [9.5,125.5],[8.5,126.5],[7.0,126.0],[6.0,125.5],[6.0,124.0],
                    [7.0,123.5],[8.0,124.0],[9.0,125.0],[9.5,125.5]
                ]
            },
            // Madagascar
            madagascar: {
                color: '#FF6D00',
                outline: [
                    [-12.0,49.5],[-14.0,48.0],[-16.0,46.5],[-18.0,45.0],[-20.0,44.5],
                    [-22.0,44.0],[-24.0,44.5],[-25.5,46.0],[-24.0,47.5],[-22.0,48.0],
                    [-20.0,48.5],[-18.0,49.5],[-16.0,50.0],[-14.0,50.0],[-12.0,49.5]
                ]
            },
            // Nova Zelandia
            nzNorth: {
                color: '#FFEA00',
                outline: [
                    [-34.5,173.0],[-36.0,174.5],[-37.5,176.0],[-39.0,177.5],[-41.0,175.5],
                    [-39.5,174.0],[-38.0,174.5],[-36.5,174.0],[-35.0,173.5],[-34.5,173.0]
                ]
            },
            nzSouth: {
                color: '#FFEA00',
                outline: [
                    [-41.0,173.5],[-42.5,171.5],[-44.0,169.0],[-45.5,167.0],[-46.5,168.5],
                    [-45.5,170.5],[-44.0,172.0],[-42.5,173.5],[-41.0,174.0],[-41.0,173.5]
                ]
            },
            // Gra-Bretanha e Irlanda
            graBretanha: {
                color: '#2979FF',
                outline: [
                    [58.5,-3.0],[57.5,-5.5],[56.0,-5.5],[55.0,-5.0],[54.0,-3.0],
                    [53.5,-3.5],[52.5,-4.0],[51.5,-5.0],[50.5,-4.0],[50.0,-2.0],
                    [50.5,-1.0],[51.0,1.0],[52.0,1.5],[53.0,0.5],[54.0,-0.5],
                    [55.5,-1.5],[57.0,-2.0],[58.5,-3.0]
                ]
            },
            irlanda: {
                color: '#2979FF',
                outline: [
                    [55.5,-6.0],[54.5,-8.0],[53.5,-10.0],[52.5,-10.5],[51.5,-10.0],
                    [51.5,-8.5],[52.0,-6.5],[53.0,-6.0],[54.0,-6.5],[55.0,-7.5],
                    [55.5,-6.0]
                ]
            },
            // Islandia
            islandia: {
                color: '#2979FF',
                outline: [
                    [66.5,-18.0],[65.5,-20.0],[64.5,-22.0],[64.0,-23.0],[64.0,-21.0],
                    [64.5,-18.5],[65.5,-15.0],[66.0,-14.0],[66.5,-16.0],[66.5,-18.0]
                ]
            },
            // Sri Lanka
            sriLanka: {
                color: '#E91E63',
                outline: [
                    [9.8,80.0],[8.5,81.5],[7.0,81.5],[6.0,80.5],[6.5,79.8],
                    [8.0,79.8],[9.5,80.0],[9.8,80.0]
                ]
            },
            // Taiwan
            taiwan: {
                color: '#FF1744',
                outline: [
                    [25.3,121.5],[24.5,121.8],[23.5,121.5],[22.5,120.5],[22.0,120.5],
                    [22.5,120.0],[23.5,120.0],[24.5,120.5],[25.3,121.5]
                ]
            },
            // Nova Guine (Papua)
            novaGuine: {
                color: '#FF6D00',
                outline: [
                    [-2.5,141.0],[-3.5,142.0],[-4.5,144.0],[-5.5,145.5],[-6.0,147.0],
                    [-6.5,148.0],[-7.0,147.5],[-8.0,146.5],[-9.0,147.0],[-10.0,148.0],
                    [-10.5,150.0],[-10.0,151.0],[-8.5,149.0],[-7.0,148.5],[-6.0,149.0],
                    [-5.0,150.0],[-4.0,151.5],[-3.0,151.0],[-2.5,150.0],[-3.0,148.0],
                    [-4.0,145.0],[-3.5,143.0],[-2.5,141.0]
                ]
            },
            // Crimeia
            crimeia: {
                color: '#2979FF',
                outline: [
                    [46.2,33.5],[45.5,32.5],[45.0,33.0],[44.5,33.5],[44.4,34.0],
                    [44.6,34.5],[45.0,35.0],[45.3,35.5],[45.5,36.0],[45.8,35.5],
                    [46.0,35.0],[46.2,34.0],[46.2,33.5]
                ]
            },
            // Sicilia
            sicilia: {
                color: '#00E676',
                outline: [
                    [38.3,12.5],[38.0,13.0],[37.5,13.5],[37.0,14.5],[37.0,15.0],
                    [37.5,15.2],[38.0,15.5],[38.2,15.0],[38.3,14.0],[38.3,13.0],
                    [38.3,12.5]
                ]
            },
            // Sardenha
            sardenha: {
                color: '#00E676',
                outline: [
                    [41.2,9.0],[40.5,9.5],[40.0,9.5],[39.0,9.0],[39.0,8.5],
                    [39.5,8.3],[40.0,8.5],[40.5,8.3],[41.0,8.5],[41.2,9.0]
                ]
            },
            // Corsega
            corsega: {
                color: '#00E676',
                outline: [
                    [43.0,9.4],[42.5,9.5],[42.0,9.3],[41.5,9.2],[41.5,8.8],
                    [42.0,8.6],[42.5,8.7],[43.0,9.0],[43.0,9.4]
                ]
            },
            // Baleares (Mallorca)
            mallorca: {
                color: '#00E676',
                outline: [
                    [39.8,2.8],[39.5,3.2],[39.3,3.4],[39.4,3.0],[39.6,2.6],
                    [39.8,2.8]
                ]
            },
            // Chipre
            chipre: {
                color: '#FFEA00',
                outline: [
                    [35.6,32.5],[35.3,33.5],[35.0,34.0],[34.7,33.5],[34.6,33.0],
                    [34.8,32.5],[35.2,32.3],[35.6,32.5]
                ]
            },
            // Creta
            creta: {
                color: '#FFEA00',
                outline: [
                    [35.5,23.5],[35.2,24.5],[35.0,25.5],[35.2,26.0],[35.5,25.5],
                    [35.4,24.5],[35.5,23.5]
                ]
            },
            // Hawaii (Big Island)
            hawaii: {
                color: '#FF1744',
                outline: [
                    [20.0,-155.0],[19.5,-155.5],[19.0,-156.0],[19.5,-156.0],
                    [20.0,-155.5],[20.0,-155.0]
                ]
            },
            // Sulawesi (Celebes)
            sulawesi: {
                color: '#FF1744',
                outline: [
                    [1.5,120.5],[0.5,121.5],[-1.0,122.0],[-2.0,121.0],[-3.0,120.5],
                    [-4.5,122.0],[-5.5,120.5],[-4.5,119.5],[-3.0,119.0],[-2.0,120.0],
                    [-0.5,120.0],[0.5,120.5],[1.5,120.5]
                ]
            },
            // Hainan
            hainan: {
                color: '#FF1744',
                outline: [
                    [20.0,110.0],[19.5,110.5],[19.0,110.5],[18.5,109.5],[18.5,108.7],
                    [19.0,108.7],[19.5,109.5],[20.0,110.0]
                ]
            },
            // Sakhalin
            sakhalin: {
                color: '#FF1744',
                outline: [
                    [54.0,142.5],[52.0,141.5],[50.0,143.0],[48.0,144.0],[46.5,143.5],
                    [46.0,142.5],[47.0,142.0],[49.0,142.0],[51.0,143.0],[53.0,143.0],
                    [54.0,142.5]
                ]
            },
            // Groelandia (parte sul visivel)
            groenlandiaSul: {
                color: '#B0BEC5',
                outline: [
                    [60.0,-43.0],[61.0,-46.0],[62.0,-49.0],[64.0,-52.0],[66.0,-53.0],
                    [68.0,-52.0],[70.0,-50.0],[72.0,-46.0],[74.0,-42.0],[76.0,-38.0],
                    [78.0,-35.0],[80.0,-30.0],[82.0,-25.0],[83.0,-30.0],[82.0,-40.0],
                    [80.0,-50.0],[78.0,-55.0],[75.0,-58.0],[72.0,-56.0],[70.0,-54.0],
                    [68.0,-55.0],[65.0,-52.0],[62.0,-48.0],[60.0,-45.0],[60.0,-43.0]
                ]
            }
        };

        // ================================================================
        // ESTADO GLOBAL
        // ================================================================

        let scene, camera, renderer, controls;
        let globe, presentMarker3D, paleoMarker3D, trajectoryLine3D, uncertaintyMesh3D;
        let canvas2D, ctx2D;
        let currentView = '3d';
        let journeyData = null;
        let trajectoryPoints = [];
        let currentProgress = 0;
        let isPlaying = false;
        let currentAge = 0;

        // Coordenadas originais (onde o fossil foi encontrado HOJE) - FIXAS
        let originalLat = 0;
        let originalLon = 0;

        // Posição reconstruída atual (onde o ponto ESTAVA no passado)
        let currentReconstructedPos = null;
        let lastReconstructedAge = -1;
        let isReconstructingPoint = false;

        // Ponto selecionado pelo usuario no mapa
        let selectedPoint = null;


        // ================================================================
        // FUNCOES DE CONVERSAO
        // ================================================================

        function latLonToVector3(lat, lon, radius) {
            const phi = (90 - lat) * Math.PI / 180;
            const theta = (lon + 180) * Math.PI / 180;
            return new THREE.Vector3(
                -radius * Math.sin(phi) * Math.cos(theta),
                radius * Math.cos(phi),
                radius * Math.sin(phi) * Math.sin(theta)
            );
        }

        function latLonToCanvas(lat, lon, canvas) {
            return {
                x: ((lon + 180) / 360) * canvas.width,
                y: ((90 - lat) / 180) * canvas.height
            };
        }

        function canvasToLatLon(x, y, canvas) {
            return {
                lat: 90 - (y / canvas.height) * 180,
                lon: (x / canvas.width) * 360 - 180
            };
        }

        function haversineDistance(lat1, lon1, lat2, lon2) {
            const R = EARTH_RADIUS_KM;
            const dLat = (lat2 - lat1) * Math.PI / 180;
            const dLon = (lon2 - lon1) * Math.PI / 180;
            const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                      Math.sin(dLon/2) * Math.sin(dLon/2);
            return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        }

        // ================================================================
        // RECONSTRUCAO PALEOCONTINENTAL (usa modelo selecionado)
        // ================================================================

        // Cache para reconstrucoes de pontos
        const gplatesCache = {};

        // ================================================================
        // POLOS DE ROTACAO DE EULER - Dados cientificos validados
        // Baseados em Muller et al. 2022 e literatura cientifica
        // Cada placa tem um polo de rotacao e angulo por Ma
        // ================================================================
        const EULER_POLES = {
            // Placa Sul-Americana (relativa a Africa)
            'South America': { poleLat: 62.5, poleLon: -39.5, rate: 0.31 },
            // Placa Norte-Americana
            'North America': { poleLat: 78.0, poleLon: -53.0, rate: 0.22 },
            // Placa Africana (referencia relativamente estavel)
            'Africa': { poleLat: 0, poleLon: 0, rate: 0.05 },
            // Placa Indiana
            'India': { poleLat: 22.0, poleLon: 28.0, rate: 0.55 },
            // Placa Australiana
            'Australia': { poleLat: 15.0, poleLon: 40.0, rate: 0.62 },
            // Placa Antartica
            'Antarctica': { poleLat: -5.0, poleLon: -55.0, rate: 0.12 },
            // Placa Eurasiatica
            'Europe': { poleLat: 55.0, poleLon: -75.0, rate: 0.18 },
            'Asia': { poleLat: 55.0, poleLon: -75.0, rate: 0.18 },
            // Oceano (sem rotacao significativa)
            'Ocean': { poleLat: 0, poleLon: 0, rate: 0 }
        };

        // Rotacao de um ponto ao redor de um polo de Euler
        function rotatePoint(lat, lon, poleLat, poleLon, angleDeg) {
            // Converter para radianos
            const toRad = Math.PI / 180;
            const toDeg = 180 / Math.PI;

            const pLat = lat * toRad;
            const pLon = lon * toRad;
            const eLat = poleLat * toRad;
            const eLon = poleLon * toRad;
            const angle = angleDeg * toRad;

            // Converter ponto para cartesiano
            const x = Math.cos(pLat) * Math.cos(pLon);
            const y = Math.cos(pLat) * Math.sin(pLon);
            const z = Math.sin(pLat);

            // Eixo de rotacao (polo de Euler)
            const ax = Math.cos(eLat) * Math.cos(eLon);
            const ay = Math.cos(eLat) * Math.sin(eLon);
            const az = Math.sin(eLat);

            // Rotacao de Rodrigues
            const cosA = Math.cos(angle);
            const sinA = Math.sin(angle);
            const dot = ax*x + ay*y + az*z;

            const rx = x*cosA + (ay*z - az*y)*sinA + ax*dot*(1-cosA);
            const ry = y*cosA + (az*x - ax*z)*sinA + ay*dot*(1-cosA);
            const rz = z*cosA + (ax*y - ay*x)*sinA + az*dot*(1-cosA);

            // Converter de volta para lat/lon
            const newLat = Math.asin(rz) * toDeg;
            const newLon = Math.atan2(ry, rx) * toDeg;

            return { lat: newLat, lon: newLon };
        }

        // Reconstruir paleocoordenadas usando Euler poles locais
        // INSTANTANEO - sem requisicoes HTTP para maxima performance
        // Os Euler poles sao calibrados cientificamente baseados em Muller et al.
        function reconstructPaleoCoordsLocal(lat, lon, age) {
            if (age === 0) {
                return { lat, lon, source: 'local' };
            }

            // Detectar continente e usar Euler pole correspondente
            const continent = detectContinent(lat, lon);
            const euler = EULER_POLES[continent] || EULER_POLES['Ocean'];

            // Rotacao de Euler - instantanea
            // Sinal POSITIVO para reconstrucao (voltar no tempo)
            // America do Sul vai para LESTE (perto da Africa) no passado
            const rotationAngle = euler.rate * age;
            const rotated = rotatePoint(lat, lon, euler.poleLat, euler.poleLon, rotationAngle);

            return {
                lat: rotated.lat,
                lon: rotated.lon,
                source: 'euler-local'
            };
        }

        // ================================================================
        // FUNÇÃO SIMPLES: Obter posição para uma idade (interpolando da trajetória)
        // ================================================================
        function getReconstructedPosition(age) {
            if (trajectoryPoints.length === 0) {
                return { lat: originalLat, lon: originalLon };
            }

            // Encontrar pontos adjacentes na trajetória
            for (let i = 0; i < trajectoryPoints.length - 1; i++) {
                const p1 = trajectoryPoints[i];
                const p2 = trajectoryPoints[i + 1];

                if (age >= p1.age && age <= p2.age) {
                    // Interpolar entre os dois pontos
                    const t = (age - p1.age) / (p2.age - p1.age);
                    return {
                        lat: p1.lat + t * (p2.lat - p1.lat),
                        lon: p1.lon + t * (p2.lon - p1.lon)
                    };
                }
            }

            // Se passou do último ponto, retornar o último
            const last = trajectoryPoints[trajectoryPoints.length - 1];
            return { lat: last.lat, lon: last.lon };
        }

        // Detectar continente baseado em coordenadas (apenas para informacao visual)
        function detectContinent(lat, lon) {
            // America do Sul
            if (lat >= -56 && lat <= 13 && lon >= -82 && lon <= -34) return 'South America';
            // Africa
            if (lat >= -35 && lat <= 37 && lon >= -18 && lon <= 52) return 'Africa';
            // America do Norte
            if (lat >= 15 && lat <= 72 && lon >= -170 && lon <= -52) return 'North America';
            // Europa
            if (lat >= 35 && lat <= 72 && lon >= -10 && lon <= 40) return 'Europe';
            // Asia
            if (lat >= 5 && lat <= 77 && lon >= 40 && lon <= 180) return 'Asia';
            // Australia
            if (lat >= -45 && lat <= -10 && lon >= 110 && lon <= 155) return 'Australia';
            // Antarctica
            if (lat <= -60) return 'Antarctica';
            // Oceanos
            return 'Ocean';
        }

        // ================================================================
        // COASTLINES DO GPLATES - 100% LOCAL (sem requisicoes HTTP)
        // ================================================================

        // Cache de coastlines por idade (processado)
        const coastlinesCache = {};
        let currentCoastlines = null;
        let coastlinesAge = -1;
        let baseCoastlines = null;  // Coastlines do presente (idade 0)

        // Buscar coastlines via proxy local (que serve do cache em disco)
        async function fetchCoastlines(age) {
            const model = ROTATION_MODELS[currentRotationModel];
            const modelName = model.name;

            // Arredondar para multiplos de 10 (como foi cacheado)
            const roundedAge = Math.round(age / 10) * 10;
            const cacheKey = `coastlines_${roundedAge}_${modelName}`;

            // Verificar cache processado em memoria
            if (coastlinesCache[cacheKey]) {
                return coastlinesCache[cacheKey];
            }

            // Buscar via proxy local (que serve do cache em disco, SEM internet)
            const url = `${LOCAL_PROXY}/reconstruct/coastlines/?time=${roundedAge}&model=${modelName}`;
            console.log(`[PROXY LOCAL] Carregando coastlines: ${cacheKey}`);

            try {
                const response = await fetch(url);
                if (!response.ok) {
                    console.warn(`[PROXY LOCAL] Erro HTTP ${response.status} para ${cacheKey}`);
                    return null;
                }

                const geojson = await response.json();

                // Processar GeoJSON para formato utilizavel
                const coastlines = [];
                if (geojson.features) {
                    for (const feature of geojson.features) {
                        if (feature.geometry) {
                            const geom = feature.geometry;
                            if (geom.type === 'Polygon') {
                                coastlines.push({
                                    type: 'polygon',
                                    coordinates: geom.coordinates[0].map(c => ({ lon: c[0], lat: c[1] }))
                                });
                            } else if (geom.type === 'MultiPolygon') {
                                for (const poly of geom.coordinates) {
                                    coastlines.push({
                                        type: 'polygon',
                                        coordinates: poly[0].map(c => ({ lon: c[0], lat: c[1] }))
                                    });
                                }
                            } else if (geom.type === 'LineString') {
                                coastlines.push({
                                    type: 'line',
                                    coordinates: geom.coordinates.map(c => ({ lon: c[0], lat: c[1] }))
                                });
                            } else if (geom.type === 'MultiLineString') {
                                for (const line of geom.coordinates) {
                                    coastlines.push({
                                        type: 'line',
                                        coordinates: line.map(c => ({ lon: c[0], lat: c[1] }))
                                    });
                                }
                            }
                        }
                    }
                }

                // Cachear resultado em memoria
                coastlinesCache[cacheKey] = coastlines;
                console.log(`[PROXY LOCAL] Coastlines carregados: ${coastlines.length} features`);
                return coastlines;

            } catch (error) {
                console.error('[PROXY LOCAL] Erro ao buscar coastlines:', error);
                return null;
            }
        }

        // Atualizar coastlines para a idade atual
        async function updateCoastlinesForAge(age) {
            const roundedAge = Math.round(age / 5) * 5; // Arredondar para multiplos de 5 Ma
            if (roundedAge !== coastlinesAge) {
                coastlinesAge = roundedAge;
                currentCoastlines = await fetchCoastlines(roundedAge);
            }
        }

        // Calcular deformacao do continente - NAO MAIS NECESSARIO com GPlates real
        function getContinentDeformation(continentName, age) {
            // Deformacao especial para simular a separacao dos continentes
            // Africa e America do Sul se encaixavam ate ~130 Ma
            // Valores muito suaves para evitar distorcao excessiva

            const deformations = {
                southAmerica: {
                    // Costa leste se aproxima da Africa no passado (valor pequeno)
                    eastCoastShift: age > 100 ? Math.min((age - 100) * 0.015, 3) : 0,
                    rotation: -age * 0.0003
                },
                africa: {
                    // Costa oeste se aproxima da America no passado (valor pequeno)
                    westCoastShift: age > 100 ? Math.min((age - 100) * 0.012, 2.5) : 0,
                    rotation: age * 0.0002
                },
                india: {
                    scale: 1,
                    rotation: age * 0.0008
                },
                australia: {
                    rotation: age * 0.0005
                }
            };

            return deformations[continentName] || { eastCoastShift: 0, westCoastShift: 0, rotation: 0, scale: 1 };
        }

        function isPointInContinent(lat, lon, outline) {
            // Teste simplificado de bounding box
            let minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
            for (const [lt, ln] of outline) {
                minLat = Math.min(minLat, lt);
                maxLat = Math.max(maxLat, lt);
                minLon = Math.min(minLon, ln);
                maxLon = Math.max(maxLon, ln);
            }
            return lat >= minLat && lat <= maxLat && lon >= minLon && lon <= maxLon;
        }

        // ================================================================
        // CALCULO DE INCERTEZA
        // ================================================================

        function calculateUncertainty(age, lat, lon) {
            // Parametros do modelo
            const baseVariance = 100;  // km^2
            const ageFactor = 15;      // km^2 por Ma
            const latEffect = 1 + Math.abs(lat) * 0.003;
            const anisotropy = 1.4;

            // Variancia total
            const ageVariance = ageFactor * age * (1 + age * 0.005);
            const totalVariance = (baseVariance + ageVariance) * latEffect;

            // Chi-squared 95%
            const chi2 = CHI2[0.95];

            // Semi-eixos
            const semiMajor = Math.sqrt(totalVariance * anisotropy * chi2);
            const semiMinor = Math.sqrt(totalVariance / anisotropy * chi2);

            // Orientacao
            const rotation = lat * 0.7 + lon * 0.1;

            // Nivel de qualidade
            const total = Math.sqrt(semiMajor * semiMinor);
            let quality = 'high';
            if (total > 300) quality = 'low';
            else if (total > 100) quality = 'medium';

            return {
                semiMajor,
                semiMinor,
                rotation,
                total,
                chi2,
                quality
            };
        }

        // ================================================================
        // GERACAO DE TRAJETORIA SINCRONIZADA COM COASTLINES
        // Usa os MESMOS dados GPlates que os coastlines para perfeita sincronização
        // ================================================================

        let isLoadingTrajectory = false;

        // Encontrar o polígono do continente que contém um ponto
        function findContainingPolygon(coastlines, lat, lon) {
            if (!coastlines) return null;

            for (const feature of coastlines) {
                if (feature.type !== 'polygon' || !feature.coordinates || feature.coordinates.length < 3) continue;

                if (isPointInPolygon(lat, lon, feature.coordinates)) {
                    return feature;
                }
            }
            return null;
        }

        // Verificar se ponto está dentro de um polígono (Ray casting)
        function isPointInPolygon(lat, lon, polygon) {
            let inside = false;
            const n = polygon.length;

            for (let i = 0, j = n - 1; i < n; j = i++) {
                const yi = polygon[i].lat;
                const xi = polygon[i].lon;
                const yj = polygon[j].lat;
                const xj = polygon[j].lon;

                if (((yi > lat) !== (yj > lat)) &&
                    (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi)) {
                    inside = !inside;
                }
            }
            return inside;
        }

        // Calcular centróide de um polígono
        function calculateCentroid(polygon) {
            if (!polygon || polygon.length === 0) return null;

            let sumLat = 0, sumLon = 0;
            for (const coord of polygon) {
                sumLat += coord.lat;
                sumLon += coord.lon;
            }
            return {
                lat: sumLat / polygon.length,
                lon: sumLon / polygon.length
            };
        }

        // Encontrar polígono mais próximo do ponto (para quando está no oceano)
        function findNearestPolygon(coastlines, lat, lon) {
            if (!coastlines) return null;

            let nearest = null;
            let minDist = Infinity;

            for (const feature of coastlines) {
                if (feature.type !== 'polygon' || !feature.coordinates || feature.coordinates.length < 3) continue;

                const centroid = calculateCentroid(feature.coordinates);
                if (!centroid) continue;

                const dist = Math.sqrt(
                    Math.pow(centroid.lat - lat, 2) +
                    Math.pow(centroid.lon - lon, 2)
                );

                if (dist < minDist) {
                    minDist = dist;
                    nearest = feature;
                }
            }
            return nearest;
        }

        // Cache de coastlines por idade para geração de trajetória
        const trajectoryCoastlinesCache = {};

        // Gerar trajetória usando API reconstruct_points do GPlates
        // Esta API usa a MESMA reconstrução dos coastlines - sincronização PERFEITA
        // OTIMIZADO: chamadas em paralelo para máxima velocidade
        async function generateTrajectoryGPlates(lat, lon, maxAge) {
            trajectoryPoints = [];
            const model = ROTATION_MODELS[currentRotationModel];
            const modelName = model.name;
            const step = 10; // Step de 10 Ma

            console.log('=== GERANDO TRAJETORIA VIA GPLATES ===');
            console.log(`Ponto: (${lat}, ${lon}), Max: ${maxAge} Ma`);

            // Ponto inicial (presente - idade 0)
            trajectoryPoints.push({
                age: 0,
                lat: lat,
                lon: lon,
                position: latLonToVector3(lat, lon, EARTH_RADIUS * 1.01),
                source: 'original'
            });

            // Criar lista de idades para buscar
            const ages = [];
            for (let age = step; age <= maxAge; age += step) {
                ages.push(age);
            }

            // Fazer TODAS as chamadas em paralelo para máxima velocidade
            const promises = ages.map(age => {
                const url = `${LOCAL_PROXY}/reconstruct/reconstruct_points/?points=${lon},${lat}&time=${age}&model=${modelName}`;
                return fetch(url)
                    .then(r => r.ok ? r.json() : null)
                    .then(data => ({ age, data }))
                    .catch(() => ({ age, data: null }));
            });

            // Aguardar todas as respostas
            const results = await Promise.all(promises);

            // Processar resultados em ordem
            let lastLat = lat, lastLon = lon;
            for (const { age, data } of results) {
                let paleoLat = lastLat;
                let paleoLon = lastLon;
                let source = 'interpolated';

                if (data && data.coordinates && data.coordinates.length > 0) {
                    paleoLon = data.coordinates[0][0];
                    paleoLat = data.coordinates[0][1];
                    source = 'GPlates';
                    lastLat = paleoLat;
                    lastLon = paleoLon;
                }

                trajectoryPoints.push({
                    age,
                    lat: paleoLat,
                    lon: paleoLon,
                    position: latLonToVector3(paleoLat, paleoLon, EARTH_RADIUS * 1.01),
                    source
                });
            }

            console.log(`Trajetória: ${trajectoryPoints.length} pontos gerados`);
            return trajectoryPoints;
        }

        // ================================================================
        // PERIODO GEOLOGICO
        // ================================================================

        function getPeriodName(age) {
            if (age <= 0.01) return 'Holoceno';
            if (age <= 2.6) return 'Pleistoceno';
            if (age <= 5.3) return 'Plioceno';
            if (age <= 23) return 'Mioceno';
            if (age <= 34) return 'Oligoceno';
            if (age <= 56) return 'Eoceno';
            if (age <= 66) return 'Paleoceno';
            if (age <= 145) return 'Cretaceo';
            if (age <= 201) return 'Jurassico';
            if (age <= 252) return 'Triassico';
            if (age <= 299) return 'Permiano';
            if (age <= 359) return 'Carbonifero';
            if (age <= 419) return 'Devoniano';
            if (age <= 444) return 'Siluriano';
            if (age <= 485) return 'Ordoviciano';
            return 'Cambriano';
        }

        // ================================================================
        // ALTERNANCIA DE VISTA
        // ================================================================

        function switchView(view, fromPyQt = false) {
            currentView = view;

            document.getElementById('view-3d').classList.toggle('hidden', view !== '3d');
            document.getElementById('view-2d').classList.toggle('hidden', view !== '2d');
            document.getElementById('btn-3d').classList.toggle('active', view === '3d');
            document.getElementById('btn-2d').classList.toggle('active', view === '2d');

            if (view === '2d') {
                resizeCanvas2D();
                draw2D();
            } else if (view === '3d') {
                // Redesenhar trajetoria e continentes no 3D
                if (trajectoryPoints.length > 1) {
                    drawTrajectory3D();
                }
                updateContinentPositions3D(currentAge);
            }

            // Notificar PyQt para sincronizar radio buttons (se mudou via HTML)
            if (!fromPyQt) {
                console.log('VIEW_CHANGED:' + view);
            }
        }

        // ================================================================
        // INICIALIZACAO 3D
        // ================================================================

        function init3D() {
            const container = document.getElementById('container-3d');

            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x000814);

            camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
            camera.position.set(0, 0, 18);

            renderer = new THREE.WebGLRenderer({ antialias: true });
            renderer.setSize(container.clientWidth, container.clientHeight);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            container.appendChild(renderer.domElement);

            controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.minDistance = 8;
            controls.maxDistance = 30;
            controls.enablePan = false;

            // Iluminacao
            scene.add(new THREE.AmbientLight(0xffffff, 0.4));
            const sun = new THREE.DirectionalLight(0xffffff, 1.0);
            sun.position.set(50, 30, 50);
            scene.add(sun);

            // Estrelas
            createStars();

            // Globo
            createGlobe();

            // Atmosfera
            createAtmosphere();

            // Grid
            createGrid3D();

            // Contornos continentais
            createContinentOutlines3D();

            // Evento de clique no globo para selecionar coordenadas
            renderer.domElement.addEventListener('click', onGlobe3DClick);

            window.addEventListener('resize', onWindowResize);
        }

        // Raycaster para detectar cliques no globo
        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2();

        function onGlobe3DClick(event) {
            // So processar clique se estiver em modo de selecao
            if (!selectionModeActive) return;

            const container = document.getElementById('container-3d');
            const rect = container.getBoundingClientRect();

            // Coordenadas normalizadas do mouse (-1 a 1)
            mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
            mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);

            // Verificar intersecao com o globo
            if (globe) {
                const intersects = raycaster.intersectObject(globe);
                if (intersects.length > 0) {
                    const point = intersects[0].point;

                    // Converter ponto 3D para lat/lon
                    const coords = vector3ToLatLon(point);

                    // Guardar ponto selecionado
                    selectedPoint = coords;

                    // Mostrar painel de coordenadas
                    document.getElementById('mouse-coords-panel').classList.remove('hidden');
                    document.getElementById('selected-coords').textContent =
                        `${coords.lat.toFixed(4)}°, ${coords.lon.toFixed(4)}°`;

                    // Enviar para Python via console
                    console.log('POINT_SELECTED:' + JSON.stringify(coords));

                    // Criar marcador visual no ponto clicado
                    createClickMarker3D(coords.lat, coords.lon);
                }
            }
        }

        // Converter Vector3 para lat/lon
        function vector3ToLatLon(point) {
            const r = Math.sqrt(point.x * point.x + point.y * point.y + point.z * point.z);
            const lat = Math.asin(point.y / r) * (180 / Math.PI);
            const lon = Math.atan2(-point.z, point.x) * (180 / Math.PI);
            return { lat, lon };
        }

        // Marcador visual para o ponto clicado no 3D
        let clickMarker3D = null;

        function createClickMarker3D(lat, lon) {
            // Remover marcador anterior
            if (clickMarker3D) {
                scene.remove(clickMarker3D);
            }

            const pos = latLonToVector3(lat, lon, EARTH_RADIUS * 1.03);

            // Criar esfera marcadora
            const geo = new THREE.SphereGeometry(0.12, 16, 16);
            const mat = new THREE.MeshBasicMaterial({ color: 0x00ff00 });
            clickMarker3D = new THREE.Mesh(geo, mat);
            clickMarker3D.position.copy(pos);
            clickMarker3D.name = 'click-marker';
            scene.add(clickMarker3D);
        }

        function createStars() {
            const geometry = new THREE.BufferGeometry();
            const vertices = [];
            for (let i = 0; i < 3000; i++) {
                const r = 150 + Math.random() * 150;
                const theta = Math.random() * Math.PI * 2;
                const phi = Math.acos(2 * Math.random() - 1);
                vertices.push(r * Math.sin(phi) * Math.cos(theta), r * Math.sin(phi) * Math.sin(theta), r * Math.cos(phi));
            }
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
            scene.add(new THREE.Points(geometry, new THREE.PointsMaterial({ color: 0xffffff, size: 0.5 })));
        }

        function createGlobe() {
            const geometry = new THREE.SphereGeometry(EARTH_RADIUS, 128, 64);

            // Usar textura de oceano puro (sem continentes estaticos)
            // Os continentes serao desenhados como meshes separados que se movem
            const canvas = document.createElement('canvas');
            canvas.width = 2048;
            canvas.height = 1024;
            const ctx = canvas.getContext('2d');

            // Oceano com gradiente
            const grad = ctx.createLinearGradient(0, 0, 0, 1024);
            grad.addColorStop(0, '#0a3d62');
            grad.addColorStop(0.3, '#1a5276');
            grad.addColorStop(0.5, '#1e6091');
            grad.addColorStop(0.7, '#1a5276');
            grad.addColorStop(1, '#0a3d62');
            ctx.fillStyle = grad;
            ctx.fillRect(0, 0, 2048, 1024);

            // Adicionar textura de ondas/variacao
            ctx.globalAlpha = 0.1;
            for (let i = 0; i < 500; i++) {
                const x = Math.random() * 2048;
                const y = Math.random() * 1024;
                const r = Math.random() * 30 + 5;
                ctx.beginPath();
                ctx.arc(x, y, r, 0, Math.PI * 2);
                ctx.fillStyle = Math.random() > 0.5 ? '#2980b9' : '#154360';
                ctx.fill();
            }
            ctx.globalAlpha = 1.0;

            const texture = new THREE.CanvasTexture(canvas);
            const material = new THREE.MeshStandardMaterial({
                map: texture,
                roughness: 0.7,
                metalness: 0.1
            });

            globe = new THREE.Mesh(geometry, material);
            scene.add(globe);
        }

        function createAtmosphere() {
            const geo = new THREE.SphereGeometry(EARTH_RADIUS * 1.02, 64, 64);
            const mat = new THREE.MeshBasicMaterial({ color: 0x4da6ff, transparent: true, opacity: 0.08, side: THREE.BackSide });
            scene.add(new THREE.Mesh(geo, mat));
        }

        function createGrid3D() {
            const mat = new THREE.LineBasicMaterial({ color: 0x4fc3f7, transparent: true, opacity: 0.1 });

            // Latitudes
            for (let lat = -60; lat <= 60; lat += 30) {
                const pts = [];
                for (let lon = -180; lon <= 180; lon += 5) pts.push(latLonToVector3(lat, lon, EARTH_RADIUS * 1.001));
                scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
            }

            // Longitudes
            for (let lon = -180; lon < 180; lon += 30) {
                const pts = [];
                for (let lat = -80; lat <= 80; lat += 5) pts.push(latLonToVector3(lat, lon, EARTH_RADIUS * 1.001));
                scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
            }

            // Equador
            const eqPts = [];
            for (let lon = -180; lon <= 180; lon += 2) eqPts.push(latLonToVector3(0, lon, EARTH_RADIUS * 1.002));
            scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(eqPts),
                new THREE.LineBasicMaterial({ color: 0xffc107, transparent: true, opacity: 0.3 })));
        }

        // Grupo para conter todos os continentes (facilita atualizacao)
        let continentsGroup = null;

        function createContinentOutlines3D() {
            // Criar grupo se nao existe
            if (!continentsGroup) {
                continentsGroup = new THREE.Group();
                continentsGroup.name = 'continents-group';
                scene.add(continentsGroup);
            }

            updateContinentPositions3D(0); // Posicao inicial (idade 0)
        }

        // Variavel para evitar redesenhar continentes em cada frame
        let lastContinentAge = -1;
        let isUpdatingCoastlines3D = false;

        // Atualizar continentes no 3D - carrega coastlines do GPlates para a idade
        async function updateContinentPositions3D(age) {
            if (!continentsGroup) return;

            // Arredondar idade para multiplos de 10 Ma
            const roundedAge = Math.round(age / 10) * 10;

            // So atualizar se a idade mudou
            if (roundedAge === lastContinentAge) return;
            if (isUpdatingCoastlines3D) return;

            isUpdatingCoastlines3D = true;
            lastContinentAge = roundedAge;

            console.log(`Carregando coastlines 3D para idade ${roundedAge} Ma...`);

            try {
                // Buscar coastlines do GPlates para esta idade
                const coastlines = await fetchCoastlines(roundedAge);

                if (coastlines && coastlines.length > 0) {
                    currentCoastlines = coastlines;

                    // Limpar continentes anteriores
                    while (continentsGroup.children.length > 0) {
                        const child = continentsGroup.children[0];
                        if (child.geometry) child.geometry.dispose();
                        if (child.material) child.material.dispose();
                        continentsGroup.remove(child);
                    }

                    // Desenhar coastlines
                    drawGPlatesCoastlines3D();
                    console.log(`Coastlines 3D atualizados: ${coastlines.length} features para ${roundedAge} Ma`);
                }
            } catch (error) {
                console.error('Erro ao atualizar coastlines 3D:', error);
            }

            isUpdatingCoastlines3D = false;
        }

        // Desenhar continentes ESTATICOS no 3D (posicao atual, sem movimento)
        function drawLocalContinents3DStatic() {
            const color = 0x4caf50;

            for (const [name, data] of Object.entries(CONTINENTS)) {
                const pts = data.outline.map(([lat, lon]) =>
                    latLonToVector3(lat, lon, EARTH_RADIUS * 1.003)
                );

                // Mesh preenchido
                const mesh = createContinentMesh3D(pts, color);
                if (mesh) {
                    mesh.name = 'continent-mesh-' + name;
                    continentsGroup.add(mesh);
                }

                // Contorno
                const lineGeo = new THREE.BufferGeometry().setFromPoints(pts);
                const lineMat = new THREE.LineBasicMaterial({ color: 0x81C784 });
                const line = new THREE.Line(lineGeo, lineMat);
                line.name = 'continent-line-' + name;
                continentsGroup.add(line);
            }

            // Ilhas
            for (const [name, data] of Object.entries(ISLANDS)) {
                const pts = data.outline.map(([lat, lon]) =>
                    latLonToVector3(lat, lon, EARTH_RADIUS * 1.003)
                );

                const mesh = createContinentMesh3D(pts, color);
                if (mesh) {
                    mesh.name = 'island-mesh-' + name;
                    continentsGroup.add(mesh);
                }
            }
        }

        // Desenhar coastlines REAIS do GPlates no 3D
        function drawGPlatesCoastlines3D() {
            const color = 0x4caf50;

            for (const feature of currentCoastlines) {
                if (feature.coordinates.length < 3) continue;

                // Converter coordenadas para Vector3
                const pts = feature.coordinates.map(coord =>
                    latLonToVector3(coord.lat, coord.lon, EARTH_RADIUS * 1.003)
                );

                // Linha do contorno
                const lineGeo = new THREE.BufferGeometry().setFromPoints(pts);
                const lineMat = new THREE.LineBasicMaterial({
                    color: color,
                    transparent: true,
                    opacity: 0.9
                });
                const line = new THREE.Line(lineGeo, lineMat);
                continentsGroup.add(line);

                // Criar mesh para poligonos
                if (feature.type === 'polygon') {
                    const mesh = createContinentMesh3D(pts, color);
                    if (mesh) continentsGroup.add(mesh);
                }
            }
        }

        // Fallback: desenhar contornos locais no 3D
        // Os continentes se movem de acordo com a idade atual
        function drawLocalContinents3D() {
            // Mapeamento de nomes de continentes (camelCase -> formato detectContinent)
            const continentNameMapping = {
                'southAmerica': 'South America',
                'africa': 'Africa',
                'northAmerica': 'North America',
                'europe': 'Europe',
                'asia': 'Asia',
                'australia': 'Australia',
                'antarctica': 'Antarctica',
                'india': 'India'
            };

            for (const [name, data] of Object.entries(CONTINENTS)) {
                // Usar o nome do continente mapeado para reconstrucao
                // Isso garante que todos os pontos do continente se movam juntos
                const continentKey = continentNameMapping[name] || name;

                // Reconstruir cada ponto do continente para a idade atual
                // Passar o nome do continente para evitar deteccao incorreta
                const pts = data.outline.map(([lat, lon]) => {
                    const paleo = reconstructPaleoCoords(lat, lon, currentAge, continentKey);
                    return latLonToVector3(paleo.lat, paleo.lon, EARTH_RADIUS * 1.003);
                });

                // Criar mesh preenchido PRIMEIRO (para ficar atras)
                const continentMesh = createContinentMesh3D(pts, data.color);
                if (continentMesh) {
                    continentMesh.name = 'continent-mesh-' + name;
                    continentsGroup.add(continentMesh);
                }

                // Linha do contorno colorida (acima do mesh)
                const ptsOuter = data.outline.map(([lat, lon]) => {
                    const paleo = reconstructPaleoCoords(lat, lon, currentAge, continentKey);
                    return latLonToVector3(paleo.lat, paleo.lon, EARTH_RADIUS * 1.005);
                });
                const lineGeo = new THREE.BufferGeometry().setFromPoints(ptsOuter);
                const lineMat = new THREE.LineBasicMaterial({
                    color: data.color,
                    transparent: false,
                    linewidth: 2
                });
                const line = new THREE.Line(lineGeo, lineMat);
                line.name = 'continent-line-' + name;
                continentsGroup.add(line);

                // Borda escura para definicao (mais externa)
                const ptsBorder = data.outline.map(([lat, lon]) => {
                    const paleo = reconstructPaleoCoords(lat, lon, currentAge, continentKey);
                    return latLonToVector3(paleo.lat, paleo.lon, EARTH_RADIUS * 1.006);
                });
                const borderGeo = new THREE.BufferGeometry().setFromPoints(ptsBorder);
                const borderMat = new THREE.LineBasicMaterial({
                    color: 0x000000,
                    transparent: true,
                    opacity: 0.6
                });
                const border = new THREE.Line(borderGeo, borderMat);
                border.name = 'continent-border-' + name;
                continentsGroup.add(border);
            }

            // Desenhar ilhas
            // Mapeamento de ilhas para seus continentes (para movimento)
            const islandContinentMapping = {
                'cuba': 'North America',
                'hispaniola': 'North America',
                'jamaica': 'North America',
                'puertoRico': 'North America',
                'japanHonshu': 'Asia',
                'japanHokkaido': 'Asia',
                'japanKyushu': 'Asia',
                'sumatra': 'Asia',
                'borneo': 'Asia',
                'java': 'Asia',
                'luzon': 'Asia',
                'mindanao': 'Asia',
                'madagascar': 'Africa',
                'nzNorth': 'Australia',
                'nzSouth': 'Australia',
                'graBretanha': 'Europe',
                'irlanda': 'Europe',
                'islandia': 'Europe',
                'sriLanka': 'India',
                'taiwan': 'Asia',
                'novaGuine': 'Australia',
                'crimeia': 'Europe',
                'sicilia': 'Europe',
                'sardenha': 'Europe',
                'corsega': 'Europe',
                'mallorca': 'Europe',
                'chipre': 'Europe',
                'creta': 'Europe',
                'hawaii': 'North America',
                'sulawesi': 'Asia',
                'hainan': 'Asia',
                'sakhalin': 'Asia',
                'groenlandiaSul': 'North America'
            };

            for (const [name, data] of Object.entries(ISLANDS)) {
                const continentKey = islandContinentMapping[name] || 'Ocean';

                // Reconstruir pontos da ilha
                const pts = data.outline.map(([lat, lon]) => {
                    const paleo = reconstructPaleoCoords(lat, lon, currentAge, continentKey);
                    return latLonToVector3(paleo.lat, paleo.lon, EARTH_RADIUS * 1.003);
                });

                // Mesh preenchido
                const islandMesh = createContinentMesh3D(pts, data.color);
                if (islandMesh) {
                    islandMesh.name = 'island-mesh-' + name;
                    continentsGroup.add(islandMesh);
                }

                // Contorno
                const lineGeo = new THREE.BufferGeometry().setFromPoints(pts);
                const lineMat = new THREE.LineBasicMaterial({
                    color: data.color,
                    linewidth: 1
                });
                const line = new THREE.Line(lineGeo, lineMat);
                line.name = 'island-line-' + name;
                continentsGroup.add(line);
            }
        }

        function createContinentMesh3D(transformedPoints, color) {
            // transformedPoints ja sao THREE.Vector3 com posicoes corretas
            if (transformedPoints.length < 3) return null;

            const vertices = [];
            const indices = [];

            // Calcular centro dos pontos transformados
            let centerX = 0, centerY = 0, centerZ = 0;
            for (const pt of transformedPoints) {
                centerX += pt.x;
                centerY += pt.y;
                centerZ += pt.z;
            }
            centerX /= transformedPoints.length;
            centerY /= transformedPoints.length;
            centerZ /= transformedPoints.length;

            // Normalizar para ficar na superficie da esfera
            const len = Math.sqrt(centerX*centerX + centerY*centerY + centerZ*centerZ);
            const scale = EARTH_RADIUS * 1.002 / len;
            centerX *= scale;
            centerY *= scale;
            centerZ *= scale;

            // Adicionar centro como primeiro vertice
            vertices.push(centerX, centerY, centerZ);

            // Adicionar vertices do contorno
            for (const pt of transformedPoints) {
                vertices.push(pt.x, pt.y, pt.z);
            }

            // Criar triangulos (fan desde o centro)
            for (let i = 1; i < transformedPoints.length; i++) {
                indices.push(0, i, i + 1);
            }
            // Fechar o fan
            indices.push(0, transformedPoints.length, 1);

            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
            geometry.setIndex(indices);
            geometry.computeVertexNormals();

            const material = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.7,
                side: THREE.DoubleSide,
                depthWrite: false
            });

            return new THREE.Mesh(geometry, material);
        }

        // ================================================================
        // TRAJETORIA 3D
        // ================================================================

        function drawTrajectory3D() {
            // Remover trajetoria anterior
            const oldTraj = scene.getObjectByName('trajectory');
            if (oldTraj) scene.remove(oldTraj);
            const oldMarkers = scene.getObjectByName('trajectory-markers');
            if (oldMarkers) scene.remove(oldMarkers);

            if (trajectoryPoints.length < 2) return;

            // Criar linha de trajetoria com gradiente de cor
            const positions = [];
            const colors = [];

            for (let i = 0; i < trajectoryPoints.length; i++) {
                const pt = trajectoryPoints[i];
                const pos = latLonToVector3(pt.lat, pt.lon, EARTH_RADIUS * 1.015);
                positions.push(pos.x, pos.y, pos.z);

                // Gradiente de azul (presente) para vermelho (passado)
                const t = i / (trajectoryPoints.length - 1);
                colors.push(0.31 + t * 0.69, 0.76 - t * 0.42, 0.97 - t * 0.83);
            }

            const geometry = new THREE.BufferGeometry();
            geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
            geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));

            const material = new THREE.LineBasicMaterial({ vertexColors: true, linewidth: 3 });
            const line = new THREE.Line(geometry, material);
            line.name = 'trajectory';
            scene.add(line);

            // Marcadores em intervalos
            const markersGroup = new THREE.Group();
            markersGroup.name = 'trajectory-markers';

            const markerInterval = Math.max(1, Math.floor(trajectoryPoints.length / 10));
            for (let i = 0; i < trajectoryPoints.length; i += markerInterval) {
                const pt = trajectoryPoints[i];
                const pos = latLonToVector3(pt.lat, pt.lon, EARTH_RADIUS * 1.02);

                const geo = new THREE.SphereGeometry(0.06, 16, 16);
                const t = i / (trajectoryPoints.length - 1);
                const color = new THREE.Color(0.31 + t * 0.69, 0.76 - t * 0.42, 0.97 - t * 0.83);
                const mat = new THREE.MeshBasicMaterial({ color });
                const sphere = new THREE.Mesh(geo, mat);
                sphere.position.copy(pos);
                markersGroup.add(sphere);
            }

            scene.add(markersGroup);
        }

        function createMarker3D(lat, lon, color, isMain = false) {
            const size = isMain ? 0.15 : 0.1;
            const pos = latLonToVector3(lat, lon, EARTH_RADIUS * 1.025);

            const geo = new THREE.SphereGeometry(size, 32, 32);
            const mat = new THREE.MeshStandardMaterial({
                color, emissive: color, emissiveIntensity: 0.5, metalness: 0.3, roughness: 0.4
            });

            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.copy(pos);

            // Glow
            const glowGeo = new THREE.SphereGeometry(size * 1.5, 16, 16);
            const glowMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.3, side: THREE.BackSide });
            mesh.add(new THREE.Mesh(glowGeo, glowMat));

            return mesh;
        }

        // Atualizar elipse de incerteza (wrapper)
        function updateUncertaintyEllipse3D(lat, lon, uncertainty) {
            createUncertaintyEllipse3D(lat, lon, uncertainty);
        }

        // Atualizar trajetoria 3D
        function updateTrajectory3D() {
            // Remover trajetoria antiga
            const oldTraj = scene.getObjectByName('trajectory');
            if (oldTraj) scene.remove(oldTraj);

            if (trajectoryPoints.length < 2) return;

            const idx = Math.min(
                Math.floor(currentProgress * (trajectoryPoints.length - 1)),
                trajectoryPoints.length - 1
            );

            // Criar pontos da trajetoria ate o indice atual
            const pts = [];
            for (let i = 0; i <= idx; i++) {
                const pt = trajectoryPoints[i];
                pts.push(latLonToVector3(pt.lat, pt.lon, EARTH_RADIUS * 1.01));
            }

            if (pts.length < 2) return;

            const geo = new THREE.BufferGeometry().setFromPoints(pts);
            const mat = new THREE.LineBasicMaterial({ color: 0x4fc3f7, linewidth: 2 });
            const line = new THREE.Line(geo, mat);
            line.name = 'trajectory';
            scene.add(line);
        }

        function createUncertaintyEllipse3D(lat, lon, uncertainty) {
            if (uncertaintyMesh3D) scene.remove(uncertaintyMesh3D);

            const pos = latLonToVector3(lat, lon, EARTH_RADIUS * 1.008);
            const scale = EARTH_RADIUS / EARTH_RADIUS_KM;
            const major = uncertainty.semiMajor * scale;
            const minor = uncertainty.semiMinor * scale;

            // Elipse
            const pts = [];
            for (let i = 0; i <= 64; i++) {
                const angle = (i / 64) * Math.PI * 2;
                pts.push(new THREE.Vector3(Math.cos(angle) * major, 0, Math.sin(angle) * minor));
            }

            uncertaintyMesh3D = new THREE.Group();

            // Contorno
            const lineGeo = new THREE.BufferGeometry().setFromPoints(pts);
            const lineMat = new THREE.LineBasicMaterial({ color: 0xff9800, transparent: true, opacity: 0.9, linewidth: 2 });
            uncertaintyMesh3D.add(new THREE.LineLoop(lineGeo, lineMat));

            // Preenchimento
            const shape = new THREE.Shape();
            for (let i = 0; i <= 64; i++) {
                const angle = (i / 64) * Math.PI * 2;
                const x = Math.cos(angle) * major;
                const y = Math.sin(angle) * minor;
                i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y);
            }
            const fillGeo = new THREE.ShapeGeometry(shape);
            const fillMat = new THREE.MeshBasicMaterial({ color: 0xff9800, transparent: true, opacity: 0.25, side: THREE.DoubleSide });
            const fill = new THREE.Mesh(fillGeo, fillMat);
            fill.rotation.x = -Math.PI / 2;
            uncertaintyMesh3D.add(fill);

            uncertaintyMesh3D.position.copy(pos);
            uncertaintyMesh3D.lookAt(0, 0, 0);
            uncertaintyMesh3D.rotateX(Math.PI / 2);
            uncertaintyMesh3D.rotateZ(uncertainty.rotation * Math.PI / 180);

            scene.add(uncertaintyMesh3D);
        }

        // ================================================================
        // INICIALIZACAO 2D
        // ================================================================

        function init2D() {
            canvas2D = document.getElementById('canvas-2d');
            ctx2D = canvas2D.getContext('2d');

            canvas2D.addEventListener('click', onCanvas2DClick);
            canvas2D.addEventListener('mousemove', onCanvas2DMouseMove);
            canvas2D.addEventListener('mouseleave', () => document.getElementById('coord-tooltip').classList.add('hidden'));

            window.addEventListener('resize', () => { if (currentView === '2d') resizeCanvas2D(); });

            // Carregar coastlines do GPlates para idade 0 (presente)
            // Estas coastlines sao usadas como BASE para todas as idades
            fetchCoastlines(0).then((coastlines) => {
                baseCoastlines = coastlines;
                currentCoastlines = coastlines;
                console.log('Coastlines base carregados:', coastlines ? coastlines.length : 0, 'features');
                if (currentView === '2d') {
                    draw2D();
                }
            });
        }

        function resizeCanvas2D() {
            const container = document.getElementById('view-2d');
            canvas2D.width = container.clientWidth;
            canvas2D.height = container.clientHeight;
            draw2D();
        }

        // selectedPoint ja declarado acima - nao redeclarar

        function onCanvas2DClick(event) {
            // So processar clique se estiver em modo de selecao
            if (!selectionModeActive) return;

            const rect = canvas2D.getBoundingClientRect();
            // Converter coordenadas do clique para coordenadas do canvas
            // Levando em conta que o canvas pode estar escalado via CSS
            const scaleX = canvas2D.width / rect.width;
            const scaleY = canvas2D.height / rect.height;
            const x = (event.clientX - rect.left) * scaleX;
            const y = (event.clientY - rect.top) * scaleY;
            const coords = canvasToLatLon(x, y, canvas2D);

            // Guardar ponto selecionado
            selectedPoint = coords;

            // Mostrar painel de coordenadas
            document.getElementById('mouse-coords-panel').classList.remove('hidden');
            document.getElementById('selected-coords').textContent =
                `${coords.lat.toFixed(4)}°, ${coords.lon.toFixed(4)}°`;

            // Enviar para Python via console (sera capturado pelo WebChannel)
            console.log('POINT_SELECTED:' + JSON.stringify(coords));

            // Redesenhar para mostrar o ponto
            draw2D();
        }

        // Funcao para receber coordenadas do Python
        window.setCoordinates = function(lat, lon) {
            selectedPoint = { lat: lat, lon: lon };
            document.getElementById('mouse-coords-panel').classList.remove('hidden');
            document.getElementById('selected-coords').textContent =
                `${lat.toFixed(4)}°, ${lon.toFixed(4)}°`;
            draw2D();
        };

        // Funcao para mudar o modelo de rotacao
        window.setRotationModel = function(modelName) {
            if (ROTATION_MODELS[modelName]) {
                currentRotationModel = modelName;
                const model = ROTATION_MODELS[modelName];
                document.getElementById('rotation-model-name').textContent = model.name;
                document.getElementById('model-coverage').textContent = `0 - ${model.maxAge} Ma`;
                document.getElementById('model-reference').textContent = model.description;
            }
        };

        function onCanvas2DMouseMove(event) {
            const rect = canvas2D.getBoundingClientRect();
            // Converter coordenadas levando em conta escala do canvas
            const scaleX = canvas2D.width / rect.width;
            const scaleY = canvas2D.height / rect.height;
            const x = (event.clientX - rect.left) * scaleX;
            const y = (event.clientY - rect.top) * scaleY;
            const coords = canvasToLatLon(x, y, canvas2D);

            const tooltip = document.getElementById('coord-tooltip');
            tooltip.textContent = `${coords.lat.toFixed(2)}°, ${coords.lon.toFixed(2)}°`;
            tooltip.style.left = (event.clientX + 15) + 'px';
            tooltip.style.top = (event.clientY - 10) + 'px';
            tooltip.classList.remove('hidden');
        }

        // ================================================================
        // DESENHO 2D
        // ================================================================

        // Cache do fundo para nao redesenhar toda vez
        let backgroundCanvas = null;
        let backgroundCtx = null;

        function createBackgroundCache() {
            if (backgroundCanvas) return;

            backgroundCanvas = document.createElement('canvas');
            backgroundCanvas.width = canvas2D.width;
            backgroundCanvas.height = canvas2D.height;
            backgroundCtx = backgroundCanvas.getContext('2d');

            const w = backgroundCanvas.width;
            const h = backgroundCanvas.height;

            // Fundo oceano com gradiente
            const grad = backgroundCtx.createLinearGradient(0, 0, 0, h);
            grad.addColorStop(0, '#051937');
            grad.addColorStop(0.5, '#1a5276');
            grad.addColorStop(1, '#051937');
            backgroundCtx.fillStyle = grad;
            backgroundCtx.fillRect(0, 0, w, h);

            // Grade simples
            backgroundCtx.strokeStyle = 'rgba(79, 195, 247, 0.2)';
            backgroundCtx.lineWidth = 1;

            for (let lat = -60; lat <= 60; lat += 30) {
                const y = ((90 - lat) / 180) * h;
                backgroundCtx.beginPath();
                backgroundCtx.moveTo(0, y);
                backgroundCtx.lineTo(w, y);
                backgroundCtx.stroke();
            }

            for (let lon = -150; lon <= 150; lon += 30) {
                const x = ((lon + 180) / 360) * w;
                backgroundCtx.beginPath();
                backgroundCtx.moveTo(x, 0);
                backgroundCtx.lineTo(x, h);
                backgroundCtx.stroke();
            }

            // Equador
            backgroundCtx.strokeStyle = 'rgba(255, 193, 7, 0.4)';
            backgroundCtx.lineWidth = 2;
            backgroundCtx.beginPath();
            backgroundCtx.moveTo(0, h / 2);
            backgroundCtx.lineTo(w, h / 2);
            backgroundCtx.stroke();
        }

        function draw2D() {
            if (!ctx2D) return;

            const w = canvas2D.width;
            const h = canvas2D.height;

            // Criar cache do fundo se nao existir
            if (!backgroundCanvas || backgroundCanvas.width !== w) {
                backgroundCanvas = null;
                createBackgroundCache();
            }

            // Desenhar fundo do cache (muito rapido)
            ctx2D.drawImage(backgroundCanvas, 0, 0);

            // Continentes
            drawContinents2D();

            // Trajetoria
            if (trajectoryPoints.length > 1 && journeyData) {
                drawTrajectory2D();
            }

            // Desenhar ponto selecionado pelo usuario (SEMPRE visível, mesmo durante jornada)
            if (selectedPoint && !journeyData) {
                const pos = latLonToCanvas(selectedPoint.lat, selectedPoint.lon, canvas2D);

                // Circulo verde para o ponto selecionado
                ctx2D.fillStyle = '#00ff00';
                ctx2D.beginPath();
                ctx2D.arc(pos.x, pos.y, 10, 0, Math.PI * 2);
                ctx2D.fill();
                ctx2D.strokeStyle = 'white';
                ctx2D.lineWidth = 2;
                ctx2D.stroke();

                // Label
                ctx2D.font = 'bold 11px Arial';
                ctx2D.fillStyle = '#00ff00';
                ctx2D.fillText(`${selectedPoint.lat.toFixed(2)}°, ${selectedPoint.lon.toFixed(2)}°`, pos.x + 14, pos.y + 4);
            }

            // ================================================================
            // DURANTE A JORNADA:
            // - O PONTO permanece VISUALMENTE FIXO na posicao original
            // - Os CONTINENTES se movem (coastlines mudam conforme idade)
            // - A TRAJETORIA mostra o caminho que o ponto percorreu
            // ================================================================
            if (journeyData && trajectoryPoints.length > 0) {
                // Posicao FIXA do ponto (onde o usuario clicou - Rio de Janeiro)
                const fixedPos = latLonToCanvas(originalLat, originalLon, canvas2D);

                // ============================================================
                // DESENHAR LINHA DA TRAJETORIA (tracejada laranja)
                // Mostra o caminho que o ponto percorreu no tempo geologico
                // Para se encontrar ponto com salto grande (local nao existia)
                // ============================================================
                if (trajectoryPoints.length > 1) {
                    ctx2D.strokeStyle = 'rgba(255, 87, 34, 0.8)';
                    ctx2D.lineWidth = 3;
                    ctx2D.setLineDash([8, 4]);
                    ctx2D.beginPath();

                    let lastDrawnPt = null;
                    let trajectoryBroken = false;

                    // Desenhar trajetoria ate a idade atual
                    for (let i = 0; i < trajectoryPoints.length; i++) {
                        const pt = trajectoryPoints[i];
                        if (pt.age > currentAge) break;

                        // Verificar se ponto esta dentro dos limites da tela
                        const ptPos = latLonToCanvas(pt.lat, pt.lon, canvas2D);
                        const isOnScreen = ptPos.x >= -100 && ptPos.x <= canvas2D.width + 100 &&
                                          ptPos.y >= -100 && ptPos.y <= canvas2D.height + 100;

                        // Verificar salto muito grande
                        if (lastDrawnPt && !trajectoryBroken) {
                            const jump = Math.sqrt(
                                Math.pow(pt.lat - lastDrawnPt.lat, 2) +
                                Math.pow(pt.lon - lastDrawnPt.lon, 2)
                            );
                            if (jump > 30) {
                                // Salto muito grande - parar trajetoria aqui
                                trajectoryBroken = true;
                                // Desenhar X no ponto onde a trajetoria para
                                ctx2D.stroke();
                                ctx2D.setLineDash([]);
                                ctx2D.strokeStyle = '#ff0000';
                                ctx2D.lineWidth = 2;
                                const lastPos = latLonToCanvas(lastDrawnPt.lat, lastDrawnPt.lon, canvas2D);
                                ctx2D.beginPath();
                                ctx2D.moveTo(lastPos.x - 6, lastPos.y - 6);
                                ctx2D.lineTo(lastPos.x + 6, lastPos.y + 6);
                                ctx2D.moveTo(lastPos.x + 6, lastPos.y - 6);
                                ctx2D.lineTo(lastPos.x - 6, lastPos.y + 6);
                                ctx2D.stroke();
                                break;
                            }
                        }

                        if (isOnScreen) {
                            if (i === 0 || !lastDrawnPt) {
                                ctx2D.moveTo(ptPos.x, ptPos.y);
                            } else {
                                ctx2D.lineTo(ptPos.x, ptPos.y);
                            }
                            lastDrawnPt = pt;
                        }
                    }

                    if (!trajectoryBroken) {
                        ctx2D.stroke();
                    }
                    ctx2D.setLineDash([]);

                    // Marcar pontos da trajetoria (a cada 50 Ma)
                    ctx2D.fillStyle = 'rgba(255, 152, 0, 0.9)';
                    for (let i = 0; i < trajectoryPoints.length; i++) {
                        const pt = trajectoryPoints[i];
                        if (pt.age > currentAge) break;
                        if (pt.isEndPoint) break; // Parar em ponto final
                        if (pt.age % 50 === 0 || i === 0) {
                            const ptPos = latLonToCanvas(pt.lat, pt.lon, canvas2D);
                            if (ptPos.x >= 0 && ptPos.x <= canvas2D.width &&
                                ptPos.y >= 0 && ptPos.y <= canvas2D.height) {
                                ctx2D.beginPath();
                                ctx2D.arc(ptPos.x, ptPos.y, 4, 0, Math.PI * 2);
                                ctx2D.fill();
                            }
                        }
                    }
                }

                // ============================================================
                // MARCADOR PRINCIPAL - posicao do FOSSIL no tempo atual
                // Este ponto se move junto com o continente!
                // ============================================================
                const currentPos = getTrajectoryPosition(currentAge);
                const markerPos = latLonToCanvas(currentPos.lat, currentPos.lon, canvas2D);

                // Circulo externo (halo)
                ctx2D.fillStyle = 'rgba(255, 87, 34, 0.3)';
                ctx2D.beginPath();
                ctx2D.arc(markerPos.x, markerPos.y, 20, 0, Math.PI * 2);
                ctx2D.fill();

                // Circulo principal
                ctx2D.fillStyle = '#ff5722';
                ctx2D.beginPath();
                ctx2D.arc(markerPos.x, markerPos.y, 12, 0, Math.PI * 2);
                ctx2D.fill();
                ctx2D.strokeStyle = 'white';
                ctx2D.lineWidth = 3;
                ctx2D.stroke();

                // Icone de fossil no centro
                ctx2D.fillStyle = 'white';
                ctx2D.font = 'bold 10px Arial';
                ctx2D.textAlign = 'center';
                ctx2D.fillText('F', markerPos.x, markerPos.y + 4);
                ctx2D.textAlign = 'left';

                // ============================================================
                // INFORMACOES NO CANTO SUPERIOR ESQUERDO
                // ============================================================
                ctx2D.fillStyle = 'rgba(0, 0, 0, 0.85)';
                ctx2D.fillRect(10, 10, 280, 85);

                ctx2D.font = 'bold 14px Arial';
                ctx2D.fillStyle = '#FF5722';
                ctx2D.fillText('IDADE: ' + currentAge.toFixed(0) + ' Ma', 20, 32);

                ctx2D.font = '11px Arial';
                ctx2D.fillStyle = '#4CAF50';
                ctx2D.fillText('Continentes: ' + lastCoastlinesAge2D + ' Ma', 20, 50);

                ctx2D.fillStyle = '#64B5F6';
                ctx2D.fillText('Coordenadas: ' + currentPos.lat.toFixed(2) + ', ' + currentPos.lon.toFixed(2), 20, 66);

                ctx2D.fillStyle = '#888';
                ctx2D.fillText('Modelo: ' + ROTATION_MODELS[currentRotationModel].name, 20, 82);

                // ============================================================
                // LABEL DO PONTO COM IDADE
                // ============================================================
                ctx2D.font = 'bold 11px Arial';
                ctx2D.fillStyle = '#ff5722';
                const ageText = currentAge < 1 ? 'HOJE' : Math.round(currentAge) + ' Ma';
                ctx2D.fillText(ageText, markerPos.x + 18, markerPos.y - 8);

                ctx2D.font = '10px Arial';
                ctx2D.fillStyle = '#aaa';
                ctx2D.fillText(currentPos.lat.toFixed(1) + ', ' + currentPos.lon.toFixed(1), markerPos.x + 18, markerPos.y + 6);
            }
        }

        // Obter posicao interpolada da trajetoria para uma idade especifica
        // Trata casos onde o ponto nao existia (saltos grandes)
        function getTrajectoryPosition(age) {
            if (trajectoryPoints.length === 0) {
                return { lat: originalLat, lon: originalLon };
            }

            // Encontrar pontos adjacentes
            let lastValidPoint = trajectoryPoints[0];

            for (let i = 0; i < trajectoryPoints.length - 1; i++) {
                const p1 = trajectoryPoints[i];
                const p2 = trajectoryPoints[i + 1];

                // Verificar se ha salto muito grande (ponto nao existia)
                const jump = Math.sqrt(
                    Math.pow(p2.lat - p1.lat, 2) +
                    Math.pow(p2.lon - p1.lon, 2)
                );
                if (jump > 30) {
                    // Salto muito grande - parar no ultimo ponto valido
                    if (age >= p1.age) {
                        return { lat: p1.lat, lon: p1.lon, endOfTrajectory: true };
                    }
                }

                if (age >= p1.age && age <= p2.age) {
                    // Interpolar
                    const t = (p2.age - p1.age) > 0 ? (age - p1.age) / (p2.age - p1.age) : 0;
                    return {
                        lat: p1.lat + t * (p2.lat - p1.lat),
                        lon: p1.lon + t * (p2.lon - p1.lon)
                    };
                }

                lastValidPoint = p1;
            }

            // Se passou do ultimo, retornar o ultimo valido
            const last = trajectoryPoints[trajectoryPoints.length - 1];
            return { lat: last.lat, lon: last.lon };
        }

        // Variavel para controlar atualizacao de coastlines 2D
        let lastCoastlinesAge2D = -1;
        let isUpdatingCoastlines2D = false;

        // Carregar coastlines - VERSÃO OTIMIZADA com cache em memória
        function loadCoastlinesForAge(targetAge) {
            if (targetAge === lastCoastlinesAge2D) return;

            const model = ROTATION_MODELS[currentRotationModel];
            const cacheKey = 'coastlines_' + targetAge + '_' + model.name;

            // PRIMEIRO: verificar cache em memória (pré-carregado)
            if (coastlinesCache[cacheKey]) {
                currentCoastlines = coastlinesCache[cacheKey];
                lastCoastlinesAge2D = targetAge;
                // Log apenas a cada 100 Ma para não poluir console
                if (targetAge % 100 === 0) {
                    console.log('Coastlines CACHE HIT: ' + targetAge + ' Ma (' + currentCoastlines.length + ' features)');
                }
                return;
            } else {
                console.log('Coastlines CACHE MISS: ' + cacheKey);
            }

            // SEGUNDO: se não está no cache, carregar em background
            if (isUpdatingCoastlines2D) return;

            isUpdatingCoastlines2D = true;
            fetchCoastlines(targetAge).then(coastlines => {
                if (coastlines && coastlines.length > 0) {
                    currentCoastlines = coastlines;
                    lastCoastlinesAge2D = targetAge;
                    console.log('Coastlines carregados para ' + targetAge + ' Ma: ' + coastlines.length + ' features');
                }
                isUpdatingCoastlines2D = false;
            }).catch(e => {
                console.error('Erro ao carregar coastlines:', e);
                isUpdatingCoastlines2D = false;
            });
        }

        // Reconstruir posição do ponto para a idade atual
        function reconstructPointForAge(targetAge) {
            if (targetAge === lastReconstructedAge || isReconstructingPoint) return;
            if (!journeyData) return;

            // Para idade 0, usar coordenadas originais
            if (targetAge === 0) {
                currentReconstructedPos = { lat: originalLat, lon: originalLon };
                lastReconstructedAge = 0;
                return;
            }

            isReconstructingPoint = true;
            const model = ROTATION_MODELS[currentRotationModel];
            const modelName = model.name;

            // Chamar API reconstruct_points do GPlates
            const url = `${LOCAL_PROXY}/reconstruct/reconstruct_points/?points=${originalLon},${originalLat}&time=${targetAge}&model=${modelName}`;

            fetch(url)
                .then(r => r.ok ? r.json() : null)
                .then(data => {
                    if (data && data.coordinates && data.coordinates.length > 0) {
                        currentReconstructedPos = {
                            lat: data.coordinates[0][1],
                            lon: data.coordinates[0][0]
                        };
                        console.log(`Ponto reconstruído para ${targetAge} Ma: (${currentReconstructedPos.lat.toFixed(1)}, ${currentReconstructedPos.lon.toFixed(1)})`);
                    }
                    lastReconstructedAge = targetAge;
                    isReconstructingPoint = false;
                })
                .catch(e => {
                    console.error('Erro ao reconstruir ponto:', e);
                    isReconstructingPoint = false;
                });
        }

        function drawContinents2D() {
            // COASTLINES MUDAM conforme a idade
            const targetAge = journeyData ? Math.round(currentAge / 10) * 10 : 0;

            // Se a idade mudou, carregar novos coastlines
            if (targetAge !== lastCoastlinesAge2D) {
                const model = ROTATION_MODELS[currentRotationModel];
                const cacheKey = 'coastlines_' + targetAge + '_' + model.name;

                // Verificar cache em memoria
                if (coastlinesCache[cacheKey]) {
                    currentCoastlines = coastlinesCache[cacheKey];
                    lastCoastlinesAge2D = targetAge;
                } else {
                    // Carregar do proxy (assincrono)
                    fetchCoastlines(targetAge).then(coastlines => {
                        if (coastlines && coastlines.length > 0) {
                            currentCoastlines = coastlines;
                            lastCoastlinesAge2D = targetAge;
                        }
                    });
                }
            }

            // Desenhar coastlines atuais
            if (currentCoastlines && currentCoastlines.length > 0) {
                drawGPlatesCoastlines2D();
            } else {
                drawLocalContinentsStatic2D();
            }
        }

        // Desenhar coastlines REAIS do GPlates - ALTA QUALIDADE
        // Usa currentCoastlines que eh atualizado para cada idade geologica
        function drawGPlatesCoastlines2D() {
            const coastlinesToDraw = currentCoastlines || baseCoastlines;
            if (!coastlinesToDraw || coastlinesToDraw.length === 0) return;

            try {
                // Primeiro passo: desenhar preenchimento dos continentes
                for (const feature of coastlinesToDraw) {
                    if (!feature.coordinates || feature.coordinates.length < 3) continue;
                    if (feature.type !== 'polygon') continue;

                    const segments = splitAtDateLine(feature.coordinates);

                    for (const segment of segments) {
                        if (segment.length < 3) continue;

                        ctx2D.fillStyle = '#4CAF50';
                        ctx2D.beginPath();
                        segment.forEach((coord, idx) => {
                            const pos = latLonToCanvas(coord.lat, coord.lon, canvas2D);
                            idx === 0 ? ctx2D.moveTo(pos.x, pos.y) : ctx2D.lineTo(pos.x, pos.y);
                        });
                        ctx2D.closePath();
                        ctx2D.fill();
                    }
                }

                // Segundo passo: desenhar contornos (linhas de costa)
                for (const feature of coastlinesToDraw) {
                    if (!feature.coordinates || feature.coordinates.length < 2) continue;

                    const segments = splitAtDateLine(feature.coordinates);

                    for (const segment of segments) {
                        if (segment.length < 2) continue;

                        ctx2D.strokeStyle = '#81C784';
                        ctx2D.lineWidth = 1;
                        ctx2D.beginPath();
                        segment.forEach((coord, idx) => {
                            const pos = latLonToCanvas(coord.lat, coord.lon, canvas2D);
                            idx === 0 ? ctx2D.moveTo(pos.x, pos.y) : ctx2D.lineTo(pos.x, pos.y);
                        });
                        if (feature.type === 'polygon') ctx2D.closePath();
                        ctx2D.stroke();
                    }
                }
            } catch (e) {
                console.error('Erro ao desenhar coastlines:', e);
            }
        }

        // Dividir array de coordenadas quando cruza a linha de data internacional
        function splitAtDateLine(coordinates) {
            const segments = [];
            let currentSegment = [];

            for (let i = 0; i < coordinates.length; i++) {
                const coord = coordinates[i];

                if (currentSegment.length === 0) {
                    currentSegment.push(coord);
                } else {
                    const prevCoord = currentSegment[currentSegment.length - 1];
                    const lonDiff = Math.abs(coord.lon - prevCoord.lon);

                    if (lonDiff > 180) {
                        // Cruzou a linha de data
                        if (currentSegment.length > 0) {
                            segments.push(currentSegment);
                        }
                        currentSegment = [coord];
                    } else {
                        currentSegment.push(coord);
                    }
                }
            }
            if (currentSegment.length > 0) {
                segments.push(currentSegment);
            }

            return segments;
        }

        // Desenhar continentes ESTATICOS (sem movimento) - versao rapida
        function drawLocalContinentsStatic2D() {
            ctx2D.fillStyle = '#4CAF50';
            ctx2D.strokeStyle = '#2E7D32';
            ctx2D.lineWidth = 1;

            // Desenhar continentes
            for (const [name, data] of Object.entries(CONTINENTS)) {
                const segments = splitAtDateLine(data.outline.map(([lat, lon]) => ({lat, lon})));
                for (const segment of segments) {
                    if (segment.length < 2) continue;
                    ctx2D.beginPath();
                    segment.forEach((pt, idx) => {
                        const pos = latLonToCanvas(pt.lat, pt.lon, canvas2D);
                        idx === 0 ? ctx2D.moveTo(pos.x, pos.y) : ctx2D.lineTo(pos.x, pos.y);
                    });
                    ctx2D.closePath();
                    ctx2D.fill();
                    ctx2D.stroke();
                }
            }

            // Desenhar ilhas
            for (const [name, data] of Object.entries(ISLANDS)) {
                const segments = splitAtDateLine(data.outline.map(([lat, lon]) => ({lat, lon})));
                for (const segment of segments) {
                    if (segment.length < 2) continue;
                    ctx2D.beginPath();
                    segment.forEach((pt, idx) => {
                        const pos = latLonToCanvas(pt.lat, pt.lon, canvas2D);
                        idx === 0 ? ctx2D.moveTo(pos.x, pos.y) : ctx2D.lineTo(pos.x, pos.y);
                    });
                    ctx2D.closePath();
                    ctx2D.fill();
                    ctx2D.stroke();
                }
            }
        }

        // Fallback: desenhar contornos locais (quando GPlates nao disponivel)
        // Os continentes se movem de acordo com a idade atual
        function drawLocalContinents2D() {
            // Mapeamento de nomes de continentes (camelCase -> formato detectContinent)
            const continentNameMapping = {
                'southAmerica': 'South America',
                'africa': 'Africa',
                'northAmerica': 'North America',
                'europe': 'Europe',
                'asia': 'Asia',
                'australia': 'Australia',
                'antarctica': 'Antarctica',
                'india': 'India'
            };

            // Funcao auxiliar para desenhar poligonos - OTIMIZADA
            function drawPolygon2D(outline, color, lineWidth, continentKey) {
                // Reconstruir todos os pontos
                const points = outline.map(([lat, lon]) => {
                    const paleo = reconstructPaleoCoords(lat, lon, currentAge, continentKey);
                    return { lat: paleo.lat, lon: paleo.lon };
                });

                // Dividir em segmentos quando cruza a linha de data
                const segments = [];
                let currentSegment = [];

                for (let i = 0; i < points.length; i++) {
                    const pt = points[i];
                    if (currentSegment.length === 0) {
                        currentSegment.push(pt);
                    } else {
                        const prevPt = currentSegment[currentSegment.length - 1];
                        if (Math.abs(pt.lon - prevPt.lon) > 180) {
                            if (currentSegment.length > 0) segments.push(currentSegment);
                            currentSegment = [pt];
                        } else {
                            currentSegment.push(pt);
                        }
                    }
                }
                if (currentSegment.length > 0) segments.push(currentSegment);

                // Desenhar cada segmento - SEM sombras para performance
                ctx2D.fillStyle = color;
                ctx2D.strokeStyle = '#2E7D32';
                ctx2D.lineWidth = 1;

                for (const segment of segments) {
                    if (segment.length < 2) continue;
                    ctx2D.beginPath();
                    segment.forEach((pt, idx) => {
                        const pos = latLonToCanvas(pt.lat, pt.lon, canvas2D);
                        idx === 0 ? ctx2D.moveTo(pos.x, pos.y) : ctx2D.lineTo(pos.x, pos.y);
                    });
                    ctx2D.closePath();
                    ctx2D.fill();
                    ctx2D.stroke();
                }
            }

            // Usar cor verde uniforme para todos os continentes (melhor visualizacao)
            const continentColor = '#4CAF50';  // Verde

            for (const [name, data] of Object.entries(CONTINENTS)) {
                const continentKey = continentNameMapping[name] || name;
                drawPolygon2D(data.outline, continentColor, 2, continentKey);
            }

            // Desenhar ilhas
            const islandContinentMapping = {
                'cuba': 'North America',
                'hispaniola': 'North America',
                'jamaica': 'North America',
                'puertoRico': 'North America',
                'japanHonshu': 'Asia',
                'japanHokkaido': 'Asia',
                'japanKyushu': 'Asia',
                'sumatra': 'Asia',
                'borneo': 'Asia',
                'java': 'Asia',
                'luzon': 'Asia',
                'mindanao': 'Asia',
                'madagascar': 'Africa',
                'nzNorth': 'Australia',
                'nzSouth': 'Australia',
                'graBretanha': 'Europe',
                'irlanda': 'Europe',
                'islandia': 'Europe',
                'sriLanka': 'India',
                'taiwan': 'Asia',
                'novaGuine': 'Australia',
                'crimeia': 'Europe',
                'sicilia': 'Europe',
                'sardenha': 'Europe',
                'corsega': 'Europe',
                'mallorca': 'Europe',
                'chipre': 'Europe',
                'creta': 'Europe',
                'hawaii': 'North America',
                'sulawesi': 'Asia',
                'hainan': 'Asia',
                'sakhalin': 'Asia',
                'groenlandiaSul': 'North America'
            };

            // Ilhas apenas no presente (idade 0) para performance
            if (currentAge === 0) {
                for (const [name, data] of Object.entries(ISLANDS)) {
                    const continentKey = islandContinentMapping[name] || 'Ocean';
                    drawPolygon2D(data.outline, continentColor, 1.5, continentKey);
                }
            }

            // Desenhar mares interiores e lagos (como "buracos" nos continentes)
            const WATER_BODIES = {
                // Mar Caspio
                caspio: {
                    continent: 'Europe',
                    outline: [
                        [47.0,51.5],[46.0,50.0],[45.0,49.0],[44.0,48.5],[43.0,48.0],
                        [42.0,48.5],[41.0,49.5],[40.0,50.0],[39.0,50.5],[38.0,51.5],
                        [37.5,52.5],[38.0,53.5],[39.0,54.0],[40.0,53.5],[41.0,52.5],
                        [42.5,51.5],[44.0,51.0],[45.5,51.5],[47.0,51.5]
                    ]
                },
                // Mar Negro
                marNegro: {
                    continent: 'Europe',
                    outline: [
                        [46.5,31.0],[46.0,32.0],[45.5,33.0],[45.0,34.5],[44.5,35.5],
                        [44.0,36.5],[43.5,38.0],[43.0,39.5],[42.0,41.0],[41.5,41.0],
                        [41.0,40.0],[41.5,38.5],[42.0,37.0],[42.5,35.0],[43.0,33.5],
                        [43.5,32.0],[44.5,31.0],[45.5,30.5],[46.5,31.0]
                    ]
                },
                // Mar de Aral (pequeno)
                aral: {
                    continent: 'Asia',
                    outline: [
                        [46.0,59.0],[45.5,59.5],[45.0,60.0],[44.5,60.5],[44.0,60.0],
                        [44.5,59.0],[45.5,58.5],[46.0,59.0]
                    ]
                },
                // Grandes Lagos (America do Norte)
                lagoSuperior: {
                    continent: 'North America',
                    outline: [
                        [49.0,-88.0],[48.5,-87.0],[48.0,-86.0],[47.5,-85.0],[47.0,-84.5],
                        [46.5,-85.0],[46.5,-86.0],[47.0,-87.5],[47.5,-89.0],[48.0,-89.5],
                        [48.5,-88.5],[49.0,-88.0]
                    ]
                },
                lagoMichigan: {
                    continent: 'North America',
                    outline: [
                        [46.0,-86.5],[45.5,-86.0],[45.0,-86.5],[44.0,-87.0],[43.0,-87.5],
                        [42.0,-87.0],[42.5,-86.5],[43.5,-86.0],[44.5,-85.5],[45.5,-85.5],
                        [46.0,-86.5]
                    ]
                },
                lagoHuron: {
                    continent: 'North America',
                    outline: [
                        [46.0,-84.0],[45.5,-83.0],[45.0,-82.5],[44.5,-82.0],[44.0,-82.5],
                        [43.5,-82.0],[44.0,-81.5],[44.5,-81.5],[45.0,-82.0],[45.5,-83.0],
                        [46.0,-84.0]
                    ]
                },
                lagoErie: {
                    continent: 'North America',
                    outline: [
                        [42.8,-79.0],[42.5,-80.0],[42.2,-81.0],[42.0,-82.0],[41.5,-82.5],
                        [41.5,-81.5],[42.0,-80.5],[42.5,-79.5],[42.8,-79.0]
                    ]
                },
                lagoOntario: {
                    continent: 'North America',
                    outline: [
                        [44.0,-77.0],[43.8,-77.5],[43.5,-78.0],[43.3,-79.0],[43.5,-79.5],
                        [44.0,-78.5],[44.2,-77.5],[44.0,-77.0]
                    ]
                },
                // Lago Baikal
                baikal: {
                    continent: 'Asia',
                    outline: [
                        [55.5,109.0],[54.5,108.5],[53.5,108.0],[52.5,107.5],[52.0,106.5],
                        [52.5,106.0],[53.5,106.5],[54.5,107.5],[55.5,109.0]
                    ]
                },
                // Lago Victoria
                victoria: {
                    continent: 'Africa',
                    outline: [
                        [0.5,33.0],[0.0,33.5],[-0.5,34.0],[-1.0,34.5],[-1.5,34.0],
                        [-2.0,33.5],[-2.5,33.0],[-2.0,32.5],[-1.0,32.5],[0.0,32.5],
                        [0.5,33.0]
                    ]
                },
                // Lago Tanganica
                tanganica: {
                    continent: 'Africa',
                    outline: [
                        [-3.5,29.5],[-4.5,29.5],[-5.5,29.5],[-6.5,30.0],[-7.5,30.5],
                        [-8.0,30.5],[-8.0,30.0],[-7.0,29.5],[-6.0,29.0],[-5.0,29.0],
                        [-4.0,29.0],[-3.5,29.5]
                    ]
                },
                // Lago Malawi
                malawi: {
                    continent: 'Africa',
                    outline: [
                        [-9.5,34.0],[-10.5,34.5],[-11.5,34.5],[-12.5,34.5],[-13.5,35.0],
                        [-14.0,35.0],[-14.0,34.5],[-13.0,34.0],[-12.0,34.0],[-11.0,34.0],
                        [-10.0,33.5],[-9.5,34.0]
                    ]
                },
                // Mar Baltico
                baltico: {
                    continent: 'Europe',
                    outline: [
                        [66.0,24.0],[65.0,25.0],[64.0,24.0],[63.0,22.0],[62.0,21.0],
                        [61.0,21.0],[60.0,20.0],[59.5,19.0],[59.0,18.0],[58.5,17.0],
                        [57.5,16.5],[56.5,16.0],[55.5,14.0],[54.5,13.0],[54.0,12.0],
                        [54.5,10.5],[55.5,11.0],[56.0,12.5],[57.0,14.0],[58.0,16.0],
                        [59.0,17.5],[60.0,19.5],[61.0,21.0],[62.5,21.5],[64.0,23.0],
                        [65.5,24.0],[66.0,24.0]
                    ]
                },
                // Golfo de Botnia
                golfoBotnia: {
                    continent: 'Europe',
                    outline: [
                        [66.0,24.0],[65.0,23.5],[64.0,22.0],[63.5,20.5],[63.0,19.5],
                        [62.5,18.5],[63.0,18.0],[63.5,19.0],[64.5,20.5],[65.5,22.0],
                        [66.0,24.0]
                    ]
                },
                // Mar Vermelho
                marVermelho: {
                    continent: 'Africa',
                    outline: [
                        [30.0,32.5],[28.0,33.5],[26.0,34.5],[24.0,35.5],[22.0,37.0],
                        [20.0,38.5],[18.0,40.0],[16.0,41.0],[14.0,42.5],[12.5,43.5],
                        [13.0,43.0],[15.0,41.5],[17.0,40.0],[19.0,38.0],[21.0,36.5],
                        [23.0,35.0],[25.0,34.0],[27.0,33.5],[29.0,33.0],[30.0,32.5]
                    ]
                },
                // Golfo Persico
                golfoPersico: {
                    continent: 'Asia',
                    outline: [
                        [30.0,48.5],[29.0,49.5],[28.0,50.0],[27.0,51.0],[26.0,52.0],
                        [25.0,52.5],[24.5,54.0],[25.5,56.0],[26.5,56.5],[27.5,56.5],
                        [28.5,55.0],[29.5,52.0],[30.0,50.0],[30.0,48.5]
                    ]
                },
                // Hudson Bay
                hudsonBay: {
                    continent: 'North America',
                    outline: [
                        [63.0,-95.0],[62.0,-92.0],[61.0,-89.0],[60.0,-86.0],[59.0,-83.0],
                        [58.0,-80.0],[57.0,-78.0],[56.0,-79.0],[55.0,-82.0],[54.0,-85.0],
                        [55.0,-88.0],[56.5,-91.0],[58.0,-93.0],[60.0,-94.5],[62.0,-95.0],
                        [63.0,-95.0]
                    ]
                }
            };

            // Cor do oceano para os corpos d'agua
            const oceanColor = '#0d3b66';

            // Funcao para desenhar corpos d'agua
            function drawWaterBody(outline, continentKey) {
                const points = outline.map(([lat, lon]) => {
                    const paleo = reconstructPaleoCoords(lat, lon, currentAge, continentKey);
                    return { lat: paleo.lat, lon: paleo.lon };
                });

                // Verificar segmentos para linha de data
                const segments = [];
                let currentSegment = [];
                for (let i = 0; i < points.length; i++) {
                    const pt = points[i];
                    if (currentSegment.length === 0) {
                        currentSegment.push(pt);
                    } else {
                        const prevPt = currentSegment[currentSegment.length - 1];
                        if (Math.abs(pt.lon - prevPt.lon) > 180) {
                            if (currentSegment.length > 0) segments.push(currentSegment);
                            currentSegment = [pt];
                        } else {
                            currentSegment.push(pt);
                        }
                    }
                }
                if (currentSegment.length > 0) segments.push(currentSegment);

                // Desenhar
                ctx2D.fillStyle = oceanColor;
                ctx2D.strokeStyle = 'rgba(79, 195, 247, 0.5)';
                ctx2D.lineWidth = 1;

                for (const segment of segments) {
                    if (segment.length < 3) continue;
                    ctx2D.beginPath();
                    segment.forEach((pt, idx) => {
                        const pos = latLonToCanvas(pt.lat, pt.lon, canvas2D);
                        idx === 0 ? ctx2D.moveTo(pos.x, pos.y) : ctx2D.lineTo(pos.x, pos.y);
                    });
                    ctx2D.closePath();
                    ctx2D.fill();
                    ctx2D.stroke();
                }
            }

            // Desenhar corpos d'agua apenas no presente (idade 0) para performance
            if (currentAge === 0) {
                for (const [name, data] of Object.entries(WATER_BODIES)) {
                    drawWaterBody(data.outline, data.continent);
                }
            }
        }

        function drawTrajectory2D() {
            if (!journeyData || trajectoryPoints.length < 2) return;

            // ============================================================
            // DESENHAR LINHA DA TRAJETÓRIA (tracejada)
            // ============================================================
            ctx2D.strokeStyle = 'rgba(255, 87, 34, 0.6)';
            ctx2D.lineWidth = 2;
            ctx2D.setLineDash([5, 5]);
            ctx2D.beginPath();

            for (let i = 0; i < trajectoryPoints.length; i++) {
                const pt = trajectoryPoints[i];
                if (pt.age > currentAge) break;

                const pos = latLonToCanvas(pt.lat, pt.lon, canvas2D);
                if (i === 0) {
                    ctx2D.moveTo(pos.x, pos.y);
                } else {
                    ctx2D.lineTo(pos.x, pos.y);
                }
            }
            ctx2D.stroke();
            ctx2D.setLineDash([]);

            // Nota: O marcador é desenhado em draw2D() agora
            return; // O resto foi movido para draw2D()

            // Código legado abaixo (não executado)
            const origPos = latLonToCanvas(originalLat, originalLon, canvas2D);
            ctx2D.fillStyle = '#2196f3';
            ctx2D.beginPath();
            ctx2D.arc(origPos.x, origPos.y, 8, 0, Math.PI * 2);
            ctx2D.fill();
            ctx2D.strokeStyle = 'white';
            ctx2D.lineWidth = 2;
            ctx2D.stroke();

            ctx2D.font = 'bold 10px Arial';
            ctx2D.fillStyle = '#2196f3';
            ctx2D.fillText('HOJE', origPos.x + 12, origPos.y + 4);

            // Desenhar envelope de incerteza
            const uncertainty = calculateUncertainty(currentAge, displayLat, displayLon);
            if (uncertainty && uncertainty.semiMajor > 0) {
                const scale = canvas2D.width / 360;
                const kmPerDeg = 111;
                const majorPx = (uncertainty.semiMajor / kmPerDeg) * scale;
                const minorPx = (uncertainty.semiMinor / kmPerDeg) * scale;

                ctx2D.save();
                ctx2D.translate(displayPos.x, displayPos.y);
                ctx2D.rotate(uncertainty.rotation * Math.PI / 180);

                ctx2D.fillStyle = 'rgba(255, 152, 0, 0.3)';
                ctx2D.beginPath();
                ctx2D.ellipse(0, 0, majorPx, minorPx, 0, 0, Math.PI * 2);
                ctx2D.fill();

                ctx2D.strokeStyle = '#ff9800';
                ctx2D.lineWidth = 2;
                ctx2D.beginPath();
                ctx2D.ellipse(0, 0, majorPx, minorPx, 0, 0, Math.PI * 2);
                ctx2D.stroke();

                ctx2D.restore();
            }

            // ============================================================
            // MARCADOR DO FÓSSIL (laranja) - posição reconstruída
            // ============================================================
            ctx2D.fillStyle = '#ff5722';
            ctx2D.beginPath();
            ctx2D.arc(displayPos.x, displayPos.y, 10, 0, Math.PI * 2);
            ctx2D.fill();
            ctx2D.strokeStyle = 'white';
            ctx2D.lineWidth = 2;
            ctx2D.stroke();

            // Label
            ctx2D.font = 'bold 12px Arial';
            ctx2D.fillStyle = '#ff5722';
            const ageLabel = currentAge < 1 ? 'HOJE' : currentAge.toFixed(0) + ' Ma';
            ctx2D.fillText(ageLabel, displayPos.x + 14, displayPos.y + 4);
        }

        // ================================================================
        // CONTROLE DA JORNADA
        // ================================================================

        function startJourney(specimen) {
            journeyData = specimen;
            currentProgress = 0;
            isPlaying = false;
            currentAge = 0;
            lastContinentAge = -1;  // Forcar redesenho dos continentes
            lastCoastlinesAge2D = -1;  // Forçar recarregar coastlines
            lastReconstructedAge = -1;  // Forçar reconstruir ponto
            currentReconstructedPos = null;  // Resetar posição reconstruída

            // Atualizar modelo de rotacao se especificado
            if (specimen.rotation_model && ROTATION_MODELS[specimen.rotation_model]) {
                // Se modelo mudou, limpar cache de coastlines em memoria
                if (currentRotationModel !== specimen.rotation_model) {
                    console.log('Modelo mudou de ' + currentRotationModel + ' para ' + specimen.rotation_model + ' - limpando cache');
                    // NAO limpar coastlinesCache pois ele usa chave com nome do modelo
                    // Apenas resetar variaveis de controle
                    currentCoastlines = null;
                    lastCoastlinesAge2D = -1;
                }
                currentRotationModel = specimen.rotation_model;
                const model = ROTATION_MODELS[specimen.rotation_model];
                document.getElementById('rotation-model-name').textContent = model.name;
                document.getElementById('model-coverage').textContent = `0 - ${model.maxAge} Ma`;
                document.getElementById('model-reference').textContent = model.description;
            }

            // Ocultar tela de espera
            document.getElementById('waiting').classList.add('hidden');

            // Reset velocidade e pausa
            isPaused = false;
            document.getElementById('pause-btn').textContent = '⏸';
            document.getElementById('pause-btn').style.background = '';

            // Atualizar UI
            const typeNames = {
                'FOR': 'Foraminifero',
                'OST': 'Ostracoda',
                'RAD': 'Radiolario',
                'CON': 'Conodonte',
                'DIA': 'Diatomacea',
                'ACR': 'Acritarco',
                'QUI': 'Quitinozoario'
            };
            document.getElementById('specimen-type').textContent = typeNames[specimen.specimen_type] || specimen.specimen_type;
            document.getElementById('current-coords').textContent = `${specimen.latitude.toFixed(2)}°, ${specimen.longitude.toFixed(2)}°`;
            document.getElementById('max-age-label').textContent = specimen.fad_ma.toFixed(0) + ' Ma';

            // ============================================================
            // GUARDAR COORDENADAS ORIGINAIS (onde o fossil foi encontrado HOJE)
            // Este ponto FICA FIXO durante toda a animacao!
            // ============================================================
            originalLat = specimen.latitude;
            originalLon = specimen.longitude;

            // Remover marcador verde de selecao
            if (clickMarker3D) {
                scene.remove(clickMarker3D);
                clickMarker3D = null;
            }

            // Remover marcadores anteriores da jornada
            if (presentMarker3D) {
                scene.remove(presentMarker3D);
                presentMarker3D = null;
            }
            if (paleoMarker3D) {
                scene.remove(paleoMarker3D);
                paleoMarker3D = null;
            }

            // ============================================================
            // CONCEITO CORRETO:
            // - Coastlines MUDAM conforme a idade (GPlates reconstruído)
            // - Ponto SE MOVE junto com o continente (via API reconstruct_points)
            // - Trajetória é gerada ANTES de iniciar a animação
            // ============================================================

            // Mostrar controles
            document.getElementById('info-panel').classList.remove('hidden');
            document.getElementById('trajectory-legend').classList.remove('hidden');
            document.getElementById('timeline').classList.remove('hidden');

            // Configurar timeline
            setupTimeline(specimen.fad_ma);

            // ============================================================
            // MOSTRAR LOADING OVERLAY
            // ============================================================
            const loadingOverlay = document.getElementById('loading-overlay');
            const loadingText = document.getElementById('loading-text');
            const loadingStatus = document.getElementById('loading-status');
            const loadingProgressBar = document.getElementById('loading-progress-bar');

            loadingOverlay.classList.remove('hidden');
            loadingText.textContent = 'Preparando Jornada...';
            loadingStatus.textContent = 'Carregando trajetoria do GPlates';
            loadingProgressBar.style.width = '10%';

            const maxAge = specimen.fad_ma;

            // ============================================================
            // CARREGAR TRAJETORIA (coastlines sob demanda do cache)
            // ============================================================
            loadingStatus.textContent = 'Calculando trajetoria (' + Math.ceil(maxAge/10) + ' pontos)...';
            loadingProgressBar.style.width = '20%';

            generateFullTrajectoryAsync(specimen.latitude, specimen.longitude, maxAge)
                .then(() => {
                    loadingStatus.textContent = 'Trajetoria pronta! Carregando continentes...';
                    loadingProgressBar.style.width = '70%';

                    // Carregar coastlines inicial
                    return fetchCoastlines(0);
                })
                .then((coastlines) => {
                    loadingProgressBar.style.width = '90%';

                    // Configurar coastlines iniciais
                    if (coastlines) {
                        currentCoastlines = coastlines;
                        lastCoastlinesAge2D = 0;
                    }

                    // Filtrar pontos invalidos
                    filterInvalidTrajectoryPoints();

                    loadingStatus.textContent = 'Iniciando simulacao!';
                    loadingProgressBar.style.width = '100%';

                    // Pequeno delay para mostrar 100%
                    setTimeout(() => {
                        loadingOverlay.classList.add('hidden');
                        isPlaying = true;
                        console.log('Jornada iniciada! ' + trajectoryPoints.length + ' pontos');
                    }, 300);
                })
                .catch(err => {
                    console.error('Erro:', err);
                    loadingOverlay.classList.add('hidden');
                    trajectoryPoints = [{ age: 0, lat: specimen.latitude, lon: specimen.longitude }];
                    isPlaying = true;
                });
        }

        // Filtrar pontos invalidos da trajetoria
        // (pontos que nao existiam, coordenadas fora dos limites, saltos muito grandes)
        function filterInvalidTrajectoryPoints() {
            if (trajectoryPoints.length < 2) return;

            const validPoints = [trajectoryPoints[0]]; // Primeiro ponto sempre valido
            let lastValidPoint = trajectoryPoints[0];

            for (let i = 1; i < trajectoryPoints.length; i++) {
                const pt = trajectoryPoints[i];

                // Verificar se coordenadas estao dentro dos limites
                if (pt.lat < -90 || pt.lat > 90 || pt.lon < -180 || pt.lon > 180) {
                    console.log('Ponto invalido (fora dos limites): ' + pt.age + ' Ma');
                    continue;
                }

                // Verificar salto muito grande (> 50 graus em 10 Ma indica ponto inexistente)
                const latDiff = Math.abs(pt.lat - lastValidPoint.lat);
                const lonDiff = Math.abs(pt.lon - lastValidPoint.lon);
                const ageDiff = pt.age - lastValidPoint.age;

                // Se o salto for maior que 30 graus por 10 Ma, provavelmente o ponto nao existia
                const maxJumpPerMa = 3; // graus por Ma
                const expectedMaxJump = maxJumpPerMa * ageDiff;

                if (latDiff > expectedMaxJump || lonDiff > expectedMaxJump) {
                    console.log('Ponto com salto grande: ' + pt.age + ' Ma (lat: ' + latDiff.toFixed(1) + ', lon: ' + lonDiff.toFixed(1) + ')');
                    // Marcar como ponto final da trajetoria valida
                    pt.isEndPoint = true;
                }

                validPoints.push(pt);
                lastValidPoint = pt;
            }

            trajectoryPoints = validPoints;
            console.log('Pontos validos apos filtro: ' + trajectoryPoints.length);
        }

        // ============================================================
        // ENCONTRAR PONTO DE ANCORAGEM NA PLACA MAIS PROXIMA
        // Quando o ponto está no mar, encontra o ponto mais próximo
        // em uma placa tectônica para usar como referência
        // ============================================================
        async function findAnchorPoint(lat, lon, modelName) {
            // Testar se o ponto original se move com reconstrução
            const testAge = 50; // Testar com 50 Ma
            const testUrl = `${LOCAL_PROXY}/reconstruct/reconstruct_points/?points=${lon},${lat}&time=${testAge}&model=${modelName}`;

            try {
                const response = await fetch(testUrl);
                if (response.ok) {
                    const data = await response.json();
                    if (data && data.coordinates && data.coordinates.length > 0) {
                        const reconLat = data.coordinates[0][1];
                        const reconLon = data.coordinates[0][0];

                        // Calcular distância do movimento
                        const movement = Math.sqrt(
                            Math.pow(reconLat - lat, 2) +
                            Math.pow(reconLon - lon, 2)
                        );

                        // Se moveu mais de 0.5 graus, ponto está em uma placa
                        if (movement > 0.5) {
                            console.log('Ponto está em placa tectônica (movimento: ' + movement.toFixed(2) + '°)');
                            return null; // Não precisa de ancoragem
                        }
                    }
                }
            } catch (e) {
                console.log('Erro ao testar ponto:', e);
            }

            console.log('Ponto no mar detectado - buscando ancoragem...');

            // Ponto não se moveu - está no mar
            // Buscar pontos de ancoragem em várias direções
            const searchDistances = [1, 2, 3, 5, 8, 10, 15, 20]; // graus
            const searchAngles = [0, 45, 90, 135, 180, 225, 270, 315]; // 8 direções

            let bestAnchor = null;
            let bestMovement = 0;

            for (const dist of searchDistances) {
                const testPromises = searchAngles.map(async (angle) => {
                    const rad = angle * Math.PI / 180;
                    const testLat = Math.max(-85, Math.min(85, lat + dist * Math.cos(rad)));
                    const testLon = lon + dist * Math.sin(rad);

                    const url = `${LOCAL_PROXY}/reconstruct/reconstruct_points/?points=${testLon},${testLat}&time=${testAge}&model=${modelName}`;

                    try {
                        const r = await fetch(url);
                        if (r.ok) {
                            const d = await r.json();
                            if (d && d.coordinates && d.coordinates.length > 0) {
                                const rLat = d.coordinates[0][1];
                                const rLon = d.coordinates[0][0];
                                const mov = Math.sqrt(
                                    Math.pow(rLat - testLat, 2) +
                                    Math.pow(rLon - testLon, 2)
                                );
                                return { lat: testLat, lon: testLon, movement: mov, dist: dist };
                            }
                        }
                    } catch (e) {}
                    return null;
                });

                const results = await Promise.all(testPromises);

                for (const r of results) {
                    if (r && r.movement > 0.5 && r.movement > bestMovement) {
                        bestAnchor = r;
                        bestMovement = r.movement;
                    }
                }

                // Se encontrou um bom ponto de ancoragem, parar
                if (bestAnchor && bestMovement > 2) {
                    break;
                }
            }

            if (bestAnchor) {
                console.log('Ponto de ancoragem encontrado: ' + bestAnchor.lat.toFixed(2) + ', ' + bestAnchor.lon.toFixed(2) + ' (dist: ' + bestAnchor.dist + '°, mov: ' + bestMovement.toFixed(2) + '°)');
                return {
                    anchorLat: bestAnchor.lat,
                    anchorLon: bestAnchor.lon,
                    offsetLat: lat - bestAnchor.lat,
                    offsetLon: lon - bestAnchor.lon
                };
            }

            console.log('Nenhum ponto de ancoragem encontrado - usando ponto original');
            return null;
        }

        // Gerar trajetória completa - versão async OTIMIZADA
        async function generateFullTrajectoryAsync(lat, lon, maxAge) {
            trajectoryPoints = [];
            const model = ROTATION_MODELS[currentRotationModel];
            const modelName = model.name;

            // Step maior para ser mais rapido (20 Ma = ~15 pontos para 300 Ma)
            let step = 20;
            if (maxAge < 20) step = 5;
            else if (maxAge < 100) step = 10;

            console.log('Buscando ' + Math.ceil(maxAge/step) + ' pontos da API GPlates...');

            // ============================================================
            // VERIFICAR SE PONTO PRECISA DE ANCORAGEM (está no mar)
            // ============================================================
            const anchor = await findAnchorPoint(lat, lon, modelName);

            // Coordenadas a usar para reconstrução
            const reconLat = anchor ? anchor.anchorLat : lat;
            const reconLon = anchor ? anchor.anchorLon : lon;

            if (anchor) {
                console.log('Usando ancoragem - offset: ' + anchor.offsetLat.toFixed(2) + ', ' + anchor.offsetLon.toFixed(2));
            }

            // Ponto inicial (sempre usa coordenadas originais do usuário)
            trajectoryPoints.push({ age: 0, lat: lat, lon: lon });

            // Gerar lista de idades
            const ages = [];
            for (let age = step; age <= maxAge; age += step) {
                ages.push(age);
            }

            // Fazer TODAS as chamadas em paralelo (usando ponto de ancoragem se existir)
            const promises = ages.map(age => {
                const url = `${LOCAL_PROXY}/reconstruct/reconstruct_points/?points=${reconLon},${reconLat}&time=${age}&model=${modelName}`;
                return fetch(url)
                    .then(r => r.ok ? r.json() : null)
                    .then(data => {
                        if (data && data.coordinates && data.coordinates.length > 0) {
                            let resultLat = data.coordinates[0][1];
                            let resultLon = data.coordinates[0][0];

                            // Aplicar offset se usando ancoragem
                            if (anchor) {
                                resultLat += anchor.offsetLat;
                                resultLon += anchor.offsetLon;
                            }

                            return { age, lat: resultLat, lon: resultLon };
                        }
                        return { age, lat: lat, lon: lon }; // fallback
                    })
                    .catch(() => ({ age, lat: lat, lon: lon }));
            });

            // ESPERAR todas as respostas
            const results = await Promise.all(promises);

            // Ordenar por idade e adicionar à trajetória
            results.sort((a, b) => a.age - b.age);
            for (const pt of results) {
                trajectoryPoints.push(pt);
            }

            console.log('Trajetória gerada: ' + trajectoryPoints.length + ' pontos');
            // Log alguns pontos para debug
            if (trajectoryPoints.length > 0) {
                const first = trajectoryPoints[0];
                const last = trajectoryPoints[trajectoryPoints.length - 1];
                console.log('  Início (0 Ma): ' + first.lat.toFixed(1) + ', ' + first.lon.toFixed(1));
                console.log('  Fim (' + last.age + ' Ma): ' + last.lat.toFixed(1) + ', ' + last.lon.toFixed(1));
            }

            return trajectoryPoints;
        }
        // Variável para controlar capturas de screenshot
        let lastScreenshotAge = -1;
        const screenshotAges = [0, 10, 20, 50, 100, 150, 200, 300, 400, 500]; // Idades para capturar

        function stopJourney() {
            isPlaying = false;
            isPaused = false;
            journeyData = null;
            trajectoryPoints = [];

            // Remover marcador verde de selecao
            if (clickMarker3D) {
                scene.remove(clickMarker3D);
                clickMarker3D = null;
            }

            // Remover elipse de incerteza
            if (uncertaintyMesh3D) {
                scene.remove(uncertaintyMesh3D);
                uncertaintyMesh3D = null;
            }

            // Remover marcadores de jornada
            if (presentMarker3D) {
                scene.remove(presentMarker3D);
                presentMarker3D = null;
            }
            if (paleoMarker3D) {
                scene.remove(paleoMarker3D);
                paleoMarker3D = null;
            }

            // Remover trajetoria 3D
            const traj = scene.getObjectByName('trajectory');
            if (traj) scene.remove(traj);
            const markers = scene.getObjectByName('trajectory-markers');
            if (markers) scene.remove(markers);

            // Ocultar controles da jornada (speed-control permanece visivel)
            document.getElementById('info-panel').classList.add('hidden');
            document.getElementById('trajectory-legend').classList.add('hidden');
            document.getElementById('timeline').classList.add('hidden');

            // Redesenhar 2D para limpar trajetoria
            if (currentView === '2d' && ctx2D) {
                draw2D();
            }
        }

        // Resetar a visualizacao para o estado inicial
        function resetView() {
            // Parar jornada
            isPlaying = false;
            isPaused = false;
            currentProgress = 0;
            currentAge = 0;
            journeyData = null;
            trajectoryPoints = [];

            // Remover marcador verde de selecao
            if (clickMarker3D) {
                scene.remove(clickMarker3D);
                clickMarker3D = null;
            }

            // Remover marcadores
            if (presentMarker3D) {
                scene.remove(presentMarker3D);
                presentMarker3D = null;
            }
            if (paleoMarker3D) {
                scene.remove(paleoMarker3D);
                paleoMarker3D = null;
            }

            // Remover elipse de incerteza
            if (uncertaintyMesh3D) {
                scene.remove(uncertaintyMesh3D);
                uncertaintyMesh3D = null;
            }

            // Remover trajetoria
            const traj = scene.getObjectByName('trajectory');
            if (traj) scene.remove(traj);
            const markers = scene.getObjectByName('trajectory-markers');
            if (markers) scene.remove(markers);

            // Resetar continentes para idade 0
            lastContinentAge = -1;  // Forcar redesenho
            updateContinentPositions3D(0);

            // Resetar camera
            camera.position.set(0, 0, 18);
            controls.target.set(0, 0, 0);
            controls.update();

            // Ocultar paineis
            document.getElementById('info-panel').classList.add('hidden');
            document.getElementById('trajectory-legend').classList.add('hidden');

            // Resetar timeline
            const targetMarker = document.getElementById('timeline-target-marker');
            if (targetMarker) targetMarker.style.display = 'none';
            const animMarker = document.getElementById('timeline-marker');
            if (animMarker) animMarker.style.display = 'none';

            // Redesenhar 2D se ativo
            if (currentView === '2d' && ctx2D) {
                draw2D();
            }

            console.log('Visualizacao resetada para estado inicial');
        }
        window.resetView = resetView;

        function setupTimeline(maxAge) {
            // A escala de tempo geologico ja esta fixa no HTML
            // Apenas atualiza o label de idade maxima e mostra o marcador de animacao
            document.getElementById('max-age-label').textContent = maxAge.toFixed(0) + ' Ma';

            // Mostrar marcador de animacao (vermelho)
            const animMarker = document.getElementById('timeline-marker');
            if (animMarker) {
                animMarker.style.display = 'block';
                animMarker.style.left = '0%';
            }

            // Ocultar marcador de destino durante animacao
            const targetMarker = document.getElementById('timeline-target-marker');
            if (targetMarker) {
                targetMarker.style.display = 'none';
            }
        }

        function updateCurrentPosition() {
            if (!journeyData) return;

            // Calcular posicao inicial
            currentAge = 0;
            const currentLat = originalLat;
            const currentLon = originalLon;

            // Atualizar UI
            document.getElementById('current-age').textContent = '0.0';
            document.getElementById('current-period').textContent = getPeriodName(0);
            document.getElementById('paleo-coords').textContent = `${currentLat.toFixed(2)}°, ${currentLon.toFixed(2)}°`;
            document.getElementById('displacement').textContent = '0 km';

            // Incerteza inicial
            const unc = calculateUncertainty(0, currentLat, currentLon);
            document.getElementById('unc-major').textContent = unc.semiMajor.toFixed(0);
            document.getElementById('unc-minor').textContent = unc.semiMinor.toFixed(0);
            document.getElementById('unc-angle').textContent = unc.rotation.toFixed(1) + '°';
            document.getElementById('unc-chi2').textContent = unc.chi2.toFixed(2);

            const badge = document.getElementById('quality-badge');
            badge.className = 'quality-badge quality-' + unc.quality;
            badge.textContent = unc.quality === 'high' ? 'ALTA CONFIANÇA' :
                               unc.quality === 'medium' ? 'CONFIANÇA MÉDIA' : 'BAIXA CONFIANÇA';

            // Timeline marker
            document.getElementById('timeline-marker').style.left = '0%';

            // Atualizar posicoes dos continentes no 3D
            updateContinentPositions3D(0);

            // Marcador inicial
            if (!paleoMarker3D) {
                paleoMarker3D = createMarker3D(currentLat, currentLon, 0xff5722, true);
                paleoMarker3D.name = 'fossil-marker';
                scene.add(paleoMarker3D);
            }

            // Atualizar elipse de incerteza
            createUncertaintyEllipse3D(currentLat, currentLon, unc);

            // Redesenhar 2D
            if (currentView === '2d') draw2D();
        }

        // ================================================================
        // ANIMACAO
        // ================================================================

        let lastFrameTime = 0;
        let animationInitialized = false;

        function animate(timestamp) {
            requestAnimationFrame(animate);

            // Inicializar lastFrameTime no primeiro frame para evitar deltaTime gigante
            if (!animationInitialized) {
                lastFrameTime = timestamp;
                animationInitialized = true;
                return;
            }

            // Calcular delta time para animacao suave independente de FPS
            const deltaTime = Math.min(timestamp - lastFrameTime, 100); // Max 100ms para evitar saltos
            lastFrameTime = timestamp;

            if (isPlaying && journeyData && !isPaused) {
                // Velocidade baseada em tempo real (nao em frames)
                // Com simulationSpeed = 1: viagem completa em ~120 segundos (2 min)
                // Com simulationSpeed = 5: viagem completa em ~24 segundos
                // Com simulationSpeed = 10: viagem completa em ~12 segundos
                // Com simulationSpeed = 50: viagem completa em ~2.4 segundos
                const progressPerMs = (simulationSpeed / 120000);
                currentProgress += progressPerMs * deltaTime;

                if (currentProgress >= 1) {
                    currentProgress = 1;
                    isPlaying = false;
                }

                // Atualizar posicao continuamente
                updateCurrentPositionSmooth();
            }

            // Rotacao lenta do globo quando parado ou pausado
            if (globe && (!isPlaying || isPaused)) {
                globe.rotation.y += 0.0003;
            }

            // Pulse do marcador do PASSADO (laranja)
            if (paleoMarker3D && isPlaying && !isPaused) {
                const pulse = 1 + Math.sin(timestamp * 0.004) * 0.2;
                paleoMarker3D.scale.setScalar(pulse);
            }

            // Atualizar vista 2D a 30 FPS
            if (currentView === '2d' && ctx2D) {
                draw2D();
            }

            controls.update();
            renderer.render(scene, camera);
        }

        // ================================================================
        // ATUALIZACAO DA ANIMACAO
        // - Coastlines MUDAM conforme a idade (GPlates reconstruído)
        // - Ponto TAMBÉM reconstruído via GPlates (sincronizado!)
        // ================================================================
        function updateCurrentPositionSmooth() {
            if (!journeyData) return;

            // Calcular idade atual baseada no progresso
            const maxAge = journeyData.fad_ma;
            currentAge = currentProgress * maxAge;

            // ================================================================
            // CAPTURA DE SCREENSHOT EM IDADES ESPECÍFICAS
            // ================================================================
            const roundedAge = Math.round(currentAge / 10) * 10;
            if (roundedAge !== lastScreenshotAge && screenshotAges.includes(roundedAge)) {
                lastScreenshotAge = roundedAge;
                const paleoTemp = getReconstructedPosition(currentAge);
                console.log(`CAPTURE_SCREENSHOT:age_${roundedAge}Ma_lat${paleoTemp.lat.toFixed(1)}_lon${paleoTemp.lon.toFixed(1)}`);
            }

            // ================================================================
            // OBTER POSIÇÃO RECONSTRUÍDA DA TRAJETÓRIA (gerada via GPlates)
            // Isso garante sincronização perfeita com os coastlines
            // ================================================================
            const paleoPos = getReconstructedPosition(currentAge);
            const paleoLat = paleoPos.lat;
            const paleoLon = paleoPos.lon;

            // Calcular deslocamento
            const distance = haversineDistance(originalLat, originalLon, paleoLat, paleoLon);

            // Calcular incerteza baseada na idade
            const unc = calculateUncertainty(currentAge, paleoLat, paleoLon);

            // Atualizar UI
            document.getElementById('current-age').textContent = currentAge.toFixed(1);
            document.getElementById('current-period').textContent = getPeriodName(currentAge);
            document.getElementById('paleo-coords').textContent = `${paleoLat.toFixed(2)}°, ${paleoLon.toFixed(2)}°`;
            document.getElementById('displacement').textContent = distance.toFixed(0) + ' km';

            // Incerteza
            document.getElementById('unc-major').textContent = unc.semiMajor.toFixed(0);
            document.getElementById('unc-minor').textContent = unc.semiMinor.toFixed(0);
            document.getElementById('unc-angle').textContent = unc.rotation.toFixed(1) + '°';
            document.getElementById('unc-chi2').textContent = unc.chi2.toFixed(2);

            const badge = document.getElementById('quality-badge');
            badge.className = 'quality-badge quality-' + unc.quality;
            badge.textContent = unc.quality === 'high' ? 'ALTA CONFIANÇA' :
                               unc.quality === 'medium' ? 'CONFIANÇA MÉDIA' : 'BAIXA CONFIANÇA';

            // Timeline marker
            document.getElementById('timeline-marker').style.left = (currentProgress * 100) + '%';

            // ================================================================
            // COASTLINES MUDAM CONFORME A IDADE
            // Os coastlines do GPlates mostram onde os continentes estavam
            // ================================================================
            updateContinentPositions3D(currentAge);

            // ================================================================
            // MARCADOR SE MOVE JUNTO COM O CONTINENTE
            // Usando a mesma reconstrução do GPlates
            // ================================================================
            if (!paleoMarker3D) {
                paleoMarker3D = createMarker3D(paleoLat, paleoLon, 0xff5722, true);
                paleoMarker3D.name = 'fossil-marker';
                scene.add(paleoMarker3D);
            } else {
                // Atualizar posição do marcador
                const newPos = latLonToVector3(paleoLat, paleoLon, EARTH_RADIUS * 1.02);
                paleoMarker3D.position.copy(newPos);
            }

            // Atualizar elipse de incerteza
            createUncertaintyEllipse3D(paleoLat, paleoLon, unc);
        }

        function onWindowResize() {
            const container = document.getElementById('container-3d');
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);

            if (currentView === '2d') resizeCanvas2D();
        }

        // ================================================================
        // API PARA PYTHON
        // ================================================================

        window.startJourney = startJourney;
        window.stopJourney = stopJourney;
        window.resetView = resetView;
        window.switchView = switchView;

        // ================================================================
        // INICIALIZACAO
        // ================================================================

        function init() {
            init3D();
            init2D();
            animate();
        }

        init();
    </script>
</body>
</html>
"""

# Manter compatibilidade com codigo antigo
THREEJS_HTML = None  # Sera gerado dinamicamente

def get_threejs_html():
    """Retorna o HTML completo com bibliotecas embutidas."""
    global THREEJS_HTML
    if THREEJS_HTML is None:
        THREEJS_HTML = get_html_content()
    return THREEJS_HTML


# ============================================================================
# CLASSES PYQT
# ============================================================================

class CustomWebPage(QWebEnginePage):
    """WebPage customizada para capturar mensagens de console do JavaScript."""

    point_selected = pyqtSignal(float, float)
    view_changed = pyqtSignal(str)  # Emitido quando usuario troca vista via HTML
    capture_requested = pyqtSignal(str)

    def javaScriptConsoleMessage(self, level, message, line, source):
        """Captura mensagens de console do JavaScript."""
        # Mostrar erros JavaScript no console Python
        if level == 3:  # Error level
            print(f"[JS ERROR] {message} (line {line})")

        if message.startswith('POINT_SELECTED:'):
            try:
                data = json.loads(message.replace('POINT_SELECTED:', ''))
                print(f"[DEBUG] Ponto selecionado: {data['lat']}, {data['lon']}")
                self.point_selected.emit(data['lat'], data['lon'])
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[ERROR] Erro ao processar ponto: {e}")

        if message.startswith('CAPTURE_SCREENSHOT:'):
            tag = message.replace('CAPTURE_SCREENSHOT:', '')
            self.capture_requested.emit(tag)

        if message.startswith('VIEW_CHANGED:'):
            view = message.replace('VIEW_CHANGED:', '').strip()
            self.view_changed.emit(view)


class GlobeVisualization(QWidget):
    """Widget de visualizacao."""

    journey_started = pyqtSignal(dict)
    point_selected = pyqtSignal(float, float)
    capture_requested = pyqtSignal(str)
    view_changed = pyqtSignal(str)  # Emitido quando usuario troca vista via botoes HTML

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView()
        self.custom_page = CustomWebPage(self.web_view)
        self.custom_page.point_selected.connect(self.point_selected.emit)
        self.custom_page.capture_requested.connect(self.capture_requested.emit)
        self.custom_page.view_changed.connect(self.view_changed.emit)
        self.web_view.setPage(self.custom_page)

        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)  # Nao precisa mais!

        # Carregar HTML com bibliotecas embutidas (100% offline)
        self.custom_page.setHtml(get_threejs_html())
        layout.addWidget(self.web_view)

    def start_journey(self, specimen: dict):
        js = f"if(window.startJourney) window.startJourney({json.dumps(specimen)});"
        self.web_view.page().runJavaScript(js)
        self.journey_started.emit(specimen)

    def stop_journey(self):
        self.web_view.page().runJavaScript("if(window.stopJourney) window.stopJourney();")

    def reset_view(self):
        """Reseta a visualizacao para o estado inicial."""
        self.web_view.page().runJavaScript("if(window.resetView) window.resetView();")

    def switch_view(self, view: str):
        # fromPyQt=true para evitar loop de notificacao
        js = f"if(window.switchView) window.switchView('{view}', true);"
        self.web_view.page().runJavaScript(js)

    def preview_specimen(self, spec: dict):
        """Atualiza preview na timeline quando usuario seleciona um preset."""
        age = spec.get('fad_ma', 0)
        period_code = spec.get('period_code', '')
        era_code = spec.get('era_code', '')
        name = spec.get('name', 'Especime')
        js = f"if(window.previewSpecimenAge) window.previewSpecimenAge({age}, '{period_code}', '{era_code}', '{name}');"
        self.web_view.page().runJavaScript(js)

    def set_selection_mode(self, active: bool):
        """Ativa/desativa modo de selecao de pontos no mapa."""
        js = f"if(window.setSelectionMode) window.setSelectionMode({str(active).lower()});"
        self.web_view.page().runJavaScript(js)


class SimulatorPanel(QWidget):
    """Painel de controle."""

    specimen_sent = pyqtSignal(dict)
    stop_requested = pyqtSignal()
    reset_requested = pyqtSignal()  # Emitido quando usuario clica em Reset
    view_changed = pyqtSignal(str)
    preset_changed = pyqtSignal(dict)  # Emitido quando usuario seleciona preset
    selection_mode_changed = pyqtSignal(bool)  # Emitido quando modo de selecao muda
    optimization_changed = pyqtSignal(dict)  # Emitido quando otimizacoes mudam

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumWidth(300)
        self.setMaximumWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Titulo
        title = QLabel("Fossil Journey Tracker")
        title.setStyleSheet("color: #4fc3f7; font-size: 16px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("v9.0 - GPlates Web Service")
        subtitle.setStyleSheet("color: #8b949e; font-size: 11px;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # Toggle de vista
        view_group = QGroupBox("Tipo de Visualização")
        view_group.setStyleSheet(self._group_style())
        view_layout = QHBoxLayout(view_group)

        self.view_3d_radio = QRadioButton("Globo 3D")
        self.view_2d_radio = QRadioButton("Mapa 2D")
        self.view_3d_radio.setChecked(True)
        self.view_3d_radio.setStyleSheet("color: #e6edf3;")
        self.view_2d_radio.setStyleSheet("color: #e6edf3;")
        self.view_3d_radio.toggled.connect(lambda checked: self.view_changed.emit('3d') if checked else None)
        self.view_2d_radio.toggled.connect(lambda checked: self.view_changed.emit('2d') if checked else None)

        view_layout.addWidget(self.view_3d_radio)
        view_layout.addWidget(self.view_2d_radio)
        layout.addWidget(view_group)

        # Especimes
        preset_group = QGroupBox("Espécimes Pré-definidos")
        preset_group.setStyleSheet(self._group_style())
        preset_layout = QVBoxLayout(preset_group)

        self.specimen_combo = QComboBox()
        self.specimen_combo.setStyleSheet(self._combo_style())
        for spec in SPECIMEN_EXAMPLES:
            self.specimen_combo.addItem(spec["name"], spec)
        self.specimen_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.specimen_combo)

        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #8b949e; font-style: italic; font-size: 10px; padding: 5px;")
        preset_layout.addWidget(self.desc_label)

        layout.addWidget(preset_group)

        # Parametros
        params_group = QGroupBox("Parâmetros")
        params_group.setStyleSheet(self._group_style())
        params_layout = QFormLayout(params_group)
        params_layout.setLabelAlignment(Qt.AlignRight)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Foraminífero", "FOR")
        self.type_combo.addItem("Ostracoda", "OST")
        self.type_combo.addItem("Radiolário", "RAD")
        self.type_combo.addItem("Conodonte", "CON")
        self.type_combo.addItem("Diatomácea", "DIA")
        self.type_combo.addItem("Acritarco", "ACR")
        self.type_combo.addItem("Quitinozoário", "QUI")
        self.type_combo.setStyleSheet(self._combo_style())
        params_layout.addRow("Tipo:", self.type_combo)

        self.fad_spin = QDoubleSpinBox()
        self.fad_spin.setRange(1, 540)
        self.fad_spin.setValue(23.0)
        self.fad_spin.setSuffix(" Ma")
        self.fad_spin.setStyleSheet(self._spin_style())
        self.fad_spin.valueChanged.connect(self._on_fad_changed)
        params_layout.addRow("Idade (FAD):", self.fad_spin)

        # Combobox de periodo geologico (atualiza automaticamente com a idade)
        self.period_combo = QComboBox()
        self._populate_period_combo()
        self.period_combo.setStyleSheet(self._combo_style())
        self.period_combo.currentIndexChanged.connect(self._on_period_changed)
        params_layout.addRow("Período:", self.period_combo)

        self.lat_spin = QDoubleSpinBox()
        self.lat_spin.setRange(-85, 85)
        self.lat_spin.setValue(-29.75)
        self.lat_spin.setDecimals(2)
        self.lat_spin.setSuffix("°")
        self.lat_spin.setStyleSheet(self._spin_style())
        params_layout.addRow("Latitude:", self.lat_spin)

        self.lon_spin = QDoubleSpinBox()
        self.lon_spin.setRange(-180, 180)
        self.lon_spin.setValue(-51.15)
        self.lon_spin.setDecimals(2)
        self.lon_spin.setSuffix("°")
        self.lon_spin.setStyleSheet(self._spin_style())
        params_layout.addRow("Longitude:", self.lon_spin)

        # Botao para selecionar coordenadas no mapa
        self.select_map_btn = QPushButton("📍 Selecionar no Mapa")
        self.select_map_btn.setStyleSheet("""
            QPushButton { background-color: #1f6feb; color: white; padding: 10px;
                          border-radius: 6px; border: none; font-size: 11px; }
            QPushButton:hover { background-color: #388bfd; }
            QPushButton:checked { background-color: #f85149; }
        """)
        self.select_map_btn.setCheckable(True)
        self.select_map_btn.setToolTip("Clique no mapa para definir as coordenadas do microfóssil")
        self.select_map_btn.toggled.connect(self._on_select_map_toggled)
        params_layout.addRow("", self.select_map_btn)

        self.coord_status = QLabel("Clique no mapa para selecionar um ponto")
        self.coord_status.setStyleSheet("color: #8b949e; font-size: 10px; font-style: italic;")
        self.coord_status.setVisible(False)
        params_layout.addRow("", self.coord_status)

        layout.addWidget(params_group)

        # Modelo de rotacao
        model_group = QGroupBox("Modelo de Rotação")
        model_group.setStyleSheet(self._group_style())
        model_layout = QVBoxLayout(model_group)

        self.model_combo = QComboBox()
        self.model_combo.addItem("MÜLLER2022 (0-1000 Ma)", "MULLER2022")
        self.model_combo.addItem("SETON2012 (0-200 Ma)", "SETON2012")
        self.model_combo.addItem("MERDITH2021 (0-1000 Ma)", "MERDITH2021")
        self.model_combo.setStyleSheet(self._combo_style())
        model_layout.addWidget(self.model_combo)

        model_info = QLabel("Fonte: Modelo local (simulação)")
        model_info.setStyleSheet("color: #ff9800; font-size: 10px;")
        model_layout.addWidget(model_info)

        layout.addWidget(model_group)

        # Acoes
        self.start_btn = QPushButton("▶  Iniciar Jornada")
        self.start_btn.setStyleSheet("""
            QPushButton { background-color: #238636; color: white; font-size: 14px;
                          font-weight: bold; padding: 14px; border-radius: 8px; border: none; }
            QPushButton:hover { background-color: #2ea043; }
        """)
        self.start_btn.clicked.connect(self._send_specimen)
        layout.addWidget(self.start_btn)

        # Botoes de controle em linha
        btn_row = QHBoxLayout()

        self.stop_btn = QPushButton("◼ Parar")
        self.stop_btn.setStyleSheet("""
            QPushButton { background-color: #da3633; color: white; padding: 10px;
                          border-radius: 6px; border: none; font-size: 12px; }
            QPushButton:hover { background-color: #f85149; }
        """)
        self.stop_btn.clicked.connect(lambda: self.stop_requested.emit())
        btn_row.addWidget(self.stop_btn)

        self.reset_btn = QPushButton("↺ Reset")
        self.reset_btn.setStyleSheet("""
            QPushButton { background-color: #6e7681; color: white; padding: 10px;
                          border-radius: 6px; border: none; font-size: 12px; }
            QPushButton:hover { background-color: #8b949e; }
        """)
        self.reset_btn.clicked.connect(lambda: self.reset_requested.emit())
        btn_row.addWidget(self.reset_btn)

        layout.addLayout(btn_row)

        layout.addStretch()

        # Grupo de Otimizações (Feature Flags)
        opt_group = QGroupBox("⚡ Otimizações")
        opt_group.setStyleSheet(self._group_style())
        opt_layout = QVBoxLayout(opt_group)

        self.opt_preload_coastlines = QCheckBox("Pré-carregar coastlines")
        self.opt_preload_coastlines.setChecked(False)
        self.opt_preload_coastlines.setToolTip("Carrega coastlines principais ao iniciar (usa mais memória)")
        self.opt_preload_coastlines.setStyleSheet("color: #e6edf3; font-size: 11px;")
        opt_layout.addWidget(self.opt_preload_coastlines)

        self.opt_preload_ages = QCheckBox("Pré-carregar próximas idades")
        self.opt_preload_ages.setChecked(False)
        self.opt_preload_ages.setToolTip("Durante animação, carrega próximas idades em background")
        self.opt_preload_ages.setStyleSheet("color: #e6edf3; font-size: 11px;")
        opt_layout.addWidget(self.opt_preload_ages)

        self.opt_interpolation = QCheckBox("Interpolar do cache")
        self.opt_interpolation.setChecked(False)
        self.opt_interpolation.setToolTip("Usa interpolação bilinear para coordenadas não cacheadas")
        self.opt_interpolation.setStyleSheet("color: #e6edf3; font-size: 11px;")
        opt_layout.addWidget(self.opt_interpolation)

        self.opt_fast_render = QCheckBox("Renderização otimizada")
        self.opt_fast_render.setChecked(False)
        self.opt_fast_render.setToolTip("Simplifica coastlines e usa cache de renderização")
        self.opt_fast_render.setStyleSheet("color: #e6edf3; font-size: 11px;")
        opt_layout.addWidget(self.opt_fast_render)

        # Conectar sinais para aplicar otimizações
        self.opt_preload_coastlines.toggled.connect(self._on_optimization_changed)
        self.opt_preload_ages.toggled.connect(self._on_optimization_changed)
        self.opt_interpolation.toggled.connect(self._on_optimization_changed)
        self.opt_fast_render.toggled.connect(self._on_optimization_changed)

        layout.addWidget(opt_group)

        # Info
        info_label = QLabel(
            "• Clique no mapa 2D para definir coordenadas\n"
            "• A trajetória mostra o caminho do fóssil\n"
            "• Otimizações podem melhorar performance"
        )
        info_label.setStyleSheet("color: #6e7681; font-size: 10px; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 6px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self._on_preset_changed(0)

    def _group_style(self):
        return """
            QGroupBox { color: #e6edf3; font-weight: bold; border: 1px solid #30363d;
                        border-radius: 8px; margin-top: 8px; padding-top: 8px; font-size: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """

    def _combo_style(self):
        return """
            QComboBox { background-color: #21262d; border: 1px solid #30363d;
                        border-radius: 6px; padding: 8px; color: #e6edf3; font-size: 12px; }
            QComboBox:hover { border-color: #4fc3f7; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background-color: #21262d; color: #e6edf3; }
        """

    def _spin_style(self):
        return """
            QDoubleSpinBox { background-color: #21262d; border: 1px solid #30363d;
                             border-radius: 6px; padding: 6px; color: #e6edf3; font-size: 12px; }
            QDoubleSpinBox:hover { border-color: #4fc3f7; }
        """

    def _on_preset_changed(self, index):
        spec = SPECIMEN_EXAMPLES[index]
        self.desc_label.setText(spec["description"])
        # Mapear tipo de especime para indice do combo
        type_map = {"FOR": 0, "OST": 1, "RAD": 2, "CON": 3, "DIA": 4, "ACR": 5, "QUI": 6}
        type_idx = type_map.get(spec["specimen_type"], 0)
        self.type_combo.setCurrentIndex(type_idx)
        self.fad_spin.setValue(spec["fad_ma"])
        # SÓ atualizar coordenadas se usuário NÃO selecionou ponto no mapa
        if not getattr(self, '_point_selected_from_map', False):
            self.lat_spin.setValue(spec["latitude"])
            self.lon_spin.setValue(spec["longitude"])

        # FILTRAR MODELOS DE ROTACAO baseado na idade do fossil
        self._update_available_models(spec["fad_ma"])

        # Emitir sinal para atualizar preview na timeline
        self.preset_changed.emit(spec)

    def _update_available_models(self, fossil_age):
        """Atualiza modelos disponiveis baseado na idade do fossil."""
        # Limites de cada modelo
        MODEL_LIMITS = {
            "MULLER2022": 1000,
            "MERDITH2021": 1000,
            "SETON2012": 200,
        }

        # Guardar selecao atual
        current_model = self.model_combo.currentData()

        # Bloquear sinais durante atualizacao
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        # Adicionar apenas modelos que suportam a idade do fossil
        if fossil_age <= 200:
            self.model_combo.addItem("MÜLLER2022 (0-1000 Ma)", "MULLER2022")
            self.model_combo.addItem("SETON2012 (0-200 Ma)", "SETON2012")
            self.model_combo.addItem("MERDITH2021 (0-1000 Ma)", "MERDITH2021")
        else:
            # Fossil mais antigo que 200 Ma - SETON2012 nao disponivel
            self.model_combo.addItem("MÜLLER2022 (0-1000 Ma)", "MULLER2022")
            self.model_combo.addItem("MERDITH2021 (0-1000 Ma)", "MERDITH2021")

        # Restaurar selecao se ainda disponivel
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == current_model:
                self.model_combo.setCurrentIndex(i)
                break

        self.model_combo.blockSignals(False)

    def _on_fad_changed(self, value):
        """Atualiza modelos disponiveis e periodo geologico quando a idade muda."""
        self._update_available_models(value)
        self._update_period_from_age(value)

    def _populate_period_combo(self):
        """Popula o combobox com todos os periodos geologicos."""
        # Tabela de periodos geologicos (nome, idade_inicio, idade_fim em Ma)
        self.geological_periods = [
            ("Holoceno", 0, 0.0117),
            ("Pleistoceno", 0.0117, 2.58),
            ("Plioceno", 2.58, 5.33),
            ("Mioceno", 5.33, 23.03),
            ("Oligoceno", 23.03, 33.9),
            ("Eoceno", 33.9, 56.0),
            ("Paleoceno", 56.0, 66.0),
            ("Cretáceo", 66.0, 145.0),
            ("Jurássico", 145.0, 201.3),
            ("Triássico", 201.3, 251.9),
            ("Permiano", 251.9, 298.9),
            ("Carbonífero", 298.9, 358.9),
            ("Devoniano", 358.9, 419.2),
            ("Siluriano", 419.2, 443.8),
            ("Ordoviciano", 443.8, 485.4),
            ("Cambriano", 485.4, 541.0),
        ]

        for name, start, end in self.geological_periods:
            self.period_combo.addItem(f"{name} ({start:.1f}-{end:.1f} Ma)", (start, end))

    def _update_period_from_age(self, age_ma):
        """Atualiza o combobox de periodo baseado na idade em Ma."""
        self.period_combo.blockSignals(True)

        for i, (name, start, end) in enumerate(self.geological_periods):
            if start <= age_ma < end or (i == len(self.geological_periods) - 1 and age_ma >= start):
                self.period_combo.setCurrentIndex(i)
                break

        self.period_combo.blockSignals(False)

    def _on_period_changed(self, index):
        """Atualiza a idade quando o usuario muda o periodo."""
        if index >= 0 and index < len(self.geological_periods):
            name, start, end = self.geological_periods[index]
            # Define a idade como o meio do periodo
            mid_age = (start + end) / 2
            self.fad_spin.blockSignals(True)
            self.fad_spin.setValue(mid_age)
            self.fad_spin.blockSignals(False)
            # Atualizar modelos disponiveis
            self._update_available_models(mid_age)

    def _on_optimization_changed(self):
        """Emite sinal quando opcoes de otimizacao mudam."""
        opts = {
            'preload_coastlines': self.opt_preload_coastlines.isChecked(),
            'preload_ages': self.opt_preload_ages.isChecked(),
            'interpolation': self.opt_interpolation.isChecked(),
            'fast_render': self.opt_fast_render.isChecked(),
        }
        print(f"Otimizações alteradas: {opts}")
        self.optimization_changed.emit(opts)

    def get_optimization_settings(self):
        """Retorna configurações atuais de otimização."""
        return {
            'preload_coastlines': self.opt_preload_coastlines.isChecked(),
            'preload_ages': self.opt_preload_ages.isChecked(),
            'interpolation': self.opt_interpolation.isChecked(),
            'fast_render': self.opt_fast_render.isChecked(),
        }

    def _on_select_map_toggled(self, checked):
        """Ativa/desativa modo de selecao no mapa."""
        self.coord_status.setVisible(checked)
        if checked:
            self.select_map_btn.setText("🎯 Clique no Mapa...")
            self.coord_status.setText("Aguardando clique no mapa...")
            self.coord_status.setStyleSheet("color: #4fc3f7; font-size: 10px; font-style: italic;")
        else:
            self.select_map_btn.setText("📍 Selecionar no Mapa")
        self.selection_mode_changed.emit(checked)

    def on_point_selected(self, lat: float, lon: float):
        """Chamado quando usuario clica no mapa para selecionar ponto."""
        self._point_selected_from_map = True  # Marcar que coordenadas vieram do mapa
        self.lat_spin.setValue(lat)
        self.lon_spin.setValue(lon)
        self.select_map_btn.setChecked(False)
        self.coord_status.setText(f"Ponto: {lat:.2f}°, {lon:.2f}° - Clique 'Iniciar Jornada'")
        self.coord_status.setStyleSheet("color: #4caf50; font-size: 10px; font-weight: bold;")
        self.coord_status.setVisible(True)

        # NAO iniciar automaticamente - usuario deve clicar em "Iniciar Jornada"
        # A idade sera a do especime selecionado no combobox

    def _send_specimen(self):
        specimen = {
            "specimen_type": self.type_combo.currentData(),
            "era_code": SPECIMEN_EXAMPLES[self.specimen_combo.currentIndex()]["era_code"],
            "period_code": SPECIMEN_EXAMPLES[self.specimen_combo.currentIndex()]["period_code"],
            "fad_ma": self.fad_spin.value(),
            "confidence": 95.0,
            "latitude": self.lat_spin.value(),
            "longitude": self.lon_spin.value(),
            "rotation_model": self.model_combo.currentData(),
        }
        self.specimen_sent.emit(specimen)


class MainWindow(QMainWindow):
    """Janela principal."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fossil Journey Tracker v9.0")
        self.setMinimumSize(1400, 850)
        self._apply_theme()

        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        self.visualization = GlobeVisualization()
        splitter.addWidget(self.visualization)

        self.panel = SimulatorPanel()
        splitter.addWidget(self.panel)

        splitter.setSizes([1100, 300])

        # Conexoes
        self.panel.specimen_sent.connect(self.visualization.start_journey)
        self.panel.stop_requested.connect(self.visualization.stop_journey)
        self.panel.reset_requested.connect(self.visualization.reset_view)
        self.panel.view_changed.connect(self.visualization.switch_view)
        self.panel.preset_changed.connect(self.visualization.preview_specimen)
        self.panel.selection_mode_changed.connect(self.visualization.set_selection_mode)
        self.visualization.point_selected.connect(self._on_point_selected)
        self.visualization.point_selected.connect(self.panel.on_point_selected)
        self.visualization.capture_requested.connect(self._on_capture_requested)
        self.panel.model_combo.currentIndexChanged.connect(self._on_model_changed)
        self.panel.optimization_changed.connect(self._on_optimization_changed)
        self.visualization.view_changed.connect(self._on_view_changed_from_html)

        # Disparar preset inicial para mostrar na timeline
        self.panel._on_preset_changed(0)

        self.statusBar().showMessage("Pronto - Selecione um espécime e clique em 'Iniciar Jornada'")
        self.statusBar().setStyleSheet("color: #8b949e; background-color: #161b22; padding: 5px;")

    def _on_point_selected(self, lat: float, lon: float):
        """Atualiza coordenadas do painel quando usuario clica no mapa."""
        self.panel.lat_spin.setValue(lat)
        self.panel.lon_spin.setValue(lon)
        self.statusBar().showMessage(f"Ponto selecionado: {lat:.4f}°, {lon:.4f}°")

        # Capturar screenshot automaticamente para debug
        from datetime import datetime
        screenshot_dir = Path(__file__).parent / "screenshots"
        screenshot_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = screenshot_dir / f"point_selected_{timestamp}_{lat:.2f}_{lon:.2f}.png"

        # Agendar screenshot após 500ms para dar tempo de renderizar
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(500, lambda: self._capture_screenshot(screenshot_path, lat, lon))

    def _capture_screenshot(self, path, lat=None, lon=None):
        """Captura screenshot da janela."""
        try:
            screen = QApplication.primaryScreen()
            pixmap = screen.grabWindow(self.winId())
            pixmap.save(str(path))
            print(f"[SCREENSHOT] Salvo: {path}")
            if lat is not None and lon is not None:
                print(f"[SCREENSHOT] Ponto: lat={lat:.4f}, lon={lon:.4f}")
        except Exception as e:
            print(f"[SCREENSHOT] Erro: {e}")

    def _on_capture_requested(self, tag: str):
        """Captura screenshot durante a jornada."""
        from datetime import datetime
        screenshot_dir = Path(__file__).parent / "screenshots"
        screenshot_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = screenshot_dir / f"{tag}_{timestamp}.png"
        # Capturar imediatamente
        self._capture_screenshot(screenshot_path)

    def _on_model_changed(self, index: int):
        """Atualiza modelo de rotacao na visualizacao."""
        model_name = self.panel.model_combo.currentData()
        js = f"if(window.setRotationModel) window.setRotationModel('{model_name}');"
        self.visualization.web_view.page().runJavaScript(js)

    def _on_optimization_changed(self, opts: dict):
        """Atualiza configuracoes de otimizacao na visualizacao."""
        import json
        opts_json = json.dumps(opts)
        js = f"if(window.setOptimizations) window.setOptimizations({opts_json});"
        self.visualization.web_view.page().runJavaScript(js)
        self.statusBar().showMessage(f"Otimizações atualizadas: {opts}")

    def _on_view_changed_from_html(self, view: str):
        """Sincroniza radio buttons do painel quando usuario troca vista via HTML."""
        # Bloquear sinais para evitar loop
        self.panel.view_3d_radio.blockSignals(True)
        self.panel.view_2d_radio.blockSignals(True)

        if view == '3d':
            self.panel.view_3d_radio.setChecked(True)
        elif view == '2d':
            self.panel.view_2d_radio.setChecked(True)

        self.panel.view_3d_radio.blockSignals(False)
        self.panel.view_2d_radio.blockSignals(False)

    def _apply_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#0d1117"))
        palette.setColor(QPalette.WindowText, QColor("#e6edf3"))
        palette.setColor(QPalette.Base, QColor("#161b22"))
        palette.setColor(QPalette.Text, QColor("#e6edf3"))
        palette.setColor(QPalette.Button, QColor("#21262d"))
        palette.setColor(QPalette.ButtonText, QColor("#e6edf3"))
        palette.setColor(QPalette.Highlight, QColor("#4fc3f7"))
        self.setPalette(palette)

    def closeEvent(self, event):
        """Garante que a aplicação feche completamente."""
        # Parar jornada se estiver rodando
        self.visualization.stop_journey()
        # Aceitar o evento de fechamento
        event.accept()
        # Forçar saída de todas as threads e processos
        QApplication.quit()
        import os, sys
        os._exit(0)
        sys.exit(0)


def main():
    # Verificar argumentos de linha de comando
    if "--download" in sys.argv:
        print("Modo de download de dados do GPlates")
        download_all_gplates_data()
        return 0

    if "--help" in sys.argv or "-h" in sys.argv:
        print("Fossil Journey Tracker v9.1")
        print("=" * 40)
        print("Uso:")
        print("  python simulator.py              Executa o simulador")
        print("  python simulator.py --download   Baixa TODOS os dados do GPlates")
        print("                                   para funcionamento offline")
        print("  python simulator.py --help       Mostra esta ajuda")
        return 0

    # Verificar se ha dados em cache
    cache_files = list(CACHE_DIR.glob("*.json"))
    if len(cache_files) == 0:
        print("[AVISO] Nenhum dado em cache local!")
        print("        Para funcionamento offline, execute:")
        print("        python simulator.py --download")
        print()
    else:
        print(f"[OK] Cache local: {len(cache_files)} arquivos ({sum(f.stat().st_size for f in cache_files) / 1024 / 1024:.1f} MB)")

    # Iniciar servidor proxy para GPlates Web Service
    print("Iniciando Fossil Journey Tracker v9.1 com GPlates Web Service...")
    proxy_server = start_gplates_proxy()

    # Dar tempo para o servidor iniciar
    time.sleep(0.5)

    app = QApplication(sys.argv)
    app.setApplicationName("Fossil Journey Tracker")
    app.setStyle("Fusion")

    window = MainWindow()
    window.showMaximized()

    return app.exec_()


if __name__ == "__main__":
    import traceback
    try:
        sys.exit(main())
    except Exception as e:
        print(f"ERRO FATAL: {e}")
        traceback.print_exc()
        input("Pressione Enter para sair...")
