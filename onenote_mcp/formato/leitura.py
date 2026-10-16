# HTML de saída do OneNote → ONMD (o mesmo dialeto que a escrita aceita), POR BLOCO:
# cada bloco editável (p, h1–h6, lista inteira, tabela mais externa, img, object) guarda o seu ONMD e o id gerado,
# e a página é a junção deles; assim `editar` procura o trecho no mesmo texto que o modelo leu
# padrões medidos que a leitura omite (docs/provas-v2.md): margens 5.5pt, Calibri/11pt (e 11px, crítica 14),
# estilo padrão de h1–h6, border:0px/1px da tabela, <br /> solto depois de lista, tag sem espaço ("a,b")
# a fonte que domina o texto (ex.: Segoe UI posta no body) vira "fonte da página" e some dos spans
# texto da página que pareça sintaxe ONMD sai escapado (\*, \<, \{…): página de terceiro não vira comando
# ATRIBUTO de terceiro também: href sem quebra de linha e com ( ) < > { } [ ] | " espaço em %XX; fonte, data-id e
# etiqueta fora do padrão são omitidos (um \n num atributo viraria linha nova = bloco ONMD vivo ao reescrever)
# imagem/anexo existente sai como recurso:<id>, nunca a URL (ela traz o e-mail da conta)
# o que a leitura OMITE dentro de um bloco (img/tabela/iframe no texto, tag desconhecida na célula) marca o bloco
# com `perdas`: editar recusa esse bloco (regravá-lo apagaria o que o ONMD não mostra)
# <br /> dentro do texto (e o U+FFFC que o OneNote deixa no lugar do \n de um <pre>) volta como <br>
import html as _html
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser

from ..sanitizar import ETIQUETAS, ID_PROPRIO, MARCAVEIS
from . import paleta
from .escrita import LARGURA

_VAZIAS = {"br", "img", "object", "meta", "link", "input", "hr", "col", "source", "embed", "wbr"}
_BLOCOS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "div", "img", "object", "iframe",
           "pre", "blockquote"}
# estilo padrão medido nas provas (a leitura omite)
_PADRAO_H = {
    "h1": {"font-size": "16pt", "color": "#1E4E79"},
    "h2": {"font-size": "14pt", "color": "#2E75B5"},
    "h3": {"font-size": "12pt", "color": "#5B9BD5"},
    "h4": {"font-size": "12pt", "color": "#5B9BD5", "font-style": "italic"},
    "h5": {"color": "#2E75B5"},
    "h6": {"color": "#2E75B5", "font-style": "italic"},
}
_TIPO_OL = {"lower-alpha": "a", "upper-alpha": "A", "lower-roman": "i", "upper-roman": "I", "lower-latin": "a"}
_MARCADOR = {"circle": "circulo", "square": "quadrado", "none": "nenhum"}
_ALINHAR = {"left": "esquerda", "center": "centro", "right": "direita"}
RECURSO = re.compile(r"/resources/([0-9A-Za-z!\-]{1,200})/(?:\$value|content)")
_INICIO_ESPECIAL = re.compile(r"^(#|-|>|\||\+)")
_INICIO_ITEM = re.compile(r"^(\d{1,3}|[a-zA-Z]{1,2}|[ivxlcdmIVXLCDM]{1,6})\.(\s|$)")
_FONTE = re.compile(r"^[A-Za-z0-9 \-]{1,40}$")   # o mesmo que a escrita e o sanitizador aceitam
_URL_RUIM = re.compile(r'[ <>"{}\[\]()\\`|]')
_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")


def _fonte(v):
    """font-family de terceiro → 1º nome da lista, só se é nome simples; senão None"""
    f = (v or "").split(",")[0].strip().strip("'\"").strip()
    return f if _FONTE.match(f) else None


def _href(h):
    """href de terceiro: sem controle/quebra de linha; o que abre ou fecha sintaxe ONMD vira %XX"""
    return _URL_RUIM.sub(lambda m: f"%{ord(m.group(0)):02X}", _CONTROLE.sub("", h or ""))


# ---------------- árvore ----------------
class No:
    __slots__ = ("tag", "attrs", "filhos", "texto", "pai")

    def __init__(self, tag=None, attrs=None, texto=None, pai=None):
        self.tag, self.attrs, self.texto, self.pai = tag, dict(attrs or {}), texto, pai
        self.filhos = []

    def css(self):
        return estilo(self.attrs.get("style"))

    def elementos(self):
        return [f for f in self.filhos if f.tag]


class _Arvore(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.raiz = No("#doc")
        self.pilha = [self.raiz]

    def handle_starttag(self, tag, attrs):
        no = No(tag, [(k, v or "") for k, v in attrs], pai=self.pilha[-1])
        self.pilha[-1].filhos.append(no)
        if tag not in _VAZIAS:
            self.pilha.append(no)

    def handle_startendtag(self, tag, attrs):
        no = No(tag, [(k, v or "") for k, v in attrs], pai=self.pilha[-1])
        self.pilha[-1].filhos.append(no)

    def handle_endtag(self, tag):
        if any(n.tag == tag for n in self.pilha[1:]):
            while self.pilha[-1].tag != tag:
                self.pilha.pop()
            self.pilha.pop()

    def handle_data(self, data):
        self.pilha[-1].filhos.append(No(texto=data, pai=self.pilha[-1]))


def arvore(html):
    p = _Arvore()
    p.feed(html or "")
    p.close()
    return p.raiz


def achar(no, tag):
    if no.tag == tag:
        return no
    for f in no.filhos:
        r = achar(f, tag)
        if r:
            return r
    return None


def serializar(no):
    """nó → HTML (para o diário local guardar o antes)"""
    if no.tag is None:
        return _html.escape(no.texto, quote=False)
    attrs = "".join(f' {k}="{_html.escape(v, quote=True)}"' for k, v in no.attrs.items())
    if no.tag in _VAZIAS:
        return f"<{no.tag}{attrs} />"
    return f"<{no.tag}{attrs}>{''.join(serializar(f) for f in no.filhos)}</{no.tag}>"


def estilo(s):
    d = {}
    for decl in (s or "").split(";"):
        k, _, v = decl.partition(":")
        if k.strip() and v.strip():
            d[k.strip().lower()] = v.strip()
    return d


def _tamanho(v):
    """'14pt' → 14.0; '16px' → 12.0; padrão (11pt/11px) → None"""
    m = re.match(r"^([\d.]+)\s*(pt|px)?$", (v or "").strip().lower())
    if not m:
        return None
    if m.group(1) == "11" and m.group(2) in ("pt", "px", None):
        return None
    n = float(m.group(1))
    if m.group(2) == "px":
        n = round(n * 0.75 * 2) / 2
    return n


def _px(v):
    m = re.match(r"^([\d.]+)\s*(px)?$", (v or "").strip().lower())
    return float(m.group(1)) if m else None


def _pct(px):
    return f"{max(1, min(100, round(px * 100 / LARGURA)))}%"


# ---------------- escape de texto ----------------
def escapar(t, celula=False):
    t = t.replace("\\", "\\\\")
    t = re.sub(r"([*`\[<{])", r"\\\1", t)
    t = t.replace("~~", "\\~\\~").replace("==", "\\=\\=")
    if celula:
        t = t.replace("|", "\\|")
    return t


def _escapar_inicio(t):
    if _INICIO_ESPECIAL.match(t):
        return "\\" + t
    return _INICIO_ITEM.sub(lambda m: f"{m.group(1)}\\.{m.group(2)}", t, count=1)


# ---------------- marcas (inline) ----------------
_MARCAS = ("link", "span", "hl", "b", "i", "u", "s", "sup", "sub")


def _vazia():
    return {"b": False, "i": False, "u": False, "s": False, "sup": False, "sub": False, "hl": False,
            "code": False, "cor": None, "fundo": None, "fonte": None, "tam": None, "link": None, "raw": False}


@dataclass
class Bloco:
    tipo: str            # par, tit, tarefa, cit, linha, lista, tabela, img, anexo
    no: No
    onmd: str
    onmd_ids: str
    grupo: str = ""
    tags: list = field(default_factory=list)
    perdas: bool = False  # a leitura omitiu algo dentro dele: regravar apagaria (editar recusa)

    @property
    def id_gerado(self):
        return self.no.attrs.get("id")

    @property
    def data_id(self):
        d = self.no.attrs.get("data-id")
        return d if d and d != "_default" else None


@dataclass
class Caixa:
    abre: str
    fecha: str
    filhos: list
    data_id: str = ""
    no: No = None


@dataclass
class Leitura:
    onmd: str
    avisos: list
    fonte: str
    blocos: list          # folhas editáveis, na ordem
    secoes: list          # data-id das <div> nomeadas
    data_ids: set         # todo data-id próprio da página
    ultima_div: str       # id gerado da última div filha do body (alvo do "fim")
    itens: list = field(default_factory=list)
    repetidos: set = field(default_factory=set)   # data-id que aparece mais de uma vez (alvo #id ambíguo)


class _Leitor:
    def __init__(self, raiz):
        self.raiz = raiz
        self.avisos = []
        self.fonte = None
        self.ids = False
        self.n_perdas = 0

    def aviso(self, m):
        if m not in self.avisos:
            self.avisos.append(m)

    def perda(self, m):
        """omissão DENTRO de um bloco: conta para o Bloco virar `perdas` (ver _duplo)"""
        self.n_perdas += 1
        self.aviso(m + " (o bloco que o contém não aceita editar)")

    def etiquetas(self, valor):
        """data-tag de terceiro → só etiquetas oficiais (com :completed); o resto é omitido (perda)"""
        saida = []
        for x in (valor or "").split(","):
            x = x.strip()
            base, _, estado = x.partition(":")
            if base in ETIQUETAS and estado in ("", "completed"):
                saida.append(x)
            elif x:
                self.perda(f"etiqueta fora da lista oficial omitida: {x[:40]!r}")
        return saida

    # ---- fonte dominante ----
    def _contar_fontes(self, no, fonte, cont):
        if no.tag is None:
            if fonte and no.texto.strip():
                cont[fonte] += len(no.texto.strip())
            return
        if re.match(r"^h[1-6]$", no.tag):
            return  # título não recebe a fonte da página (provas-v2): não conta
        f = no.css().get("font-family")
        if f:
            fonte = _fonte(f)   # fora do padrão não vira fonte da página (a escrita recusaria em todo acrescentar)
        for x in no.filhos:
            self._contar_fontes(x, fonte, cont)

    def dominante(self, corpo):
        cont = Counter()
        self._contar_fontes(corpo, None, cont)
        cont.pop("Consolas", None)
        total = sum(cont.values())
        if total and cont:
            f, n = cont.most_common(1)[0]
            if f.lower() != "calibri" and n >= 0.6 * total:
                self.fonte = f
                self.aviso(f"fonte da página: {f} (omitida no texto)")

    # ---- marcas ----
    def marcas(self, no, herd, sem=()):
        m = dict(herd)
        t = no.tag
        if t in ("b", "strong"):
            m["b"] = True
        elif t in ("i", "em"):
            m["i"] = True
        elif t == "u":
            m["u"] = True
        elif t in ("del", "s", "strike"):
            m["s"] = True
        elif t in ("sup", "sub"):
            m[t] = True
        elif t == "a":
            m["link"] = _href(no.attrs.get("href")) or None
        css = {k: v for k, v in no.css().items() if k not in sem}
        fw = css.get("font-weight", "").lower()
        if fw:
            m["b"] = fw in ("bold", "700", "800", "900")
        fs = css.get("font-style", "").lower()
        if fs:
            m["i"] = fs == "italic"
        td = css.get("text-decoration", "").lower()
        if td:
            m["u"], m["s"] = "underline" in td, "line-through" in td
        if "background-color" in css:
            h = paleta.para_hex(css["background-color"])
            if h == paleta.REALCE:
                m["hl"], m["fundo"] = True, None
            else:
                m["fundo"] = h
        if "color" in css:
            m["cor"] = paleta.para_hex(css["color"])
        if "font-family" in css:
            f = _fonte(css["font-family"])
            if not f:
                self.aviso("fonte com nome fora do padrão omitida (só letras, números, espaço e hífen)")
            m["fonte"] = None if not f or f.lower() in ("calibri", (self.fonte or "").lower()) else f
        if "font-size" in css:
            m["tam"] = _tamanho(css["font-size"])
        if (m["fonte"] or "").lower() == "consolas" and m["tam"] in (None, 10.0):
            m["code"], m["fonte"], m["tam"] = True, None, None
        return m

    def runs(self, nos, herd, tags=None):
        out = []
        apos_br = False
        for no in nos:
            if no.tag is None:
                t = no.texto
                if "\n" in t and not t.strip():
                    continue
                if apos_br:
                    # o OneNote serializa "<br />\n\ntexto" (prova real 15/10): a quebra de formatação depois
                    # do <br> não é espaço do texto; sem isso cada regravação somava um espaço no começo da linha
                    t = re.sub(r"^[ \t]*\r?\n[ \t\r\n]*", "", t)
                t = t.replace("\r", "").replace("\n", " ").replace("\t", " ")
                # U+FFFC = a quebra de linha que o OneNote guardou de um <pre>: volta como <br>, nunca literal
                for k, pedaco in enumerate(t.split("￼")):
                    if k:
                        out.append(["<br>", dict(herd, raw=True)])
                    out.append([pedaco, dict(herd)])
            elif no.tag == "br":
                out.append(["<br>", dict(herd, raw=True)])
            elif no.tag in ("img", "object", "iframe", "table", "ul", "ol"):
                self.perda(f"<{no.tag}> dentro do texto foi omitido")
            else:
                if tags is not None and no.attrs.get("data-tag"):
                    tags.extend(self.etiquetas(no.attrs["data-tag"]))
                out.extend(self.runs(no.filhos, self.marcas(no, herd), tags))
            apos_br = no.tag == "br"   # texto só de formatação (o continue acima) não desfaz o "depois do br"
        return out

    # ---- render inline ----
    @staticmethod
    def _envoltorios(m):
        w = []
        if m["link"]:
            w.append(("link", m["link"]))
        if m["cor"] or m["fundo"] or m["fonte"] or m["tam"]:
            w.append(("span", (m["cor"], m["fundo"], m["fonte"], m["tam"])))
        for k in ("hl", "b", "i", "u", "s", "sup", "sub"):
            if m[k]:
                w.append((k,))
        return w

    @staticmethod
    def _abre(w):
        k = w[0]
        if k == "link":
            return "["
        if k == "span":
            cor, fundo, fonte, tam = w[1]
            a = []
            if cor:
                a.append(f"cor={paleta.nome_texto(cor)}")
            if fundo:
                a.append(f"fundo={paleta.nome_fundo(fundo)}")
            if fonte:
                a.append(f'fonte="{fonte}"')
            if tam:
                a.append(f"tamanho={tam:g}")
            return f"<span {' '.join(a)}>"
        return {"hl": "==", "b": "**", "i": "*", "u": "<u>", "s": "~~", "sup": "<sup>", "sub": "<sub>"}[k]

    @staticmethod
    def _fecha(w):
        k = w[0]
        if k == "link":
            href = w[1].replace(" ", "%20").replace(")", "%29")
            return f"]({href})"
        return {"span": "</span>", "hl": "==", "b": "**", "i": "*", "u": "</u>", "s": "~~", "sup": "</sup>",
                "sub": "</sub>"}[k]

    def render(self, runs, celula=False):
        juntos = []
        for t, m in runs:
            if not t:
                continue
            if juntos and juntos[-1][1] == m:
                juntos[-1][0] += t
            else:
                juntos.append([t, m])
        # tokens: ("t", texto) | ("a", envoltório) | ("f", envoltório)
        tok, pilha = [], []
        for t, m in juntos:
            ws = self._envoltorios(m)
            k = 0
            while k < len(pilha) and k < len(ws) and pilha[k] == ws[k]:
                k += 1
            while len(pilha) > k:
                tok.append(("f", pilha.pop()))
            for w in ws[k:]:
                tok.append(("a", w))
                pilha.append(w)
            if m["raw"]:
                tok.append(("t", t))   # <br>: sintaxe ONMD, não texto
            elif m["code"]:
                if "`" in t:
                    tok.append(("t", f'<span fonte="Consolas" tamanho=10>{escapar(t, celula)}</span>'))
                else:   # em célula GFM o | também se escapa dentro do código (senão corta a célula)
                    tok.append(("t", "`" + (t.replace("|", "\\|") if celula else t) + "`"))
            else:
                tok.append(("t", escapar(t, celula)))
        while pilha:
            tok.append(("f", pilha.pop()))
        # **/*/~~/== não abrem antes de espaço nem fecham depois de espaço: o espaço sai para fora
        sens = {"b", "i", "s", "hl"}
        mudou = True
        while mudou:
            mudou = False
            for k in range(len(tok) - 1):
                (ta, va), (tb, vb) = tok[k], tok[k + 1]
                if ta == "a" and va[0] in sens and tb == "t" and vb[:1].isspace():
                    sp = vb[: len(vb) - len(vb.lstrip())]
                    tok[k], tok[k + 1] = ("t", sp), ("a", va)
                    tok.insert(k + 2, ("t", vb[len(sp):]))
                    mudou = True
                    break
                if tb == "f" and vb[0] in sens and ta == "t" and va[-1:].isspace():
                    sp = va[len(va.rstrip()):]
                    tok[k], tok[k + 1] = ("t", va.rstrip()), ("f", vb)
                    tok.insert(k + 2, ("t", sp))
                    mudou = True
                    break
        # run formatado só de espaço (ex.: negrito num espaço) deixaria "****": some o par vazio
        tok = [x for x in tok if not (x[0] == "t" and x[1] == "")]
        mudou = True
        while mudou:
            mudou = False
            for k in range(len(tok) - 1):
                if tok[k][0] == "a" and tok[k + 1][0] == "f" and tok[k][1] == tok[k + 1][1]:
                    del tok[k:k + 2]
                    mudou = True
                    break
        out = []
        for k, (tp, v) in enumerate(tok):
            if tp == "t":
                out.append(v)
            elif tp == "a":
                out.append(self._abre(v))
            else:
                out.append(self._fecha(v))
        return "".join(out)

    @staticmethod
    def levantar(runs, props=("cor", "fundo", "fonte", "tam")):
        """propriedade igual em todo o texto do bloco → atributo do bloco (sai dos spans)"""
        cheias = [r for r in runs if r[0].strip() and not r[1]["code"] and not r[1]["raw"]]
        achado = {}
        for p in props:
            vals = {r[1][p] for r in cheias}
            if len(vals) == 1 and None not in vals:
                achado[p] = vals.pop()
                for r in runs:
                    if r[1][p] == achado[p]:
                        r[1] = dict(r[1], **{p: None})
        return achado

    def attrs_bloco(self, no, lev=None, tags=(), extra=None):
        lev = lev or {}
        a = []
        did = no.attrs.get("data-id") if no is not None else None
        if self.ids and did and did != "_default" and not did.startswith("on-") and ID_PROPRIO.match(did):
            a.append(f"id={did}")
        if lev.get("cor"):
            a.append(f"cor={paleta.nome_texto(lev['cor'])}")
        if lev.get("fundo"):
            a.append(f"fundo={paleta.nome_fundo(lev['fundo'])}")
        if lev.get("fonte"):
            a.append(f'fonte="{lev["fonte"]}"')
        if lev.get("tam"):
            a.append(f"tamanho={lev['tam']:g}")
        if no is not None:
            al = no.css().get("text-align", "").lower()
            if al in ("center", "right"):
                a.append(f"alinhar={_ALINHAR[al]}")
        if tags:
            a.append(f"tags={','.join(tags)}")
        for k, v in (extra or {}).items():
            a.append(f"{k}={v}")
        return (" {" + " ".join(a) + "}") if a else ""

    # ---- blocos ----
    def itens(self, no):
        """filhos de um contêiner → lista de Bloco/Caixa; texto solto vira parágrafo; <li> soltos seguidos (lista
        com etiqueta) viram uma lista, sem id gerado: não é alvo de editar"""
        saida, solto, lis = [], [], []

        def fecha_lis():
            if lis:
                ul = No("ul", pai=no)
                ul.filhos = list(lis)
                saida.append(self._duplo("lista", ul, lambda: self._lista(ul, 0)))
                lis.clear()

        def fecha_solto():
            if solto:
                r = self.runs(solto, _vazia())
                lev = self.levantar(r)
                txt = self.render(r).strip()
                if txt:
                    s = _escapar_inicio(txt) + self.attrs_bloco(None, lev)
                    # sem id gerado próprio: não é editável (o id do contêiner apagaria tudo num replace)
                    saida.append(Bloco("par", No("#texto"), s, s))
                solto.clear()
        for f in no.filhos:
            if f.tag is None and not f.texto.strip():
                continue
            if f.tag == "li":
                fecha_solto()
                lis.append(f)
                continue
            fecha_lis()
            if f.tag is None or (f.tag not in _BLOCOS and f.tag != "br" and not re.match(r"^h[1-6]$", f.tag)):
                solto.append(f)
                continue
            fecha_solto()
            saida.extend(self.bloco(f))
        fecha_lis()
        fecha_solto()
        return saida

    def bloco(self, no):
        t = no.tag
        if t == "br":
            return []
        if t == "p":
            return self._p(no)
        if re.match(r"^h[1-6]$", t):
            return [self._duplo("tit", no, lambda: self._h(no))]
        if t in ("ul", "ol"):
            return [self._duplo("lista", no, lambda: self._lista(no, 0))]
        if t == "table":
            return [self._duplo("tabela", no, lambda: self._tabela(no))]
        if t == "img":
            return [self._duplo("img", no, lambda: self._img(no))]
        if t == "object":
            return [self._duplo("anexo", no, lambda: self._obj(no))]
        if t == "div":
            did = no.attrs.get("data-id")
            if did and did != "_default" and ID_PROPRIO.match(did):
                return [Caixa(f"<secao id={did}>", "</secao>", self.itens(no), did, no)]
            return self.itens(no)
        self.perda(f"conteúdo não suportado omitido: <{t}>")
        return []

    def _duplo(self, tipo, no, fn, grupo="", tags=(), n0=None):
        """Bloco com o ONMD sem e com ids; `perdas` se alguma omissão aconteceu desde n0 (dentro do bloco)"""
        n0 = self.n_perdas if n0 is None else n0
        ids = self.ids
        self.ids = False
        sem = fn()
        self.ids = True
        com = fn()
        self.ids = ids
        return Bloco(tipo, no, sem, com, grupo, list(tags), self.n_perdas > n0)

    def _texto_p(self, no, herd=None, sem=()):
        tags = []
        r = self.runs(no.filhos, self.marcas(no, herd or _vazia(), sem), tags)
        return r, tags

    def _p(self, no):
        n0 = self.n_perdas
        did = no.attrs.get("data-id") or ""
        tags = self.etiquetas(no.attrs.get("data-tag", ""))
        _, nos_spans = self._texto_p(no)   # etiqueta posta num <span> do parágrafo vale para o parágrafo
        tags += [x for x in dict.fromkeys(nos_spans) if x not in tags]
        if did.startswith("on-cit-"):
            def fn():
                r, _ = self._texto_p(no)
                for x in r:
                    if x[1]["cor"] == paleta.CINZA_CITACAO:
                        x[1] = dict(x[1], cor=None)
                    x[1] = dict(x[1], i=False)
                return "> " + self.render(r).strip()
            grupo = did.rsplit("-", 1)[0]
            return [self._duplo("cit", no, fn, grupo, n0=n0)]
        caixas = [x for x in tags if x.split(":")[0] in MARCAVEIS]
        if caixas:
            c = caixas[0]
            feito = c.endswith(":completed")
            base = c.split(":")[0]
            outras = [x for x in tags if x != c]
            extra = ([base] if base != "to-do" else []) + outras

            def fn():
                r, _ = self._texto_p(no)
                lev = self.levantar(r)
                return f"- [{'x' if feito else ' '}] " + self.render(r).strip() + self.attrs_bloco(no, lev, extra)
            return [self._duplo("tarefa", no, fn, tags=tags, n0=n0)]
        r, _ = self._texto_p(no)
        plano = "".join(x[0] for x in r if not x[1]["raw"]).strip()
        if len(plano) >= 8 and set(plano) == {"─"}:
            return [Bloco("linha", no, "---", "---", perdas=self.n_perdas > n0)]
        if not plano:
            return []

        def fn():
            r2, _ = self._texto_p(no)
            lev = self.levantar(r2)
            return _escapar_inicio(self.render(r2).strip()) + self.attrs_bloco(no, lev, tags)
        return [self._duplo("par", no, fn, tags=tags, n0=n0)]

    def _h(self, no):
        n = no.tag
        padrao = _PADRAO_H[n]
        css = no.css()
        sem = [k for k, v in padrao.items()
               if k in css and (paleta.para_hex(css[k]) == v if k == "color" else css[k].lower() == v.lower())]
        tags = self.etiquetas(no.attrs.get("data-tag", ""))
        r, nos_spans = self._texto_p(no, sem=sem)
        tags += [x for x in dict.fromkeys(nos_spans) if x not in tags]
        lev = self.levantar(r)
        return f"{'#' * int(n[1])} " + self.render(r).strip() + self.attrs_bloco(no, lev, tags)

    def _lista(self, no, nivel):
        itens = [li for li in no.elementos() if li.tag == "li"]
        if not itens:
            return ""
        css0 = estilo(itens[0].attrs.get("style"))
        tipo = (css0.get("list-style-type") or no.css().get("list-style-type") or "").lower()
        linhas = []
        for k, li in enumerate(itens):
            inl, sub = [], []
            for f in li.filhos:
                if f.tag in ("ul", "ol"):
                    sub.append(f)
                elif f.tag == "p":
                    inl.append(f)
                else:
                    inl.append(f)
            tags = self.etiquetas(li.attrs.get("data-tag", ""))
            herd = self.marcas(li, _vazia(), sem=("list-style-type",))
            r, viu_p = [], False
            for f in inl:
                if f.tag == "p":
                    if viu_p:
                        r.append([" ", herd])
                    viu_p = True
                    r.extend(self.runs(f.filhos, self.marcas(f, herd), tags))
                else:
                    r.extend(self.runs([f], herd, tags))
            lev = self.levantar(r)
            if no.tag == "ol":
                mk = _numero(k, _TIPO_OL.get(tipo, "1"))
            else:
                mk = "-"
            extra = {}
            if k == 0 and no.tag == "ul" and tipo in _MARCADOR:
                extra["marcador"] = _MARCADOR[tipo]
            tags = list(dict.fromkeys(tags))
            texto = self.render(r).strip()
            linhas.append("  " * nivel + f"{mk} {texto}" + self.attrs_bloco(li, lev, tags, extra))
            for s in sub:
                linhas.append(self._lista(s, nivel + 1))
        return "\n".join(x for x in linhas if x)

    # ---- tabelas ----
    @staticmethod
    def _linhas(tab):
        trs = []
        for f in tab.elementos():
            if f.tag == "tr":
                trs.append(f)
            elif f.tag in ("tbody", "thead", "tfoot"):
                trs.extend(x for x in f.elementos() if x.tag == "tr")
        return [[td for td in tr.elementos() if td.tag in ("td", "th")] for tr in trs]

    @staticmethod
    def _so_inline(td):
        return all(f.tag is None or f.tag not in _BLOCOS and not re.match(r"^h[1-6]$", f.tag) and f.tag != "li"
                   for f in td.filhos)

    def _miolo_td(self, td, celula=False):
        """conteúdo da célula: inline (1 linha) ou blocos (várias linhas)"""
        if self._so_inline(td):
            r = self.runs(td.filhos, _vazia())
            if td.tag == "th":
                for x in r:
                    x[1] = dict(x[1], b=True)
            return self.render(r, celula).strip()
        return juntar(self.itens(td), self.ids)

    def _tabela(self, no):
        did = no.attrs.get("data-id") or ""
        linhas = self._linhas(no)
        if did.startswith("on-cod-"):
            return self._codigo(did, linhas)
        if did.startswith("on-dst-") and linhas and linhas[0]:
            return self._destaque(linhas[0][0])
        if did.startswith("on-col-") and linhas:
            cols = []
            for td in linhas[0]:
                w = _px(td.css().get("width"))
                larg = f" largura={_pct(w)}" if w else ""
                cols.append(f"<coluna{larg}>\n{self._miolo_td(td)}\n</coluna>")
            return "<colunas>\n" + "\n".join(cols) + "\n</colunas>"
        gfm = self._gfm(no, did, linhas)
        if gfm:
            return gfm
        return self._rica(no, did, linhas)

    def _codigo(self, did, linhas):
        partes = did.split("-")
        lang = partes[3] if len(partes) > 3 else ""
        texto = []
        for row in linhas:
            for td in row:
                ps = [f for f in td.elementos() if f.tag == "p"]
                fontes = ps if ps else [td]
                for p in fontes:
                    bruto = "".join(_todo_texto(p))
                    texto.extend(bruto.split("￼"))
        texto = [l.replace(" ", " ") for l in texto]
        if texto and all(not l.strip() for l in texto):
            texto = [""]
        # cerca maior que qualquer sequência de crases do código: uma linha "````" não fecha o bloco antes da hora
        maior = max((len(c) for l in texto for c in re.findall(r"`+", l)), default=0)
        cerca = "`" * max(3, maior + 1)
        return f"{cerca}{lang}\n" + "\n".join(l.rstrip() if not l.strip() else l for l in texto) + f"\n{cerca}"

    def _destaque(self, td):
        fundo = paleta.para_hex(td.css().get("background-color", "")) or paleta.PALETA["amarelo"][1]
        miolo = self._miolo_td(td)
        icone = ""
        linhas = miolo.split("\n")
        if linhas:
            mh = re.match(r"^(#{1,6} )(.*)$", linhas[0])
            pre, resto = (mh.group(1), mh.group(2)) if mh else ("", linhas[0])
            tok, _, depois = resto.partition(" ")
            if _eh_icone(tok):
                icone = tok
                if depois.strip() or pre:
                    linhas[0] = pre + depois
                else:
                    linhas = linhas[1:]
                    while linhas and not linhas[0].strip():
                        linhas = linhas[1:]
        ic = f' icone="{icone}"' if icone else ""
        return f"<destaque cor={paleta.nome_fundo(fundo)}{ic}>\n" + "\n".join(linhas) + "\n</destaque>"

    def _borda(self, no):
        b = no.attrs.get("border")
        css = no.css()
        m = re.match(r"^(\d)", css.get("border", "").strip())
        if m:
            return m.group(1)
        return b if b in ("0", "1", "2", "3") else "0"

    def _gfm(self, no, did, linhas):
        if did or not linhas or self._borda(no) != "1":
            return None
        n = len(linhas[0])
        if n == 0 or any(len(r) != n for r in linhas):
            return None
        for r in linhas:
            for td in r:
                if not self._so_inline(td) or "background-color" in td.css():
                    return None
        cab = []
        for td in linhas[0]:
            r = self.runs(td.filhos, _vazia())
            cheias = [x for x in r if x[0].strip() and not x[1]["raw"]]
            # célula vazia no cabeçalho (canto de tabela-matriz) vale; a que tem texto precisa ser negrito
            if td.tag != "th" and cheias and not all(x[1]["b"] for x in cheias):
                return None
            for x in r:
                x[1] = dict(x[1], b=False)
            cab.append(self.render(r, celula=True).strip())
        alin = []
        for k in range(n):
            vals = {(r[k].css().get("text-align") or "").lower() for r in linhas}
            if len(vals) > 1:
                return None
            alin.append(vals.pop())
        sep = {"": "---", "left": ":--", "center": ":-:", "right": "--:"}
        if any(a not in sep for a in alin):
            return None

        def linha(cels):   # célula vazia sai "| |" (um espaço), igual ao que se escreve
            return "|" + "|".join(f" {c} " if c else " " for c in cels) + "|"
        saida = [linha(cab), linha(sep[a] for a in alin)]
        for r in linhas[1:]:
            saida.append(linha(self.render(self.runs(td.filhos, _vazia()), celula=True).strip() for td in r))
        return "\n".join(saida)

    def _rica(self, no, did, linhas):
        a = []
        b = self._borda(no)
        if b != "1":
            a.append(f"borda={b}")
        w = _px(no.css().get("width") or no.attrs.get("width"))
        if w:
            a.append(f"largura={_pct(w)}")
        if self.ids and did and not did.startswith("on-") and ID_PROPRIO.match(did):
            a.append(f"id={did}")
        saida = ["<tabela" + (" " + " ".join(a) if a else "") + ">"]
        for row in linhas:
            fundos = [paleta.para_hex(td.css().get("background-color", "")) for td in row]
            fl = fundos[0] if fundos and fundos[0] and len(set(fundos)) == 1 else None
            saida.append(f"<linha fundo={paleta.nome_fundo(fl)}>" if fl else "<linha>")
            for td, fd in zip(row, fundos):
                ca = []
                cw = _px(td.css().get("width"))
                if cw:
                    ca.append(f"largura={_pct(cw)}")
                al = (td.css().get("text-align") or "").lower()
                if al in _ALINHAR and al != "left":
                    ca.append(f"alinhar={_ALINHAR[al]}")
                if fd and fd != fl:
                    ca.append(f"fundo={paleta.nome_fundo(fd)}")
                abre = "<celula" + (" " + " ".join(ca) if ca else "") + ">"
                miolo = self._miolo_td(td)
                if "\n" in miolo:
                    saida.append(f"{abre}\n{miolo}\n</celula>")
                else:
                    saida.append(f"{abre}{miolo}</celula>")
            saida.append("</linha>")
        saida.append("</tabela>")
        return "\n".join(saida)

    # ---- imagem e anexo ----
    def _img(self, no):
        src = no.attrs.get("src") or no.attrs.get("data-fullres-src") or ""
        m = RECURSO.search(src)
        if not m:
            self.perda("imagem sem recurso reconhecido omitida")
            return ""
        alt = re.sub(r"[\]\x00-\x1f\x7f]", " ", no.attrs.get("alt", "")).strip()
        extra = {}
        w = _px(no.attrs.get("width") or no.css().get("width"))
        if w:
            extra["largura"] = _pct(w)
        tags = self.etiquetas(no.attrs.get("data-tag", ""))
        return f"![{alt}](recurso:{m.group(1)})" + self.attrs_bloco(no, None, tags, extra).replace(" {", "{", 1)

    def _obj(self, no):
        m = RECURSO.search(no.attrs.get("data", ""))
        if not m:
            self.perda("anexo sem recurso reconhecido omitido")
            return ""
        nome = re.sub(r"[<>]", "", _CONTROLE.sub(" ", no.attrs.get("data-attachment", ""))).replace('"', "'")
        return f'<anexo recurso="{m.group(1)}" nome="{nome}"/>'


def _todo_texto(no):
    if no.tag is None:
        yield no.texto
    else:
        for f in no.filhos:
            yield from _todo_texto(f)


def _eh_icone(tok):
    if not tok or len(tok) > 8:
        return False
    cats = [unicodedata.category(c) for c in tok]
    return "So" in cats and all(c in ("So", "Sk", "Mn", "Cf", "Me") for c in cats)


def _romano(n):
    val = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
           (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    s = ""
    for v, r in val:
        while n >= v:
            s, n = s + r, n - v
    return s


def _numero(k, tipo):
    n = k + 1
    if tipo == "a":
        return (chr(96 + n) if n <= 26 else "a" + chr(96 + (n - 1) % 26 + 1)) + "."
    if tipo == "A":
        return _numero(k, "a").upper()
    if tipo == "i":
        return _romano(n) + "."
    if tipo == "I":
        return _romano(n).upper() + "."
    return f"{n}."


def juntar(itens, ids=False):
    """lista de Bloco/Caixa → ONMD; tarefas seguidas e linhas da mesma citação ficam coladas"""
    partes, ant = [], None
    for it in itens:
        if isinstance(it, Caixa):
            dentro = juntar(it.filhos, ids)
            s = it.abre + "\n" + dentro + "\n" + it.fecha
            sep = "\n\n"
        else:
            s = it.onmd_ids if ids else it.onmd
            if not s:
                continue
            colado = isinstance(ant, Bloco) and (
                (ant.tipo == it.tipo == "tarefa") or (ant.tipo == it.tipo == "cit" and ant.grupo == it.grupo))
            sep = "\n" if colado else "\n\n"
        partes.append((sep if partes else "") + s)
        ant = it
    return "".join(partes)


def _folhas(itens):
    for it in itens:
        if isinstance(it, Caixa):
            yield from _folhas(it.filhos)
        else:
            yield it


def ler(html, incluir_ids=False):
    """HTML de saída do OneNote → Leitura (ONMD da página + blocos editáveis com id gerado)"""
    raiz = arvore(html)
    corpo = achar(raiz, "body") or raiz
    lt = _Leitor(raiz)
    lt.dominante(corpo)
    divs = [d for d in corpo.elementos() if d.tag == "div"]
    livres = [d for d in divs if "absolute" in d.css().get("position", "")]
    itens = []
    if len(livres) > 1:
        lt.aviso("página com várias caixas (posição livre): <caixa> é só de leitura; edite os blocos por trecho")
        for d in corpo.elementos():
            if d.tag == "div" and d in livres:
                css = d.css()
                x, y, w = _px(css.get("left")), _px(css.get("top")), _px(css.get("width"))
                a = " ".join(f"{k}={int(v)}" for k, v in (("x", x), ("y", y), ("largura", w)) if v is not None)
                itens.append(Caixa(f"<caixa {a}>".replace(" >", ">"), "</caixa>", lt.itens(d)))
            else:
                itens.extend(lt.bloco(d) if d.tag else [])
    else:
        itens = lt.itens(corpo)
    blocos = list(_folhas(itens))
    secoes, contagem = [], Counter()

    def coletar(no):
        if no.tag:
            d = no.attrs.get("data-id")
            if d and d != "_default":
                contagem[d] += 1
                if no.tag == "div":
                    secoes.append(d)
            for f in no.filhos:
                coletar(f)
    coletar(corpo)
    data_ids = set(contagem)
    repetidos = {d for d, n in contagem.items() if n > 1}
    ultima = None
    for d in divs:
        i = d.attrs.get("id", "")
        if i.startswith("div:"):
            ultima = i
    return Leitura(juntar(itens, incluir_ids).strip(), lt.avisos, lt.fonte, blocos, secoes, data_ids, ultima, itens,
                   repetidos)


def titulo(html):
    t = achar(arvore(html), "title")
    return "".join(_todo_texto(t)).strip() if t else ""
