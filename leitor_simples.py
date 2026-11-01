import re
import os
import time
import queue
import hashlib
import tempfile
import threading
import tkinter as tk
from tkinter import ttk

import torch
import pygame
import pyperclip
import pystray
from PIL import Image, ImageDraw
from pynput import keyboard
from TTS.api import TTS

IDIOMA = "pt"
FRASE_AQUECIMENTO = "Sistema pronto para uso."
PASTA_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache_vozes")
os.makedirs(PASTA_CACHE, exist_ok=True)

VOZES_FEMININAS_CONHECIDAS = [
    "Claribel Dervla",
    "Daisy Studious",
    "Gracie Wise",
    "Tammie Ema",
    "Alison Dietlinde",
    "Ana Florence",
    "Annmarie Nele",
    "Asya Anara",
    "Brenda Stern",
    "Gitta Nikolina",
    "Henriette Usha",
    "Sofia Hellen",
    "Tammy Grit",
    "Tanja Adelina",
    "Vjollca Johnnie",
]

PADROES_RISADA = [
    r"\bk{2,}\b",
    r"\b(?:ha){2,}h?\b",
    r"\b(?:kk)+\b",
    r"\b(?:rs){2,}\b",
    r"\b(?:ka){2,}\b",
    r"\b(?:hue){2,}\b",
    r"\bau+(?:ha+u*)+\b",
    r"\bkc?\b(?=\s|$)",
]
REGEX_RISADA = re.compile("|".join(PADROES_RISADA), flags=re.IGNORECASE)


def limpar_texto(texto):
    texto_limpo = REGEX_RISADA.sub("", texto)
    texto_limpo = re.sub(r"\s{2,}", " ", texto_limpo)
    return texto_limpo.strip()


def caminho_no_cache(voz, texto):
    chave = f"{voz}|{texto}"
    hash_chave = hashlib.sha1(chave.encode("utf-8")).hexdigest()
    return os.path.join(PASTA_CACHE, f"{hash_chave}.wav")


class MotorDeFala:
    def __init__(self, ao_mudar_status):
        self.modelo = None
        self.dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
        self.ao_mudar_status = ao_mudar_status
        self.vozes_disponiveis = []

    def carregar(self):
        self.ao_mudar_status(f"Carregando o modelo de voz... (dispositivo: {self.dispositivo})")
        self.modelo = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.dispositivo)

        todas_vozes = list(self.modelo.speakers) if self.modelo.speakers else []
        self.vozes_disponiveis = [v for v in VOZES_FEMININAS_CONHECIDAS if v in todas_vozes] or todas_vozes

        if self.vozes_disponiveis:
            self.ao_mudar_status("Aquecendo o modelo...")
            self._aquecer(self.vozes_disponiveis[0])

        self.ao_mudar_status("Pronto. Digite e pressione F7.")

    def _aquecer(self, voz):
        try:
            destino = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            destino.close()
            self.modelo.tts_to_file(text=FRASE_AQUECIMENTO, speaker=voz, language=IDIOMA, file_path=destino.name)
            os.remove(destino.name)
        except Exception as erro:
            print(f"[aviso] aquecimento falhou (sem problema, só ia ser mais rápido): {erro}")

    def gerar(self, texto, voz):
        destino = caminho_no_cache(voz, texto)
        if os.path.exists(destino):
            return destino, True
        self.modelo.tts_to_file(text=texto, speaker=voz, language=IDIOMA, file_path=destino)
        return destino, False


class FilaDeLeitura:
    def __init__(self, motor, ao_mudar_status, ao_mudar_texto_lendo):
        self.motor = motor
        self.fila = queue.Queue()
        self.ao_mudar_status = ao_mudar_status
        self.ao_mudar_texto_lendo = ao_mudar_texto_lendo
        self.evento_parar = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def adicionar(self, texto, voz):
        self.fila.put((texto, voz))

    def parar_tudo(self):
        while not self.fila.empty():
            try:
                self.fila.get_nowait()
            except queue.Empty:
                break
        self.evento_parar.set()
        pygame.mixer.music.stop()
        self.ao_mudar_status("Interrompido. Fila limpa.")
        self.ao_mudar_texto_lendo("")

    def _loop(self):
        while True:
            texto, voz = self.fila.get()
            self.evento_parar.clear()
            self.ao_mudar_texto_lendo(texto)

            restantes = self.fila.qsize()
            aviso_fila = f" ({restantes} na fila)" if restantes else ""
            self.ao_mudar_status(f"Falando...{aviso_fila}")

            try:
                caminho_audio, veio_do_cache = self.motor.gerar(texto, voz)
                if self.evento_parar.is_set():
                    continue

                pygame.mixer.music.load(caminho_audio)
                pygame.mixer.music.play()

                while pygame.mixer.music.get_busy():
                    if self.evento_parar.is_set():
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.1)

            except Exception as erro:
                print(f"[erro ao gerar/tocar fala] {erro}")
            finally:
                if self.fila.empty():
                    self.ao_mudar_status("Pronto. Digite e pressione F7.")
                    self.ao_mudar_texto_lendo("")


class CapturaDeTexto:
    def __init__(self):
        self.buffer = []
        self.ctrl_pressionado = False
        self.lock = threading.Lock()

    def texto_atual_e_limpa(self):
        with self.lock:
            texto = "".join(self.buffer).strip()
            self.buffer = []
            return texto

    def limpar(self):
        with self.lock:
            self.buffer = []

    def ao_pressionar(self, tecla):
        if tecla in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressionado = True
            return

        try:
            char = tecla.char
        except AttributeError:
            char = None

        if char is not None and self.ctrl_pressionado:
            if char.lower() == "c":
                threading.Timer(0.15, self._capturar_clipboard).start()
                return
            if char.lower() == "v":
                threading.Timer(0.05, self._capturar_clipboard).start()
                return

        if char is not None:
            with self.lock:
                self.buffer.append(char)
        elif tecla == keyboard.Key.space:
            with self.lock:
                self.buffer.append(" ")
        elif tecla == keyboard.Key.enter:
            with self.lock:
                self.buffer.append("\n")
        elif tecla == keyboard.Key.backspace:
            with self.lock:
                if self.buffer:
                    self.buffer.pop()

    def ao_soltar(self, tecla):
        if tecla in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressionado = False

    def _capturar_clipboard(self):
        try:
            conteudo = pyperclip.paste()
        except Exception:
            return
        if not conteudo:
            return
        with self.lock:
            if self.buffer and not self.buffer[-1].endswith((" ", "\n")):
                self.buffer.append(" ")
            self.buffer.append(conteudo)


def criar_imagem_icone():
    imagem = Image.new("RGB", (64, 64), "white")
    desenho = ImageDraw.Draw(imagem)
    desenho.ellipse((8, 8, 56, 56), fill=(90, 60, 180))
    desenho.text((24, 20), "V", fill="white")
    return imagem


class LeitorDeVoz:
    def __init__(self, root):
        self.root = root
        self.root.title("Leitor de Voz")
        self.root.geometry("500x320")
        self.root.protocol("WM_DELETE_WINDOW", self.minimizar_para_bandeja)

        self.captura = CapturaDeTexto()
        self.motor = MotorDeFala(self._status_thread_segura)
        self.fila_leitura = None  # criada depois que o modelo carregar

        self.status_var = tk.StringVar(value="Iniciando...")
        self.voz_selecionada = tk.StringVar(value="")

        self._montar_interface()
        self._iniciar_listener_teclado()
        self._iniciar_bandeja()

        pygame.mixer.init()
        threading.Thread(target=self._carregar_tudo, daemon=True).start()

    def _montar_interface(self):
        ttk.Label(self.root, textvariable=self.status_var, font=("Segoe UI", 12, "bold"), padding=10).pack()

        frame_voz = ttk.Frame(self.root, padding=(10, 0))
        frame_voz.pack(fill="x")
        ttk.Label(frame_voz, text="Voz:").pack(side="left")
        self.combo_voz = ttk.Combobox(frame_voz, textvariable=self.voz_selecionada, state="disabled", width=28)
        self.combo_voz.pack(side="left", padx=8)
        ttk.Button(frame_voz, text="Testar voz", command=self.testar_voz).pack(side="left")

        ttk.Label(self.root, text="Lendo agora:", font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=(8, 0))
        self.caixa_lendo = tk.Text(self.root, height=5, wrap="word", font=("Segoe UI", 11), state="disabled")
        self.caixa_lendo.pack(fill="both", expand=True, padx=10, pady=5)

        frame_botoes = ttk.Frame(self.root, padding=(10, 0))
        frame_botoes.pack(fill="x")
        ttk.Button(frame_botoes, text="Limpar buffer", command=self.limpar_buffer).pack(side="left")
        ttk.Button(frame_botoes, text="Parar tudo (F8)", command=self.parar_tudo).pack(side="left", padx=8)

        ttk.Label(
            self.root,
            text="F7 adiciona o texto à fila de leitura. F8 para tudo e limpa a fila.\n"
                 "Ctrl+C e Ctrl+V também são capturados automaticamente.",
            foreground="gray", justify="left",
        ).pack(pady=8, padx=10, anchor="w")

    def _mostrar_texto_lendo(self, texto):
        self.caixa_lendo.config(state="normal")
        self.caixa_lendo.delete("1.0", "end")
        self.caixa_lendo.insert("1.0", texto)
        self.caixa_lendo.config(state="disabled")

    def _status_thread_segura(self, texto):
        self.root.after(0, lambda: self.status_var.set(texto))

    def _texto_lendo_thread_segura(self, texto):
        self.root.after(0, lambda: self._mostrar_texto_lendo(texto))

    def _carregar_tudo(self):
        self.motor.carregar()
        self.fila_leitura = FilaDeLeitura(self.motor, self._status_thread_segura, self._texto_lendo_thread_segura)
        self.root.after(0, self._preencher_vozes)

    def _preencher_vozes(self):
        vozes = self.motor.vozes_disponiveis
        self.combo_voz["values"] = vozes
        self.combo_voz.config(state="readonly")
        if vozes:
            self.voz_selecionada.set(vozes[0])

    def _iniciar_listener_teclado(self):
        def ao_pressionar(tecla):
            if tecla == keyboard.Key.f7:
                self.root.after(0, self.adicionar_a_fila)
                return
            if tecla == keyboard.Key.f8:
                self.root.after(0, self.parar_tudo)
                return
            self.captura.ao_pressionar(tecla)

        def ao_soltar(tecla):
            self.captura.ao_soltar(tecla)

        self.listener = keyboard.Listener(on_press=ao_pressionar, on_release=ao_soltar)
        self.listener.daemon = True
        self.listener.start()

    def adicionar_a_fila(self):
        if self.fila_leitura is None or not self.voz_selecionada.get():
            self.status_var.set("Ainda carregando o modelo, espera um pouco...")
            return

        texto_bruto = self.captura.texto_atual_e_limpa()
        texto = limpar_texto(texto_bruto)

        if not texto:
            self.status_var.set("Nada pra ler (ou era só risada). Digite algo e tente de novo.")
            return

        self.fila_leitura.adicionar(texto, self.voz_selecionada.get())

    def parar_tudo(self):
        if self.fila_leitura:
            self.fila_leitura.parar_tudo()

    def limpar_buffer(self):
        self.captura.limpar()
        self.status_var.set("Buffer limpo.")

    def testar_voz(self):
        if self.fila_leitura is None or not self.voz_selecionada.get():
            return
        self.fila_leitura.adicionar("Olá, esta é a minha voz. Espero que goste.", self.voz_selecionada.get())

    def _iniciar_bandeja(self):
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar janela", self._mostrar_janela, default=True),
            pystray.MenuItem("Sair", self._sair_de_vez),
        )
        self.icone_bandeja = pystray.Icon("leitor_de_voz", criar_imagem_icone(), "Leitor de Voz", menu)
        threading.Thread(target=self.icone_bandeja.run, daemon=True).start()

    def _mostrar_janela(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)

    def minimizar_para_bandeja(self):
        self.root.withdraw()

    def _sair_de_vez(self, icon=None, item=None):
        self.icone_bandeja.stop()
        self.root.after(0, self.root.destroy)


def main():
    root = tk.Tk()
    LeitorDeVoz(root)
    root.mainloop()


if __name__ == "__main__":
    main()