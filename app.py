"""
app.py — Interface gráfica principal do Sistema SDR Inteligente.

Responsabilidade: construção da UI (PyQt6) e orquestração dos módulos.
Processamento pesado fica em:
    - src/dsp.py          → MotorDSP  (captura, demodulação)
    - src/transcricao.py  → TranscritorSDR  (Whisper STT)
    - src/analise.py      → CientistaSDR  (PLN Clássico + Gráficos)
"""

from __future__ import annotations

import logging
import os
import threading
import time
import wave
import glob
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import numpy as np
import pyqtgraph as pg
import qtawesome as qta  # <-- Importação vital para os ícones
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QPushButton,
    QSlider, QTextEdit, QVBoxLayout, QWidget, QMessageBox,
    QTabWidget, QGroupBox, QSplitter, QDoubleSpinBox
)

from config import (
    BASE_DIR,
    CAMINHO_PROJETOS,
    FFT_SIZE,
    FREQUENCIA_PADRAO_MHZ,
    GANHO_PADRAO_DB,
    INTERVALO_TIMER_MS,
    LARGURA_PAINEL_LATERAL,
    MAX_WORKERS_WHISPER,
    TAXA_AUDIO,
)
from src.dsp import MotorDSP
from src.transcricao import TranscritorSDR

logger = logging.getLogger(__name__)

# =========================================================================
# ESTILO GLOBAL (QSS) - Tema Dark Moderno
# =========================================================================
ESTILO_GLOBAL = """
QMainWindow {
    background-color: #0f1015;
    color: #e2e8f0;
    font-family: 'Segoe UI', system-ui, sans-serif;
}
QWidget {
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #2d3748;
    background-color: #1a202c;
    border-radius: 6px;
    margin-top: -1px;
}
QTabBar::tab {
    background: #2d3748;
    color: #a0aec0;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
}
QTabBar::tab:selected {
    background: #1a202c;
    color: #00ffcc;
    font-weight: bold;
    border: 1px solid #2d3748;
    border-bottom: 1px solid #1a202c;
}
QTabBar::tab:hover:!selected {
    background: #3a4759;
}
QGroupBox {
    border: 1px solid #2d3748;
    border-radius: 8px;
    margin-top: 18px;
    padding-top: 15px;
    font-weight: bold;
    color: #cbd5e0;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #00ffcc;
}
QSlider::groove:horizontal {
    border: 1px solid #2d3748;
    height: 6px;
    background: #0f1015;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #00ffcc;
    width: 16px;
    margin: -5px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: #33ffdb;
    width: 18px;
    margin: -6px 0;
}
QLineEdit, QDoubleSpinBox {
    background-color: #0f1015;
    border: 1px solid #2d3748;
    border-radius: 4px;
    padding: 6px;
    color: #e2e8f0;
}
QLineEdit:focus, QDoubleSpinBox:focus {
    border: 1px solid #00ffcc;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #2d3748;
    border-radius: 2px;
    width: 16px;
}
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #4a5568;
}
QTextEdit {
    background-color: #0a0b0e;
    color: #33ffdb;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 8px;
}
QPushButton {
    background-color: #2d3748;
    border: 1px solid #4a5568;
    border-radius: 4px;
    padding: 8px;
    color: white;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #4a5568;
    border: 1px solid #00ffcc;
}
QPushButton:disabled {
    background-color: #1a202c;
    color: #4a5568;
    border: 1px solid #2d3748;
}
"""

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SDR TCC — Monitorização e Edge AI (Estatística)")
        self.resize(1300, 850)
        self.setMinimumWidth(1000)
        self.setStyleSheet(ESTILO_GLOBAL)

        # --- Estado da missão de captura ---
        self.gravando = False
        self.inicio_captura_tempo = 0.0
        self.duracao_alvo_segundos = 0.0
        self.horario_alvo = ""

        # --- Gestão de Sessões / Projetos ---
        self.nome_sessao_atual = f"sessao_{datetime.now().strftime('%Y%m%d_%H%M')}"
        self.pasta_sessao = ""
        self.pasta_audios = ""
        self.pasta_graficos = ""
        self.caminho_csv = ""
        self._configurar_pastas_sessao(self.nome_sessao_atual)

        # --- Eixo de frequências pré-alocado (imutável) ---
        self._freq_axis = np.linspace(-0.512, 0.512, FFT_SIZE)

        # --- Motor DSP ---
        self.dsp = MotorDSP(
            frequencia_mhz=FREQUENCIA_PADRAO_MHZ,
            ganho_db=GANHO_PADRAO_DB,
        )
        self.dsp.on_ganho_real = self._cb_ganho_real
        self.dsp.on_erro_antena = self._cb_erro_antena
        self.dsp.on_chunk_pronto = self._cb_chunk_pronto
        self.dsp.on_verificar_termino = self._cb_verificar_termino

        # --- Transcritor + pool de threads dedicado ---
        self.transcritor = TranscritorSDR(modelo_tamanho="base")
        self.pool_chunks = ThreadPoolExecutor(
            max_workers=MAX_WORKERS_WHISPER,
            thread_name_prefix="whisper",
        )

        # --- Timer do gráfico de espectro ---
        self.timer_grafico = QTimer()
        self.timer_grafico.timeout.connect(self._atualizar_grafico)

        self._construir_interface()
        
        # Aplicar ranges iniciais do gráfico
        self._atualizar_eixos_grafico()
        
        self.timer_grafico.start(INTERVALO_TIMER_MS)
        self.dsp.iniciar()

    # =========================================================================
    # GESTÃO DE PASTAS DE PROJETO/SESSÃO
    # =========================================================================
    def _configurar_pastas_sessao(self, nome: str) -> None:
        """Configura os caminhos lógicos (Lazy Creation). Pastas físicas são criadas sob demanda."""
        self.nome_sessao_atual = nome
        self.pasta_sessao = os.path.join(CAMINHO_PROJETOS, self.nome_sessao_atual)
        self.pasta_audios = os.path.join(self.pasta_sessao, "audios")
        self.pasta_graficos = os.path.join(self.pasta_sessao, "estatisticas")
        self.caminho_csv = os.path.join(self.pasta_sessao, f"transcricoes_{self.nome_sessao_atual}.csv")
        
        if hasattr(self, 'transcritor'):
            self.transcritor.caminho_csv = self.caminho_csv

    # =========================================================================
    # CICLO DE VIDA DA JANELA
    # =========================================================================
    def closeEvent(self, event) -> None:
        logger.info("A encerrar aplicação…")
        self.gravando = False
        self.dsp.gravando = False
        self.timer_grafico.stop()
        time.sleep(0.3)
        self.pool_chunks.shutdown(wait=False)
        self.dsp.parar()
        event.accept()

    # =========================================================================
    # CONSTRUÇÃO DA INTERFACE
    # =========================================================================
    def _construir_interface(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout_raiz = QHBoxLayout(central)
        layout_raiz.setContentsMargins(10, 10, 10, 10)
        layout_raiz.setSpacing(15)

        # ---- PAINEL LATERAL (Fixo) ----
        painel_lateral = QWidget()
        painel_lateral.setFixedWidth(LARGURA_PAINEL_LATERAL + 20)
        col_lateral = QVBoxLayout(painel_lateral)
        col_lateral.setContentsMargins(0, 0, 0, 0)
        col_lateral.setSpacing(15)

        # -- Frequência Destaque --
        self.lbl_freq = QLabel(f"{FREQUENCIA_PADRAO_MHZ} MHz")
        self.lbl_freq.setStyleSheet("""
            font-size: 46px; 
            font-weight: bold; 
            color: #00ffcc; 
            background-color: #0a0b0e; 
            border: 2px solid #2d3748;
            border-radius: 10px; 
            padding: 15px 10px;
            letter-spacing: 2px;
        """)
        self.lbl_freq.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col_lateral.addWidget(self.lbl_freq)

        # -- ABAS (Tabs) --
        tabs = QTabWidget()
        tabs.setIconSize(QSize(18, 18))

        # --- ABA 1: SINTONIA DE RÁDIO ---
        tab_sintonia = QWidget()
        lay_sintonia = QVBoxLayout(tab_sintonia)
        lay_sintonia.setSpacing(20)
        lay_sintonia.setContentsMargins(15, 20, 15, 15)

        # Controlos de Frequência
        grupo_freq = QGroupBox("Ajuste de Rádio")
        lay_grupo_freq = QVBoxLayout(grupo_freq)
        lay_grupo_freq.setSpacing(12)
        
        # Row: Frequência com Botões e SpinBox
        lay_freq_row = QHBoxLayout()
        lay_freq_row.addWidget(QLabel("Frequência FM:"))
        lay_freq_row.addStretch()
        
        self.btn_freq_menos = QPushButton("-")
        self.btn_freq_menos.setFixedWidth(28)
        self.btn_freq_menos.clicked.connect(lambda: self._mudar_frequencia_spin(self.spin_freq.value() - 0.1))
        
        self.spin_freq = QDoubleSpinBox()
        self.spin_freq.setRange(0.0, 2000.0)
        self.spin_freq.setDecimals(1)
        self.spin_freq.setSingleStep(0.1)
        self.spin_freq.setValue(FREQUENCIA_PADRAO_MHZ)
        self.spin_freq.setSuffix(" MHz")
        self.spin_freq.setFixedWidth(90)
        self.spin_freq.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_freq.setStyleSheet("font-weight: bold;")
        self.spin_freq.valueChanged.connect(self._mudar_frequencia_spin)

        self.btn_freq_mais = QPushButton("+")
        self.btn_freq_mais.setFixedWidth(28)
        self.btn_freq_mais.clicked.connect(lambda: self._mudar_frequencia_spin(self.spin_freq.value() + 0.1))
        
        lay_freq_row.addWidget(self.btn_freq_menos)
        lay_freq_row.addWidget(self.spin_freq)
        lay_freq_row.addWidget(self.btn_freq_mais)
        lay_grupo_freq.addLayout(lay_freq_row)
        
        self.slider_freq = QSlider(Qt.Orientation.Horizontal)
        self.slider_freq.setRange(875, 1080) # 87.5 a 108.0 MHz
        self.slider_freq.setValue(int(FREQUENCIA_PADRAO_MHZ * 10))
        self.slider_freq.valueChanged.connect(self._mudar_frequencia_slider)
        lay_grupo_freq.addWidget(self.slider_freq)

        # Row: Ganho
        lay_ganho_row = QHBoxLayout()
        lay_ganho_row.addWidget(QLabel("Ganho de RF (Antena):"))
        lay_ganho_row.addStretch()
        self.lbl_ganho = QLabel(f"{GANHO_PADRAO_DB} dB")
        self.lbl_ganho.setStyleSheet("color: #a0aec0;")
        lay_ganho_row.addWidget(self.lbl_ganho)
        lay_grupo_freq.addLayout(lay_ganho_row)

        self.slider_ganho = QSlider(Qt.Orientation.Horizontal)
        self.slider_ganho.setRange(0, 500)
        self.slider_ganho.setValue(int(GANHO_PADRAO_DB * 10))
        self.slider_ganho.valueChanged.connect(self._mudar_ganho)
        lay_grupo_freq.addWidget(self.slider_ganho)
        lay_sintonia.addWidget(grupo_freq)

        # Controlo de Áudio
        grupo_audio = QGroupBox("Saída de Áudio")
        lay_grupo_audio = QVBoxLayout(grupo_audio)
        lay_grupo_audio.setSpacing(15)
        
        lay_vol_row = QHBoxLayout()
        lay_vol_row.addWidget(QLabel("Volume:"))
        lay_vol_row.addStretch()
        self.lbl_vol_val = QLabel("100%")
        self.lbl_vol_val.setStyleSheet("color: #a0aec0;")
        lay_vol_row.addWidget(self.lbl_vol_val)
        lay_grupo_audio.addLayout(lay_vol_row)

        self.slider_volume = QSlider(Qt.Orientation.Horizontal)
        self.slider_volume.setRange(0, 200)
        self.slider_volume.setValue(100)
        self.slider_volume.valueChanged.connect(self._mudar_volume)
        lay_grupo_audio.addWidget(self.slider_volume)

        self.btn_audio = QPushButton(" Ouvir Áudio ao Vivo")
        self.btn_audio.setIcon(qta.icon('fa5s.play', color='white'))
        self.btn_audio.setStyleSheet("background-color:#2f855a; border-color:#276749;")
        self.btn_audio.clicked.connect(self._toggle_audio)
        lay_grupo_audio.addWidget(self.btn_audio)
        lay_sintonia.addWidget(grupo_audio)
        lay_sintonia.addStretch()

        tabs.addTab(tab_sintonia, qta.icon('fa5s.broadcast-tower', color='#a0aec0'), "Sintonia")

        # --- ABA 2: CAPTURA E PROCESSAMENTO ---
        tab_ia = QWidget()
        lay_ia = QVBoxLayout(tab_ia)
        lay_ia.setSpacing(15)
        lay_ia.setContentsMargins(15, 20, 15, 15)

        # Gestão de Sessão
        grupo_proj = QGroupBox("Gestão de Sessão")
        lay_proj = QVBoxLayout(grupo_proj)
        
        lay_h_proj = QHBoxLayout()
        self.input_projeto = QLineEdit(self.nome_sessao_atual)
        
        btn_novo_proj = QPushButton(" Definir")
        btn_novo_proj.setIcon(qta.icon('fa5s.check', color='white'))
        btn_novo_proj.setFixedWidth(80)
        btn_novo_proj.clicked.connect(self._alterar_sessao)
        
        btn_procurar = QPushButton()
        btn_procurar.setIcon(qta.icon('fa5s.folder-open', color='white'))
        btn_procurar.setToolTip("Procurar sessão existente...")
        btn_procurar.setFixedWidth(40)
        btn_procurar.clicked.connect(self._escolher_pasta_sessao)

        lay_h_proj.addWidget(self.input_projeto)
        lay_h_proj.addWidget(btn_novo_proj)
        lay_h_proj.addWidget(btn_procurar)
        lay_proj.addLayout(lay_h_proj)
        
        self.lbl_pasta = QLabel(f"Ativo: .../{self.nome_sessao_atual}")
        self.lbl_pasta.setStyleSheet("font-size:11px; color:#a0aec0;")
        self.lbl_pasta.setWordWrap(True)
        lay_proj.addWidget(self.lbl_pasta)
        lay_ia.addWidget(grupo_proj)

        # Ações IA
        grupo_acoes = QGroupBox("Processamento de Borda (Edge)")
        lay_acoes = QVBoxLayout(grupo_acoes)
        lay_acoes.setSpacing(12)

        self.btn_capturar = QPushButton(" 1. Gravar e Transcrever")
        self.btn_capturar.setIcon(qta.icon('fa5s.microphone', color='white'))
        self.btn_capturar.setStyleSheet("background-color:#c53030; border-color:#9b2c2c;")
        self.btn_capturar.clicked.connect(self._toggle_missao)
        lay_acoes.addWidget(self.btn_capturar)

        self.btn_retranscrever = QPushButton(" 2. Re-Transcrever Sessão")
        self.btn_retranscrever.setIcon(qta.icon('fa5s.sync-alt', color='white'))
        self.btn_retranscrever.setStyleSheet("background-color:#2b6cb0; border-color:#2c5282;")
        self.btn_retranscrever.clicked.connect(self._forcar_retranscricao)
        lay_acoes.addWidget(self.btn_retranscrever)

        self.btn_analise = QPushButton(" 3. Gerar Estatísticas")
        self.btn_analise.setIcon(qta.icon('fa5s.chart-line', color='white'))
        self.btn_analise.setStyleSheet("background-color:#6b46c1; border-color:#553c9a;")
        self.btn_analise.clicked.connect(self._abrir_analise)
        lay_acoes.addWidget(self.btn_analise)
        lay_ia.addWidget(grupo_acoes)
        lay_ia.addStretch()

        tabs.addTab(tab_ia, qta.icon('fa5s.cogs', color='#a0aec0'), "Captura & Processamento")
        col_lateral.addWidget(tabs)
        layout_raiz.addWidget(painel_lateral)

        # ---- PAINEL DIREITO (Splitter para Gráfico e Console) ----
        painel_direito = QSplitter(Qt.Orientation.Vertical)
        painel_direito.setHandleWidth(8)
        painel_direito.setStyleSheet("QSplitter::handle { background-color: #2d3748; border-radius: 4px; margin: 2px; }")

        # 1. Container Superior (Toolbar + Gráfico de Espectro)
        container_grafico_full = QWidget()
        lay_grafico_full = QVBoxLayout(container_grafico_full)
        lay_grafico_full.setContentsMargins(0, 0, 0, 0)
        lay_grafico_full.setSpacing(5)

        # 1.1 Toolbar do Gráfico (Zoom e Altura)
        toolbar_grafico = QFrame()
        toolbar_grafico.setStyleSheet("background-color: #1a202c; border: 1px solid #2d3748; border-radius: 6px;")
        lay_toolbar = QHBoxLayout(toolbar_grafico)
        lay_toolbar.setContentsMargins(10, 8, 10, 8)
        
        lbl_zoom = QLabel("🔍 Zoom X:")
        lbl_zoom.setStyleSheet("color: #a0aec0; border: none; background: transparent;")
        self.slider_zoom_x = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom_x.setRange(5, 200) # De 0.05 a 2.0 MHz de span
        self.slider_zoom_x.setValue(50)     # Default 0.5 MHz
        self.slider_zoom_x.setFixedWidth(120)
        self.slider_zoom_x.setStyleSheet("border: none; background: transparent;")
        self.slider_zoom_x.valueChanged.connect(self._atualizar_eixos_grafico)
        
        lbl_ymax = QLabel("↕️ Topo Y:")
        lbl_ymax.setStyleSheet("color: #a0aec0; border: none; background: transparent;")
        self.slider_y_max = QSlider(Qt.Orientation.Horizontal)
        self.slider_y_max.setRange(-20, 100)
        self.slider_y_max.setValue(40)
        self.slider_y_max.setFixedWidth(120)
        self.slider_y_max.setStyleSheet("border: none; background: transparent;")
        self.slider_y_max.valueChanged.connect(self._atualizar_eixos_grafico)

        lbl_ymin = QLabel(" Base Y:")
        lbl_ymin.setStyleSheet("color: #a0aec0; border: none; background: transparent;")
        self.slider_y_min = QSlider(Qt.Orientation.Horizontal)
        self.slider_y_min.setRange(-120, 20)
        self.slider_y_min.setValue(-60)
        self.slider_y_min.setFixedWidth(120)
        self.slider_y_min.setStyleSheet("border: none; background: transparent;")
        self.slider_y_min.valueChanged.connect(self._atualizar_eixos_grafico)

        lay_toolbar.addWidget(lbl_zoom)
        lay_toolbar.addWidget(self.slider_zoom_x)
        lay_toolbar.addSpacing(20)
        lay_toolbar.addWidget(lbl_ymax)
        lay_toolbar.addWidget(self.slider_y_max)
        lay_toolbar.addSpacing(10)
        lay_toolbar.addWidget(lbl_ymin)
        lay_toolbar.addWidget(self.slider_y_min)
        lay_toolbar.addStretch()

        lay_grafico_full.addWidget(toolbar_grafico)

        # 1.2 Gráfico em si
        pg.setConfigOption("background", "#0a0b0e")
        pg.setConfigOption("foreground", "#a0aec0")
        self.grafico = pg.PlotWidget(title="Análise de Espectro em Tempo Real")
        self.grafico.showGrid(x=True, y=True, alpha=0.3)
        self.grafico.setMouseEnabled(x=False, y=False)
        self.grafico.hideButtons()
        
        self.curva_sinal = self.grafico.plot(pen=pg.mkPen("#00ffcc", width=2))
        self.regiao_banda = pg.LinearRegionItem(
            values=[FREQUENCIA_PADRAO_MHZ - 0.085, FREQUENCIA_PADRAO_MHZ + 0.085], 
            movable=False, 
            brush=pg.mkBrush(255, 0, 0, 30)
        )
        self.grafico.addItem(self.regiao_banda)
        
        lay_grafico_full.addWidget(self.grafico)
        painel_direito.addWidget(container_grafico_full)

        # 2. Console de Logs (Terminal)
        container_console = QWidget()
        lay_console = QVBoxLayout(container_console)
        lay_console.setContentsMargins(0, 5, 0, 0)
        
        lbl_console = QLabel("Terminal de Eventos & Transcrições:")
        lbl_console.setStyleSheet("color:#a0aec0; font-weight:bold;")
        lay_console.addWidget(lbl_console)

        self.caixa_texto = QTextEdit()
        self.caixa_texto.setReadOnly(True)
        lay_console.addWidget(self.caixa_texto)
        
        painel_direito.addWidget(container_console)
        painel_direito.setSizes([600, 200])

        layout_raiz.addWidget(painel_direito, stretch=1)

    # =========================================================================
    # EVENTOS DE UI E LÓGICA DE INTERFACE
    # =========================================================================
    
    def _escolher_pasta_sessao(self):
        """Abre o explorador para escolher uma pasta de sessão existente."""
        os.makedirs(CAMINHO_PROJETOS, exist_ok=True) # Garante que a raiz existe
        pasta_selecionada = QFileDialog.getExistingDirectory(self, "Selecionar Sessão Existente", CAMINHO_PROJETOS)
        
        if pasta_selecionada:
            # Captura apenas o nome final do diretório
            nome_sessao = os.path.basename(pasta_selecionada)
            self.input_projeto.setText(nome_sessao)
            self._alterar_sessao()

    def _alterar_sessao(self):
        novo_nome = self.input_projeto.text().strip()
        if novo_nome:
            self._configurar_pastas_sessao(novo_nome)
            self.lbl_pasta.setText(f"Ativo: .../{self.nome_sessao_atual}")
            self._log(f"[INFO] Sessão alterada para: {self.nome_sessao_atual}")

    def _mudar_frequencia_slider(self, v: int):
        freq = round(v / 10.0, 1)
        self.spin_freq.blockSignals(True)
        self.spin_freq.setValue(freq)
        self.spin_freq.blockSignals(False)
        self._aplicar_frequencia(freq)

    def _mudar_frequencia_spin(self, freq: float):
        freq = round(freq, 1)
        self.spin_freq.setValue(freq)
        self.slider_freq.blockSignals(True)
        self.slider_freq.setValue(int(freq * 10))
        self.slider_freq.blockSignals(False)
        self._aplicar_frequencia(freq)
        
    def _aplicar_frequencia(self, freq: float):
        self.dsp.set_frequencia(freq)
        self.lbl_freq.setText(f"{freq} MHz")
        self._atualizar_eixos_grafico()

    def _mudar_ganho(self, v: int): 
        self.dsp.set_ganho(v / 10.0)

    def _mudar_volume(self, v: int): 
        self.dsp.set_volume(v / 100.0)
        self.lbl_vol_val.setText(f"{v}%")

    def _atualizar_eixos_grafico(self):
        ymin = self.slider_y_min.value()
        ymax = self.slider_y_max.value()
        if ymin >= ymax: ymax = ymin + 1
        self.grafico.setYRange(ymin, ymax, padding=0)
        
        freq = self.dsp.frequencia_mhz
        span = self.slider_zoom_x.value() / 100.0
        self.grafico.setXRange(freq - span, freq + span, padding=0)
        self.regiao_banda.setRegion([freq - 0.085, freq + 0.085])

    def _toggle_audio(self):
        self.dsp.ouvindo_audio = not self.dsp.ouvindo_audio
        if self.dsp.ouvindo_audio:
            self.dsp.reset_ring_buffer()
            self.btn_audio.setIcon(qta.icon('fa5s.stop', color='white'))
            self.btn_audio.setText(" Parar Áudio")
            self.btn_audio.setStyleSheet("background-color:#c53030; border-color:#9b2c2c;")
        else:
            self.btn_audio.setIcon(qta.icon('fa5s.play', color='white'))
            self.btn_audio.setText(" Ouvir Áudio ao Vivo")
            self.btn_audio.setStyleSheet("background-color:#2f855a; border-color:#276749;")

    def _atualizar_grafico(self) -> None:
        dados = self.dsp.dados_grafico
        if dados is not None:
            psd = 10 * np.log10(np.abs(np.fft.fftshift(np.fft.fft(dados[:FFT_SIZE]))) ** 2 + 1e-12)
            f = self._freq_axis + self.dsp.frequencia_mhz
            self.curva_sinal.setData(f, psd)

    # =========================================================================
    # CALLBACKS DSP E AÇÕES
    # =========================================================================
    def _cb_ganho_real(self, ganho: float): 
        QTimer.singleShot(0, lambda: self.lbl_ganho.setText(f"{ganho} dB"))
        
    def _cb_erro_antena(self, msg: str): 
        QTimer.singleShot(0, lambda: self._log(f"[ERRO] Erro Antena: {msg}"))
        
    def _cb_verificar_termino(self): 
        pass

    def _cb_chunk_pronto(self, audio: np.ndarray) -> None:
        self.pool_chunks.submit(self._processar_chunk, audio)

    def _toggle_missao(self) -> None:
        if self.gravando:
            self.gravando = False
            self.dsp.gravando = False
            self.btn_capturar.setIcon(qta.icon('fa5s.microphone', color='white'))
            self.btn_capturar.setText(" 1. Gravar e Transcrever")
            self.btn_capturar.setStyleSheet("background-color:#c53030; border-color:#9b2c2c;")
            self._log("[INFO] Captura parada.")
        else:
            self.dsp.buffer_ia.clear()
            self.gravando = True
            self.dsp.gravando = True
            self.btn_capturar.setIcon(qta.icon('fa5s.stop-circle', color='white'))
            self.btn_capturar.setText(" Parar Captura")
            self.btn_capturar.setStyleSheet("background-color:#dd6b20; border-color:#c05621; color: white;")
            self._log(f"[REC] Gravando na sessão: {self.nome_sessao_atual}...")

    def _processar_chunk(self, audio: np.ndarray) -> None:
        os.makedirs(self.pasta_audios, exist_ok=True)
        
        hora_s = datetime.now().strftime("%Hh%Mm%Ss")
        path = os.path.join(self.pasta_audios, f"audio_{hora_s}.wav")

        try:
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(TAXA_AUDIO)
                wf.writeframes((audio * 32767).astype(np.int16).tobytes())

            txt = self.transcritor.transcrever(path, self.dsp.frequencia_mhz)
            resumo = (txt or "Sem voz clara.")[:80]
            QTimer.singleShot(0, lambda: self._log(f"[OK] Salvo ({hora_s}): {resumo}…"))
        except Exception:
            logger.exception("Erro ao processar chunk")
            QTimer.singleShot(0, lambda: self._log(f"[ERRO] Falha ao salvar chunk ({hora_s})"))

    def _forcar_retranscricao(self):
        """Varre recursivamente todas as subpastas da sessão em busca de arquivos .wav."""
        if not os.path.exists(self.pasta_sessao):
            self._log("[AVISO] A pasta desta sessão não existe. Escolha ou grave algo primeiro.")
            return

        # =========================================================================
        # BUSCA RECURSIVA PROFUNDA (Deep Search para as subpastas antigas)
        # =========================================================================
        padrao_busca = os.path.join(self.pasta_sessao, "**", "*.wav")
        audios = glob.glob(padrao_busca, recursive=True)

        if not audios:
            self._log("[AVISO] Nenhum arquivo de áudio (.wav) encontrado nesta sessão.")
            self._log("Coloca os teus áudios antigos/pastas dentro da pasta do projeto ativo.")
            return
            
        self._log(f"[INFO] Iniciando re-transcrição de {len(audios)} áudios da sessão...")
        self.btn_retranscrever.setEnabled(False)
        self.btn_retranscrever.setIcon(qta.icon('fa5s.hourglass-half', color='white'))
        self.btn_retranscrever.setText(" Processando...")
        
        def task():
            for audio_path in audios:
                self.transcritor.transcrever(audio_path, self.dsp.frequencia_mhz)
                
                nome_ficheiro = os.path.basename(audio_path)
                pasta_pai = os.path.basename(os.path.dirname(audio_path))
                QTimer.singleShot(0, lambda pt=pasta_pai, nf=nome_ficheiro: self._log(f"[OK] Lido: {pt}/{nf}"))
            
            QTimer.singleShot(0, lambda: self.btn_retranscrever.setEnabled(True))
            QTimer.singleShot(0, lambda: self.btn_retranscrever.setIcon(qta.icon('fa5s.sync-alt', color='white')))
            QTimer.singleShot(0, lambda: self.btn_retranscrever.setText(" 2. Re-Transcrever Sessão"))
            QTimer.singleShot(0, lambda: self._log("[OK] Re-transcrição concluída!"))
            
        threading.Thread(target=task, daemon=True).start()

    def _abrir_analise(self) -> None:
        if not os.path.exists(self.caminho_csv):
            self._log("[AVISO] CSV não existe ainda. Grave ou transcreva algo primeiro.")
            return
            
        self.btn_analise.setEnabled(False)
        self.btn_analise.setIcon(qta.icon('fa5s.hourglass-half', color='white'))
        self.btn_analise.setText(" Gerando...")
        self._log("[INFO] Gerando gráficos e estatísticas da sessão...")
        threading.Thread(target=self._rodar_analise, daemon=True).start()

    def _rodar_analise(self) -> None:
        try:
            os.makedirs(self.pasta_graficos, exist_ok=True)
            
            from src.analise import CientistaSDR
            cientista = CientistaSDR(caminho_csv=self.caminho_csv, pasta_saida=self.pasta_graficos)
            cientista.executar_analise()
            QTimer.singleShot(0, lambda: self._log("[OK] Estatísticas geradas! Verifique a pasta."))
        except Exception as exc:
            logger.exception("Erro na análise")
            QTimer.singleShot(0, lambda: self._log(f"[ERRO] Falha na análise: {exc}"))
        finally:
            QTimer.singleShot(0, lambda: self.btn_analise.setEnabled(True))
            QTimer.singleShot(0, lambda: self.btn_analise.setIcon(qta.icon('fa5s.chart-line', color='white')))
            QTimer.singleShot(0, lambda: self.btn_analise.setText(" 3. Gerar Estatísticas"))

    def _log(self, msg: str) -> None:
        atual = self.caixa_texto.toPlainText()
        self.caixa_texto.setText(f"{atual}\n{msg}" if atual else msg)
        sb = self.caixa_texto.verticalScrollBar()
        sb.setValue(sb.maximum())

# =========================================================================
# PONTO DE ENTRADA DA APLICAÇÃO
# =========================================================================
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    janela = MainWindow()
    janela.show()
    sys.exit(app.exec())