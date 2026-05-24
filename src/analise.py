import os
import sys
import time
import re
import textwrap
import gc 
import tracemalloc
from collections import Counter
import pandas as pd

# --- CONFIGURAÇÃO GRÁFICA SEGURA ---
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# --- BLINDAGEM DE CAMINHOS E IMPORTAÇÃO DO CONFIG ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(CURRENT_DIR) == 'src':
    BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
else:
    BASE_DIR = CURRENT_DIR

# Adiciona o diretório principal ao PATH para conseguirmos importar o config.py
sys.path.append(BASE_DIR)
import config

class CientistaSDR:
    def __init__(self, caminho_csv=None, pasta_saida=None):
        print("🔬 A iniciar Análise Estatística e PLN (Sem LLM)...")
        
        self.caminho_csv = caminho_csv
        # Se não for passada uma pasta de saída específica, cria uma padrão
        self.pasta_saida = pasta_saida if pasta_saida else os.path.join(BASE_DIR, 'dados', 'analise_estatistica')
        os.makedirs(self.pasta_saida, exist_ok=True)
        
        self.historico_tempos = []
        self.historico_memoria = [] 
        self.palavras_gerais = []
        self.bigramas_gerais = [] # Para armazenar expressões de 2 palavras
        
    def limpar_texto(self, texto):
        # Remove pontuações e passa tudo para minúsculas
        return re.sub(r'[^\w\s]', '', str(texto).lower())

    def extrair_bigramas(self, palavras):
        # Cria pares de palavras subsequentes para detetar expressões (ex: "frequência modular")
        return [f"{palavras[i]} {palavras[i+1]}" for i in range(len(palavras)-1)]

    def analise_estatistica(self, texto):
        tracemalloc.start()
        inicio = time.time()
        
        texto_limpo = self.limpar_texto(texto)
        palavras = texto_limpo.split()
        
        # Carrega as stopwords centralizadas no nosso config.py
        stopwords = config.STOPWORDS
        
        # Filtra as palavras
        palavras_uteis = [p for p in palavras if p not in stopwords and len(p) > 2]
        self.palavras_gerais.extend(palavras_uteis)
        
        # Se houver mais de uma palavra útil, extrai bigramas
        if len(palavras_uteis) > 1:
            bigramas = self.extrair_bigramas(palavras_uteis)
            self.bigramas_gerais.extend(bigramas)
        
        tempo_gasto = time.time() - inicio
        _, pico_memoria = tracemalloc.get_traced_memory() 
        tracemalloc.stop()
        
        self.historico_tempos.append(tempo_gasto)
        self.historico_memoria.append(pico_memoria / 1024 / 1024) 
        
        return tempo_gasto

    def gerar_graficos(self, df_completo):
        if not self.historico_tempos: return
            
        print(f"\n📈 A gerar Imagens Estatísticas em: {self.pasta_saida}")
        sns.set_theme(style="whitegrid")
        prefixo_tempo = int(time.time())
        
        # =========================================================================
        # FIGURA 1: Termos mais Frequentes (Unigramas)
        # =========================================================================
        if self.palavras_gerais:
            plt.figure(figsize=(8, 6))
            top_10 = Counter(self.palavras_gerais).most_common(10)
            sns.barplot(x=[p[1] for p in top_10], y=[p[0] for p in top_10], palette="magma", hue=[p[0] for p in top_10], legend=False)
            plt.title('Termos Mais Frequentes (Unigramas)', fontsize=14, fontweight='bold')
            plt.xlabel('Frequência')
            plt.tight_layout()
            plt.savefig(os.path.join(self.pasta_saida, f"fig1_termos.png"), dpi=300)
            plt.close()

        # =========================================================================
        # FIGURA 2: Expressões mais Frequentes (Bigramas)
        # =========================================================================
        if self.bigramas_gerais:
            plt.figure(figsize=(9, 6))
            top_10_bi = Counter(self.bigramas_gerais).most_common(10)
            sns.barplot(x=[p[1] for p in top_10_bi], y=[p[0] for p in top_10_bi], palette="coolwarm", hue=[p[0] for p in top_10_bi], legend=False)
            plt.title('Expressões Mais Frequentes (Bigramas)', fontsize=14, fontweight='bold')
            plt.xlabel('Frequência')
            plt.tight_layout()
            plt.savefig(os.path.join(self.pasta_saida, f"fig2_expressoes.png"), dpi=300)
            plt.close()

        # =========================================================================
        # FIGURA 3: Evolução Temporal 
        # =========================================================================
        plt.figure(figsize=(10, 5))
        df_completo['Data_Hora_DT'] = pd.to_datetime(df_completo['Data_Hora'], format='mixed', errors='coerce')
        df_valido = df_completo.dropna(subset=['Data_Hora_DT']).copy()
        
        if not df_valido.empty:
            df_valido['Hora_Formatada'] = df_valido['Data_Hora_DT'].dt.strftime('%H:00')
            contagem_horario = df_valido.groupby('Hora_Formatada').size().reset_index(name='Volume')
            
            sns.lineplot(data=contagem_horario, x='Hora_Formatada', y='Volume', marker='o', color='#d62728', linewidth=2.5, markersize=8)
            plt.title('Evolução Temporal: Interceptações por Horário', fontsize=14, fontweight='bold')
            plt.xlabel('Horário do Dia')
            plt.ylabel('Volume de Transcrições (Eventos)')
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.savefig(os.path.join(self.pasta_saida, f"fig3_linha_do_tempo.png"), dpi=300)
        plt.close()

        print(f"✅ Figuras estatísticas guardadas com sucesso!")

    def executar_analise(self, limite=None):
        if not self.caminho_csv or not os.path.exists(self.caminho_csv):
            print(f"⚠️ Ficheiro de dados não encontrado: {self.caminho_csv}")
            return
            
        # Leitura flexível do CSV (com ou sem cabeçalho)
        _COLUNAS = ['Data_Hora', 'Frequencia_MHz', 'Caminho_Audio', 'Texto_Transcrito']
        _df_teste = pd.read_csv(self.caminho_csv, nrows=1, header=None)
        primeira_celula = str(_df_teste.iloc[0, 0])
        
        if primeira_celula.strip() == 'Data_Hora':
            df_completo = pd.read_csv(self.caminho_csv)
        else:
            df_completo = pd.read_csv(self.caminho_csv, header=None, names=_COLUNAS)

        # Se houver limite analisa apenas os N últimos, senão analisa tudo (ideal para Sessões inteiras)
        alvo_df = df_completo.tail(limite) if limite else df_completo
            
        nome_ficheiro = os.path.basename(self.caminho_csv)
        print(f"\n📡 A PROCESSAR ESTATÍSTICAS ({nome_ficheiro}) - {len(alvo_df)} registos\n" + "="*60)
        
        for _, linha in alvo_df.iterrows():
            # Executa a contagem e filtragem PLN para cada linha de transcrição
            self.analise_estatistica(linha['Texto_Transcrito'])
            
        # Gera as representações visuais com base nos dados processados
        self.gerar_graficos(df_completo)
        
        # Gera um relatório CSV com o Top 50 palavras encontradas na sessão
        if self.palavras_gerais:
            df_report = pd.DataFrame(Counter(self.palavras_gerais).most_common(50), columns=["Termo_Frequente", "Ocorrencias"])
            caminho_relatorio = os.path.join(self.pasta_saida, 'relatorio_estatistico.csv')
            df_report.to_csv(caminho_relatorio, index=False, encoding='utf-8-sig')
            
        gc.collect()

if __name__ == "__main__":
    # Teste rápido: Tenta rodar apontando para um CSV padrão caso executado solto
    csv_teste = os.path.join(BASE_DIR, 'dados', 'banco_dados', 'banco_transcricoes.csv')
    CientistaSDR(caminho_csv=csv_teste).executar_analise()