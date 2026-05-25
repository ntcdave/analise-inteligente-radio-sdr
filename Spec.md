# 📡 SPEC.me — Bíblia Técnica do Sistema SDR Inteligente

> **Projeto:** Sistema SDR Inteligente — Monitorização e Edge AI  
> **Tipo:** Trabalho de Conclusão de Curso (TCC) em Engenharia  
> **Gerado em:** Maio de 2026  
> **Versão do Documento:** 1.0

---

## Sumário

1. [Arquitetura do Sistema](#1-arquitetura-do-sistema)
2. [Stack Técnica](#2-stack-técnica)
3. [Dicionário de Funcionalidades](#3-dicionário-de-funcionalidades)
4. [Padrões de Projeto](#4-padrões-de-projeto)
5. [Pontos de Extensibilidade](#5-pontos-de-extensibilidade)
6. [Guia de Manutenção](#6-guia-de-manutenção)

---

## 1. Arquitetura do Sistema

### 1.1 Visão Geral

O sistema opera como um **pipeline de três camadas** que transformam ondas eletromagnéticas em inteligência acionável, executando tudo localmente (Edge Computing) e de forma extremamente otimizada:

```
┌─────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  ANTENA      │───▸│  MOTOR DSP       │───▸│  WHISPER (STT)   │───▸│  NLP & ONTOLOGIA│
│  RTL-SDR V4  │    │  (src/dsp.py)    │    │  (transcricao.py)│    │  (src/analise.py│
│  Hardware    │    │  Desmodulação FM  │    │  Áudio → Texto   │    │  Texto → OSINT  │
└─────────────┘    └──────────────────┘    └──────────────────┘    └─────────────────┘
       │                    │                       │                       │
       │              ┌─────▼──────┐          ┌─────▼──────┐         ┌─────▼──────┐
       │              │ sounddevice│          │ Sessão CSV │         │ Dashboard  │
       │              │ (Áudio ao  │          │  (dados/   │         │ (Matplotlib│
       │              │  vivo)     │          │  projetos) │         │  + Donut)  │
       └──────────────┴────────────┘          └────────────┘         └────────────┘
```

### 1.2 Fluxo de Dados Detalhado

**Fase 1 — Captura e Desmodulação (Camada DSP em `src/dsp.py`)**

1. O `RtlSdr` abre o dispositivo USB e configura a taxa de amostragem (1.024 MHz), a frequência central e o ganho discreto ideal.
2. A thread `sdr-reader` lê blocos de **262.144 amostras I/Q** continuamente do barramento USB (~250 ms por ciclo) de forma bloqueante, enfileirando-as em uma fila circular thread-safe sem realizar processamento.
3. A thread `dsp-worker` consome as amostras da fila e executa uma **cadeia de DSP matemático puro**:
   - **Decimação I/Q (÷4):** Reduz a taxa de amostragem de 1.024 MHz para 256 kHz via downsampling.
   - **Filtro Butterworth passa-baixa (ordem 3):** Isola o canal FM sintonizado (banda padrão de 170 kHz). O estado do filtro (`zi`) é persistido para eliminar transientes.
   - **Desmodulação FM:** Calcula a diferença de fase de fase de sinal consecutiva via `np.angle(sinal[n] * conj(sinal[n-1]))`.
   - **Decimação de áudio (÷8):** Reduz de 256 kHz para **32 kHz** (taxa padrão de processamento de áudio).
   - **Filtro De-Emphasis (75µs):** Atenua agudos para repor o perfil da rádio FM comercial de áudio analógico.
4. O áudio final é direcionado ao Ring Buffer (SPSC circular lock-free) se o áudio ao vivo estiver ligado, alimentando o callback do `sounddevice`.

**Fase 2 — Transcrição (Camada STT em `src/transcricao.py`)**

5. Se a gravação estiver ativa, a thread do DSP acumula os blocos no `buffer_ia`.
6. A cada **300 blocos (~30 segundos)**, o bloco é persistido no disco como arquivo WAV na pasta da sessão ativa (`dados/projetos/<nome_sessao>/audios/audio_<timestamp>.wav`).
7. O `TranscritorSDR` carrega em cache local o modelo neural OpenAI Whisper (`base`), executando a inferência forçada em português (`pt`), desativando o histórico de texto anterior (evita alucinações repetitivas) e aplicando filtros de silêncio e chiado rígidos.
8. Transcrições válidas são persistidas de forma append no arquivo CSV local da sessão de captura (`transcricoes_<nome_sessao>.csv`).

**Fase 3 — Análise Semântica (Camada NLP em `src/analise.py`)**

9. O `CientistaSDR` é instanciado de forma lazy e lê o CSV da sessão ativa de forma incremental.
10. Para cada linha de transcrição, executa de forma offline:
    - **Análise Estatística Clássica:** Tokenização, limpeza de pontuação, filtragem de mais de 70 stopwords em português, contagem de unigramas (termos) e extração de bigramas (expressões).
    - **Mapeamento de Ontologia OSINT:** Percorre de forma determinística e recursiva a árvore de categorias (`config.ONTOLOGIA_OSINT`) sintonizando termos com categorias de interesse em inteligência de sinais (Segurança Pública, Desporto, Política, Religião, Trânsito e Logística).
11. A computação é monitorada via `tracemalloc` para auditar a pegada de memória e tempo de processamento físico.
12. São gerados **5 gráficos de alta resolução (300dpi)** e salvos na subpasta `estatisticas/` da sessão, juntamente com o CSV consolidado de agregação `matriz_estatistica.csv`.

### 1.3 Módulo Legado — `src/captura.py`

O `SDRReceiver` é uma implementação **anterior** baseada em subprocessos (`rtl_fm.exe` → `sox.exe` via pipe). Foi substituída pelo motor DSP nativo de alto desempenho em `src/dsp.py`, mas permanece no codebase como referência. Ele não é importado por nenhum módulo ativo.

---

## 2. Stack Técnica

### 2.1 Interface Gráfica

| Biblioteca | Versão | Justificativa |
|---|---|---|
| **PyQt6** | — | Framework de GUI desktop com suporte nativo a widgets, layouts responsivos e `QTimer` para integração thread-safe com a UI. Escolhido por maturidade e capacidade de construir interfaces complexas sem servidor web. |
| **pyqtgraph** | — | Renderização de espectrogramas em tempo real com performance GPU-acelerada. Superior ao matplotlib para dados dinâmicos (atualização a cada 220ms). |

### 2.2 Processamento Digital de Sinal

| Biblioteca | Justificativa |
|---|---|
| **numpy** | Operações vetorizadas sobre arrays I/Q (reshape, mean, angle, conj). Essencial para processar 262.144 amostras por ciclo sem degradação de performance. |
| **scipy.signal** | Implementação dos filtros Butterworth (`butter`) e filtragem stateful (`lfilter` com `zi`). O estado `zi` é preservado entre iterações para evitar transientes nas fronteiras de blocos. |
| **sounddevice** | Stream de áudio em tempo real via callback. O `OutputStream` com `blocksize=2048` permite latência adaptativa, evitando stutters. |

### 2.3 Inteligência Artificial & NLP

| Componente | Modelo | Justificativa |
|---|---|---|
| **openai-whisper** | `base` (~140MB) | Modelo de STT robusto contra ruído de rádio. A variante `base` equilibra precisão e velocidade em hardware consumer. O `fp16=False` garante compatibilidade com CPUs sem suporte a half-precision. |
| **torch** | — | Backend de inferência do Whisper. Dependência obrigatória. |
| **Ontologia OSINT Nativa** | Dicionário Estático | Mecanismo de busca léxica determinística em Python baseada no dicionário estruturado `ONTOLOGIA_OSINT` em `config.py`. Fornece categorização semântica instantânea, 100% offline e com custo computacional nulo. |

### 2.4 Análise e Visualização

| Biblioteca | Justificativa |
|---|---|
| **pandas** | Leitura e manipulação do CSV de transcrições de sessões. Operações como `tail()`, `groupby()` e conversão temporal (`to_datetime`). |
| **matplotlib** (backend `Agg`) | Gera�## 3. Dicionário de Funcionalidades

### 3.1 `app.py` — Orquestrador Principal

#### Classe `MainWindow(QMainWindow)`

| Método / Atributo | Responsabilidade |
|---|---|
| `__init__` | Inicializa estado de sintonia, cria `TranscritorSDR` e `MotorDSP`, constrói a interface PyQt6 e inicia os timers dinâmicos de atualização. |
| `closeEvent` | Shutdown gracioso: desativa flags de gravação e dsp, para os timers de atualização e da missão, desliga a pool de threads concorrentes do Whisper e fecha a antena. |
| `_construir_interface` | Desenha toda a interface PyQt6 com painel de sintonia de rádio (sliders e spinbox de frequência e ganho), controlo de volume, aba de sessão de captura (com timers/relógio e botões de ação), console de logs e gráfico de espectro PSD. |
| `_configurar_pastas_sessao` | Configura dinamicamente a estrutura de pastas do projeto no formato `dados/projetos/<nome_sessao>`, isolando os chunks de áudio e as estatísticas. |
| `_escolher_pasta_sessao` | Abre diálogo nativo do sistema para selecionar uma pasta de sessão de gravação já existente no disco. |
| `_alterar_sessao` | Atualiza o nome da sessão de captura ativa a partir do campo de texto e ajusta as pastas internas. |
| `_mudar_frequencia_slider` / `_mudar_frequencia_spin` | Sincroniza a sintonização e aplica a alteração de MHz no hardware e no eixo X do gráfico. |
| `_mudar_ganho` / `_mudar_volume` | Aplica as alterações de ganho de RF no hardware SDR e volume linear nos blocos de áudio. |
| `_atualizar_eixos_grafico` | Ajusta as escalas visuais X (limites de zoom) e Y (amplitude em dB) do PlotWidget. |
| `_toggle_audio` | Ativa ou silencia a reprodução ao vivo de áudio demodulado, limpando os buffers em caso de ativação para evitar lag. |
| `_atualizar_grafico` | Executa o cálculo da densidade espectral PSD no bloco de dados I/Q dinâmicos do SDR e plota em tempo real. |
| `_toggle_missao` | Inicializa ou interrompe a gravação em disco e transcrição. Bloqueia parâmetros de configuração temporal durante a execução. |
| `_verificar_termino_tempo` | Timer disparado a cada 1 segundo que verifica se o limite de tempo por duração s (modo *Duração*) ou por relógio de sistema (modo *Até Horário*) foi atingido para terminar a captura de forma limpa. |
| `_processar_chunk` | Executado de forma concorrente em thread secundária. Salva as amostras de áudio acumuladas de 30 segundos em arquivo `.wav` e aciona o Whisper para transcrever, escrevendo o resultado no CSV da sessão. |
| `_toggle_retranscricao` | Inicia ou cancela o motor de re-transcrição de uma sessão inteira, útil para refazer as transcrições de todos os arquivos WAV de uma pasta apagando o CSV anterior. |
| `_abrir_analise` / `_rodar_analise` | Desabilita os botões e invoca o `CientistaSDR` em thread secundária daemonizada para gerar relatórios e os 5 gráficos em background. |

### 3.2 `src/transcricao.py` — Camada de Transcrição

#### Classe `TranscritorSDR`

| Método | Responsabilidade |
|---|---|
| `__init__(modelo_tamanho)` | Inicializa o modelo OpenAI Whisper local na memória RAM. |
| `_inicializar_csv` | Cria o arquivo CSV específico da sessão ativa com o cabeçalho (`Data_Hora`, `Frequencia_MHz`, `Caminho_Audio`, `Texto_Transcrito`) de forma segura. |
| `transcrever(caminho_audio, frequencia_mhz)` | Transcreve o áudio WAV offline forçando o idioma português (`pt`), desliga condicionamento de contexto para mitigar repetições cíclicas, ignora chiados puros através do threshold de ruído de `0.6` e persiste no arquivo CSV. |

### 3.3 `src/analise.py` — Motor Semântico e Estatístico

#### Classe `CientistaSDR`

| Método | Responsabilidade |
|---|---|
| `__init__(caminho_csv, pasta_saida)` | Constrói a estrutura analítica, configura a pasta de destino para as figuras e estatísticas da sessão. |
| `limpar_texto(texto)` | Processa o texto da transcrição em minúsculas e remove pontuações e dígitos numéricos soltos via expressões regulares. |
| `extrair_bigramas(palavras)` | Constrói pares contíguos de palavras (bigramas) a partir de uma lista de unigramas. |
| `mapear_ontologia(palavras)` | Varre recursivamente a árvore do dicionário `ONTOLOGIA_OSINT` em busca de correspondências diretas de palavras para identificar os domínios governamentais e táticos no sinal de rádio. |
| `analise_estatistica(texto)` | Pipeline de NLP: limpa o texto → filtra mais de 70 stopwords comerciais e legislativas → extrai unigramas e bigramas úteis → dispara o mapeamento ontológico. |
| `gerar_graficos(df_completo)` | Gera 5 figuras acadêmicas em 300 dpi: **Fig 1** (Termos Frequentes), **Fig 2** (Bigramas de Expressões), **Fig 3** (Linha do Tempo de interceptações por horário), **Fig 4** (Nuvem de Palavras com wordcloud) e **Fig 5** (Gráfico Donut de Domínios OSINT sintonizados). |
| `executar_analise(limite)` | Orquestra a execução estatística sobre o CSV. Instrumentado com `tracemalloc` para medir o consumo de RAM e registrar logs de desempenho e tempos de processamento. Exporta o consolidado ordenado de palavras mais frequentes para o arquivo `matriz_estatistica.csv`. |

### 3.4 `src/captura.py` — Módulo Legado

#### Classe `SDRReceiver`

| Método | Responsabilidade |
|---|---|
| `__init__(...)` | Configura parâmetros de captura (frequência, duração, caminhos de `rtl_fm.exe` e `sox.exe`). |
| `record_audio` | Cria pipeline de subprocessos `rtl_fm → sox` via pipe stdout/stdin. Gerencia ciclo de vida dos processos com terminação explícita e tempo de recuperação USB. **Não utilizado ativamente.** |0.1. |
| `gerar_graficos_separados(df)` | Gera 5 figuras científicas: (1) barras de termos frequentes, (2) pizza de categorias, (3) barras de entidades com word-wrap, (4) subplot duplo de desempenho CPU vs LLM (tempo + RAM), (5) série temporal de interceptações por hora. Todas salvas em 300 dpi. |
| `executar_analise(limite)` | Orquestrador: lê CSV → seleciona últimos N registros → executa análise dual por registro → gera gráficos → exporta relatório CSV consolidado (`relatorio_alertas_tcc.csv`). |

### 3.4 `src/captura.py` — Módulo Legado

#### Classe `SDRReceiver`

| Método | Responsabilidade |
|---|---|
| `__init__(...)` | Configura parâmetros de captura (frequência, duração, caminhos de `rtl_fm.exe` e `sox.exe`). |
| `record_audio` | Cria pipeline de subprocessos `rtl_fm → sox` via pipe stdout/stdin. Gerencia ciclo de vida dos processos com terminação explícita e tempo de recuperação USB. **Não utilizado ativamente.** |

---

## 4. Padrões de Projeto

### 4.1 Producer-Consumer (com Buffer Thread-Safe)

O padrão mais crítico do sistema. A `thread_master_loop` (producer) gera amostras de áudio processado e as deposita no `buffer_audio`. O `callback_audio` do sounddevice (consumer) consome essas amostras em ritmo determinado pelo driver de áudio. A sincronização é garantida por `threading.Lock`, e o buffer possui limite de 2 segundos para evitar acúmulo de latência.

### 4.2 Observer / Event-Driven (Qt Signals & Slots)

Todos os sliders e botões da interface utilizam o sistema de signals/slots do Qt: `slider.valueChanged.connect(self.handler)`. Isso desacopla a geração de eventos da lógica de negócio, permitindo que a UI reaja a mudanças de estado sem polling.

### 4.3 Lazy Import

O módulo `src/analise.py` (e sua pesada cadeia de dependências: pandas, matplotlib, seaborn, ollama) é importado **apenas quando o utilizador clica em "Gerar Dashboard"** (dentro de `rodar_analise`). Isso evita carregar ~200MB+ de bibliotecas no arranque da aplicação.

### 4.4 Template Method (Implícito)

O `executar_analise` funciona como um template method: define a sequência fixa (ler CSV → iterar registos → análise quantitativa → análise qualitativa → gerar gráficos → exportar), delegando cada passo a métodos especializados.

### 4.5 Stateful Filter Chain

Os filtros DSP (Butterworth e De-Emphasis) mantêm estado (`zi`) entre iterações do loop. Este padrão garante continuidade do sinal entre blocos de 102.400 amostras, eliminando artefatos de fronteira (cliques e descontinuidades).

### 4.6 Graceful Shutdown

O `closeEvent` implementa um protocolo de encerramento ordenado: sinaliza → espera drenagem → fecha streams → libera hardware. Previne corrupção de estado do dispositivo USB.

### 4.7 Smart Snapping (Quantização de Ganho)

O `mudar_ganho` implementa um padrão de adaptação: o valor contínuo do slider é mapeado para o valor discreto mais próximo aceite pelo hardware (`min(..., key=lambda)`). A UI é atualizada com o valor real, não o desejado.

---

## 5. Pontos de Extensibilidade

### 5.1 Multi-Frequência e Scanning

O sistema já possui separação entre `frequencia_atual` e o loop de captura. É possível implementar um **scanner automático** que varra uma faixa de frequências, sintonizando cada uma por N segundos e acumulando transcrições. O `toggle_missao` já suporta modos de captura parametrizáveis via `combo_modo`.

### 5.2 Modelos de IA Intercambiáveis

- **Whisper:** O `modelo_tamanho` é parametrizado no construtor de `TranscritorSDR`. Trocar de `base` para `small`, `medium` ou `large` requer apenas alterar essa string.
- **LLM:** O `modelo_llm` em `CientistaSDR` é uma string (`llama3.2:1b`). Qualquer modelo compatível com Ollama pode ser usado sem alterar código (ex: `mistral`, `gemma`, `phi3`).

### 5.3 Persistência e Banco de Dados

O CSV é o mecanismo atual de persistência. A interface `escolher_csv` já permite operar sobre ficheiros distintos. A migração para SQLite ou PostgreSQL requer apenas substituir os métodos `_inicializar_csv` e o bloco de escrita em `transcrever`, mantendo a mesma interface pública.

### 5.4 Novos Tipos de Análise

O `executar_analise` itera sobre registros e delega a métodos individuais. Novas análises (ex: análise de sentimento, detecção de alertas urgentes, correlação cruzada entre frequências) podem ser adicionadas como novos métodos na classe `CientistaSDR` e chamadas dentro do loop de iteração.

### 5.5 Exportação de Relatórios

O sistema já gera PNGs e CSVs. A adição de exportação para PDF (via `reportlab` ou `fpdf2`), HTML interativo (via `plotly`), ou integração com APIs externas (Telegram, webhook) pode ser feita como módulos adicionais na pasta `src/`.

### 5.6 Modos de Modulação

O motor DSP em `thread_master_loop` implementa desmodulação WBFM. O pipeline de filtros é modular: substituir o bloco de desmodulação (linha 353 de `app.py`) por outros esquemas (AM, SSB, NBFM) é viável sem refatoração estrutural. O `SDRReceiver` legado já referencia o parâmetro `-M wbfm`, indicando que a arquitetura contemplava múltiplos modos.

### 5.7 Dashboard em Tempo Real

O `pyqtgraph` já renderiza o espectro em tempo real. É possível adicionar novos widgets (waterfall/spectrogram 2D, medidor de SNR, indicador de nível de áudio) como novos `PlotWidget` no layout principal.

---

## 6. Guia de Manutenção

### 6.1 Dependências Críticas e Versões

| Dependência | Risco | Observação |
|---|---|---|
| **PyQt6** | 🟡 Médio | Incompatível com PyQt5. Migrar para PySide6 requer renomear imports (API idêntica). |
| **openai-whisper** | 🔴 Alto | Depende de `torch` e `ffmpeg`. O `ffmpeg` **deve estar no PATH** do sistema para a transcrição funcionar. Não está listado no `requirements.txt`. |
| **pyrtlsdr** | 🟡 Médio | Depende da `rtlsdr.dll` presente em `ferramentas/rtl-sdr/`. O PATH é modificado em runtime (linha 15 de `app.py`). Se a DLL não for encontrada, o import falha silenciosamente até a primeira chamada `RtlSdr()`. |
| **ollama** | 🟡 Médio | Requer o servidor Ollama rodando em `localhost:11434`. Se o servidor estiver offline, `analise_qualitativa_llm` captura a exceção mas classifica como "Erro". |

### 6.2 Configuração de Ambiente

1. **Drivers USB:** A antena RTL-SDR requer drivers WinUSB instalados via **Zadig**. Sem eles, `RtlSdr()` lançará exceção.
2. **Servidor Ollama:** Deve estar rodando antes de clicar em "Gerar Dashboard". Instalar e executar: `ollama serve` + `ollama pull llama3.2:1b`.
3. **ffmpeg:** Dependência implícita do Whisper. Instalar via `choco install ffmpeg` ou adicionar manualmente ao PATH.
4. **Python 3.10+:** Necessário para compatibilidade com PyQt6 e tipagem moderna.

### 6.3 Ficheiros Não Versionados (`.gitignore`)

- `dados/brutos/` e `*.wav` — Chunks de áudio bruto (podem atingir GBs).
- `dados/graficos_tcc/` — PNGs gerados pela análise.
- `venv/`, `__pycache__/` — Ambientes virtuais e bytecode.

### 6.4 Pontos de Atenção no Código

| Local | Observação |
|---|---|
| `app.py:73-78` | `except: pass` genérico no `closeEvent`. Pode ocultar erros de liberação de hardware. Recomenda-se logging. |
| `app.py:308` | `except: pass` no arranque de ganho. Falhas de comunicação com a antena são silenciadas. |
| `app.py:372-373` | `except: pass` no loop principal DSP. Erros de leitura do SDR (USB desconectado) são ignorados, o loop continua tentando. |
| `app.py:367` | O threshold de 300 blocos para chunk é um **magic number**. Deveria ser uma constante nomeada. |
| `config.py` | Ficheiro **vazio**. Indica intenção de centralizar configurações que atualmente estão hardcoded em `app.py` (frequência padrão, ganho, taxa de amostragem, etc.). |
| `main.py` | Ficheiro **vazio**. O entry point real é `app.py`. Pode indicar plano futuro de separação CLI vs GUI. |
| `src/captura.py` | Módulo **órfão** — não é importado por nenhum ficheiro ativo. Referencia `sox.exe` que não está incluído em `ferramentas/`. |
| `analise.py:226` | `os.startfile()` é **Windows-only**. Quebra em Linux/macOS. |
| `transcricao.py:20-21` | O CSV de transcrições é criado em `dados/` (raiz), mas `app.py` espera-o em `dados/banco_dados/`. Isso cria **dois ficheiros CSV distintos** se ambos os caminhos forem utilizados. |

### 6.5 Performance e Limites

- **Buffer de áudio:** Limitado a 2 segundos (`taxa_audio * 2`). Se o processamento atrasar, áudio antigo é descartado silenciosamente.
- **Memória Whisper:** O modelo `base` ocupa ~140MB de RAM permanentemente após carregamento no `__init__` do `TranscritorSDR`.
- **Chunks concorrentes:** Cada chunk de 30s dispara uma nova thread (`processar_chunk`). Não há pool ou limite de threads. Capturas longas podem gerar dezenas de threads simultâneas.
- **Gráficos matplotlib:** O backend `Agg` e `gc.collect()` explícito mitigam vazamentos de memória, mas sessões muito longas de análise podem acumular objetos temporários.

### 6.6 Estrutura de Diretórios em Runtime

```
projeto/
├── app.py                          # Entry point e motor DSP
├── config.py                       # (Vazio — reservado)
├── main.py                         # (Vazio — reservado)
├── requirements.txt                # Dependências pip
├── src/
│   ├── transcricao.py              # Whisper STT + persistência CSV
│   ├── analise.py                  # Llama 3.2 + dashboards
│   └── captura.py                  # (Legado — não utilizado)
├── dados/
│   ├── banco_transcricoes.csv      # CSV gerado por transcricao.py
│   ├── banco_dados/                # Diretório alternativo de CSV (app.py)
│   ├── brutos/                     # Chunks WAV organizados por data/hora
│   │   └── 2026-05-13/
│   │       └── 15h30m00s/
│   │           └── chunk.wav
│   └── graficos_tcc/               # PNGs gerados pela análise
│       ├── *_fig1_palavras.png
│       ├── *_fig2_categorias.png
│       ├── *_fig3_entidades.png
│       ├── *_fig4_desempenho.png
│       └── *_fig5_linha_do_tempo.png
└── ferramentas/
    └── rtl-sdr/                    # DLLs e binários nativos Windows
        ├── rtlsdr.dll
        ├── rtl_fm.exe
        └── ...
```

---

> **Nota Final:** Este documento reflete o estado do codebase na data de geração. Alterações subsequentes no código devem ser refletidas com atualizações neste ficheiro para manter sua utilidade como referência canónica do sistema.
