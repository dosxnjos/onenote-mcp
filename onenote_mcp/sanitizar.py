# 2ª barreira: roda no HTML FINAL que vai para a Microsoft (o conversor ONMD já só emite o que a spec define)
# lista de tags × atributos × propriedades CSS (desenho §3.2, corrigido pela crítica e pelas provas-v2):
# - nada que faça o servidor da Microsoft buscar URL: img/object só com "name:<parte criada NESTA chamada>",
#   data-render-src, iframe, data-original-src fora; href só https/http/onenote
# - pre fora (provas: o pre some e a quebra vira U+FFFC); bgcolor fora (provas: some); id fora (a Microsoft descarta)
# - data-tag só da lista oficial; ":completed" só nas marcáveis; call-back fora (provas: vira schedule-meeting)
# - caractere de controle (\x00–\x1f menos \t\n\r, U+FFFE/FFFF) sai do texto e dos atributos: quebra o XHTML
# tudo o que cai vira aviso (nunca descarte em silêncio)
import html as _html
import re
from html.parser import HTMLParser

from .formato.paleta import CSS as _CSS_NOMES

# etiquetas oficiais (onenote-note-tags), menos call-back (provas-v2: volta como schedule-meeting)
ETIQUETAS = {
    "to-do", "important", "question", "definition", "highlight", "contact", "address", "phone-number",
    "web-site-to-visit", "idea", "password", "critical", "project-a", "project-b", "remember-for-later",
    "movie-to-see", "book-to-read", "music-to-listen-to", "source-for-article", "remember-for-blog",
    "discuss-with-person-a", "discuss-with-person-b", "discuss-with-manager", "send-in-email",
    "schedule-meeting", "to-do-priority-1", "to-do-priority-2", "client-request",
}
MARCAVEIS = {"to-do", "discuss-with-person-a", "discuss-with-person-b", "discuss-with-manager",
             "schedule-meeting", "to-do-priority-1", "to-do-priority-2", "client-request"}

# anexo: tipo MIME aceito no <object> (extensão → MIME fica em arquivos.py)
MIMES_OBJETO = {
    "application/pdf", "text/plain", "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-excel", "application/msword", "application/vnd.ms-powerpoint",
    "application/zip",
}

# data-id próprio (provas-v2: "secaoA" com maiúscula foi aceito e virou alvo #secaoA)
ID_PROPRIO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$")
_PROIBIDO_ANEXO = set('\\/:*?<>|"')  # erro 20119

_BLOCO = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td"}
_COM_ID = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "table", "div", "img", "object"}
_ATRIBUTOS = {
    **{t: {"style", "data-id", "data-tag"} for t in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li")},
    "span": {"style"},
    "table": {"border", "style", "data-id"},
    "td": {"style"},
    "a": {"href"},
    "div": {"data-id"},
    "img": {"src", "alt", "width", "height", "data-id", "data-tag"},
    "object": {"data", "data-attachment", "type", "data-id"},
    **{t: set() for t in ("b", "i", "u", "del", "sup", "sub", "br", "tr")},
}
_VAZIAS = {"br", "img", "object"}
# somem COM o conteúdo
_FORA = {"script", "style", "iframe", "form", "link", "svg", "math", "embed", "noscript", "template", "head",
         "title", "meta", "audio", "video", "canvas", "textarea", "select", "button", "input", "applet", "base"}

_LISTA_TIPOS = {"none", "disc", "circle", "square", "decimal", "lower-alpha", "upper-alpha", "lower-roman",
                "upper-roman", "lower-latin"}
# caracteres que o XML 1.0 proíbe (o XHTML deixa de ser bem-formado e o Graph recusa): \t \n \r ficam
CONTROLE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿\ud800-\udfff]")


def sem_controle(texto, avisos=None):
    """tira os caracteres que o XML proíbe; avisa uma vez se tirou algum"""
    limpo = CONTROLE.sub("", texto or "")
    if avisos is not None and limpo != (texto or ""):
        m = "caractere de controle (invisível, proibido no XHTML) removido do texto"
        if m not in avisos:
            avisos.append(m)
    return limpo
_RUIM = re.compile(r"url\(|expression|\\|@|/\*|javascript:", re.I)
_HEX6 = re.compile(r"^#[0-9a-fA-F]{6}$")


def _cor_ok(v):
    return bool(_HEX6.match(v)) or v.lower() in _CSS_NOMES


def _tamanho_ok(v):
    m = re.match(r"^(\d{1,3}(?:\.\d)?)pt$", v)
    return bool(m) and 1 <= float(m.group(1)) <= 200


_CSS = {
    "color": lambda t, v: _cor_ok(v),
    "background-color": lambda t, v: _cor_ok(v),
    "font-family": lambda t, v: bool(re.match(r"^[A-Za-z0-9 \-]{1,40}$", v)),
    "font-size": lambda t, v: _tamanho_ok(v),
    "font-weight": lambda t, v: v in ("normal", "bold"),
    "font-style": lambda t, v: v in ("normal", "italic"),
    "text-decoration": lambda t, v: v in ("none", "underline", "line-through"),
    "text-align": lambda t, v: t in _BLOCO and v in ("left", "center", "right"),
    "list-style-type": lambda t, v: t in ("ul", "ol", "li") and v in _LISTA_TIPOS,
    "width": lambda t, v: t in ("table", "td", "img") and bool(re.match(r"^\d{1,4}(px|%)$", v)),
    "max-width": lambda t, v: t == "img" and bool(re.match(r"^\d{1,4}(px|%)$", v)),
    "max-height": lambda t, v: t == "img" and bool(re.match(r"^\d{1,4}px$", v)),
}


def estilo_limpo(tag, estilo, avisos):
    saida = []
    for decl in (estilo or "").split(";"):
        if not decl.strip():
            continue
        prop, _, val = decl.partition(":")
        prop, val = prop.strip().lower(), val.strip()
        if _RUIM.search(decl):
            avisos.append(f"estilo perigoso descartado em <{tag}>: {decl.strip()[:60]}")
            continue
        regra = _CSS.get(prop)
        if not regra or not val or not regra(tag, val):
            avisos.append(f"estilo não suportado descartado em <{tag}>: {decl.strip()[:60]}")
            continue
        saida.append(f"{prop}:{val}")
    return ";".join(saida)


def etiquetas_limpas(valor, avisos):
    boas = []
    for item in str(valor or "").split(","):
        item = item.strip()
        if not item:
            continue
        base, _, status = item.partition(":")
        if base not in ETIQUETAS:
            avisos.append(f"etiqueta fora da lista oficial descartada: {item}")
        elif status and not (status == "completed" and base in MARCAVEIS):
            avisos.append(f"etiqueta com estado inválido descartada: {item}")
        else:
            boas.append(item)
    return ", ".join(dict.fromkeys(boas))


def _href_ok(href):
    h = re.sub(r"[\x00-\x20]", "", href or "").lower()
    return h.startswith(("https://", "http://", "onenote:"))


class _Limpa(HTMLParser):
    def __init__(self, partes):
        super().__init__(convert_charrefs=True)
        self.partes = set(partes or ())
        self.out, self.pilha, self.avisos = [], [], []
        self.pular = 0          # dentro de tag que some com conteúdo
        self.pular_tag = []     # pilha das tags que abriram o pular

    def _attrs(self, tag, attrs):
        permitidos = _ATRIBUTOS.get(tag, set())
        bons = []
        for k, v in attrs:
            k = (k or "").lower()
            v = sem_controle(v if v is not None else "", self.avisos)
            if k not in permitidos:
                if k in ("id",):
                    continue  # a Microsoft descarta id de entrada; não é perigo
                self.avisos.append(f"atributo não suportado descartado em <{tag}>: {k}")
                continue
            if k == "style":
                v = estilo_limpo(tag, v, self.avisos)
                if not v:
                    continue
            elif k == "data-id":
                if not ID_PROPRIO.match(v):
                    self.avisos.append(f"data-id inválido descartado: {v[:50]}")
                    continue
            elif k == "data-tag":
                v = etiquetas_limpas(v, self.avisos)
                if not v:
                    continue
            elif k == "href":
                if not _href_ok(v):
                    self.avisos.append(f"link com esquema não permitido descartado: {v[:50]}")
                    continue
            elif k == "border":
                if v not in ("0", "1", "2", "3"):
                    self.avisos.append(f"borda inválida descartada: {v[:10]}")
                    continue
            elif k in ("width", "height"):
                if not re.match(r"^\d{1,4}$", v) or not 1 <= int(v) <= 2000:
                    self.avisos.append(f"{k} inválido descartado em <{tag}>: {v[:10]}")
                    continue
            elif k in ("src", "data"):
                if not (v.startswith("name:") and v[5:] in self.partes):
                    self.avisos.append(f"<{tag}> com origem externa ou desconhecida descartado: {v[:50]}")
                    return None
            elif k == "type":
                if v not in MIMES_OBJETO:
                    self.avisos.append(f"anexo com tipo não permitido descartado: {v[:60]}")
                    return None
            elif k == "data-attachment":
                if not v.strip() or any(c in _PROIBIDO_ANEXO for c in v) or len(v) > 120:
                    self.avisos.append(f"nome de anexo inválido descartado: {v[:60]}")
                    return None
            bons.append((k, v))
        chaves = {k for k, _ in bons}
        if tag == "img" and "src" not in chaves:
            self.avisos.append("<img> sem parte própria descartada")
            return None
        if tag == "object" and not {"data", "data-attachment", "type"} <= chaves:
            self.avisos.append("<object> incompleto descartado (precisa de data, data-attachment e type)")
            return None
        return bons

    def _abrir(self, tag, attrs, fechada):
        if self.pular:
            if tag in _FORA and not fechada:
                self.pular += 1
            return
        if tag in _FORA:
            self.avisos.append(f"<{tag}> descartado com o conteúdo")
            if not fechada:
                self.pular += 1
            return
        if tag not in _ATRIBUTOS:
            self.avisos.append(f"<{tag}> não suportado: ficou só o texto")
            return
        bons = self._attrs(tag, attrs)
        if bons is None:
            if tag == "object" and not fechada:
                self.pular += 1
                self.pular_tag.append("object")
            return
        txt = "".join(f' {k}="{_html.escape(v, quote=True)}"' for k, v in bons)
        if tag in _VAZIAS:
            self.out.append(f"<{tag}{txt} />")
            if tag == "object" and not fechada:
                self.pular += 1  # conteúdo de fallback do object some
                self.pular_tag.append("object")
            return
        self.out.append(f"<{tag}{txt}>")
        if fechada:
            self.out.append(f"</{tag}>")
        else:
            self.pilha.append(tag)

    def handle_starttag(self, tag, attrs):
        self._abrir(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._abrir(tag, attrs, True)

    def handle_endtag(self, tag):
        if self.pular:
            if tag in _FORA or (self.pular_tag and tag == self.pular_tag[-1]):
                self.pular -= 1
                if self.pular_tag and tag == self.pular_tag[-1]:
                    self.pular_tag.pop()
            return
        if tag in _VAZIAS or tag not in self.pilha:
            return
        while self.pilha:
            t = self.pilha.pop()
            self.out.append(f"</{t}>")
            if t == tag:
                break

    def handle_data(self, data):
        if not self.pular:
            self.out.append(_html.escape(sem_controle(data, self.avisos), quote=False))

    def resultado(self):
        while self.pilha:
            self.out.append(f"</{self.pilha.pop()}>")
        return "".join(self.out)


def sanitizar(html, partes=()):
    """HTML (fragmento do body) → (HTML limpo em XHTML, avisos). `partes` = nomes das partes criadas nesta chamada"""
    p = _Limpa(partes)
    p.feed(html or "")
    p.close()
    return p.resultado(), list(dict.fromkeys(p.avisos))
