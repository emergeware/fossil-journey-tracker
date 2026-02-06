# Plano de Implementação - Fossil Journey Tracker v2.0

## Status do Download GPlates
- Grid de 10° (684 pontos × 3 modelos × ~100 idades = ~150.000 arquivos)
- Em execução em background

---

## PARTE 1: OTIMIZAÇÕES DE PERFORMANCE

### 1.1 Carregar Coastlines em Memória no Início
**Problema:** Coastlines são carregados sob demanda, causando latência durante animação.

**Solução:**
```javascript
// Ao iniciar aplicação, pré-carregar coastlines principais
const PRELOAD_AGES = [0, 50, 100, 150, 200, 250, 300, 400, 500];
async function preloadCoastlines() {
    for (const model of ['MULLER2022', 'MERDITH2021', 'SETON2012']) {
        for (const age of PRELOAD_AGES) {
            await fetchCoastlines(age, model);  // Salva em coastlinesCache
        }
    }
}
```

**Benefício:** Coastlines já estarão em memória, eliminando delay.

---

### 1.2 Pré-carregar Idades Próximas Durante Animação
**Problema:** Durante animação, sistema espera carregar próxima idade.

**Solução:**
```javascript
// Durante animação, pré-carregar próximas 3 idades
function preloadNextAges(currentAge, step = 10) {
    const nextAges = [currentAge + step, currentAge + step*2, currentAge + step*3];
    nextAges.forEach(age => {
        if (!coastlinesCache[age]) {
            fetchCoastlines(age);  // Carrega em background
        }
    });
}
```

**Benefício:** Transições suaves sem pausas.

---

### 1.3 Interpolação Entre Pontos do Cache
**Problema:** Se coordenada não está no cache, busca da internet.

**Solução:**
```javascript
// Encontrar 4 pontos mais próximos no cache e interpolar
function interpolateFromCache(lat, lon, age, model) {
    const gridStep = 10;  // Cache em grid de 10°

    // Pontos do grid mais próximos
    const lat1 = Math.floor(lat / gridStep) * gridStep;
    const lat2 = lat1 + gridStep;
    const lon1 = Math.floor(lon / gridStep) * gridStep;
    const lon2 = lon1 + gridStep;

    // Buscar 4 pontos do cache
    const p11 = getCachedPoint(lat1, lon1, age, model);
    const p12 = getCachedPoint(lat1, lon2, age, model);
    const p21 = getCachedPoint(lat2, lon1, age, model);
    const p22 = getCachedPoint(lat2, lon2, age, model);

    // Interpolação bilinear
    return bilinearInterpolate(lat, lon, p11, p12, p21, p22);
}
```

**Benefício:** 100% offline para QUALQUER coordenada.

---

### 1.4 Otimizar Renderização JavaScript
**Problemas identificados:**
- Redesenho completo a cada frame
- Muitos objetos Path2D criados dinamicamente
- Coastlines com muitos pontos

**Soluções:**
```javascript
// 1. Cache de paths renderizados por idade
const renderedPaths = {};

// 2. Simplificar coastlines (reduzir pontos)
function simplifyPolygon(points, tolerance = 0.5) {
    // Algoritmo Douglas-Peucker
}

// 3. Usar requestAnimationFrame com throttle
let lastRender = 0;
function render(timestamp) {
    if (timestamp - lastRender < 16) return;  // Max 60 FPS
    lastRender = timestamp;
    draw2D();
}
```

---

## PARTE 2: SISTEMA DE EVENTOS GEOLÓGICOS

### 2.1 Análise dos Eventos do GT_Data.xlsx

**Total de eventos:** 105

**Categorias principais:**
| Categoria | Quantidade | Tipo de Visualização |
|-----------|------------|---------------------|
| Anoxic Event (Oceanic/Lacustrine) | 18 | Regional/Global |
| Biozone (Microfossil/Nannofossil) | 19 | Global (temporal) |
| Plate Tectonic | 7 | Regional com coordenadas |
| Tectonic Activity (Orogeny/Rifting) | 11 | Regional com coordenadas |
| Extinction Event | 6 | Global |
| Climate Change | 9 | Global |
| Volcanic Activity | 3 | Regional com coordenadas |
| Impact Event (Asteroid) | 3 | Pontual com coordenadas |
| Oil Field (Pre-Salt) | 3 | Pontual com coordenadas |
| Sedimentary Basin | 5 | Regional com coordenadas |
| Outros | ~21 | Variado |

---

### 2.2 Classificação dos Eventos

#### EVENTOS GLOBAIS (aparecem em toda a tela)
- **Extinction Events** - Mostrar como overlay vermelho/laranja
- **Climate Change** - Mostrar como gradiente de cor no fundo
- **Anoxic Events (Oceanic)** - Mostrar oceanos em cor diferente

#### EVENTOS REGIONAIS (precisam de coordenadas)
- **Plate Tectonic** - Linhas mostrando movimento
- **Volcanic Activity** - Ícone de vulcão na localização
- **Impact Events** - Ícone de impacto na localização
- **Tectonic Activity** - Áreas destacadas
- **Rift Formation** - Linhas tracejadas

#### EVENTOS TEMPORAIS (biozonas)
- **Biozone** - Indicador na timeline, não no mapa

---

### 2.3 Estrutura de Dados Proposta

```python
# Banco de dados SQLite para eventos (leve e portátil)
CREATE TABLE geological_events (
    id INTEGER PRIMARY KEY,
    event_name TEXT NOT NULL,
    event_type TEXT NOT NULL,           -- Categoria principal
    event_subtype TEXT,                 -- Subcategoria
    acronym TEXT,
    start_ma REAL NOT NULL,             -- Idade início (Ma)
    end_ma REAL NOT NULL,               -- Idade fim (Ma)
    duration_ma REAL,

    -- Localização (NULL = evento global)
    latitude REAL,
    longitude REAL,
    radius_km REAL,                     -- Raio de influência

    -- Região (para eventos regionais)
    region_polygon TEXT,                -- GeoJSON de polígono

    -- Visualização
    display_type TEXT,                  -- 'global', 'regional', 'point', 'timeline'
    icon TEXT,                          -- Nome do ícone
    color TEXT,                         -- Cor hex
    opacity REAL DEFAULT 0.7,

    -- Descrições
    description_en TEXT,
    description_pt TEXT,
    comments_en TEXT,
    comments_pt TEXT,

    -- Metadados
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para busca rápida
CREATE INDEX idx_events_time ON geological_events(start_ma, end_ma);
CREATE INDEX idx_events_type ON geological_events(event_type);
CREATE INDEX idx_events_location ON geological_events(latitude, longitude);
```

---

### 2.4 Coordenadas para Eventos Regionais

Eventos que precisam de coordenadas específicas:

| Evento | Coordenadas Sugeridas | Raio |
|--------|----------------------|------|
| **Volcanic Activity** | | |
| Karoo Basalts | -30.0, 28.0 (África do Sul) | 500 km |
| Paraná Flood Basalts | -24.0, -51.0 (Brasil) | 800 km |
| Serra Geral Formation | -28.0, -52.0 (Brasil) | 600 km |
| **Impact Events** | | |
| Nadir Impact | 21.0, -23.0 (Atlântico) | 100 km |
| Alamo Impact | 37.5, -116.0 (Nevada) | 50 km |
| Siljan Impact | 61.0, 14.7 (Suécia) | 30 km |
| **Rift Formation** | | |
| Rio Grande Rift | 35.0, -106.0 (EUA) | 200 km |
| East African Rift | -2.0, 36.0 (África) | 300 km |
| Red Sea Opening | 22.0, 38.0 | 400 km |
| **Plate Tectonic** | | |
| South Atlantic Opening | -30.0, -20.0 | Linha |
| Drake Passage | -60.0, -65.0 | 300 km |
| Mid-Atlantic Ridge | 0.0, -25.0 | Linha |
| **Pre-Salt Fields** | | |
| Tupi (Lula) Field | -24.5, -42.5 | 50 km |
| Libra Oil Field | -23.5, -41.5 | 40 km |
| Búzios Field | -23.0, -41.0 | 45 km |
| **Sedimentary Basins** | | |
| Santos Basin | -25.0, -44.0 | 400 km |
| Campos Basin | -22.5, -40.5 | 300 km |

---

### 2.5 Interface de Usuário para Eventos

```
┌─────────────────────────────────────┐
│  LAYERS DE EVENTOS                  │
├─────────────────────────────────────┤
│  [✓] Extinções em Massa             │
│  [✓] Eventos Anóxicos               │
│  [ ] Atividade Vulcânica            │
│  [ ] Impactos de Asteroides         │
│  [✓] Mudanças Climáticas            │
│  [ ] Tectônica de Placas            │
│  [ ] Biozonas                       │
│  [ ] Campos de Petróleo             │
│  [ ] Bacias Sedimentares            │
├─────────────────────────────────────┤
│  [Mostrar Todos] [Ocultar Todos]    │
└─────────────────────────────────────┘
```

---

### 2.6 Visualização no Mapa

```javascript
// Overlay de eventos sobre o mapa
function drawEventLayer(ctx, currentAge) {
    const activeEvents = getEventsForAge(currentAge);

    for (const event of activeEvents) {
        switch (event.display_type) {
            case 'global':
                drawGlobalEvent(ctx, event);  // Overlay em toda tela
                break;
            case 'regional':
                drawRegionalEvent(ctx, event);  // Área destacada
                break;
            case 'point':
                drawPointEvent(ctx, event);  // Ícone no local
                break;
        }
    }
}

// Exemplo: Evento de extinção global
function drawGlobalEvent(ctx, event) {
    if (event.event_type.includes('Extinction')) {
        ctx.fillStyle = 'rgba(255, 0, 0, 0.15)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Texto
        ctx.fillStyle = 'rgba(255, 50, 50, 0.9)';
        ctx.font = 'bold 16px Arial';
        ctx.fillText(`⚠️ ${event.event_name}`, 10, canvas.height - 30);
    }
}

// Exemplo: Evento pontual (impacto, vulcão)
function drawPointEvent(ctx, event) {
    const pos = latLonToCanvas(event.latitude, event.longitude, canvas);

    // Ícone
    const icons = {
        'Impact Event': '☄️',
        'Volcanic Activity': '🌋',
        'Oil Field': '🛢️'
    };

    ctx.font = '24px Arial';
    ctx.fillText(icons[event.event_type] || '📍', pos.x - 12, pos.y + 8);

    // Raio de influência
    if (event.radius_km) {
        const radiusPx = event.radius_km / 111;  // ~111 km por grau
        ctx.strokeStyle = 'rgba(255, 100, 0, 0.5)';
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radiusPx * (canvas.width / 360), 0, Math.PI * 2);
        ctx.stroke();
    }
}
```

---

## PARTE 3: INTEGRAÇÃO COM MÁQUINA DE TRIAGEM

### 3.1 Fluxo de Dados

```
┌──────────────────┐     ┌─────────────────┐     ┌─────────────────────┐
│  Máquina de      │────▶│  API/WebSocket  │────▶│  Fossil Journey     │
│  Triagem         │     │  (JSON)         │     │  Tracker            │
└──────────────────┘     └─────────────────┘     └─────────────────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────────┐
                                                 │  Visualização com   │
                                                 │  • Trajetória       │
                                                 │  • Eventos ativos   │
                                                 │  • Timeline         │
                                                 └─────────────────────┘
```

### 3.2 Formato de Dados da Máquina

```json
{
    "specimen_id": "FOR-2024-0001",
    "specimen_type": "FOR",
    "species_name": "Globigerina bulloides",
    "latitude": -22.90,
    "longitude": -43.17,
    "fad_ma": 23.0,
    "confidence": 95.5,
    "timestamp": "2024-02-06T15:30:00Z",
    "image_path": "/images/specimens/FOR-2024-0001.jpg",

    // Opcional: eventos a destacar
    "highlight_events": ["Miocene Foraminiferal Biozones", "Neogene Diatomaceous Sediments"]
}
```

---

## PARTE 4: BANCO DE DADOS vs ARQUIVO

### Comparação

| Aspecto | SQLite | JSON/Python Dict |
|---------|--------|------------------|
| **Performance** | Muito boa (índices) | Boa para dados pequenos |
| **Queries** | SQL completo | Manual/loops |
| **Edição** | Via SQL/interface | Editar arquivo |
| **Portabilidade** | Arquivo único | Arquivo único |
| **Integração Python** | sqlite3 (builtin) | json (builtin) |
| **Atualizações** | Fácil | Recarregar arquivo |

### Recomendação: **SQLite**

**Razões:**
1. 105 eventos agora, pode crescer para centenas
2. Queries por tempo são frequentes
3. Permite adicionar/editar eventos sem recarregar
4. Interface de admin fácil de criar
5. Já builtin no Python

---

## PARTE 5: PRÓXIMOS PASSOS

### Fase 1: Performance (Prioridade Alta)
1. [ ] Implementar pré-carregamento de coastlines
2. [ ] Implementar interpolação bilinear para cache
3. [ ] Otimizar renderização JavaScript

### Fase 2: Banco de Dados de Eventos
4. [ ] Criar esquema SQLite
5. [ ] Importar eventos do GT_Data.xlsx
6. [ ] Adicionar coordenadas aos eventos regionais
7. [ ] Criar API Python para consulta

### Fase 3: Visualização de Eventos
8. [ ] Implementar layer de eventos globais
9. [ ] Implementar layer de eventos pontuais
10. [ ] Implementar layer de eventos regionais
11. [ ] Criar painel de controle de layers

### Fase 4: Integração
12. [ ] Criar endpoint para máquina de triagem
13. [ ] Testar fluxo completo
14. [ ] Documentação

---

## Perguntas para Definir

1. **Quais eventos são mais importantes para mostrar por padrão?**
   - Extinções? Eventos anóxicos? Biozonas?

2. **Deve haver limite de eventos simultâneos na tela?**
   - Evitar poluição visual

3. **Eventos devem ter animação de aparecimento/desaparecimento?**
   - Fade in/out suave?

4. **Quer poder adicionar eventos customizados?**
   - Interface de admin para novos eventos?

5. **Prioridade: Performance primeiro ou Eventos primeiro?**
   - Sugiro Performance para base sólida

---

*Documento criado em: 2024-02-06*
*Versão: 1.0*
