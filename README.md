# 📡 Sistema SDR Inteligente: Monitorização e Edge AI

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt-6-green.svg)
![Edge AI](https://img.shields.io/badge/Edge%20AI-Whisper%20%7C%20NLP%20OSINT-orange)
![TCC](https://img.shields.io/badge/Projeto-TCC-purple.svg)

> Plataforma avançada de Inteligência de Sinais (SIGINT) que automatiza a captura, descodificação, transcrição e análise semântica de transmissões de rádio (FM) em tempo real, utilizando processamento 100% local (Edge Computing).

Este repositório contém o código-fonte desenvolvido para o Trabalho de Conclusão de Curso (TCC) em Sistemas para Internet pelo Instituto Federal do Acre. O foco principal é garantir privacidade, segurança e autonomia, processando dados sem qualquer dependência de serviços na nuvem ou APIs externas.

*Demo de demonstração da ferramenta*
![Demo da ferramenta](./assets/python_frL29le4BX.gif)

---

## ✨ Funcionalidades Principais

- **📻 Motor DSP Customizado:** Desmodulação de rádio FM em tempo real com numpy e scipy, aplicando decimação matemática e filtros Butterworth/De-Emphasis de forma multi-thread, com suporte robusto a desconexões de hardware.
- **🎙️ Transcrição Offline (Speech-to-Text):** Conversão de áudio com ruídos em texto estruturado em tempo real usando o modelo local OpenAI Whisper (`base`).
- **🧠 Mapeamento Ontológico OSINT (Edge NLP):** Classificação semântica em tempo real de termos e frases-chave contra uma ontologia de rádio estruturada em categorias de interesse (Segurança Pública, Desporto, Política, Religião, Trânsito, etc.), de forma instantânea e determinística.
- **📊 Dashboards Automáticos:** Geração de relatórios analíticos em CSV e 5 gráficos de publicação (Nuvem de Palavras, Donut de Domínios Ontológicos, Termos Frequentes, Bigramas e Linha do Tempo).
- **🖥️ Interface Gráfica Responsiva:** Desenvolvida em PyQt6 com visualização de espectro de radiofrequência em tempo real, isolando as threads de UI, DSP e Whisper para garantir fluidez.

---

## 🛠️ Tecnologias Utilizadas

- **Interface:** `PyQt6`, `pyqtgraph` (aceleração por GPU), `qtawesome`
- **DSP e Áudio:** `numpy`, `scipy`, `sounddevice`, hardware RTL-SDR Blog V4 (`pyrtlsdr`, `pyrtlsdrlib`)
- **Inteligência Artificial (STT):** `openai-whisper` (PyTorch) rodando localmente
- **Análise Semântica (NLP):** Processamento estatístico em Python com stopwords otimizadas para português e árvore ontológica de OSINT
- **Análise de Dados e Plotting:** `pandas`, `matplotlib` (backend não interativo `Agg`), `seaborn`, `wordcloud`

---

## 🚀 Como Instalar e Executar

### Pré-requisitos Obrigatórios
1. **Python 3.10 ou superior:** Instalado no sistema.
2. **FFmpeg:** Obrigatório para o Whisper. Instale e garanta que está [adicionado ao PATH do Windows](https://phoenixnap.com/kb/ffmpeg-windows). O sistema também tentará localizar instalações feitas via `winget` automaticamente.
3. **Antena RTL-SDR:** Conectada via USB. Você deve instalar os drivers WinUSB corretos usando o software [Zadig](https://zadig.akeo.ie/).

### Passo a Passo

**1. Clonar o Repositório:**
```bash
git clone https://github.com/ntcdave/Sistema-SDR-Inteligente-TCC_2.git
cd Sistema-SDR-Inteligente-TCC_2
```

**2. Instalar Dependências:**
Recomendamos o uso de um ambiente virtual (venv).
```bash
pip install -r requirements.txt
```

**3. Descarregar os Modelos de IA:**
O modelo Whisper (`base`) será baixado automaticamente na primeira execução (~140MB) e salvo localmente. Não é necessária nenhuma outra configuração de IA ou servidores locais.

**4. Iniciar a Aplicação:**
Com a antena ligada e configurada, execute o entry point principal do sistema:
```bash
python main.py
```

---

## 📂 Organização do Projeto

```text
projeto/
├── main.py                 # Entry point (Bootstrap de ambiente e variáveis de PATH para DLLs e FFmpeg)
├── app.py                  # Interface principal (PyQt6) e orquestração dos módulos do sistema
├── config.py               # Configurações globais, constantes DSP, stopwords e dicionário ontológico OSINT
├── requirements.txt        # Lista de dependências Python reais do projeto
├── src/
│   ├── dsp.py              # Motor DSP (hardware SDR, threads apartadas de leitura/processamento e ring buffer SPSC)
│   ├── transcricao.py      # TranscritorSDR: Interação local com o OpenAI Whisper (STT) com filtros anti-alucinação
│   ├── analise.py          # CientistaSDR: Análise estatística de NLP, mapeamento ontológico por dicionário e gráficos
│   └── captura.py          # LEGADO/ÓRFÃO: Antigo script usando subprocessos (rtl_fm + sox), não utilizado
├── ferramentas/rtl-sdr/    # DLLs e utilitários nativos da RTL-SDR para Windows (linkagem dinâmica)
└── dados/projetos/         # Armazenamento local das sessões capturadas (audios WAV, CSV de transcrições e gráficos)
```

---

## 📖 Documentação Técnica Avançada

Para entender a fundo a arquitetura do projeto, fluxo de dados do Processamento Digital de Sinal (DSP), padrões de projeto aplicados e pontos de extensibilidade, consulte a nossa documentação completa:

👉 **[Ler a Especificação Completa (SPEC.me)](./SPEC.me)**

---

## 🤝 Contribuição e Resolução de Problemas (Troubleshooting)

Este projeto é **Open Source**! A comunidade é muito bem-vinda para explorar o código, abrir Issues para reportar problemas ou sugerir melhorias através de Pull Requests. 

Caso encontre alguma dificuldade inicial na execução, confira as soluções para os problemas mais comuns relatados pela comunidade:

- **Erro na biblioteca RTL-SDR:** Verifique se a pasta `ferramentas/rtl-sdr/` contém a `rtlsdr.dll` e se você configurou os drivers corretos usando o Zadig. (Usuários Linux/macOS podem precisar compilar a biblioteca localmente). Se encontrar erros como `AttributeError: function 'rtlsdr_set_dithering' not found`, assegure-se de que a biblioteca pyrtlsdr está atualizada.
- **Falhas de Conexão com Antena ("Hardware Desconectado"):** O motor DSP (`src/dsp.py`) agora detecta automaticamente e lida de forma graciosa com erros `OSError` e desconexões de antena, emitindo logs e encerrando as threads corretamente para não causar "access violation".
- **Falha ao Transcrever Áudio:** Se a aplicação apresentar erros durante o Whisper, o `ffmpeg` provavelmente não foi encontrado pelo sistema. Assegure-se de que ele está instalado e configurado no PATH. O `main.py` tenta injetar o caminho do ffmpeg do winget, mas a forma mais segura é adicioná-lo manualmente.
- **Análise Semântica / NLP:** O sistema realiza a análise clássica de Processamento de Linguagem Natural e classificação ontológica 100% offline de forma instantânea. O sistema é robusto e lê tanto arquivos CSV novos quanto os gerados em sessões passadas de forma transparente, sem qualquer necessidade de servidores de IA adicionais rodando localmente.

Sentiu falta de alguma funcionalidade ou conseguiu resolver um bug diferente? **Contribua com o projeto abrindo uma Pull Request!**

---

> *Trabalho académico desenvolvido para investigar a implementação de técnicas de Edge AI aplicadas a Radiofrequência e processamento DSP em tempo real.*
