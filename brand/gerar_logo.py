#!/usr/bin/env python3
"""
Gera a logo do Portal de Notícias a partir da marca "Voz" já usada no código
(frontend/components/Logomark.tsx e frontend/app/icon.tsx) e das cores dos
tokens de frontend/app/globals.css.

O texto é convertido em contornos (paths), então o SVG não depende de fontes
instaladas. Para a versão final com a tipografia oficial do site (Inter), passe
os .ttf com --fonte-negrito e --fonte-regular e rode o script de novo.

Uso:
  python3 gerar_logo.py --saida ./brand [--fonte-negrito X.ttf --fonte-regular Y.ttf]
"""
import argparse
import os

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

NOME_PRIMEIRA = "Portal"
NOME_SEGUNDA = " de Notícias"
SLOGAN = "Toda a informação que importa, organizada em um só lugar."

# Cores — espelham os tokens de frontend/app/globals.css
TEAL = "#0F766E"            # --cor-primaria (tema claro)
TEAL_CLARO = "#2DD4BF"      # --cor-primaria (tema escuro) e aspa do favicon
TEAL_CLARO2 = "#5EEAD4"     # segunda aspa do favicon
GRAFITE = "#111827"         # --cor-secundaria e fundo do favicon
TEXTO_CLARO_FUNDO = "#EDEFEE"  # --cor-texto (tema escuro)
TEXTO_SUAVE = "#5B6472"     # --cor-texto-suave (tema claro)
TEXTO_SUAVE_ESCURO = "#9BA3A1"  # --cor-texto-suave (tema escuro)
FUNDO_ESCURO = "#0B0F0E"    # --cor-fundo (tema escuro)


def marca_voz(s, x0, y0, cor, cor2, opacidade2=0.62):
    """
    Marca 'Voz': duas aspas angulares. Desenho original em caixa 27x24
    (x de 6 a 33, y de 6 a 30), reescalado por `s` e posicionado em (x0, y0).
    """
    def ponto(x, y, dx=0.0):
        return f"{x0 + (x + dx - 6) * s:.2f} {y0 + (y - 6) * s:.2f}"

    def aspa(dx):
        # M6 30 V18 Q6 8 18 6 V11 Q11 13 11 18 H17 V30 Z
        return (
            f"M{ponto(6, 30, dx)} V{ponto(6, 18, dx).split()[1]} "
            f"Q{ponto(6, 8, dx)} {ponto(18, 6, dx)} "
            f"V{ponto(18, 11, dx).split()[1]} "
            f"Q{ponto(11, 13, dx)} {ponto(11, 18, dx)} "
            f"H{ponto(17, 18, dx).split()[0]} V{ponto(17, 30, dx).split()[1]} Z"
        )

    return (
        f'<path d="{aspa(0)}" fill="{cor}"/>'
        f'<path d="{aspa(15)}" fill="{cor2}" opacity="{opacidade2}"/>'
    )


class Fonte:
    def __init__(self, caminho):
        self.f = TTFont(caminho)
        self.gs = self.f.getGlyphSet()
        self.cmap = self.f.getBestCmap()
        self.upm = self.f["head"].unitsPerEm
        self.hmtx = self.f["hmtx"]
        os2 = self.f["OS/2"]
        self.cap_px_por_em = (getattr(os2, "sCapHeight", 0) or 0.7 * self.upm) / self.upm

    def largura(self, texto, tamanho, tracking=0.0):
        total = sum(self.hmtx[self.cmap[ord(c)]][0] for c in texto if ord(c) in self.cmap)
        return total * tamanho / self.upm + tracking * (len(texto) - 1)

    def caminho(self, texto, x, linha_base, tamanho, tracking=0.0):
        """Retorna (d, x_final): contornos do texto com a linha de base em `linha_base`."""
        k = tamanho / self.upm
        cursor = x
        partes = []
        for c in texto:
            if ord(c) not in self.cmap:
                continue
            g = self.cmap[ord(c)]
            pen = SVGPathPen(self.gs)
            self.gs[g].draw(TransformPen(pen, (k, 0, 0, -k, cursor, linha_base)))
            partes.append(pen.getCommands())
            cursor += self.hmtx[g][0] * k + tracking
        return " ".join(partes), cursor

    def cap(self, tamanho):
        return self.cap_px_por_em * tamanho


def svg(largura, altura, corpo, fundo=None):
    rect = f'<rect width="{largura:.0f}" height="{altura:.0f}" fill="{fundo}"/>' if fundo else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura:.0f} {altura:.0f}" '
        f'width="{largura:.0f}" height="{altura:.0f}" role="img" aria-label="Portal de Notícias">'
        f"{rect}{corpo}</svg>\n"
    )


def nome_svg(neg, reg, x, base, tamanho, cor_texto):
    """Desenha 'Portal' (negrito) + ' de Notícias' (regular) e devolve (svg, x_final)."""
    p1, fim1 = neg.caminho(NOME_PRIMEIRA, x, base, tamanho, tracking=-1)
    p2, fim2 = reg.caminho(NOME_SEGUNDA, fim1 - 1, base, tamanho, tracking=-1)
    return f'<path d="{p1} {p2}" fill="{cor_texto}"/>', fim2


def logo_horizontal(neg, reg, cor_marca, cor_marca2, cor_texto, cor_suave, fundo=None, com_slogan=False):
    TAM, PAD = 120, 60
    cap = neg.cap(TAM)
    altura_marca = cap * 1.3
    s = altura_marca / 24.0
    largura_marca = 27 * s
    gap = TAM * 0.34

    x_marca = PAD
    x_texto = x_marca + largura_marca + gap
    # Centraliza a marca verticalmente em relação à caixa-alta do texto
    base = PAD + altura_marca / 2 + cap / 2
    y_marca = base - cap - (altura_marca - cap) / 2

    corpo = marca_voz(s, x_marca, y_marca, cor_marca, cor_marca2)
    t, fim = nome_svg(neg, reg, x_texto, base, TAM, cor_texto)
    corpo += t
    largura = fim + PAD
    altura = base + PAD

    if com_slogan:
        TAM_S = 30
        y_s = base + TAM * 0.62
        ps, fim_s = reg.caminho(SLOGAN, x_texto, y_s, TAM_S, tracking=0.5)
        corpo += f'<path d="{ps}" fill="{cor_suave}"/>'
        largura = max(largura, fim_s + PAD)
        altura = y_s + PAD

    return svg(largura, altura, corpo, fundo)


def logo_empilhada(neg, reg, cor_marca, cor_marca2, cor_texto, fundo=None):
    TAM, PAD = 110, 60
    cap = neg.cap(TAM)
    altura_marca = cap * 2.6
    s = altura_marca / 24.0
    largura_marca = 27 * s

    largura_nome = neg.largura(NOME_PRIMEIRA, TAM, -1) + reg.largura(NOME_SEGUNDA, TAM, -1)
    largura = max(largura_nome, largura_marca) + 2 * PAD

    corpo = marca_voz(s, (largura - largura_marca) / 2, PAD, cor_marca, cor_marca2)
    base = PAD + altura_marca + TAM * 0.42 + cap
    t, _ = nome_svg(neg, reg, (largura - largura_nome) / 2, base, TAM, cor_texto)
    corpo += t
    altura = base + PAD
    return svg(largura, altura, corpo, fundo)


def icone(cor_fundo=GRAFITE, cor_marca=TEAL_CLARO, cor_marca2=TEAL_CLARO2, tamanho=512, raio=0.22):
    """Ícone quadrado para app/favicon: fundo grafite e aspas em esmeralda, como em icon.tsx."""
    s = (tamanho * 0.56) / 27.0
    x0 = (tamanho - 27 * s) / 2
    y0 = (tamanho - 24 * s) / 2
    corpo = marca_voz(s, x0, y0, cor_marca, cor_marca2)
    fundo = f'<rect width="{tamanho}" height="{tamanho}" rx="{tamanho * raio:.1f}" fill="{cor_fundo}"/>'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {tamanho} {tamanho}" '
        f'width="{tamanho}" height="{tamanho}" role="img" aria-label="Portal de Notícias">'
        f"{fundo}{corpo}</svg>\n"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--saida", default="./brand")
    ap.add_argument("--fonte-negrito", default="/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")
    ap.add_argument("--fonte-regular", default="/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf")
    a = ap.parse_args()
    os.makedirs(a.saida, exist_ok=True)

    neg, reg = Fonte(a.fonte_negrito), Fonte(a.fonte_regular)

    arquivos = {
        "logo-horizontal-claro.svg": logo_horizontal(neg, reg, TEAL, TEAL, GRAFITE, TEXTO_SUAVE),
        "logo-horizontal-escuro.svg": logo_horizontal(
            neg, reg, TEAL_CLARO, TEAL_CLARO2, TEXTO_CLARO_FUNDO, TEXTO_SUAVE_ESCURO, fundo=FUNDO_ESCURO),
        "logo-horizontal-com-slogan.svg": logo_horizontal(
            neg, reg, TEAL, TEAL, GRAFITE, TEXTO_SUAVE, com_slogan=True),
        "logo-empilhada-claro.svg": logo_empilhada(neg, reg, TEAL, TEAL, GRAFITE),
        "logo-empilhada-escuro.svg": logo_empilhada(
            neg, reg, TEAL_CLARO, TEAL_CLARO2, TEXTO_CLARO_FUNDO, fundo=FUNDO_ESCURO),
        "icone-app.svg": icone(),
        "icone-monocromatico.svg": icone(cor_marca="#FFFFFF", cor_marca2="#FFFFFF"),
    }
    for nome, conteudo in arquivos.items():
        with open(os.path.join(a.saida, nome), "w", encoding="utf-8") as fh:
            fh.write(conteudo)
        print("ok", nome)


if __name__ == "__main__":
    main()
