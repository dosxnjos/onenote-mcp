# ONMD → HTML do OneNote (XHTML bem-formado; o sanitizador roda DEPOIS, no HTML final)
# parser próprio, por linhas (blocos) e por caracteres (inline). Regras medidas em docs/provas-v2.md:
# - código = tabela on-cod- com 1 <p> Consolas por linha (pre some no OneNote); espaço vira NBSP
# - citação = <p> cinza itálico com data-id on-cit-<grupo>-<n> (barra lateral cortada pela crítica)
# - destaque/colunas = tabela sem borda com data-id on-dst-/on-col-; <tabela> rica leva on-tab- se não tem id
# - fundo da tabela vai em cada <td> (bgcolor some); largura sempre em % da página (624 px), vira px
# - item de lista com etiqueta → <li> solto (data-tag no ul/ol sobrepõe os itens: crítica correção 3)
# - call-back fora (vira schedule-meeting); definition avisa que volta remember-for-later
# - HTML cru do modelo NÃO passa: tag fora da spec vira texto literal + aviso
# - imagem/anexo só por anexo:N (parâmetro anexos); recurso: (imagem que já existe) dá erro orientador
# - perda calada vira erro orientador: etiqueta em sub-item, célula GFM a mais com texto, id repetido (alvo #id
#   ambíguo); lista que não começa em 1 avisa (o OneNote numera do início); sub-item de lista avisa (linha em
#   branco antes do sub-nível, limite da Microsoft)
# - caractere de controle sai com aviso; <br> = quebra de linha dentro do parágrafo; URL aceita (…) balanceado
import html as _html
import re
from dataclasses import dataclass, field

from ..sanitizar import ID_PROPRIO, MARCAVEIS, etiquetas_limpas, sem_controle
from . import paleta

LARGURA = 624  # px da caixa padrão da página (EX [IO])
_PONTUACAO = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
_RESERVADO = ("on-",)
_TAG_CONTAINER = ("destaque", "colunas", "coluna", "tabela", "linha", "celula", "secao", "caixa")
_CHAVES_BLOCO = {"id", "cor", "fundo", "fonte", "tamanho", "alinhar", "tags", "marcador", "largura"}
_ALINHAR = {"esquerda": "left", "centro": "center", "direita": "right"}
_MARCADOR = {"circulo": "circle", "quadrado": "square", "nenhum": "none", "disco": "disc"}
_ATTR = r'[a-z]+=(?:"[^"]*"|[^\s"}]+)'
_BLOCO_ATTRS = re.compile(r'(?:^|(?<=\s))(?<!\\)\{(' + _ATTR + r'(?:\s+' + _ATTR + r')*)\}\s*$')
_PAR_ATTR = re.compile(r'([a-z]+)=(?:"([^"]*)"|\'([^\']*)\'|([^\s"\'>}/]+))')
_ITEM = re.compile(r"^( *)(-|\d{1,3}\.|[a-zA-Z]{1,2}\.|[ivxlcdmIVXLCDM]{1,6}\.)\s+(.*)$")
_TAREFA = re.compile(r"^( *)- \[( |x|X)\]\s+(.*)$")
_IMAGEM = re.compile(r"^!\[([^\]]*)\]\(([^)\s]*)\)\s*(.*)$")
_ANEXO = re.compile(r"^<anexo\b([^>]*?)/?>\s*(?:</anexo>)?$")
_TIPO_OL = {"a": "lower-alpha", "A": "upper-alpha", "i": "lower-roman", "I": "upper-roman"}
# prova real 15/10 (docs/provas-v2.md § Listas aninhadas): 10 variantes de HTML, todas com parágrafo vazio antes do
# sub-nível; o GET não mostra esse parágrafo e o editor do site salva por outro protocolo. O HTML segue igual
AVISO_SUBITEM = ("sub-item de lista: o OneNote põe uma linha em branco antes de cada sub-nível (limite da "
                 "Microsoft); prefira títulos ou lista de um nível")


class ErroFormato(ValueError):
    """conteúdo ONMD que não dá para enviar; a mensagem orienta a correção (nada foi enviado)"""


@dataclass
class Escrita:
    html: str
    partes: list = field(default_factory=list)   # [(nome, mime, bytes)]
    avisos: list = field(default_factory=list)
    anexos_usados: list = field(default_factory=list)


def _esc(t):
    return _html.escape(t, quote=False)


def _esc_attr(t):
    return _html.escape(t, quote=True)


def _attrs(texto):
    """'cor=azul fonte="Segoe UI"' → {"cor": "azul", "fonte": "Segoe UI"}"""
    return {m.group(1): next(g for g in m.groups()[1:] if g is not None) for m in _PAR_ATTR.finditer(texto or "")}


def _pct_para_px(valor):
    v = str(valor).strip().rstrip("%").strip()
    try:
        p = float(v.replace(",", "."))
    except ValueError:
        raise ErroFormato(f"largura inválida: {valor!r} (use porcentagem da página, ex.: largura=40%)") from None
    if not 1 <= p <= 100:
        raise ErroFormato(f"largura fora de 1–100%: {valor!r}")
    return round(LARGURA * p / 100)


class _Escritor:
    def __init__(self, anexos=None, resolver_pagina=None, ids_existentes=(), fonte_padrao=None):
        # sequência (len + índice): quem chama pode carregar cada arquivo só quando o texto cita anexo:N
        self.anexos = anexos if anexos is not None else []
        self.resolver_pagina = resolver_pagina
        self.fonte_padrao = fonte_padrao
        self.avisos = []
        self.partes = {}   # nome → (mime, bytes)
        self.usados = set()
        self.cont = {}
        self.ids_ocupados = {i for i in ids_existentes or () if i}   # data-id já na página: alvo #id ambíguo
        self.ids_usados = set()
        for i in ids_existentes or ():
            m = re.match(r"^on-([a-z]{3})-(\d+)", i or "")
            if m:
                self.cont[m.group(1)] = max(self.cont.get(m.group(1), 0), int(m.group(2)))

    def _novo_id(self, tipo):
        self.cont[tipo] = self.cont.get(tipo, 0) + 1
        return f"on-{tipo}-{self.cont[tipo]}"

    def aviso(self, msg):
        if msg not in self.avisos:
            self.avisos.append(msg)

    # ---------------- atributos de bloco ----------------
    def separar_attrs(self, texto):
        m = _BLOCO_ATTRS.search(texto)
        if not m:
            return texto, {}
        a = _attrs(m.group(1))
        for k in [k for k in a if k not in _CHAVES_BLOCO]:
            self.aviso(f"atributo desconhecido ignorado: {k}=")
            a.pop(k)
        return texto[: m.start()].rstrip(), a

    def estilo(self, a, alinhar=True, fonte_padrao=False):
        css = []
        try:
            if "cor" in a:
                css.append(f"color:{paleta.cor_texto(a['cor'])}")
            if "fundo" in a:
                css.append(f"background-color:{paleta.cor_fundo(a['fundo'])}")
        except paleta.CorInvalida as e:
            raise ErroFormato(str(e)) from None
        fonte = a.get("fonte") or (self.fonte_padrao if fonte_padrao else None)
        if fonte:
            if not re.match(r"^[A-Za-z0-9 \-]{1,40}$", fonte):
                raise ErroFormato(f"fonte inválida: {fonte!r} (só letras, números, espaço e hífen)")
            css.append(f"font-family:{fonte}")
        if "tamanho" in a:
            t = str(a["tamanho"]).replace(",", ".").removesuffix("pt")
            if not re.match(r"^\d{1,3}(\.\d+)?$", t) or not 1 <= float(t) <= 200:
                raise ErroFormato(f"tamanho inválido: {a['tamanho']!r} (pontos, ex.: tamanho=14)")
            css.append(f"font-size:{float(t):g}pt")
        if alinhar and "alinhar" in a:
            if a["alinhar"] not in _ALINHAR:
                raise ErroFormato(f"alinhar inválido: {a['alinhar']!r} (esquerda, centro ou direita)")
            css.append(f"text-align:{_ALINHAR[a['alinhar']]}")
        return ";".join(css)

    def id_proprio(self, a):
        i = a.get("id")
        if not i:
            return None
        if not ID_PROPRIO.match(i) or i.startswith(_RESERVADO):
            self.aviso(f"id inválido ignorado: {i!r} (minúsculas, números, - e _; o prefixo on- é reservado)")
            return None
        # o alvo #id precisa ser único: com dois iguais o Graph escolhe um sem dizer qual (crítica §1.4)
        if i in self.ids_ocupados:
            raise ErroFormato(f"id={i} já existe na página: escolha outro (o id vira o alvo #{i} e precisa ser único)")
        if i in self.ids_usados:
            raise ErroFormato(f"id={i} repetido neste conteúdo: cada id aparece uma vez só")
        self.ids_usados.add(i)
        return i

    def etiquetas(self, valor):
        if not valor:
            return []
        tags = [t.strip() for t in str(valor).split(",") if t.strip()]
        if "call-back" in tags:
            self.aviso("etiqueta call-back não é aceita (o OneNote troca por schedule-meeting); foi descartada")
            tags.remove("call-back")
        if "definition" in tags:
            self.aviso("a etiqueta definition volta na leitura como remember-for-later")
        if "password" in tags:
            self.aviso("password é só o nome de uma etiqueta: não guarde senha no OneNote")
        boas = etiquetas_limpas(",".join(tags), self.avisos)
        return [t.strip() for t in boas.split(",") if t.strip()]

    def abrir(self, tag, a, alinhar=True, extra_css="", fonte_padrao=False, tags_extra=()):
        attrs = []
        i = self.id_proprio(a)
        if i:
            attrs.append(f'data-id="{i}"')
        tags = list(tags_extra) + [t for t in self.etiquetas(a.get("tags")) if t not in tags_extra]
        if tags:
            attrs.append(f'data-tag="{_esc_attr(", ".join(tags))}"')
        css = ";".join(x for x in (extra_css, self.estilo(a, alinhar, fonte_padrao)) if x)
        if css:
            attrs.append(f'style="{_esc_attr(css)}"')
        return f"<{tag}{''.join(' ' + x for x in attrs)}>"

    # ---------------- blocos ----------------
    def blocos(self, texto):
        linhas = (texto or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        return "".join(self._blocos(linhas))

    def _blocos(self, linhas):
        out, i = [], 0
        while i < len(linhas):
            bruta = linhas[i]
            l = bruta.strip()
            if not l:
                i += 1
                continue
            if l.startswith("```"):
                i = self._codigo(linhas, i, out)
                continue
            m = re.match(r"^<(" + "|".join(_TAG_CONTAINER) + r")\b([^>]*)>(.*)$", l)
            if m:
                i = self._container(linhas, i, m, out)
                continue
            if re.match(r"^</(" + "|".join(_TAG_CONTAINER) + r")>\s*$", l):
                self.aviso(f"fechamento sem abertura ignorado: {l}")
                i += 1
                continue
            m = re.match(r"^(#{1,6})\s+(.*)$", l)
            if m:
                txt, a = self.separar_attrs(m.group(2))
                n = len(m.group(1))
                out.append(f"{self.abrir(f'h{n}', a)}{self.inline(txt)}</h{n}>")
                i += 1
                continue
            if re.match(r"^-{3,}$", l):
                out.append(f'<p style="color:{paleta.CINZA_DIVISORIA}">{"─" * 32}</p>')
                i += 1
                continue
            if l.startswith(">"):
                grupo = self._novo_id("cit")
                n = 0
                while i < len(linhas) and linhas[i].strip().startswith(">"):
                    t = linhas[i].strip()[1:].strip()
                    if t:
                        n += 1
                        dentro = self.inline(t)
                        if "<i>" in dentro:
                            self.aviso("itálico dentro de citação não aparece (a citação já é toda em itálico)")
                        out.append(f'<p data-id="{grupo}-{n}" style="color:{paleta.CINZA_CITACAO}">'
                                   f"<i>{dentro}</i></p>")
                    i += 1
                continue
            if _TAREFA.match(bruta):
                while i < len(linhas) and _TAREFA.match(linhas[i]):
                    m = _TAREFA.match(linhas[i])
                    if m.group(1):
                        self.aviso("tarefa não aninha: ficou no nível da página")
                    out.append(self._tarefa(m.group(2).lower() == "x", m.group(3)))
                    i += 1
                continue
            if _inicia_lista(l):
                i = self._lista(linhas, i, out)
                continue
            m = _IMAGEM.match(l)
            if m:
                out.append(self._imagem(m.group(1), m.group(2), m.group(3)))
                i += 1
                continue
            m = _ANEXO.match(l)
            if m:
                out.append(self._anexo(_attrs(m.group(1))))
                i += 1
                continue
            if l.startswith("|") and i + 1 < len(linhas) and _separador_gfm(linhas[i + 1]):
                i = self._gfm(linhas, i, out)
                continue
            txt, a = self.separar_attrs(l)
            if txt:
                out.append(f"{self.abrir('p', a, fonte_padrao=True)}{self.inline(txt)}</p>")
            i += 1
        return out

    def _tarefa(self, feito, texto):
        txt, a = self.separar_attrs(texto)
        tags = self.etiquetas(a.pop("tags", None))
        caixa = next((t for t in tags if t in MARCAVEIS), "to-do")
        outras = [t for t in tags if t != caixa]
        primeira = f"{caixa}:completed" if feito else caixa
        return f"{self.abrir('p', a, fonte_padrao=True, tags_extra=[primeira] + outras)}{self.inline(txt)}</p>"

    def _codigo(self, linhas, i, out):
        abertura = linhas[i].strip()
        cerca = re.match(r"^`{3,}", abertura).group(0)
        lang = abertura[len(cerca):].strip().lower()
        corpo, i = [], i + 1
        while i < len(linhas) and linhas[i].strip() != cerca:
            corpo.append(linhas[i])
            i += 1
        if i >= len(linhas):
            self.aviso("bloco de código sem ``` de fechamento: foi até o fim")
        ident = self._novo_id("cod")
        if lang:
            if re.match(r"^[a-z0-9]{1,15}$", lang):
                ident += f"-{lang}"
            else:
                self.aviso(f"linguagem do bloco de código ignorada: {lang!r}")
        ps = "".join(f'<p style="font-family:Consolas;font-size:10pt">{_esc(l.replace(" ", chr(160))) or chr(160)}</p>'
                     for l in (corpo or [""]))
        out.append(f'<table border="0" style="width:{LARGURA}px" data-id="{ident}"><tr>'
                   f'<td style="background-color:{paleta.FUNDO_CODIGO}">{ps}</td></tr></table>')
        return i + 1

    # ---- containers <destaque> <colunas> <tabela> <secao> <caixa> ----
    def _fechar(self, linhas, i, nome, resto_primeira):
        """acha o </nome> que fecha (contando aninhamento). Devolve (miolo, índice seguinte, sobra da linha)"""
        abre = re.compile(r"<" + nome + r"\b[^>]*>")
        fecha = re.compile(r"</" + nome + r">")
        prof, miolo = 1, []
        linha, j = resto_primeira, i
        while True:
            pos = 0
            while True:
                ma, mf = abre.search(linha, pos), fecha.search(linha, pos)
                if mf and (not ma or mf.start() < ma.start()):
                    prof -= 1
                    if prof == 0:
                        miolo.append(linha[: mf.start()])
                        return "\n".join(miolo), j + 1, linha[mf.end():]
                    pos = mf.end()
                elif ma:
                    prof += 1
                    pos = ma.end()
                else:
                    break
            miolo.append(linha)
            j += 1
            if j >= len(linhas):
                self.aviso(f"<{nome}> sem </{nome}>: foi até o fim")
                return "\n".join(miolo), j, ""
            linha = linhas[j]

    def _container(self, linhas, i, m, out):
        nome, a = m.group(1), _attrs(m.group(2))
        miolo, prox, sobra = self._fechar(linhas, i, nome, m.group(3))
        if sobra.strip():
            linhas.insert(prox, sobra)  # a sobra depois do fechamento vira linha própria
        html = getattr(self, f"_c_{nome}")(a, miolo)
        if html:
            out.append(html)
        return prox

    def _miolo(self, texto):
        """conteúdo de célula/destaque: 1 linha simples = inline direto; senão blocos"""
        linhas = [l for l in texto.split("\n")]
        cheias = [l for l in linhas if l.strip()]
        if len(cheias) == 1 and _so_inline(cheias[0]):
            return self.inline(cheias[0].strip())
        return "".join(self._blocos(linhas))

    def _c_destaque(self, a, miolo):
        try:
            fundo = paleta.cor_fundo(a.get("cor", "amarelo"))
        except paleta.CorInvalida as e:
            raise ErroFormato(str(e)) from None
        icone = a.get("icone", "").strip()
        linhas = miolo.split("\n")
        if icone:
            k = next((n for n, l in enumerate(linhas) if l.strip()), None)
            if k is None:
                linhas = [icone]
            else:
                l = linhas[k].strip()
                mh = re.match(r"^(#{1,6}\s+)(.*)$", l)
                if mh:
                    linhas[k] = f"{mh.group(1)}{icone} {mh.group(2)}"
                elif _so_paragrafo(l):
                    linhas[k] = f"{icone} {l}"
                else:
                    linhas.insert(k, icone)
        corpo = self._miolo("\n".join(linhas))
        return (f'<table border="0" style="width:{LARGURA}px" data-id="{self._novo_id("dst")}"><tr>'
                f'<td style="background-color:{fundo}">{corpo}</td></tr></table>')

    def _filhos(self, miolo, nome):
        """<coluna>/<linha>/<celula> dentro do pai; texto solto fora deles gera aviso"""
        linhas, i, achados = miolo.split("\n"), 0, []
        while i < len(linhas):
            l = linhas[i].strip()
            m = re.match(r"^<" + nome + r"\b([^>]*)>(.*)$", l)
            if m:
                conteudo, i, sobra = self._fechar(linhas, i, nome, m.group(2))
                achados.append((_attrs(m.group(1)), conteudo))
                if sobra.strip():
                    linhas.insert(i, sobra)
                continue
            if l:
                self.aviso(f"texto fora de <{nome}> ignorado: {l[:40]}")
            i += 1
        return achados

    def _c_colunas(self, a, miolo):
        cols = self._filhos(miolo, "coluna")
        if not cols:
            raise ErroFormato("<colunas> precisa de pelo menos uma <coluna>")
        definidas = [_pct_para_px(c[0]["largura"]) for c in cols if "largura" in c[0]]
        livres = len(cols) - len(definidas)
        sobra = max(LARGURA - sum(definidas), 0)
        tds = []
        for ca, conteudo in cols:
            px = _pct_para_px(ca["largura"]) if "largura" in ca else round(sobra / livres)
            tds.append(f'<td style="width:{px}px">{self._miolo(conteudo)}</td>')
        return (f'<table border="0" style="width:{LARGURA}px" data-id="{self._novo_id("col")}">'
                f"<tr>{''.join(tds)}</tr></table>")

    def _c_coluna(self, a, miolo):
        self.aviso("<coluna> fora de <colunas>: virou texto normal")
        return "".join(self._blocos(miolo.split("\n")))

    def _c_tabela(self, a, miolo):
        borda = a.get("borda", "1")
        if borda not in ("0", "1", "2", "3"):
            raise ErroFormato(f"borda inválida: {borda!r} (0 a 3)")
        if "fundo" in a:
            self.aviso("fundo na <tabela> não é guardado pelo OneNote: use fundo= em <linha> ou <celula>")
        ident = self.id_proprio(a) or self._novo_id("tab")
        estilo = f' style="width:{_pct_para_px(a["largura"])}px"' if "largura" in a else ""
        linhas = []
        for la, lconteudo in self._filhos(miolo, "linha"):
            fundo_linha = la.get("fundo")
            tds = []
            for ca, cconteudo in self._filhos(lconteudo, "celula"):
                if "rowspan" in ca or "colspan" in ca or "mesclar" in ca:
                    self.aviso("mesclar células não é suportado pelo OneNote: ignorado")
                css = []
                if "largura" in ca:
                    css.append(f"width:{_pct_para_px(ca['largura'])}px")
                fundo = ca.get("fundo") or fundo_linha
                if fundo:
                    try:
                        css.append(f"background-color:{paleta.cor_fundo(fundo)}")
                    except paleta.CorInvalida as e:
                        raise ErroFormato(str(e)) from None
                if "alinhar" in ca:
                    if ca["alinhar"] not in _ALINHAR:
                        raise ErroFormato(f"alinhar inválido: {ca['alinhar']!r}")
                    css.append(f"text-align:{_ALINHAR[ca['alinhar']]}")
                if "cor" in ca:
                    self.aviso("cor= na célula não é aceita: use <span cor=…> ou {cor=…} no texto")
                st = f' style="{";".join(css)}"' if css else ""
                tds.append(f"<td{st}>{self._miolo(cconteudo)}</td>")
            if tds:
                linhas.append(f"<tr>{''.join(tds)}</tr>")
        if not linhas:
            raise ErroFormato("<tabela> sem <linha>/<celula>")
        return f'<table border="{borda}"{estilo} data-id="{ident}">{"".join(linhas)}</table>'

    def _c_linha(self, a, miolo):
        self.aviso("<linha> fora de <tabela>: virou texto normal")
        return "".join(self._blocos(miolo.split("\n")))

    _c_celula = _c_linha

    def _c_secao(self, a, miolo):
        corpo = "".join(self._blocos(miolo.split("\n")))
        ident = self.id_proprio(a)
        if not ident:
            self.aviso("<secao> sem id válido: o conteúdo entrou sem a seção nomeada")
            return corpo
        return f'<div data-id="{ident}">{corpo}</div>'

    def _c_caixa(self, a, miolo):
        self.aviso("<caixa> (posição livre) é só de leitura: o conteúdo entrou no fluxo normal da página")
        return "".join(self._blocos(miolo.split("\n")))

    # ---- listas ----
    def _lista(self, linhas, i, out):
        itens = []  # (indent, marcador, texto)
        niveis = {}  # recuo → 1º marcador daquele nível (os irmãos seguem o MESMO tipo: a→b→c, i→ii, 1→2)

        def cabe(l):
            """item que continua ESTA lista: mesmo tipo do 1º item do nível ("Ok." não segue "a. b."); sub-lista
            nova começa como lista (-, número, a, A, i, I)"""
            m = _ITEM.match(l)
            if not m or _TAREFA.match(l):
                return None
            if not itens:
                return m if _inicia_lista(l.strip()) else None
            ind, mk = len(m.group(1)), m.group(2)
            if ind in niveis or ind < min(niveis):
                return m if _continua(mk, niveis.get(ind) or niveis[min(niveis)]) else None
            return m if _inicia_lista(f"{mk} x") else None
        while i < len(linhas):
            l = linhas[i]
            if not l.strip():
                k = i + 1
                while k < len(linhas) and not linhas[k].strip():
                    k += 1
                if k < len(linhas) and itens and cabe(linhas[k]):
                    i = k
                    continue
                break
            m = cabe(l)
            if not m:
                break
            ind = len(m.group(1))
            itens.append((ind, m.group(2), m.group(3)))
            niveis.setdefault(ind, m.group(2))
            for k in [k for k in niveis if k > ind]:
                del niveis[k]
            i += 1
        # decide pela ÁRVORE, não pelo recuo do 1º item: "  - a\n- b\n  - c" aninha c sob b (recuo do anterior)
        raiz = self._arvore(itens)
        if any(no["f"] for no in raiz):
            self.aviso(AVISO_SUBITEM)   # aviso() não repete: um por escrita, mesmo com várias listas
        if any(self._tem_tags(no["f"]) for no in raiz):
            # só o 1º nível vira <li> solto; o sub-item fica dentro de <ul>/<ol>, e o data-tag da lista sobrepõe
            # o do item mesmo sem tag própria ([NT], crítica §1.3): a etiqueta sumiria calada
            raise ErroFormato("etiqueta em sub-item não é guardada pelo OneNote: ponha a etiqueta no item de cima "
                              "ou num parágrafo ({tags=…} no fim da linha)")
        com_tags = any("tags" in self.separar_attrs(t)[1] for _, _, t in itens)
        out.append(self._lista_html(raiz, solta=com_tags))
        if com_tags:
            self.aviso("lista com etiqueta vira itens soltos (o OneNote não guarda etiqueta em item de lista "
                       "dentro de <ul>/<ol>): numeração e marcador da lista se perdem")
        return i

    def _tem_tags(self, nos):
        """algum nó (ou descendente) desta sub-árvore traz {tags=…}"""
        return any("tags" in self.separar_attrs(no["t"])[1] or self._tem_tags(no["f"]) for no in nos)

    def _arvore(self, itens):
        """[(indent, marcador, texto)] → [{"m":…, "t":…, "f":[filhos]}] por recuo"""
        raiz = []
        pilha = [(-1, raiz)]
        for ind, mk, txt in itens:
            while len(pilha) > 1 and ind <= pilha[-1][0]:
                pilha.pop()
            no = {"m": mk, "t": txt, "f": []}
            pilha[-1][1].append(no)
            pilha.append((ind, no["f"]))
        return raiz

    def _lista_html(self, itens, solta=False):
        if not itens:
            return ""
        mk = itens[0]["m"]
        ordenada = mk != "-"
        tipo = None
        if ordenada and mk[:-1] in _TIPO_OL:
            tipo = _TIPO_OL[mk[:-1]]
        if ordenada and mk[:-1].isdigit() and int(mk[:-1]) != 1:
            # start não é suportado (pesquisa html-entrada): o OneNote numera do 1
            self.aviso(f"a lista numerada começa em {mk[:-1]}, mas o OneNote numera do início (1.): o número "
                       "escrito se perde. Lista quebrada por outro bloco recomeça do 1")
        lis, marcador = [], None
        for n, it in enumerate(itens):
            txt, a = self.separar_attrs(it["t"])
            if n == 0 and "marcador" in a:
                if ordenada or a["marcador"] not in _MARCADOR:
                    self.aviso(f"marcador ignorado: {a['marcador']!r} (só em lista com -: circulo, quadrado, nenhum)")
                else:
                    marcador = _MARCADOR[a["marcador"]]
            a.pop("marcador", None)
            tipo_li = tipo or marcador
            extra = f"list-style-type:{tipo_li}" if tipo_li else ""
            filhos = self._lista_html(it["f"]) if it["f"] else ""
            lis.append(f"{self.abrir('li', a, extra_css=extra, fonte_padrao=True)}{self.inline(txt)}{filhos}</li>")
        if solta:
            return "".join(lis)
        tag = "ol" if ordenada else "ul"
        st = tipo or marcador
        estilo = f' style="list-style-type:{st}"' if st else ""
        return f"<{tag}{estilo}>{''.join(lis)}</{tag}>"

    # ---- GFM ----
    def _gfm(self, linhas, i, out):
        cab = _celulas_gfm(linhas[i])
        alin = []
        for c in _celulas_gfm(linhas[i + 1]):
            c = c.strip()
            alin.append("center" if c.startswith(":") and c.endswith(":") else
                        "right" if c.endswith(":") else "left" if c.startswith(":") else None)
        corpo, i = [], i + 2
        while i < len(linhas) and linhas[i].strip().startswith("|"):
            corpo.append(_celulas_gfm(linhas[i]))
            i += 1

        def td(c, k, negrito):
            al = alin[k] if k < len(alin) else None
            st = f' style="text-align:{al}"' if al else ""
            dentro = self.inline(c.strip())
            return f"<td{st}>{'<b>' + dentro + '</b>' if negrito and dentro else dentro}</td>"
        n = len(cab)
        trs = ["<tr>" + "".join(td(c, k, True) for k, c in enumerate(cab)) + "</tr>"]
        for row in corpo:
            if any(c.strip() for c in row[n:]):
                raise ErroFormato(f"linha da tabela com {len(row)} células e cabeçalho com {n}: o texto a mais se "
                                  "perderia. Escape | como \\| dentro da célula (vale dentro de `código`) ou acerte "
                                  "o cabeçalho")
            row = (row + [""] * n)[:n]   # sobra só de células vazias (| a mais no fim): nada se perde
            trs.append("<tr>" + "".join(td(c, k, False) for k, c in enumerate(row)) + "</tr>")
        out.append(f'<table border="1">{"".join(trs)}</table>')
        return i

    # ---- imagem e anexo ----
    def _anexo_n(self, ref, uso):
        if ref.startswith("recurso:") or ref.startswith("recurso="):
            raise ErroFormato("imagem ou anexo que já existe (recurso:) não se recria: deixe o bloco como está e "
                              "edite o bloco vizinho, ou mande o arquivo de novo em `anexos` e cite anexo:N")
        m = re.match(r"^anexo:(\d{1,2})$", ref)
        if not m:
            raise ErroFormato(f"{uso} só por anexo:N (N = posição em `anexos`, começando em 1); "
                              f"URL e caminho no texto não são aceitos: {ref[:60]!r}")
        n = int(m.group(1))
        if not 1 <= n <= len(self.anexos):
            raise ErroFormato(f"anexo:{n} não existe: `anexos` tem {len(self.anexos)} item(ns)")
        self.usados.add(n)
        return n, self.anexos[n - 1]

    def _imagem(self, alt, ref, resto):
        n, ax = self._anexo_n(ref, "imagem")
        if not ax.imagem:
            raise ErroFormato(f"anexo:{n} não é imagem (PNG, JPEG, GIF, BMP ou TIFF): use <anexo n={n}/>")
        _, a = self.separar_attrs(" " + resto) if resto.strip() else ("", {})
        nome = f"img{n}"
        self.partes[nome] = (ax.mime, ax.dados)
        attrs = [f'src="name:{nome}"', f'alt="{_esc_attr(alt)}"']
        if "largura" in a:
            attrs.append(f'width="{_pct_para_px(a["largura"])}"')
            # prova real 15/10: PNG de 48 px voltou sem width (pedindo 312 ou 31); o de 800 px manteve
            self.aviso("largura de imagem: o OneNote às vezes ignora em imagem pequena; confira no site")
        i = self.id_proprio(a)
        if i:
            attrs.append(f'data-id="{i}"')
        tags = self.etiquetas(a.get("tags"))
        if tags:
            attrs.append(f'data-tag="{_esc_attr(", ".join(tags))}"')
        return f"<img {' '.join(attrs)} />"

    def _anexo(self, a):
        if "recurso" in a:
            self._anexo_n("recurso:", "anexo")
        if "n" not in a:
            raise ErroFormato('<anexo> precisa de n= (posição em `anexos`), ex.: <anexo n=2 nome="relatorio.xlsx"/>')
        n, ax = self._anexo_n(f"anexo:{a['n']}", "anexo")
        if ax.imagem:
            raise ErroFormato(f"anexo:{n} é imagem: use ![legenda](anexo:{n})")
        nome = f"arq{n}"
        self.partes[nome] = (ax.mime, ax.dados)
        rotulo = a.get("nome") or ax.nome
        attrs = [f'data="name:{nome}"', f'data-attachment="{_esc_attr(rotulo)}"', f'type="{ax.mime}"']
        i = self.id_proprio(a)
        if i:
            attrs.append(f'data-id="{i}"')
        return f"<object {' '.join(attrs)} />"

    # ---------------- inline ----------------
    def inline(self, s):
        return "".join(self._inline(s))

    def _inline(self, s):
        out, buf, i, n = [], [], 0, len(s)

        def solta():
            if buf:
                out.append(_esc("".join(buf)))
                buf.clear()
        while i < n:
            c = s[i]
            if c == "\\" and i + 1 < n and s[i + 1] in _PONTUACAO:
                buf.append(s[i + 1])
                i += 2
                continue
            if c == "`":
                j = s.find("`", i + 1)
                if j > i + 1:
                    solta()
                    out.append(f'<span style="font-family:Consolas;font-size:10pt">{_esc(s[i + 1:j])}</span>')
                    i = j + 1
                    continue
            delim = next((d for d in ("**", "~~", "==") if s.startswith(d, i)), None) or ("*" if c == "*" else None)
            if delim:
                j = _achar(s, delim, i + len(delim))
                if j is not None and j > i + len(delim) and not s[i + len(delim)].isspace():
                    solta()
                    dentro = self.inline(s[i + len(delim):j])
                    abre, fecha = {"**": ("<b>", "</b>"), "*": ("<i>", "</i>"), "~~": ("<del>", "</del>"),
                                   "==": (f'<span style="background-color:{paleta.REALCE}">', "</span>")}[delim]
                    out.append(abre + dentro + fecha)
                    i = j + len(delim)
                    continue
            if c == "!" and s.startswith("![", i) and _link(s, i + 1):
                raise ErroFormato("imagem precisa ficar sozinha numa linha: ![legenda](anexo:N)")
            if c == "[":
                lk = _link(s, i)
                if lk:
                    texto, url, fim = lk
                    solta()
                    out.append(self._a(texto, url))
                    i = fim
                    continue
            if c == "<":
                tg = self._tag_inline(s, i)
                if tg:
                    html, fim = tg
                    solta()
                    out.append(html)
                    i = fim
                    continue
                m = re.match(r"</?[A-Za-z][^>]*>", s[i:])
                if m:
                    self.aviso(f"tag fora da spec virou texto: {m.group(0)[:30]}")
            buf.append(c)
            i += 1
        solta()
        return out

    def _a(self, texto, url):
        dentro = self.inline(texto)
        u = url.strip()
        if u.startswith("pagina:"):
            if not self.resolver_pagina:
                raise ErroFormato("link pagina: não disponível aqui")
            href = self.resolver_pagina(u[len("pagina:"):])
            return f'<a href="{_esc_attr(href)}">{dentro}</a>'
        if re.match(r"^(https?://|onenote:)", u, re.I) and not re.search(r"[\s<>\"]", u):
            return f'<a href="{_esc_attr(u)}">{dentro}</a>'
        self.aviso(f"link ignorado (só https://, http://, onenote: ou pagina:<id>): {u[:50]}")
        return dentro

    def _tag_inline(self, s, i):
        m = re.match(r"<br\s*/?>", s[i:])
        if m:   # quebra de linha dentro do parágrafo (a leitura devolve <br> e o U+FFFC do OneNote assim)
            return "<br />", i + m.end()
        m = re.match(r"<(u|sup|sub)>", s[i:])
        if m:
            nome = m.group(1)
            fim = _fecho_tag(s, i + m.end(), nome)
            if fim is None:
                return None
            dentro = self.inline(s[i + m.end():fim])
            return f"<{nome}>{dentro}</{nome}>", fim + len(f"</{nome}>")
        m = re.match(r"<span\b([^>]*)>", s[i:])
        if m:
            fim = _fecho_tag(s, i + m.end(), "span")
            if fim is None:
                return None
            a = _attrs(m.group(1))
            for k in [k for k in a if k not in ("cor", "fundo", "fonte", "tamanho")]:
                self.aviso(f"atributo de <span> ignorado: {k}=")
            css = self.estilo(a, alinhar=False)
            dentro = self.inline(s[i + m.end():fim])
            html = f'<span style="{_esc_attr(css)}">{dentro}</span>' if css else dentro
            return html, fim + len("</span>")
        return None


def _achar(s, d, ini):
    """posição do delimitador de fechamento d (pula escape e código); None se não fecha"""
    k = ini
    while k < len(s):
        c = s[k]
        if c == "\\":
            k += 2
            continue
        if c == "`":
            j = s.find("`", k + 1)
            if j > k:
                k = j + 1
                continue
        if s.startswith(d, k) and not s[k - 1].isspace():
            if d == "*" and s.startswith("**", k):
                k += 2
                continue
            if d == "**" and s.startswith("***", k):
                return k + 1
            return k
        k += 1
    return None


def _link(s, i):
    """[texto](url) a partir de s[i] == '[' → (texto, url, fim) ou None"""
    if i >= len(s) or s[i] != "[":
        return None
    prof, k = 0, i
    while k < len(s):
        c = s[k]
        if c == "\\":
            k += 2
            continue
        if c == "[":
            prof += 1
        elif c == "]":
            prof -= 1
            if prof == 0:
                break
        k += 1
    else:
        return None
    if k + 1 >= len(s) or s[k + 1] != "(":
        return None
    # parênteses balanceados na URL (como no CommonMark): .../Python_(linguagem) não é cortado no 1º ")"
    prof = 0
    for j in range(k + 2, len(s)):
        if s[j] == "(":
            prof += 1
        elif s[j] == ")":
            if prof == 0:
                return s[i + 1:k], s[k + 2:j], j + 1
            prof -= 1
    return None


def _fecho_tag(s, ini, nome):
    prof, k = 1, ini
    abre, fecha = re.compile(r"<" + nome + r"\b[^>]*>"), f"</{nome}>"
    while k < len(s):
        if s[k] == "\\":
            k += 2
            continue
        if s.startswith(fecha, k):
            prof -= 1
            if prof == 0:
                return k
            k += len(fecha)
            continue
        m = abre.match(s, k)
        if m:
            prof += 1
            k = m.end()
            continue
        k += 1
    return None


def _inicia_lista(l):
    m = _ITEM.match(l)
    if not m:
        return False
    mk = m.group(2)
    return mk == "-" or bool(re.match(r"^\d{1,3}\.$", mk)) or mk[:-1] in _TIPO_OL


def _continua(mk, primeiro):
    """mk segue a lista cujo 1º marcador (no mesmo recuo) foi `primeiro`: mesmo tipo e mesma caixa
    (a. → b./c./…/aa.; A. → B.; i. → ii./iv.; 1. → 2.). "Ok." ou "Eu." depois de "a. b." é parágrafo"""
    if primeiro == "-" or mk == "-":
        return mk == primeiro
    b, pb = mk[:-1], primeiro[:-1]
    if pb.isdigit() or b.isdigit():
        return pb.isdigit() and b.isdigit()
    if pb in ("i", "I"):
        return bool(re.match(r"^[ivxlcdm]{1,6}$" if pb == "i" else r"^[IVXLCDM]{1,6}$", b))
    if pb not in ("a", "A"):
        return False
    letra = "[a-z]" if pb == "a" else "[A-Z]"
    return bool(re.match(rf"^({letra}|{pb}{letra})$", b))


def _separador_gfm(l):
    l = l.strip()
    return l.startswith("|") and bool(re.match(r"^\|(\s*:?-+:?\s*\|)+$", l))


def _celulas_gfm(l):
    l = l.strip()
    if l.startswith("|"):
        l = l[1:]
    if l.endswith("|") and not l.endswith("\\|"):
        l = l[:-1]
    celulas, atual, k = [], [], 0
    while k < len(l):
        if l[k] == "\\" and k + 1 < len(l):
            # \| é a barra literal da célula (também dentro de `código`, como no GFM); outro escape segue adiante
            atual.append("|" if l[k + 1] == "|" else l[k:k + 2])
            k += 2
            continue
        if l[k] == "|":
            celulas.append("".join(atual))
            atual = []
        else:
            atual.append(l[k])
        k += 1
    celulas.append("".join(atual))
    return celulas


def _so_paragrafo(l):
    """linha que vira <p> simples (não é outro bloco)"""
    return not (l.startswith(("#", ">", "|", "```", "<", "![")) or re.match(r"^-{3,}$", l)
                or _TAREFA.match(l) or _inicia_lista(l))


def _so_inline(l):
    l = l.strip()
    return _so_paragrafo(l) and not _BLOCO_ATTRS.search(l)


def escrever(texto, anexos=None, resolver_pagina=None, ids_existentes=(), fonte_padrao=None):
    """ONMD → Escrita(html do corpo, partes binárias, avisos). Erro orientador = ErroFormato (nada enviado)"""
    e = _Escritor(anexos, resolver_pagina, ids_existentes, fonte_padrao)
    html = e.blocos(sem_controle(texto, e.avisos))   # \x00–\x1f quebram o XHTML (o Graph daria 400 cego)
    partes = [(nome, mime, dados) for nome, (mime, dados) in e.partes.items()]
    for n in range(1, len(e.anexos) + 1):
        if n not in e.usados:
            e.aviso(f"anexo:{n} não foi citado no conteúdo e não foi enviado")
    return Escrita(html, partes, e.avisos, sorted(e.usados))
