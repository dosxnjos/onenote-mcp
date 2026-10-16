# imita o que o OneNote faz com o HTML de entrada, segundo o medido em docs/provas-v2.md
# (sonda-1-criada.html): ids gerados, margens 5.5pt, b/i/u/del viram <span style>, cor/fonte do <p> descem
# para os spans, data-tag sem espaço, definition→remember-for-later, tipo da lista desce para o <li>, pai de
# sub-lista vira <p>, borda da tabela vira style, largura do td sem unidade (−1 com borda), <br /> solto depois
# de lista, img/object name: viram /resources/{id}/$value. Só para teste (ida e volta e Graph falso).
from onenote_mcp.formato.leitura import No, arvore, serializar

_PADRAO_H = {
    "h1": "font-size:16pt;color:#1e4e79", "h2": "font-size:14pt;color:#2e75b5",
    "h3": "font-size:12pt;color:#5b9bd5", "h4": "font-size:12pt;color:#5b9bd5;font-style:italic",
    "h5": "color:#2e75b5", "h6": "color:#2e75b5;font-style:italic",
}
_INLINE = {"b": "font-weight:bold", "strong": "font-weight:bold", "i": "font-style:italic",
           "em": "font-style:italic", "u": "text-decoration:underline", "del": "text-decoration:line-through",
           "strike": "text-decoration:line-through"}
_DESCE = ("color", "background-color", "font-family", "font-size")
MARGEM = "margin-top:5.5pt;margin-bottom:5.5pt"
_ORDENADOS = {"decimal", "lower-alpha", "upper-alpha", "lower-roman", "upper-roman"}


def _css(s):
    d = {}
    for decl in (s or "").split(";"):
        k, _, v = decl.partition(":")
        if k.strip() and v.strip():
            d[k.strip()] = v.strip()
    return d


def _str(d):
    return ";".join(f"{k}:{v}" for k, v in d.items())


class Simulador:
    def __init__(self, guid="00000000-0000-4000-8000-0000000000a1", inicio=10):
        self.guid, self.n, self.rec = guid, inicio, 0

    def _id(self, tag):
        self.n += 1
        return f"{tag}:{{{self.guid}}}{{{self.n}}}"

    def _descer(self, no, herdado):
        """cor/fundo/fonte/tamanho do bloco descem para spans em volta de cada texto"""
        novos = []
        for f in no.filhos:
            if f.tag is None:
                if herdado and f.texto:
                    s = No("span", {"style": _str(herdado)}, pai=no)
                    s.filhos = [No(texto=f.texto, pai=s)]
                    novos.append(s)
                else:
                    novos.append(f)
            elif f.tag in ("span", "a", "sup", "sub"):
                css = dict(herdado)
                css.update(_css(f.attrs.get("style")))
                if css:
                    f.attrs["style"] = _str(css)
                novos.append(f)
            else:
                novos.append(f)
        no.filhos = novos

    def _inline(self, no):
        for f in no.filhos:
            if f.tag in _INLINE:
                css = _css(f.attrs.get("style"))
                k, _, v = _INLINE[f.tag].partition(":")
                css[k] = v
                f.tag, f.attrs = "span", {"style": _str(css)}
            if f.tag:
                self._inline(f)

    def _no(self, no, dentro_lista=False):
        t = no.tag
        if t is None:
            return
        for f in list(no.filhos):
            self._no(f, t in ("ul", "ol"))
        if t in ("p",) or (t and t[0] == "h" and t[1:].isdigit()):
            css = _css(no.attrs.get("style"))
            if t == "p":
                desce = {k: css.pop(k) for k in list(css) if k in _DESCE}
                self._inline(no)
                self._descer(no, desce)
                css.update(_css(MARGEM))
            else:
                base = _css(_PADRAO_H[t])
                base.update(css)
                base.update(_css(MARGEM))
                css = base
                self._inline(no)
            no.attrs["style"] = _str(css)
            no.attrs["id"] = self._id(t)
            # medido na vitrine (15/10): o OneNote serializa "<br />\n\ntexto" (quebra de formatação depois do br)
            novos = []
            for f in no.filhos:
                novos.append(f)
                if f.tag == "br":
                    novos.append(No(texto="\n\n", pai=no))
            no.filhos = novos
        elif t == "li":
            css = _css(no.attrs.get("style"))
            desce = {k: css.pop(k) for k in list(css) if k in _DESCE}
            self._inline(no)
            self._descer(no, desce)
            sub = [f for f in no.filhos if f.tag in ("ul", "ol")]
            if sub:
                p = No("p", {"style": "margin-top:0pt;margin-bottom:0pt"}, pai=no)
                p.filhos = [f for f in no.filhos if f.tag not in ("ul", "ol")]
                p.attrs["id"] = self._id("p")
                no.filhos = [p] + sub
            if css:
                no.attrs["style"] = _str(css)
            else:
                no.attrs.pop("style", None)
            no.attrs["id"] = self._id("li")
        elif t in ("ul", "ol"):
            css = _css(no.attrs.pop("style", ""))
            tipo = css.get("list-style-type")
            for li in no.filhos:
                if li.tag == "li" and tipo:
                    c = _css(li.attrs.get("style"))
                    c.setdefault("list-style-type", tipo)
                    li.attrs["style"] = _str(c)
            no.attrs["id"] = self._id(t)
        elif t == "table":
            borda = no.attrs.pop("border", "0")
            css = _css(no.attrs.get("style"))
            largura = css.pop("width", None)
            trs = [f for f in no.filhos if f.tag == "tr"]
            uma = len(trs) == 1 and len([x for x in trs[0].filhos if x.tag == "td"]) == 1
            for tr in trs:
                tr.attrs["id"] = self._id("tr")
                for td in tr.filhos:
                    if td.tag != "td":
                        continue
                    c = _css(td.attrs.get("style"))
                    if uma and largura and "width" not in c:
                        c["width"] = largura
                    if "width" in c:
                        px = int(c["width"].removesuffix("px"))
                        c["width"] = str(px - 1 if borda == "1" else px)
                    c["border"] = "1px solid" if borda == "1" else "0px"
                    td.attrs["style"] = _str(c)
                    td.attrs["id"] = self._id("td")
                    self._inline(td)
            novo = {"border": "1px solid", "border-collapse": "collapse"} if borda == "1" else {"border": "0px"}
            if largura and not uma:
                novo["width"] = largura
            no.attrs["style"] = _str(novo)
            no.attrs["id"] = self._id("table")
        elif t == "div":
            i = self._id("div")
            no.attrs["id"] = f"{i}:{i[4:]}"
        elif t == "img":
            nome = no.attrs.get("src", "")[5:]
            self.rec += 1
            no.attrs["src"] = (f"https://graph.microsoft.com/v1.0/me/onenote/resources/"
                               f"0-{self.rec:032x}!1-ABC!s{nome}/$value")
            no.attrs["data-src-type"] = "image/png"
            no.attrs["id"] = self._id("img")
        elif t == "object":
            self.rec += 1
            no.attrs["data"] = f"https://graph.microsoft.com/v1.0/me/onenote/resources/0-{self.rec:032x}!1-ABC!sX/$value"
            no.attrs["id"] = self._id("object")
        if "data-tag" in no.attrs:
            tags = [x.strip() for x in no.attrs["data-tag"].split(",")]
            no.attrs["data-tag"] = ",".join("remember-for-later" if x == "definition" else x for x in tags)

    def _embrulhar(self, raiz):
        """<li> soltos seguidos (lista com etiqueta) → um <ul>/<ol> com id (medido na vitrine 15/10, no POST e no
        PATCH): a etiqueta desce do <li> para um <span data-tag> em volta do texto; o tipo ordenado no <li> vira
        <ol>; duas listas soltas seguidas viram uma só"""
        filhos, grupo = [], []

        def fecha():
            if grupo:
                tipo = _css(grupo[0].attrs.get("style")).get("list-style-type", "")
                lista = No("ol" if tipo in _ORDENADOS else "ul", pai=raiz)
                lista.attrs["id"] = self._id(lista.tag)
                for li in grupo:
                    li.pai = lista
                    tag = li.attrs.pop("data-tag", None)
                    if tag:
                        texto = [f for f in li.filhos if f.tag not in ("ul", "ol", "p")]
                        s = No("span", {"data-tag": tag}, pai=li)
                        s.filhos = texto
                        li.filhos = [s] + [f for f in li.filhos if f.tag in ("ul", "ol", "p")]
                    c = _css(li.attrs.get("style"))
                    c.update(_css(MARGEM))
                    li.attrs["style"] = _str(c)
                lista.filhos = list(grupo)
                filhos.append(lista)
                grupo.clear()
        for f in raiz.filhos:
            if f.tag == "li":
                grupo.append(f)
                continue
            if f.tag is None and not f.texto.strip() and grupo:
                continue
            fecha()
            filhos.append(f)
        fecha()
        raiz.filhos = filhos

    def nos(self, corpo_html):
        """fragmento → nós já "guardados pelo OneNote" (para o Graph falso aplicar um PATCH)"""
        raiz = arvore(corpo_html)
        for f in raiz.filhos:
            self._no(f)
        self._embrulhar(raiz)
        return [f for f in raiz.filhos if f.tag or f.texto.strip()]

    def pagina(self, corpo_html, titulo="Vitrine"):
        raiz = arvore(corpo_html)
        for f in raiz.filhos:
            self._no(f)
        self._embrulhar(raiz)
        filhos = []
        for f in raiz.filhos:
            filhos.append(f)
            if f.tag in ("ul", "ol"):
                filhos.append(No("br"))  # ruído medido nas provas
        div_id = self._id("div")
        corpo = "".join(serializar(f) for f in filhos)
        return (f'<html lang="en-US"><head><title>{titulo}</title></head>'
                f'<body data-absolute-enabled="true" style="font-family:Calibri;font-size:11pt">'
                f'<div id="{div_id}" data-id="_default" style="position:absolute;left:48px;top:120px;width:624px">'
                f"{corpo}</div></body></html>")


def simular_saida(corpo_html, titulo="Vitrine", **kw):
    return Simulador(**kw).pagina(corpo_html, titulo)
