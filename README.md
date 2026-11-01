# leitor-tts-acessibilidade
Aplicação de acessibilidade que converte texto em fala utilizando síntese de voz por IA e saída de áudio virtual.

# Leitor TTS — Acessibilidade

Aplicação desktop desenvolvida em Python com foco em acessibilidade, permitindo transformar textos em fala utilizando síntese de voz por inteligência artificial.

O projeto utiliza o modelo **XTTS v2**, oferecendo geração de áudio com diferentes opções de voz e recursos para facilitar a leitura de textos durante o uso do computador.

## Funcionalidades

- Conversão de texto em fala (Text-to-Speech).
- Síntese de voz utilizando o modelo XTTS v2.
- Seleção de diferentes vozes disponíveis.
- Reprodução de áudio através do pygame.
- Sistema de fila para processamento de textos.
- Cache de áudios para evitar processamento repetido.
- Interface gráfica desenvolvida com Tkinter.
- Atalhos de teclado para controlar a leitura.
- Minimização para a bandeja do sistema.

## Tecnologias utilizadas

| Tecnologia | Aplicação |
|---|---|
| Python | Linguagem principal |
| Tkinter | Interface gráfica |
| Coqui TTS | Síntese de voz |
| XTTS v2 | Modelo de geração de voz |
| PyTorch | Processamento do modelo |
| Pygame | Reprodução de áudio |
| Pynput | Monitoramento de teclado |
| Pyperclip | Integração com área de transferência |
| Pillow | Manipulação de imagens |

## Como executar

### 1. Clone o repositório

```bash
git clone https://github.com/brubasz/leitor-tts-acessibilidade.git
```

### 2. Entre na pasta

```bash
cd leitor-tts-acessibilidade
```

### 3. Instale as dependências

```bash
pip install TTS torch pygame pynput pyperclip pillow
```

### 4. Execute o programa

```bash
python leitor_simples.py
```

## Privacidade e acessibilidade

O programa possui funcionalidades de monitoramento de teclado e integração com a área de transferência para auxiliar no processo de leitura.

Esses recursos devem ser utilizados com conhecimento e consentimento do usuário. Ev
