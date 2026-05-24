import whisper
import os
import csv
from datetime import datetime

class TranscritorSDR:
    """
    Camada 2: A Escrita e o Banco de Dados.
    Responsável por converter o áudio em texto usando Whisper e guardar um histórico (CSV)
    específico para a sessão de captura atual.
    """
    def __init__(self, modelo_tamanho="base", caminho_csv=None):
        print(f"🧠 A carregar o modelo Whisper ({modelo_tamanho})...")
        self.modelo = whisper.load_model(modelo_tamanho)
        
        # O caminho do ficheiro CSV será gerido pelo app.py dependendo da sessão
        self.caminho_csv = caminho_csv

    def _inicializar_csv(self):
        """Cria o cabeçalho do ficheiro CSV se este ainda não existir na pasta da sessão."""
        if not self.caminho_csv:
            return

        # Garante que a pasta onde o CSV vai ficar existe
        os.makedirs(os.path.dirname(self.caminho_csv), exist_ok=True)
        
        if not os.path.exists(self.caminho_csv):
            with open(self.caminho_csv, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Data_Hora', 'Frequencia_MHz', 'Caminho_Audio', 'Texto_Transcrito'])

    def transcrever(self, caminho_audio, frequencia_mhz):
        """
        Transcreve o áudio e guarda os dados no CSV da sessão ativa.
        """
        if not os.path.exists(caminho_audio):
            print(f"❌ Erro: Ficheiro de áudio não encontrado em {caminho_audio}")
            return ""

        if not self.caminho_csv:
            print("❌ Erro: Caminho do CSV não definido. A sessão não foi inicializada corretamente.")
            return ""

        # Garante que o ficheiro/cabeçalho existe antes de cada gravação
        self._inicializar_csv()

        print(f"📝 A transcrever áudio da rádio {frequencia_mhz} MHz...")
        try:
            # fp16=False evita avisos chatos se estiver a correr apenas com CPU
            resultado = self.modelo.transcribe(caminho_audio, fp16=False, language="pt")
            texto = resultado["text"].strip()
            
            # --- GUARDAR NO BANCO DE DADOS (CSV) ---
            if texto:
                data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(self.caminho_csv, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([data_atual, frequencia_mhz, caminho_audio, texto])
                
                nome_ficheiro = os.path.basename(self.caminho_csv)
                print(f"💾 Transcrição guardada no ficheiro '{nome_ficheiro}' com sucesso!")
            
            return texto
            
        except Exception as e:
            print(f"❌ Erro crítico na transcrição: {e}")
            return ""