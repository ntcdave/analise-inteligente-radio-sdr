"""
config.py — Configurações centralizadas do Sistema SDR Inteligente.

Todas as constantes do projeto residem aqui.
Nenhum valor hardcoded deve existir em app.py, src/dsp.py ou src/transcricao.py.
"""

import os

# =============================================================================
# CAMINHOS E PASTAS DE PROJETOS
# =============================================================================

BASE_DIR         = os.path.abspath(os.path.dirname(__file__))
CAMINHO_DLL      = os.path.join(BASE_DIR, "ferramentas", "rtl-sdr")
CAMINHO_DADOS    = os.path.join(BASE_DIR, "dados")

# Nova estrutura: As sessões (ex: "captura_dia_1") serão subpastas dentro de 'projetos'.
# Cada subpasta conterá seus próprios arquivos brutos (.wav), transcrição (.csv) e estatísticas.
CAMINHO_PROJETOS = os.path.join(CAMINHO_DADOS, "projetos")

# =============================================================================
# HARDWARE RTL-SDR
# =============================================================================

FREQUENCIA_PADRAO_MHZ: float = 100.9
GANHO_PADRAO_DB: float       = 40.0
SAMPLE_RATE_SDR: int         = 1_024_000   # Hz — taxa de amostragem do RTL-SDR
TAMANHO_BLOCO_SDR: int       = 262_144     # amostras por leitura USB (~250 ms);
                                           # deve ser múltiplo de 16 384 (exigência do driver)

# =============================================================================
# PIPELINE DSP
# =============================================================================

DECIMACAO_IQ: int    = 4     # 1.024 MHz → 256 kHz
DECIMACAO_AUDIO: int = 8     # 256 kHz   →  32 kHz
TAXA_AUDIO: int      = SAMPLE_RATE_SDR // DECIMACAO_IQ // DECIMACAO_AUDIO  # 32 000 Hz

DEEMPHASIS_TAU: float  = 75e-6     # constante de tempo do filtro de de-emphasis (padrão FM)
BANDA_PADRAO_HZ: float = 170_000.0 # largura de banda do canal FM (WBFM)
ORDEM_FILTRO: int      = 3         # ordem do filtro Butterworth passa-baixa

# =============================================================================
# RING BUFFER DE ÁUDIO (SPSC, sem lock)
# =============================================================================

TAMANHO_RING: int    = TAXA_AUDIO * 4  # 4 s @ 32 kHz = 128 000 amostras
BLOCKSIZE_AUDIO: int = 2_048           # frames por callback do sounddevice (~64 ms @ 32 kHz)

# =============================================================================
# CAPTURA E TRANSCRIÇÃO
# =============================================================================

BLOCOS_POR_CHUNK: int    = 300       # nº de blocos DSP antes de salvar um chunk .wav (~30 s)
MODELO_WHISPER: str      = "base"    # "base" | "small" | "medium" | "large"
MAX_WORKERS_WHISPER: int = 2         # threads paralelas de transcrição Whisper

# =============================================================================
# ANÁLISE ESTATÍSTICA E PLN (Processamento de Linguagem Natural)
# =============================================================================

# Lista de palavras que serão ignoradas ao fazer contagem de frequência e estatísticas
STOPWORDS = {
    # Artigos e Preposições
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "para", "com", "sem", "que", "e", "ou", "mas", "se",
    
    # Pronomes
    "eu", "você", "ele", "ela", "nós", "eles", "elas",
    "me", "te", "se", "lhe", "nos", "vos", "lhes",
    "este", "esta", "esse", "essa", "aquele", "aquela",
    "isto", "isso", "aquilo", "quem", "qual", "quais",
    
    # Advérbios e outras palavras comuns sem valor semântico forte
    "não", "sim", "já", "só", "também", "mais", "muito", "aqui", "ali", "lá",
    "como", "quando", "onde", "porque",
    
    # Verbos auxiliares ou muito comuns
    "ser", "estar", "ter", "haver", "fazer", "ir",
    "é", "são", "foi", "foram", "vai", "vão", "tem", "têm", "está", "estão",

}

# =============================================================================
# INTERFACE GRÁFICA
# =============================================================================

INTERVALO_TIMER_MS: int     = 220    # período do QTimer do espectrograma (~8 FPS)
FFT_SIZE: int               = 4_096  # amostras para cálculo da PSD
LARGURA_PAINEL_LATERAL: int = 380    # px — largura fixa do painel de controlos