import os
import sys
import time
import re
import gc 
import tracemalloc
from collections import Counter
import pandas as pd

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(CURRENT_DIR) == 'src':
    BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
else:
    BASE_DIR = CURRENT_DIR

sys.path.append(BASE_DIR)
import config

class CientistaSDR:
    def __init__(self, caminho_csv=None, pasta_saida=None, callback_log=None):
        self.caminho_csv = caminho_csv
        self.pasta_saida = pasta_saida if pasta_saida else os.path.join(BASE_DIR, 'dados', 'analise_estatistica')
        self.callback_log = callback_log
        os.makedirs(self.pasta_saida, exist_ok=True)
        
        self.palavras_gerais = []
        self.bigramas_gerais = []
        self.ontologia_detectada = []  # <-- Guarda os domínios mapeados
        
    def log(self, msg):
        if self.callback_log:
            self.callback_log(msg)
        else:
            print(msg)

    def limpar_texto(self, texto):
        texto = re.sub(r'[^\w\s]', '', str(texto).lower())
        texto = re.sub(r'\b\d+\b', '', texto) 
        return texto

    def extrair_bigramas(self, palavras):
        return [f"{palavras[i]} {palavras[i+1]}" for i in range(len(palavras)-1)]

    def mapear_ontologia(self, palavras):
        """Atravessa a Árvore de Conhecimento (Ontologia) em busca de conceitos."""
        for palavra in palavras:
            # Percorre Domínios (ex: Segurança Pública)
            for dominio, subdominios in config.ONTOLOGIA_OSINT.items():
                # Percorre Subdomínios (ex: Armamento)
                for subdominio, palavras_chave in subdominios.items():
                    if palavra in palavras_chave:
                        # Se achou a palavra, regista o Domínio Principal
                        self.ontologia_detectada.append(dominio)

    def analise_estatistica(self, texto):
        texto_limpo = self.limpar_texto(texto)
        palavras = texto_limpo.split()
        
        if len(palavras) > 100:
            palavras = palavras[:100]
            
        stopwords = config.STOPWORDS
        
        palavras_uteis = [p for p in palavras if p not in stopwords and len(p) > 2]
        self.palavras_gerais.extend(palavras_uteis)
        
        if len(palavras_uteis) > 1:
            bigramas = self.extrair_bigramas(palavras_uteis)
            self.bigramas_gerais.extend(bigramas)
            
        # Realiza o mapeamento ontológico
        self.mapear_ontologia(palavras_uteis)

    def gerar_graficos(self, df_completo):
        if not self.palavras_gerais: 
            self.log("⚠️ Nenhuma palavra útil encontrada para gerar gráficos.")
            return
            
        self.log("🎨 A renderizar matrizes e inferências ontológicas...")
        sns.set_theme(style="whitegrid")
        
        # FIGURA 1: Unigramas
        plt.figure(figsize=(8, 6))
        top_10 = Counter(self.palavras_gerais).most_common(10)
        sns.barplot(x=[p[1] for p in top_10], y=[p[0] for p in top_10], palette="viridis", hue=[p[0] for p in top_10], legend=False)
        plt.title('Fig 1. Padrão Operacional: Termos Mais Frequentes', fontsize=14, fontweight='bold')
        plt.xlabel('Ocorrências Absolutas')
        plt.tight_layout()
        plt.savefig(os.path.join(self.pasta_saida, "fig1_termos.png"), dpi=300)
        plt.close()

        # FIGURA 2: Bigramas
        if self.bigramas_gerais:
            plt.figure(figsize=(9, 6))
            top_10_bi = Counter(self.bigramas_gerais).most_common(10)
            sns.barplot(x=[p[1] for p in top_10_bi], y=[p[0] for p in top_10_bi], palette="magma", hue=[p[0] for p in top_10_bi], legend=False)
            plt.title('Fig 2. Padrão Operacional: Expressões (Bigramas)', fontsize=14, fontweight='bold')
            plt.xlabel('Ocorrências Absolutas')
            plt.tight_layout()
            plt.savefig(os.path.join(self.pasta_saida, "fig2_expressoes.png"), dpi=300)
            plt.close()

        # FIGURA 3: Linha do Tempo
        plt.figure(figsize=(10, 5))
        df_completo['Data_Hora_DT'] = pd.to_datetime(df_completo['Data_Hora'], format='mixed', errors='coerce')
        df_valido = df_completo.dropna(subset=['Data_Hora_DT']).copy()
        
        if not df_valido.empty:
            df_valido['Hora_Formatada'] = df_valido['Data_Hora_DT'].dt.strftime('%H:00')
            contagem_horario = df_valido.groupby('Hora_Formatada').size().reset_index(name='Volume')
            sns.lineplot(data=contagem_horario, x='Hora_Formatada', y='Volume', marker='o', color='#d62728', linewidth=2.5, markersize=8)
            plt.title('Fig 3. Telemetria Temporal: Interceptações por Horário', fontsize=14, fontweight='bold')
            plt.xlabel('Faixa Horária')
            plt.ylabel('Volume de Transcrições (Eventos)')
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.savefig(os.path.join(self.pasta_saida, "fig3_linha_do_tempo.png"), dpi=300)
        plt.close()
        
        # FIGURA 4: Nuvem de Palavras
        try:
            texto_unido = " ".join(self.palavras_gerais)
            wordcloud = WordCloud(width=800, height=800, 
                                background_color='white', 
                                colormap='inferno',
                                min_font_size=10).generate(texto_unido)
            
            plt.figure(figsize=(8, 8), facecolor=None)
            plt.imshow(wordcloud, interpolation="bilinear")
            plt.axis("off")
            plt.title('Fig 4. Densidade Semântica: Nuvem de Palavras', fontsize=14, fontweight='bold', pad=20)
            plt.tight_layout(pad=0)
            plt.savefig(os.path.join(self.pasta_saida, "fig4_nuvem_palavras.png"), dpi=300)
            plt.close()
        except Exception as e:
            self.log(f"⚠️ Erro ao gerar Nuvem de Palavras: {e}")

        # FIGURA 5 (NOVA): Mapeamento Ontológico (Gráfico Donut)
        if self.ontologia_detectada:
            contagem_onto = Counter(self.ontologia_detectada)
            plt.figure(figsize=(8, 8))
            # Gráfico estilo Donut (anel) para um visual mais técnico
            plt.pie(contagem_onto.values(), labels=contagem_onto.keys(), autopct='%1.1f%%', 
                    colors=sns.color_palette("pastel"), startangle=140, 
                    wedgeprops=dict(width=0.4, edgecolor='w'))
            plt.title('Fig 5. Mapeamento Ontológico: Distribuição de Domínios', fontsize=14, fontweight='bold')
            plt.tight_layout()
            plt.savefig(os.path.join(self.pasta_saida, "fig5_ontologia.png"), dpi=300)
            plt.close()

    def executar_analise(self, limite=None):
        if not self.caminho_csv or not os.path.exists(self.caminho_csv):
            self.log(f"[ERRO] Banco de dados não encontrado em {self.caminho_csv}")
            return
            
        tracemalloc.start()
        tempo_inicio = time.time()
            
        _COLUNAS = ['Data_Hora', 'Frequencia_MHz', 'Caminho_Audio', 'Texto_Transcrito']
        _df_teste = pd.read_csv(self.caminho_csv, nrows=1, header=None)
        primeira_celula = str(_df_teste.iloc[0, 0])
        
        if primeira_celula.strip() == 'Data_Hora':
            df_completo = pd.read_csv(self.caminho_csv)
        else:
            df_completo = pd.read_csv(self.caminho_csv, header=None, names=_COLUNAS)

        alvo_df = df_completo.tail(limite) if limite else df_completo
        total_linhas = len(alvo_df)
            
        self.log(f"📊 A iniciar processamento de {total_linhas} interceptações...")
        
        for i, (idx, linha) in enumerate(alvo_df.iterrows(), 1):
            self.analise_estatistica(linha['Texto_Transcrito'])
            
            if i % 50 == 0 or i == total_linhas:
                self.log(f"⚙️ NLP e Ontologia Analisados: {i} de {total_linhas} registos...")
            
        self.gerar_graficos(df_completo)
        
        tempo_gasto = time.time() - tempo_inicio
        _, pico_memoria = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        pico_memoria_mb = pico_memoria / 1024 / 1024
        
        if self.palavras_gerais:
            df_report = pd.DataFrame(Counter(self.palavras_gerais).most_common(100), columns=["Termo_Frequente", "Ocorrencias"])
            caminho_relatorio = os.path.join(self.pasta_saida, 'matriz_estatistica.csv')
            df_report.to_csv(caminho_relatorio, index=False, encoding='utf-8-sig')
        
        self.log("-" * 50)
        self.log("RELATÓRIO DE DESEMPENHO COMPUTACIONAL:")
        self.log(f"   • Registos Processados: {total_linhas}")
        self.log(f"   • Tempo de Execução: {tempo_gasto:.3f} segundos")
        self.log(f"   • Pico de RAM (PLN + Ontologia): {pico_memoria_mb:.2f} MB")
        self.log("-" * 50)
            
        gc.collect()

if __name__ == "__main__":
    csv_teste = os.path.join(BASE_DIR, 'dados', 'banco_dados', 'banco_transcricoes.csv')
    CientistaSDR(caminho_csv=csv_teste).executar_analise()