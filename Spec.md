# 📡 Spec.md — Especificação Técnica de Pesquisa: Sistema SDR Inteligente

> **Projeto:** Sistema SDR Inteligente — Monitoramento e Edge AI  
> **Tipo:** Especificação de Software / Projeto de Pesquisa Científica  
> **Versão do Documento:** 1.0 (Higienizada e Anonimizada)

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

O sistema opera como um **pipeline de processamento local (Edge Computing)** estruturado em três camadas concorrentes. O objetivo é receber sinais eletromagnéticos analógicos, processá-los digitalmente, transcrever a voz demodulada para texto e gerar relatórios estatísticos e mapeamentos ontológicos determinísticos:

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│  ANTENA      │───▸│  MOTOR DSP       │───▸│    WHISPER (STT)    │───▸│  NLP & ONTOLOGIA│
│  RTL-SDR V4  │    │  (src/dsp.py)    │    │ (src/transcricao.py)│    │ (src/analise.py)│
│  Hardware    │    │  Demodulação FM  │    │    Áudio → Texto    │    │  Texto → OSINT  │
└─────────────┘    └──────────────────┘    └─────────────────────┘    └─────────────────┘
       │                    │                         │                        │
       │              ┌─────▼──────┐            ┌─────▼──────┐          ┌──────▼──────┐
       │              │ sounddevice│            │  Sessão CSV│          │  Dashboard  │
       │              │ (Áudio ao  │            │  (dados/   │          │ (Matplotlib │
       │              │  vivo)     │            │  projetos) │          │  + Donut)   │
       └──────────────┴────────────┘            └────────────┘          └─────────────┘
```

### 1.2 Fluxo de Dados Detalhado

#### Fase 1 — Captura e Processamento de Sinal Digital (Camada DSP em `src/dsp.py`)
1. **Inicialização do Hardware:** O módulo `RtlSdr` inicializa a antena conectada via USB, aplicando a taxa de amostragem física de **1.024 MHz** (`SAMPLE_RATE_SDR`), sintonizando a frequência central de FM configurada e quantizando o ganho de RF discreto ideal aceito pelo hardware.
2. **Leitura Concorrente (Thread `sdr-reader`):** Esta thread executa chamadas bloqueantes de leitura USB do driver da antena, puxando blocos de **262.144 amostras I/Q** (aproximadamente 250 ms de sinal bruto por ciclo). As amostras brutas são inseridas em uma fila thread-safe circular de limite curto (`_iq_queue`) para desacoplar a leitura física do cálculo matemático.
3. **Desmodulação e Filtragem (Thread `dsp-worker`):**
   * **Decimação IQ (÷4):** Aplica subamostragem direta reduzindo o fluxo de sinal de 1.024 MHz para 256 kHz.
   * **Filtro Butterworth Passa-Baixa (Ordem 3):** Aplica um filtro de canal de banda passante sintonizável (padrão de 170 kHz) no sinal IQ complexo. Os estados internos do filtro (`zi`) são persistidos continuamente em memória para eliminar artefatos de transição de fase nas bordas dos blocos.
   * **Demodulador Discriminador de Fase:** Extrai a modulação em frequência calculando a diferença de fase entre amostras complexas consecutivas através do cálculo vetorial de fase: $demodulado = np.angle(sinal[1:] \times np.conj(sinal[:-1]))$.
   * **Decimação de Áudio (÷8):** Reduz o sinal desmodulado de 256 kHz para a taxa de amostragem de reprodução e IA de **32.000 Hz** (`TAXA_AUDIO`).
   * **Filtro De-Emphasis (75 µs):** Aplica um filtro IIR passa-baixa analógico equivalente para restabelecer a atenuação natural de altas frequências praticada na transmissão de emissoras FM comerciais.
4. **Alimentação da Saída de Áudio:** Se a monitorização ao vivo estiver habilitada, o sinal de áudio é inserido circularmente em um **Ring Buffer circular SPSC** (Single-Producer Single-Consumer) atômico, de onde a thread sensível de callback da biblioteca `sounddevice` consome amostras de forma síncrona.

#### Fase 2 — Processamento de Voz Offline (Camada STT em `src/transcricao.py`)
5. **Acumulação:** Se a gravação de inteligência estiver ligada, a thread `dsp-worker` armazena continuamente os blocos resultantes no `buffer_ia`.
6. **Matemática do Chunk de Áudio:** O sistema de IA do Whisper requer janelas estáveis de áudio. A acumulação aguarda atingir **300 blocos** (`BLOCOS_POR_CHUNK`).
   $$\text{Amostras por Bloco Decimado} = \frac{262.144}{32} = 8.192 \text{ amostras}$$
   $$\text{Duração de 1 Bloco} = \frac{8.192 \text{ amostras}}{32.000 \text{ Hz}} = 0.256 \text{ segundos}$$
   $$\text{Duração Real do Chunk} = 300 \times 0.256\text{s} = \mathbf{76.8 \text{ segundos}}$$
7. **Persistência de Áudio:** A cada 300 blocos acumulados, a thread do DSP salva a fatia de áudio convertida em sinal de 16 bits PCM Mono em um arquivo Wave (`audio_HHhMMmSSs.wav`) na pasta específica da missão ativa (`dados/projetos/<nome_sessao>/audios/`).
8. **Transcrição Concorrente:** A tarefa de transcrição é empurrada para uma fila gerenciada por um `ThreadPoolExecutor` com até 2 workers simultâneos (`MAX_WORKERS_WHISPER`), executando a inferência local da inteligência artificial OpenAI Whisper (`base`).
9. **Filtros Anti-Alucinação:** A inferência roda forçando o idioma em português (`pt`), operando em precisão simples (`fp16=False` para garantir compatibilidade computacional de CPU), desativando o histórico contextual de loops anteriores e descartando textos menores que 3 caracteres ou classificados como chiados/silêncios típicos de rádio vazia.
10. **Banco de Dados CSV Local:** As transcrições qualificadas e válidas são gravadas via *append* no arquivo CSV dinâmico específico do projeto ativo: `dados/projetos/<nome_sessao>/transcricoes_<nome_sessao>.csv`.

#### Fase 3 — Inteligência Semântica e Estatística (Camada NLP em `src/analise.py`)
11. **Orquestração Offline sob Demanda:** O processamento estatístico de NLP é desacoplado do pipeline de gravação para garantir que as threads de áudio não sofram com gargalos computacionais. Ao clicar em *"Gerar Estatísticas"* na UI, a classe `CientistaSDR` executa uma varredura em lote (batch) no arquivo CSV consolidado da sessão ativa.
12. **Processamento de Linguagem Natural Clássico:**
    * **Limpeza e Normalização:** Remove caracteres especiais, pontuações e dígitos numéricos isolados via expressões regulares.
    * **Filtragem de Stopwords:** Limpa mais de 70 stopwords e termos comuns de rádio e muletas de linguagem ao vivo da língua portuguesa.
    * **Extração N-Gramas:** Agrupa palavras úteis gerando unigramas e pares de expressões recorrentes (bigramas).
13. **Mapeamento de Árvore Ontológica OSINT:** Classifica os termos de forma determinística varrendo a árvore estruturada `ONTOLOGIA_OSINT` em `config.py` para sintonizar palavras-chave com domínios táticos de interesse (Segurança Pública, Armamento, Narcotráficos/Facções, Trânsito, Sociedade, Política, Trânsito/Logística, etc.).
14. **Geração de Dashboards de Publicação:** Salva na pasta de estatísticas do projeto (`dados/projetos/<nome_sessao>/estatisticas/`) o consolidado de frequências `matriz_estatistica.csv` e 5 gráficos vetoriais de alta resolução (300 dpi):
    * **Fig 1:** Termos mais frequentes (Unigramas).
    * **Fig 2:** Expressões mais comuns (Bigramas).
    * **Fig 3:** Telemetria temporal (Interceptações por hora do dia).
    * **Fig 4:** Densidade semântica (Nuvem de Palavras clássica).
    * **Fig 5:** Mapeamento Ontológico (Gráfico de anel/Donut detalhando a distribuição dos domínios sintonizados no espectro).

---

## 2. Stack Técnica

### 2.1 Interface Gráfica

| Biblioteca | Papel no Sistema | Justificativa Técnica |
|---|---|---|
| **PyQt6** | Interface Gráfica Principal | Fornece arquitetura nativa orientada a eventos para sistemas Desktop, layouts responsivos QSS e timers thread-safe. |
| **pyqtgraph** | Espectrograma em Tempo Real | Biblioteca científica GPU-acelerada. Permite renderizar a densidade espectral do sinal SDR a taxas de quadro elevadas (~8 FPS) sem onerar a CPU do sistema. |
| **qtawesome** | Elementos Visuais e Ícones | Fornece catálogo vetorial de ícones técnicos de alta qualidade sem dependência de carregamento de recursos bitmap pesados. |

### 2.2 Processamento de Sinal Digital (DSP) e Áudio

| Biblioteca | Papel no Sistema | Justificativa Técnica |
|---|---|---|
| **numpy** | Álgebra Linear e Vetorização | Permite processar grandes matrizes de amostras I/Q complexas por leitura USB na velocidade do barramento nativo em C. |
| **scipy.signal** | Filtros Matemáticos | Implementa equações diferenciais estáveis de Butterworth e processamento contínuo de estados internos (`lfilter` + `zi`). |
| **sounddevice** | Saída e Callback de Áudio | Abre stream com o driver de áudio nativo em baixíssima latência usando buffers circulares. |
| **pyrtlsdr** & **pyrtlsdrlib** | Wrapper e DLLs da Antena | Realiza o mapeamento dinâmico e linkagem de chamadas C-types para a biblioteca nativa `rtlsdr.dll` no Windows. |

### 2.3 Inteligência Artificial e NLP

| Biblioteca / Componente | Papel no Sistema | Justificativa Técnica |
|---|---|---|
| **openai-whisper** | Speech-to-Text Offline | Transcritor neural altamente robusto a chiados e ruídos analíticos de rádio. Roda localmente sem dependência de internet. |
| **torch** | Backend Deep Learning | Fornece computação vetorial otimizada para a execução das redes neurais de inferência do Whisper. |
| **Dicionário Ontológico** | Busca Léxica Determinística | O mapeamento baseado na árvore estruturada `ONTOLOGIA_OSINT` em `config.py` fornece uma classificação semântica instantânea, reprodutível e com custo computacional nulo. |

### 2.4 Análise e Visualização

| Biblioteca | Papel no Sistema | Justificativa Técnica |
|---|---|---|
| **pandas** | Análise e Manipulação de Dados | Usado na leitura rápida do CSV consolidado das sessões, agrupamentos temporais e ordenação de registros históricos. |
| **matplotlib** (backend `Agg`) | Renderização de Imagens 300 dpi | Gera as figuras estáticas de alta qualidade para publicação acadêmica. O backend não-interativo `Agg` previne problemas de concorrência com a interface gráfica. |
| **seaborn** | Paletas Científicas e Estilo | Melhora a estética dos dashboards com gradientes de cores legíveis e estilos harmonizados. |
| **wordcloud** | Nuvem de Palavras | Gera a imagem analítica de densidade de termos do NLP. |

---

## 3. Dicionário de Funcionalidades

### 3.1 `app.py` — Interface Gráfica e Orquestração

#### Classe `MainWindow(QMainWindow)`
*   `__init__`: Inicializa variáveis de estado da captura, cria `TranscritorSDR` e `MotorDSP`, constrói a interface gráfica baseada em QSS escuro moderno e inicia o timer dinâmico de frame rate do espectrograma.
*   `closeEvent`: Garante desligamento gracioso: limpa flags de monitoramento, encerra os timers de clock de tempo, interrompe de forma segura a pool de threads do Whisper e desliga o barramento da antena RTL-SDR para evitar erros de violação de acesso em USB.
*   `_construir_interface`: Desenha a UI separada por Tabs (Sintonia de Rádio e Captura & Processamento), barra de ferramentas do espectrograma, PlotWidget do pyqtgraph e o terminal integrado de logs.
*   `_configurar_pastas_sessao`: Configura os caminhos físicos dinâmicos para a sessão de captura atual na pasta `dados/projetos/<nome_sessao>/`, isolando dados e gráficos.
*   `_escolher_pasta_sessao` / `_alterar_sessao`: Permite ao usuário buscar no disco uma pasta de missão antiga via janela de diálogo nativa (`QFileDialog`) ou renomear a sessão de forma dinâmica.
*   `_mudar_frequencia_slider` / `_mudar_frequencia_spin` / `_aplicar_frequencia`: Sincroniza e envia a nova frequência central em MHz para o motor DSP e altera a janela de eixos do espectrograma em tempo real.
*   `_mudar_ganho` / `_mudar_volume` / `_atualizar_label_ganho`: Atualiza o ganho analógico da antena em dB e ajusta o volume linear do áudio.
*   `_atualizar_eixos_grafico`: Ajusta a escala visual do pyqtgraph baseado nas preferências do usuário via sliders de ferramentas superior (Zoom X, Topo Y e Base Y).
*   `_toggle_audio`: Alterna o status de reprodução do áudio demodulado no alto-falante local, aplicando reset atômico no ring buffer.
*   `_atualizar_grafico`: Recupera os blocos IQ brutos em processamento pelo DSP, calcula a densidade de espectro e plota a curva no pyqtgraph a cada frame.
*   `_toggle_missao`: Inicializa ou encerra o ciclo de gravação e processamento em disco, travando modificações temporizadas enquanto estiver ativo.
*   `_verificar_termino_tempo`: QTimer disparado a cada 1 segundo. No modo *Por Duração*, encerra a captura ao atingir os minutos selecionados. No modo *Até Horário*, desliga o motor DSP ao cruzar o horário exato da máquina.
*   `_processar_chunk`: Roda em threads apartadas na pool de workers. Persiste o chunk de 76.8 segundos em arquivo WAV e dispara a conversão STT via Whisper local, salvando os resultados no CSV estruturado da sessão ativa.
*   `_toggle_retranscricao` / `_forcar_retranscricao` / `_restore_ui_rt`: Controla o pipeline concorrente de reprocessamento. Limpa o CSV anterior da sessão selecionada, localiza todos os arquivos WAV contidos na pasta de audios e re-transcreve recursivamente. Conta com flag de cancelamento seguro para o operador.
*   `_abrir_analise` / `_rodar_analise` / `_restore_ui_analise`: Executa o módulo `CientistaSDR` em thread daemonizada em background para processar NLP e exportar os 5 gráficos acadêmicos.

### 3.2 `src/transcricao.py` — Inteligência de Voz Local

#### Classe `TranscritorSDR`
*   `__init__(modelo_tamanho, caminho_csv)`: Carrega o modelo Whisper selecionado (padrão `"base"`) em cache na memória do sistema.
*   `_inicializar_csv`: Cria de forma atômica o cabeçalho estruturado do arquivo CSV da sessão ativa, caso ele não exista.
*   `transcrever(caminho_audio, frequencia_mhz)`: Dispara a inferência do Whisper com parâmetros rígidos anti-alucinação: desativa precisão de ponto flutuante de 16 bits (`fp16=False`), trava linguagem no português (`pt`), remove histórico contextual para impedir loops infinitos e rejeita alucinações comuns geradas pelo chiado estático de FM. Grava no CSV da sessão o timestamp, a frequência sintonizada, o caminho relativo do áudio e o texto resultante.

### 3.3 `src/analise.py` — Inteligência Semântica e NLP

#### Classe `CientistaSDR`
*   `__init__(caminho_csv, pasta_saida, callback_log)`: Inicializa as estruturas estatísticas do NLP clássico e aponta a pasta de destino dentro do projeto ativo.
*   `limpar_texto(texto)`: Normaliza o texto gerado pela voz (minúsculas, expressões regulares para apagar dígitos e pontuações).
*   `extrair_bigramas(palavras)`: Gera as cadeias pareadas de palavras a partir da sentença limpa.
*   `mapear_ontologia(palavras)`: Executa varreduras léxicas recursivas determinísticas comparando cada palavra da sentença contra o dicionário ontológico OSINT do `config.py` e extrai os domínios identificados no canal.
*   `analise_estatistica(texto)`: Executa de forma integrada o pipeline de NLP clássico (Limpeza → Stopwords → N-Gramas → Ontologia).
*   `gerar_graficos(df_completo)`: Renderiza as 5 figuras analíticas a 300 dpi (Termos Frequentes, Bigramas, Série Temporal de interceptação, Nuvem de Palavras e Donut Ontológico) usando matplotlib e seaborn, fechando os objetos visuais em seguida para prevenir vazamentos de RAM.
*   `executar_analise(limite)`: Método mestre orquestrador. Instrumentado com `tracemalloc` para auditoria fina de pegada de memória e tempo físico de execução em CPU. Exporta a agregação consolidada de termos mais comuns no arquivo `matriz_estatistica.csv`.

---

## 4. Padrões de Projeto

### 4.1 Producer-Consumer com Buffer Circular SPSC Lock-free
O sistema de monitoramento de áudio em tempo real possui duas frequências de relógio diferentes: a thread pesada de processamento matemático `dsp-worker` (producer) gera amostras demoduladas de forma variável, enquanto o callback sensível do hardware de áudio do `sounddevice` (consumer) requer blocos exatos e síncronos de áudio.
*   A comunicação é realizada através de um **Ring Buffer circular SPSC** (Single-Producer Single-Consumer). A sincronização atômica é baseada na publicação de ponteiros (`ring_write` e `ring_read`), impedindo stutters e bloqueios na thread crítica do driver de áudio do Windows.

### 4.2 Observer / Event-Driven (Qt Signals & Slots)
Para manter o desacoplamento rígido entre a interface PyQt6 e o motor lógico, as interações de UI (como sliders de alteração de portadora ou volume) utilizam o sistema nativo de conexões de sinais e slots:
*   A atualização de logs e parâmetros de sintonizador físico é feita via signals seguros (`pyqtSignal`), evitando polling desnecessário em loops e garantindo concorrência segura entre threads de processamento e a thread gráfica.

### 4.3 Lazy Import para Mitigação de Carga de Memória
A cadeia de importação de bibliotecas analíticas e de visualização gráfica (como pandas, matplotlib, seaborn e wordcloud) é extremamente pesada e pode consumir centenas de megabytes adicionais de RAM.
*   O import do módulo `src/analise.py` e suas dependências é executado de forma **lazy** (atrasada), carregando as bibliotecas em memória **apenas quando o operador clica no botão "Gerar Estatísticas"** (dentro do método `_rodar_analise`). Isso acelera a inicialização da aplicação principal e otimiza a RAM.

### 4.4 Stateful Filter Chain (Cadeia de Filtros com Memória)
Os blocos de dados I/Q são lidos e fatiados em ciclos de 250 ms. Se os filtros digitais de canal (passa-baixa Butterworth e De-Emphasis) fossem aplicados a cada bloco de forma independente, descontinuidades matemáticas severas ocorreriam nas fronteiras dos blocos de dados, gerando cliques e estalos acústicos insuportáveis para o operador.
*   O sistema resolve este problema preservando os estados internos do filtro (`zi`) entre as iterações do loop no `dsp-worker`, garantindo uma transição contínua e suave do sinal.

### 4.5 Graceful Encerramento Multithread
A antena RTL-SDR e os threads de cálculo de backend dependem de barramentos de hardware e subprocessos concorrentes.
*   O método `closeEvent` orquestra uma rotina de encerramento segura: desativa as flags lógicas das threads (`self._rodando`), aguarda a finalização dos laços em background, encerra de forma coordenada os workers de IA, fecha o stream do sounddevice e libera de forma controlada o ponteiro do hardware USB da antena, prevenindo falhas de segmentação de memória e travamentos do barramento USB.

---

## 5. Pontos de Extensibilidade

### 5.1 Scanning e Varredura Automática de Portadoras
O projeto já conta com o completo desacoplamento entre a frequência do hardware e a orquestração de gravação. É viável expandir o sistema adicionando um **módulo varredor (Scanner)** que modifique sequencialmente a frequência central em MHz a intervalos programados de tempo, registrando no CSV dinâmico os termos identificados em múltiplos canais de interesse.

### 5.2 Expansão do Modelo STT (Whisper)
O carregamento do Whisper em `src/transcricao.py` é totalmente parametrizado no construtor. É viável modificar a string do modelo no `config.py` de `"base"` para variantes de maior densidade de parâmetros (como `"small"`, `"medium"` ou `"large"`) em computadores dotados de GPUs dedicadas para elevar a precisão de conversão de voos complexos ou sinal de rádio sob condições severas de atenuação.

### 5.3 Integração com Outros Modos de Modulação (DSP)
O motor DSP implementado em `src/dsp.py` executa o cálculo de desmodulação para frequências moduladas de banda larga (WBFM). A estrutura interna da thread `dsp-worker` é modular: a substituição da fórmula aritmética de demodulação e dos fatores de decimação matemática permite estender o sistema de forma limpa para capturar transmissões de aviação civil (AM), rádio de banda estreita (NBFM) ou comunicações marítimas (SSB).

### 5.4 Mudança de Driver de Persistência (Banco de Dados)
O arquivamento estruturado é feito em arquivos planos CSV dinâmicos isolados por sessão. Para migrar o backend de persistência de dados históricos para um banco de dados relacional robusto (como SQLite local ou PostgreSQL em rede), necessita-se apenas substituir os métodos `_inicializar_csv` e a escrita em `transcrever` na classe `TranscritorSDR`, mantendo intacta toda a interface e consumo da UI gráfica.

---

## 6. Guia de Manutenção

### 6.1 Centralização Arquitetural em `config.py` e `main.py`
Ao contrário de versões de desenvolvimento anteriores, a codebase atual possui uma estrutura centralizada e madura:
*   **[main.py](./main.py) (O Bootstrap):** É o ponto de entrada único do sistema. Ele gerencia a codificação do terminal para garantir suporte a emojis e logs em Windows, injeta de forma dinâmica os caminhos físicos do executável `ffmpeg.exe` instalado via winget, adiciona a pasta DLL nativa nas variáveis de PATH e monta a inicialização da UI PyQt6 de forma segura.
*   **[config.py](./config.py) (A Central de Constantes):** Centraliza todos os parâmetros de hardware, constantes do pipeline de DSP (decimações, frequências de corte, de-emphasis), configurações de limites temporais, a lista otimizada de stopwords nacionais e a árvore taxonômica `ONTOLOGIA_OSINT`. **Nenhum parâmetro de processamento ou dicionário deve ser hardcoded nos arquivos de lógica.**


### 6.2 Dependências Críticas e Variáveis de Ambiente

| Biblioteca / Recurso | Risco de Quebra | Descrição e Ação Recomendada |
|---|---|---|
| **Drivers WinUSB (Zadig)** | 🔴 Alto | A antena RTL-SDR Blog V4 não será reconhecida pela biblioteca `RtlSdr` sem a substituição dos drivers padrão do Windows pelo driver WinUSB genérico. |
| **FFmpeg** | 🔴 Alto | O interpretador Whisper depende diretamente do binário do FFmpeg no Windows para decodificar áudio WAV. O `main.py` tenta localizar instalações via `winget` automaticamente, mas recomenda-se incluí-lo na variável PATH do sistema. |
| **Placa de Som (Áudio Host)** | 🟡 Médio | O `sounddevice` causará falhas ao tentar abrir o output stream físico se o computador host não contar com um dispositivo reprodutor de áudio padrão ativo. |
| **DLL Nativa rtlsdr.dll** | 🟡 Médio | O wrapper `pyrtlsdr` necessita do binário compilado da DLL em Windows. Ela é fornecida na pasta `ferramentas/rtl-sdr/` e mapeada dinamicamente pelo `main.py`. |

### 6.3 Estrutura de Diretórios em Runtime
O sistema de arquivos gerado durante a execução da aplicação é estruturado em sessões estanques de inteligência:

```
projeto/
├── main.py                             # Bootstrap e ponto de entrada da aplicação
├── app.py                              # Construção de interface PyQt6 e orquestração
├── config.py                           # Parâmetros, Stopwords e Árvore Ontológica
├── requirements.txt                    # Dependências reais do projeto Python
├── src/
│   ├── dsp.py                          # Motor DSP, ring buffer e threads concorrentes
│   ├── transcricao.py                  # Integração com Whisper local e escrita CSV
│   └── analise.py                      # Análise em lote (NLP estatístico e gráficos 300dpi)
├── dados/
│   └── projetos/                       # Pasta central de sessões organizadas
│       └── <nome_da_sessao>/           # Subpasta estruturada da sessão ativa
│           ├── audios/                 # Chunks WAV de 76,8s gravados pelo DSP
│           │   └── audio_15h30m22s.wav
│           ├── estatisticas/           # Gráficos acadêmicos e matriz consolidada
│           │   ├── fig1_termos.png
│           │   ├── fig2_expressoes.png
│           │   ├── fig3_linha_do_tempo.png
│           │   ├── fig4_nuvem_palavras.png
│           │   ├── fig5_ontologia.png
│           │   └── matriz_estatistica.csv
│           └── transcricoes_<nome_sessao>.csv # Banco de dados de voz e frequências da missão
└── ferramentas/
    └── rtl-sdr/                        # DLLs nativas da antena RTL-SDR para Windows
        ├── rtlsdr.dll
        ├── rtlsdr.lib
        └── ...
```

---

> **Nota Final:** Esta especificação reflete com absoluta exatidão o estado lógico e estrutural da codebase. Atualizações lógicas nos parâmetros ou nos motores do software devem ser documentadas neste arquivo para preservar a sua utilidade como bíblia canônica de arquitetura.
