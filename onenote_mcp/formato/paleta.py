# paleta fechada de 9 cores (desenho §1.1) + normalização de cor
# escrita: nome da paleta ou #rrggbb → hex; leitura: o OneNote devolve hex minúsculo OU nome CSS
# (provas-v2: "red" continua "red", o realce volta "yellow") → hex → nome da paleta quando bate exato
import re

# nome: (cor do texto, fundo de caixa/célula)
PALETA = {
    "cinza": ("#595959", "#EDEDED"),
    "marrom": ("#843C0C", "#EFE3D9"),
    "laranja": ("#C55A11", "#FCE4D6"),
    "amarelo": ("#BF8F00", "#FFF2CC"),
    "verde": ("#548235", "#E2EFDA"),
    "azul": ("#2E75B6", "#DDEBF7"),
    "roxo": ("#7030A0", "#E9DDF4"),
    "rosa": ("#C2185B", "#FADBE7"),
    "vermelho": ("#C00000", "#F8D7DA"),
}

REALCE = "#FFFF00"  # ==marca-texto==
CINZA_CITACAO = "#595959"
CINZA_DIVISORIA = "#BFBFBF"
FUNDO_CODIGO = "#F3F3F3"

# nomes CSS que o OneNote pode devolver (os 16 básicos + alguns comuns). Só para LER; a escrita emite hex
CSS = {
    "black": "#000000", "silver": "#C0C0C0", "gray": "#808080", "grey": "#808080", "white": "#FFFFFF",
    "maroon": "#800000", "red": "#FF0000", "purple": "#800080", "fuchsia": "#FF00FF", "magenta": "#FF00FF",
    "green": "#008000", "lime": "#00FF00", "olive": "#808000", "yellow": "#FFFF00", "navy": "#000080",
    "blue": "#0000FF", "teal": "#008080", "aqua": "#00FFFF", "cyan": "#00FFFF", "orange": "#FFA500",
    "darkred": "#8B0000", "darkblue": "#00008B", "darkgreen": "#006400", "gold": "#FFD700", "pink": "#FFC0CB",
    "brown": "#A52A2A", "darkgray": "#A9A9A9", "lightgray": "#D3D3D3", "lightgrey": "#D3D3D3",
}

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class CorInvalida(ValueError):
    pass


def _resolver(valor, indice):
    v = str(valor).strip()
    if v.lower() in PALETA:
        return PALETA[v.lower()][indice]
    if _HEX.match(v):
        return v.upper()
    raise CorInvalida(f"cor desconhecida: {valor!r} (use {', '.join(PALETA)} ou #rrggbb)")


def cor_texto(valor):
    """nome da paleta ou #rrggbb → hex da cor de TEXTO"""
    return _resolver(valor, 0)


def cor_fundo(valor):
    """nome da paleta ou #rrggbb → hex de FUNDO (caixa, célula, span)"""
    return _resolver(valor, 1)


def para_hex(valor):
    """cor como o OneNote devolve (hex ou nome CSS) → #RRGGBB, ou None se não reconhece"""
    v = str(valor or "").strip().lower()
    if _HEX.match(v):
        return v.upper()
    if re.match(r"^#[0-9a-f]{3}$", v):
        return "#" + "".join(c * 2 for c in v[1:]).upper()
    return CSS.get(v)


def nome(valor, indice):
    """hex/nome CSS → nome da paleta quando bate exato; senão #hex; None se não reconhece"""
    h = para_hex(valor)
    if not h:
        return None
    for n, par in PALETA.items():
        if par[indice].upper() == h:
            return n
    return h.lower()


def nome_texto(valor):
    return nome(valor, 0)


def nome_fundo(valor):
    return nome(valor, 1)
