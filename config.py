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
# INTERFACE GRÁFICA
# =============================================================================

INTERVALO_TIMER_MS: int     = 220    # período do QTimer do espectrograma (~8 FPS)
FFT_SIZE: int               = 4_096  # amostras para cálculo da PSD
LARGURA_PAINEL_LATERAL: int = 380    # px — largura fixa do painel de controlos

# =============================================================================
# ANÁLISE ESTATÍSTICA E PLN (Processamento de Linguagem Natural)
# =============================================================================

# Lista de palavras que serão ignoradas ao fazer contagem de frequência e estatísticas
STOPWORDS = {
    # Artigos e Preposições
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "para", "com", "sem", "que", "e", "ou", "mas", "se", "aos",
    
    # Pronomes
    "eu", "você", "ele", "ela", "nós", "eles", "elas",
    "me", "te", "se", "lhe", "nos", "vos", "lhes", "dele", "dela",
    "este", "esta", "esse", "essa", "aquele", "aquela",
    "isto", "isso", "aquilo", "quem", "qual", "quais", "seu", "sua",
    
    # Advérbios e muletas de linguagem falada ao vivo
    "não", "sim", "já", "só", "também", "mais", "muito", "aqui", "ali", "lá",
    "como", "quando", "onde", "porque", "tá", "né", "aí", "então", "tipo", "assim", 
    "gente", "sendo", "até", "fim", "dois", "três", "apoio", "ape", "medida",
    "chegou", "acabou", "algumas", "alguns", "bota", "põe", "olha", "vê", "ouvir", "pra",
    
    # Verbos de ligação muito comuns (sem peso analítico para OSINT)
    "ser", "estar", "ter", "haver", "fazer", "ir", "dar", "ver", "ficar",
    "é", "são", "foi", "foram", "era", "vou", "vai", "vão", "tem", "têm", "tinha", "está", "estão", "estava"
}

# =============================================================================
# ONTOLOGIA DE RÁDIO COMERCIAL E LEGISLATIVA (Foco: Senado & Jornalismo)
# Mapeia a grade de programação de FMs comerciais e rádios institucionais.
# =============================================================================
ONTOLOGIA_OSINT = {
    "Política e Legislativo (Senado)": {
        "Processo Legislativo": ["projeto", "lei", "votação", "plenário", "comissão", "relator", "emenda", "veto", "pauta", "aprovação", "debate", "audiência", "requerimento", "decreto", "constituição"],
        "Instituições e Cargos": ["senado", "senador", "senadora", "câmara", "deputado", "congresso", "república", "presidente", "ministro", "stf", "governo", "parlamentar", "tribunal", "justiça", "planalto"]
    },
    "Economia e Finanças": {
        "Mercado": ["economia", "dólar", "inflação", "juros", "selic", "mercado", "bolsa", "investimento", "imposto", "arrecadação", "orçamento", "pib", "crédito", "taxa"],
        "Trabalho e Direitos": ["emprego", "desemprego", "salário", "trabalhador", "empresa", "indústria", "comércio", "direitos", "aposentadoria", "previdência", "sindicato"]
    },
    "Jornalismo e Utilidade Pública": {
        "Notícias e Reportagem": ["reportagem", "entrevista", "jornal", "notícia", "informação", "destaque", "urgente", "manchete", "repórter", "informe", "boletim", "estúdio", "locutor"],
        "Trânsito e Clima": ["trânsito", "rodovia", "acidente", "engarrafamento", "clima", "tempo", "chuva", "temperatura", "previsão", "calor", "frio", "sol", "estrada", "lentidão"],
        "Saúde e Educação": ["saúde", "hospital", "médico", "paciente", "vacina", "doença", "escola", "aluno", "professor", "ensino", "universidade", "pesquisa", "ciência", "sus"]
    },
    "Cultura e Entretenimento": {
        "Música e Arte": ["música", "mpb", "cantor", "banda", "álbum", "sucesso", "canção", "artista", "cultura", "cinema", "teatro", "livro", "literatura", "exposição", "poesia"],
        "Interação com Ouvinte": ["sorteio", "prêmio", "promoção", "participação", "rádio", "ouvinte", "sintonia", "ligação", "telefone"]
    },
    "Desporto": {
        "Futebol e Competições": ["futebol", "gol", "neymar", "copa", "seleção", "campeão", "jogo", "time", "penta", "pelé", "bola", "convocação", "estádio", "torcida", "árbitro", "juiz", "pênalti", "var", "técnico", "campeonato", "final", "medalha", "olimpíadas"]
    },
    "Religião e Fé": {
        "Práticas e Cultos": ["deus", "jesus", "igreja", "amém", "oração", "senhor", "fé", "culto", "livramento", "glória", "aleluia", "pastor", "padre", "missa", "bíblia"]
    },
    "Sociedade e Eventos": {
        "Festividades": ["show", "festa", "evento", "festival", "ingresso", "público", "palco", "carnaval", "romaria", "excursão", "passeata"]
    },
    "Segurança Pública e Crime": {
        "Armamento": ["fuzil", "pistola", "arma", "tiro", "calibre", "bala", "fogo", "armados", "munição", "carregador", "escopeta", "metralhadora", "oitão", "disparo", "tiroteio"],
        "Mobilidade Tática": ["viatura", "moto", "fuga", "perseguição", "cerco", "veículo", "batalhão", "barreira", "blitz", "helicóptero", "águia", "comboio", "patrulha", "ronda", "camburão"],
        "Ocorrência": ["roubo", "furto", "assalto", "crime", "vítima", "suspeito", "flagrante", "comando", "homicídio", "sequestro", "latrocínio", "extorsão", "golpe", "fraude", "invasão", "refém", "meliante"],
        "Narcóticos e Facções": ["droga", "tráfico", "apreensão", "boca", "carga", "pino", "maconha", "cocaína", "entorpecentes", "crack", "haxixe", "traficante", "facção", "pcc", "cv", "operação"]
    },
    "Trânsito e Logística": {
        "Acidentes e Resgate": ["batida", "colisão", "acidente", "capotamento", "ferido", "ambulância", "resgate", "bombeiros", "samu", "óbito", "atropelamento", "engavetamento", "socorro"],
        "Vias e Fluxo": ["engarrafamento", "lento", "parado", "pista", "rodovia", "interditada", "semáforo", "radar", "trânsito", "desvio", "bloqueio", "pedágio", "marginal", "avenida", "congestionamento", "cruzamento"],
        "Transporte": ["ônibus", "metrô", "trem", "estação", "terminal", "caminhão", "carreta", "frete", "motorista", "passageiro", "frota", "aeroporto", "porto"]
    }
}