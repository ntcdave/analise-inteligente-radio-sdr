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
        self.caminho_csv = caminho_csv

    def _inicializar_csv(self):
        """Cria o cabeçalho do ficheiro CSV se este ainda não existir na pasta da sessão."""
        if not self.caminho_csv:
            return

        os.makedirs(os.path.dirname(self.caminho_csv), exist_ok=True)
        
        if not os.path.exists(self.caminho_csv):
            with open(self.caminho_csv, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Data_Hora', 'Frequencia_MHz', 'Caminho_Audio', 'Texto_Transcrito'])

    def transcrever(self, caminho_audio, frequencia_mhz):
        """
        Transcreve o áudio e guarda os dados no CSV da sessão ativa, com proteções Anti-Alucinação.
        """
        if not os.path.exists(caminho_audio):
            return ""

        if not self.caminho_csv:
            return ""

        self._inicializar_csv()

        try:
            # =========================================================================
            # O SEGREDO PARA RÁDIO: Parâmetros para evitar Alucinação no Chiado
            # =========================================================================
            resultado = self.modelo.transcribe(
                caminho_audio, 
                fp16=False, 
                language="pt",
                condition_on_previous_text=False, # Impede loops de repetição ("não não não")
                no_speech_threshold=0.6           # Desiste de transcrever se achar que é muito ruidoso
            )
            
            texto = resultado["text"].strip()
            
            # Filtro duro: ignora textos que são obviamente alucinações do Whisper para áudio vazio
            alucinacoes_comuns = ["obrigado.", "obrigado", "obrigada", "silêncio", ".", "..", "..."]
            if len(texto) < 3 or texto.lower() in alucinacoes_comuns:
                print("🔇 Ignorado: Apenas chiado ou silêncio detetado.")
                return ""
            
            # --- GUARDAR NO BANCO DE DADOS (CSV) ---
            if texto:
                data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                caminho_relativo = os.path.relpath(caminho_audio, raiz_projeto).replace('\\', '/')
                
                with open(self.caminho_csv, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([data_atual, frequencia_mhz, caminho_relativo, texto])
                
                nome_ficheiro = os.path.basename(self.caminho_csv)
                print(f"💾 Transcrição guardada no ficheiro '{nome_ficheiro}' com sucesso!")
            
            return texto
            
        except Exception as e:
            print(f"❌ Erro crítico na transcrição: {e}")
            return ""