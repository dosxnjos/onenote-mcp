# operações no OneNote com a lista permitida aplicada em TODAS: nada fora dela chega ao modelo
# índice de seções por bloco (caminho "Bloco/Grupo/.../Seção" → id), em cache por 60 s; antes de ler ou
# gravar, o nome ATUAL da seção (e do grupo) é conferido ao vivo, para renomear/mover não furar o bloqueio
# bloco compartilhado por outra conta só é visto percorrendo o bloco: /me/onenote/sections não garante incluí-lo
# dois blocos visíveis com o mesmo nome ficam FORA (ambíguo: o caminho não diria em qual gravar)
# v2: conteúdo em ONMD (formato/), sanitizador no HTML final, edição por trecho com o id gerado lido NA HORA
# (os ids mudam a cada update), diário local do antes, anexos só por parâmetro. Nenhuma tool apaga.
import html as _html
import re
import threading
import time
from collections import Counter
from datetime import datetime
from urllib.parse import quote as _quote_url

from . import arquivos as A
from . import diario as D
from . import permitidos as P
from .formato import escrita as E
from .formato import leitura as L
from .formato import ler_spec as _ler_spec
from .graph import ErroGraph, _texto_visivel, quote, tem_conteudo, validar_comandos
from .sanitizar import ID_PROPRIO, sanitizar, sem_controle

TTL = 60
MAX_SECOES_BUSCA = 20     # crítica §4: buscar em N seções custa N requisições (cota 120/min)
MAX_IMAGEM = 5 * 2**20
_RECURSO_ID = re.compile(r"^[0-9A-Za-z][0-9A-Za-z!\-]{0,199}$")
_EXIBIVEIS = {"image/png": "png", "image/jpeg": "jpeg", "image/gif": "gif"}


class ErroEdicao(ValueError):
    """pedido que não dá para cumprir; a mensagem orienta (nada foi enviado)"""


def _reaplicar_id(html, antigo, texto_lido, avisos):
    """repõe o data-id original no 1º elemento do HTML novo (o replace por id gerado perde o data-id). Roda ANTES
    do sanitizador (que confere o HTML final) e só quando a troca não mudou o id de propósito:
    - antigo fora do padrão (data-id de página de terceiro) → não reaplica, avisa (nunca vai cru para o HTML)
    - antigo on-xxx-N (forma: código, destaque, colunas, tabela, citação): novo da MESMA família vira on-xxx-N
      (no código com o sufixo de linguagem do novo); família diferente = a forma mudou, fica o novo
    - antigo do usuário: o novo trouxe data-id (troca de id ou de forma) → fica o novo; sem data-id → reaplica,
      salvo quando o {id=antigo} estava no texto lido e a troca o tirou"""
    if not antigo:
        return html
    if not ID_PROPRIO.match(antigo):
        avisos.append(f"data-id fora do padrão no bloco original não foi reaplicado: {antigo[:40]!r}")
        return html
    m = re.match(r"^<([a-z0-9]+)\b([^>]*?)(\s*/?)>", html)
    if not m:
        return html
    atual = re.search(r'\sdata-id="([^"]*)"', m.group(2))
    novo = atual.group(1) if atual else None
    if antigo.startswith("on-"):
        partes = antigo.split("-")
        if not novo or not novo.startswith(f"on-{partes[1]}-"):
            return html
        final = "-".join(partes[:3] + novo.split("-")[3:]) if partes[1] == "cod" else antigo
    else:
        if novo or re.search(r"(?<![\w-])id=" + re.escape(antigo) + r"(?=[\s}>])", texto_lido or ""):
            return html
        final = antigo
    attrs = re.sub(r'\sdata-id="[^"]*"', "", m.group(2))
    return f'<{m.group(1)} data-id="{final}"{attrs}{m.group(3)}>' + html[m.end():]


def _antes_de_lista(no):
    """bloco (não lista) seguido de <ul>/<ol>: o OneNote guarda o parágrafo grudado na lista seguinte e, ao
    regravá-lo, põe o novo depois dela (ARMADILHAS § Edição v2)"""
    if no.tag in ("ul", "ol") or no.pai is None:
        return False
    irmaos = [f for f in no.pai.elementos() if f.tag != "br"]
    i = next((k for k, f in enumerate(irmaos) if f is no), None)
    return i is not None and i + 1 < len(irmaos) and irmaos[i + 1].tag in ("ul", "ol")


def _ids_do_no(no):
    """todo data-id da subárvore (o bloco que vai ser trocado libera os próprios ids para o HTML novo)"""
    saida, pilha = set(), [no]
    while pilha:
        n = pilha.pop()
        if n.tag:
            d = n.attrs.get("data-id")
            if d:
                saida.add(d)
            pilha.extend(n.filhos)
    return saida


class _Anexos:
    """`anexos` como sequência preguiçosa: cada arquivo só é lido do disco quando o texto cita anexo:N"""

    def __init__(self, itens, carregar):
        self.itens, self.carregar, self.cache = list(itens), carregar, {}

    def __len__(self):
        return len(self.itens)

    def __getitem__(self, k):
        if not 0 <= k < len(self.itens):
            raise IndexError(k)
        if k not in self.cache:
            self.cache[k] = self.carregar(self.itens[k])
        return self.cache[k]


class OneNote:
    def __init__(self, graph, cfg):
        self.g = graph
        self.cfg = cfg
        self._indice = None
        self._blocos_ok = set()
        self.avisos = []
        self._quando = 0.0
        self._trava = threading.Lock()

    # ---------- índice ----------
    def _todos_blocos(self):
        blocos = self.g.get_todos("/me/onenote/notebooks?$select=id,displayName,isShared,userRole")
        vistos = {b["id"] for b in blocos}
        for nb in self.cfg.blocos_extra:
            if nb not in vistos:
                try:
                    blocos.append(self.g.get(f"/me/onenote/notebooks/{quote(nb)}?$select=id,displayName,isShared,userRole"))
                except ErroGraph as e:   # sem isto o erro não diz QUAL id de blocos_extra falhou
                    raise ErroGraph(e.status, f"o bloco {nb} de [lista].blocos_extra não abriu (id errado ou sem "
                                              f"acesso): {e}", e.codigo) from None
                vistos.add(nb)
        return blocos

    def _blocos_visiveis(self):
        blocos = [b for b in self._todos_blocos()
                  if P.bloco_visivel(b["displayName"], self.cfg.permitidos, self.cfg.bloqueados)]
        nomes = Counter(P.normalizar(b["displayName"]) for b in blocos)
        dup = [b for b in blocos if nomes[P.normalizar(b["displayName"])] > 1]
        self.avisos = [f"bloco com nome repetido ficou fora (ambíguo): {b['displayName']}" for b in dup][:1]
        return [b for b in blocos if nomes[P.normalizar(b["displayName"])] == 1]

    def _percorrer(self, base, prefixo, saida, profundidade=0):
        for s in self.g.get_todos(f"{base}/sections?$select=id,displayName"):
            saida[s["id"]] = f"{prefixo}/{s['displayName']}"
        if profundidade > 8:
            return
        for gr in self.g.get_todos(f"{base}/sectionGroups?$select=id,displayName"):
            caminho = f"{prefixo}/{gr['displayName']}"
            if P.bloqueado(caminho, self.cfg.bloqueados):
                continue
            self._percorrer(f"/me/onenote/sectionGroups/{quote(gr['id'])}", caminho, saida, profundidade + 1)

    def indice(self, forcar=False):
        with self._trava:
            if forcar or self._indice is None or time.monotonic() - self._quando > TTL:
                idx, ok = {}, set()
                for b in self._blocos_visiveis():
                    ok.add(b["id"])
                    self._percorrer(f"/me/onenote/notebooks/{quote(b['id'])}", b["displayName"], idx)
                self._indice = {sid: c for sid, c in idx.items()
                                if P.permitido(c, self.cfg.permitidos, self.cfg.bloqueados)}
                self._blocos_ok = ok
                self._quando = time.monotonic()
            return self._indice

    def _conferir_ao_vivo(self, sid, caminho):
        """nome atual da seção e do grupo pai, e o bloco certo; o índice pode estar velho"""
        s = self.g.get(f"/me/onenote/sections/{quote(sid)}?$select=id,displayName"
                       "&$expand=parentNotebook($select=id),parentSectionGroup($select=id,displayName)")
        nomes = [s.get("displayName", ""), (s.get("parentSectionGroup") or {}).get("displayName", "")]
        nb = (s.get("parentNotebook") or {}).get("id")
        if any(P.bloqueado(n, self.cfg.bloqueados) for n in nomes if n) or (nb and nb not in self._blocos_ok):
            self.indice(forcar=True)
            raise P.ForaDaLista(f"seção fora da lista permitida: {caminho}")
        if nomes[0] and P.normalizar(nomes[0]) != P.normalizar(caminho.rsplit("/", 1)[-1]):
            novo = self.indice(forcar=True).get(sid)
            if not novo:
                raise P.ForaDaLista(f"seção fora da lista permitida: {caminho}")
            return novo
        return caminho

    def _secao(self, secao):
        """aceita id ou caminho completo; devolve (id, caminho) conferido ao vivo, ou ForaDaLista"""
        alvo = "/".join(P._partes(secao))
        for forcar in (False, True):
            idx = self.indice(forcar=forcar)
            if secao in idx:
                return secao, self._conferir_ao_vivo(secao, idx[secao])
            for sid, c in idx.items():
                if "/".join(P._partes(c)) == alvo:
                    return sid, self._conferir_ao_vivo(sid, c)
        raise P.ForaDaLista(f"seção fora da lista permitida ou inexistente: {secao}")

    def _secao_da_pagina(self, pagina_id):
        pg = self.g.get(f"/me/onenote/pages/{quote(pagina_id)}"
                        "?$select=id,title,links&$expand=parentSection($select=id)")
        sid = (pg.get("parentSection") or {}).get("id")
        for forcar in (False, True):
            idx = self.indice(forcar=forcar)
            if sid in idx:
                return pg, self._conferir_ao_vivo(sid, idx[sid])
        raise P.ForaDaLista(f"página fora da lista permitida: {pagina_id}")

    # ---------- tools ----------
    def listar_blocos(self):
        r = [{"nome": b["displayName"], "compartilhado": b.get("isShared"), "papel": b.get("userRole")}
             for b in self._blocos_visiveis()]
        return r

    def listar_secoes(self, bloco=None):
        itens = sorted(self.indice().items(), key=lambda x: P.normalizar(x[1]))
        if bloco:
            pref = P._partes(bloco)
            itens = [i for i in itens if P._partes(i[1])[: len(pref)] == pref]
        return [{"id": sid, "caminho": c} for sid, c in itens]

    def listar_paginas(self, secao, com_nivel=False):
        sid, caminho = self._secao(secao)
        # sem $top: o nextLink pagina de 20 em 20 até o fim; a ordem padrão já é a última alteração primeiro
        extra = "&pagelevel=true" if com_nivel else ""
        pgs = self.g.get_todos(f"/me/onenote/sections/{quote(sid)}/pages?$select=id,title,lastModifiedDateTime{extra}")
        saida = []
        for p in pgs:
            item = {"id": p["id"], "titulo": p.get("title"), "alterada": p.get("lastModifiedDateTime")}
            if com_nivel:
                item["nivel"] = p.get("level", 0)
            saida.append(item)
        return {"secao": caminho, "paginas": saida}

    def buscar_paginas(self, texto, bloco="", limite=20):
        """título contém `texto` (sem diferenciar maiúsculas), só nas seções da lista; busca no corpo não existe
        no Graph desde 05/05/2024. Cada seção custa 2 requisições (conferência ao vivo + busca)"""
        texto = (texto or "").strip()
        if not 1 <= len(texto) <= 100:
            raise ErroEdicao("texto da busca entre 1 e 100 caracteres")
        limite = max(1, min(int(limite or 20), 100))
        secoes = self.listar_secoes(bloco or None)
        if len(secoes) > MAX_SECOES_BUSCA:
            raise ErroEdicao(f"{len(secoes)} seções na busca (máximo {MAX_SECOES_BUSCA}): restrinja com `bloco` "
                             "(começo do caminho, ex.: \"Bloco/Grupo\")")
        filtro = _quote_url(f"contains(tolower(title),'{texto.lower().replace(chr(39), chr(39) * 2)}')", safe="(),")
        achadas, avisos = [], []
        for s in secoes:
            try:
                caminho = self._conferir_ao_vivo(s["id"], s["caminho"])
            except P.ForaDaLista:
                avisos.append(f"seção saiu da lista durante a busca: {s['caminho']}")
                continue
            r = self.g.get(f"/me/onenote/sections/{quote(s['id'])}/pages?$filter={filtro}"
                           f"&$select=id,title,lastModifiedDateTime&$top={limite}")
            for p in r.get("value", []):
                achadas.append({"id": p["id"], "titulo": p.get("title"), "secao": caminho,
                                "alterada": p.get("lastModifiedDateTime")})
            if len(achadas) >= limite:
                break
        return {"paginas": achadas[:limite], "avisos": avisos}

    def ler_spec(self):
        return _ler_spec()

    # ---------- leitura ----------
    def _conteudo(self, pagina_id):
        return self.g.get_html(f"/me/onenote/pages/{quote(pagina_id)}/content?includeIDs=true")

    def ler_pagina(self, pagina_id, incluir_ids=False):
        pg, caminho = self._secao_da_pagina(pagina_id)
        lt = L.ler(self._conteudo(pagina_id), incluir_ids=incluir_ids)
        r = {"titulo": pg.get("title"), "secao": caminho, "conteudo": lt.onmd, "avisos": lt.avisos}
        if lt.fonte:
            r["fonte_da_pagina"] = lt.fonte
        return r

    def ver_imagem(self, pagina_id, recurso_id):
        """bytes da imagem SÓ se o recurso é um <img> daquela página permitida; nunca segue URL"""
        rid = (recurso_id or "").strip().removeprefix("recurso:")
        if not _RECURSO_ID.match(rid):
            raise ErroEdicao("recurso_id inválido: use o id que aparece em recurso:<id> no ler_pagina")
        self._secao_da_pagina(pagina_id)
        raiz = L.arvore(self._conteudo(pagina_id))
        ids = set()

        def coletar(no):
            if no.tag == "img":
                for k in ("src", "data-fullres-src"):
                    m = L.RECURSO.search(no.attrs.get(k, ""))
                    if m:
                        ids.add(m.group(1))
            for f in no.filhos:
                coletar(f)
        coletar(raiz)
        if rid not in ids:
            raise ErroEdicao("esse recurso não é uma imagem desta página")
        dados = self.g.get_bytes(f"/me/onenote/resources/{quote(rid)}/content")
        if len(dados) > MAX_IMAGEM:
            raise ErroEdicao(f"imagem acima de {MAX_IMAGEM // 2**20} MB")
        tipo = A.tipo_imagem(dados)
        if tipo not in _EXIBIVEIS:
            raise ErroEdicao(f"formato não exibível aqui ({tipo or 'desconhecido'}); só PNG, JPEG e GIF")
        return dados, _EXIBIVEIS[tipo]

    # ---------- escrita ----------
    def _resolver_pagina(self, pagina_id):
        """link pagina:<id> → link onenote: da página, só se ela está na lista permitida"""
        pg, _ = self._secao_da_pagina(pagina_id.strip())
        links = pg.get("links") or {}
        href = (links.get("oneNoteClientUrl") or {}).get("href") or (links.get("oneNoteWebUrl") or {}).get("href")
        if not href or not href.startswith(("onenote:", "https://")):
            raise ErroEdicao(f"a página {pagina_id} não devolveu link")
        return href

    def _preparar(self, conteudo, anexos=None, ids_existentes=(), fonte=None, permitir_anexos=True,
                  id_original=None, texto_lido=""):
        """ONMD → (html limpo, partes, avisos). Erro de formato/arquivo antes de qualquer envio.
        O data-id original (replace) entra ANTES do sanitizador: o HTML que sai é sempre o que ele conferiu"""
        if anexos and not permitir_anexos:
            raise ErroEdicao("esta tool não recebe anexos")
        if len(anexos or []) > A.MAX_PARTES:
            raise ErroEdicao(f"{len(anexos)} anexos (máximo {A.MAX_PARTES} por chamada): mande só os que o texto "
                             "cita e use acrescentar para o resto")
        carregados = _Anexos(anexos or [], lambda x: A.carregar(x, self.cfg.pastas_arquivos, self.cfg.max_mb,
                                                                  (self.cfg.cache_dir,)))
        esc = E.escrever(conteudo, carregados, self._resolver_pagina, ids_existentes, fonte)
        nomes = [n for n, _, _ in esc.partes]
        extra = []
        bruto = _reaplicar_id(esc.html, id_original, texto_lido, extra)
        html, av = sanitizar(bruto, nomes)
        A.conferir_limites(esc.partes, self.cfg.max_mb, html)
        if not html.strip():
            raise ErroEdicao("conteúdo vazio depois da conversão: nada a enviar")
        avisos = esc.avisos + extra + av
        for n in esc.anexos_usados:
            avisos.append(f"arquivo enviado: {carregados[n - 1].resumo()}")
        return html, esc.partes, avisos

    def criar_pagina(self, secao, titulo, conteudo, anexos=None, criado_em=None):
        sid, caminho = self._secao(secao)
        corpo, partes, avisos = self._preparar(conteudo, anexos)
        meta = ""
        if criado_em:
            try:
                quando = datetime.fromisoformat(str(criado_em).strip())
            except ValueError:
                raise ErroEdicao("criado_em inválido: use AAAA-MM-DD ou AAAA-MM-DDTHH:MM") from None
            meta = f'<meta name="created" content="{quando.isoformat()}" />'
        t = _html.escape(sem_controle(titulo, avisos).strip() or "Sem título", quote=False)
        pagina = (f"<!DOCTYPE html><html><head><title>{t}</title>{meta}</head>"
                  f"<body>{corpo}</body></html>")
        r = self.g.post_pagina(sid, pagina, partes or None)
        return {"id": r.get("id"), "titulo": r.get("title"), "secao": caminho,
                "link": ((r.get("links") or {}).get("oneNoteWebUrl") or {}).get("href"), "avisos": avisos}

    def acrescentar(self, pagina_id, conteudo, onde="fim", anexos=None):
        pg, caminho = self._secao_da_pagina(pagina_id)
        lt = L.ler(self._conteudo(pagina_id))
        onde = (onde or "fim").strip()
        if onde == "fim":
            # "body" mira a PRIMEIRA div; o fim da página é a última div filha do body (pelo id gerado)
            cmd = {"target": lt.ultima_div or "body", "action": "append"}
        elif onde == "inicio":
            cmd = {"target": "body", "action": "prepend"}
        elif onde.startswith("#") and onde[1:] in lt.secoes:
            self._id_unico(lt, onde[1:])
            cmd = {"target": onde, "action": "append"}
        else:
            nomes = ", ".join("#" + s for s in lt.secoes) or "nenhuma"
            raise ErroEdicao(f"onde inválido: {onde!r}. Use fim, inicio ou #id de uma <secao> (nesta página: {nomes})")
        html, partes, avisos = self._preparar(conteudo, anexos, lt.data_ids, lt.fonte)
        cmd["content"] = html
        self.g.patch_conteudo(pagina_id, [cmd], partes or None)
        return {"ok": True, "titulo": pg.get("title"), "secao": caminho, "avisos": avisos}

    @staticmethod
    def _id_unico(lt, ident):
        """alvo #id só com id único na página: com dois iguais o Graph escolhe um sem dizer qual (crítica §1.4)"""
        if ident in lt.repetidos:
            raise ErroEdicao(f"o id #{ident} aparece em mais de um lugar da página: o alvo ficaria ambíguo. "
                             "Use outra âncora (trecho único) ou acrescente no fim")

    @staticmethod
    def _achar(lt, trecho, tipos=None):
        """blocos cujo ONMD contém o trecho: [(bloco, ocorrências)]; tenta sem ids e depois com ids"""
        for campo in ("onmd", "onmd_ids"):
            achados = [(b, getattr(b, campo).count(trecho), campo) for b in lt.blocos
                       if (tipos is None or b.tipo in tipos) and trecho in getattr(b, campo)]
            if achados:
                return achados
        return []

    @staticmethod
    def _contextos(achados, trecho):
        saida = []
        for b, _, campo in achados[:5]:
            txt = getattr(b, campo)
            k = txt.find(trecho)
            saida.append("…" + txt[max(0, k - 30): k + len(trecho) + 30].replace("\n", " ") + "…")
        return " | ".join(saida)

    def _bloco_unico(self, lt, trecho, tipos=None, nome="trecho"):
        if not trecho or not trecho.strip():
            raise ErroEdicao(f"{nome} vazio")
        if trecho.startswith("#") and " " not in trecho.strip():
            alvo = trecho.strip()[1:]
            achados = [b for b in lt.blocos if b.data_id == alvo and (tipos is None or b.tipo in tipos)]
            if len(achados) == 1:
                return achados[0]
            raise ErroEdicao(f"nenhum bloco único com id {trecho!r}")
        achados = self._achar(lt, trecho, tipos)
        if not achados:
            if tipos and self._achar(lt, trecho):
                raise ErroEdicao(f"{nome} não encontrada entre os blocos desse tipo (o trecho está em outro tipo "
                                 f"de bloco): {trecho[:80]!r}")
            if trecho in lt.onmd or trecho in L.juntar(lt.itens, True):
                raise ErroEdicao(f"o {nome} atravessa mais de um bloco: use um trecho de um bloco só")
            raise ErroEdicao(f"{nome} não encontrado (copie exatamente do ler_pagina): {trecho[:80]!r}")
        if len(achados) > 1 or achados[0][1] > 1:
            raise ErroEdicao(f"{nome} ambíguo, aparece {sum(a[1] for a in achados)} vezes: "
                             f"{self._contextos(achados, trecho)}. Use um trecho maior")
        return achados[0][0]

    def inserir(self, pagina_id, ancora, conteudo, posicao="depois", anexos=None):
        pos = {"depois": "after", "antes": "before"}.get((posicao or "depois").strip())
        if not pos:
            raise ErroEdicao("posicao: antes ou depois")
        pg, caminho = self._secao_da_pagina(pagina_id)
        lt = L.ler(self._conteudo(pagina_id))
        a = (ancora or "").strip()
        if a.startswith("#") and a[1:] in lt.secoes:
            self._id_unico(lt, a[1:])
            alvo = a
        else:
            b = self._bloco_unico(lt, ancora, nome="ancora")
            if not b.id_gerado:
                raise ErroEdicao("esse bloco não tem id editável: escolha outro como âncora")
            alvo = b.id_gerado
            if pos == "after" and _antes_de_lista(b.no):
                raise ErroEdicao("esse bloco vem logo antes de uma lista, e o OneNote põe o que entra 'depois' dele "
                                 "abaixo da lista (medido em 15/10/2026): use posicao=antes com o bloco seguinte "
                                 "à lista, ou a própria lista como âncora")
        html, partes, avisos = self._preparar(conteudo, anexos, lt.data_ids, lt.fonte)
        self.g.patch_conteudo(pagina_id, [{"target": alvo, "action": "insert", "position": pos, "content": html}],
                              partes or None)
        return {"ok": True, "titulo": pg.get("title"), "secao": caminho, "avisos": avisos}

    def _trocar_blocos(self, pagina_id, lt, novos, acao):
        """novos = [(bloco, onmd novo, onmd lido em que a troca foi feita)] → 1 PATCH com todos os replace
        (atômico: provas-v2). Ordem: recusas → conversão → validação local do PATCH → diário → envio
        (o diário nunca guarda troca que a validação recusaria)"""
        cmds, itens, avisos = [], [], []
        for b, onmd, lido in novos:
            if not b.id_gerado:
                raise ErroEdicao("bloco sem id editável (texto solto na página): edite outro bloco")
            if b.perdas:
                raise ErroEdicao("este bloco tem conteúdo que o ONMD não representa (imagem, vídeo, tabela ou "
                                 "etiqueta dentro do texto ou da célula; ver avisos do ler_pagina): regravá-lo "
                                 "apagaria isso. Edite outro bloco ou use inserir/acrescentar")
            if not onmd.strip():
                raise ErroEdicao("a troca esvaziaria um bloco inteiro: para remover texto, troque por outro texto")
            if _antes_de_lista(b.no):
                raise ErroEdicao("este bloco (parágrafo, título ou tarefa) vem logo antes de uma lista, e o OneNote "
                                 "o move para depois da lista quando ele é regravado (medido em 15/10/2026, também "
                                 "regravando a lista junto): deixe-o como está e edite outro bloco")
            livres = {i for i in _ids_do_no(b.no) if not i.startswith("on-")}   # os ids do próprio bloco voltam
            html, partes, av = self._preparar(onmd, None, lt.data_ids - livres, lt.fonte, permitir_anexos=False,
                                              id_original=b.data_id, texto_lido=lido)
            if partes:
                raise ErroEdicao("editar não envia arquivo: use inserir ou acrescentar com anexos")
            if not tem_conteudo(html):
                raise ErroEdicao("a troca esvaziaria um bloco inteiro (sobra só espaço, caractere invisível ou "
                                 "tabela vazia): para remover texto, troque por outro texto")
            avisos += [x for x in av if x not in avisos]
            cmds.append({"target": b.id_gerado, "action": "replace", "content": html})
            itens.append({"alvo": b.id_gerado, "antes": L.serializar(b.no), "depois": html})
        validar_comandos(cmds)
        D.gravar(self.cfg.historico_dir, pagina_id, acao, itens)
        self.g.patch_conteudo(pagina_id, cmds)
        return avisos

    def editar(self, pagina_id, trocas):
        if not isinstance(trocas, list) or not trocas:
            raise ErroEdicao("trocas: lista de {antigo, novo, todas}")
        if len(trocas) > 50:
            raise ErroEdicao("no máximo 50 trocas por chamada")
        pg, caminho = self._secao_da_pagina(pagina_id)
        lt = L.ler(self._conteudo(pagina_id))   # ids gerados lidos AGORA: mudam a cada update
        por_bloco = {}   # índice do bloco → [(antigo, novo, todas, campo onde foi achado)]
        avisos = []
        for t in trocas:
            antigo, novo = t.get("antigo"), t.get("novo")
            todas = bool(t.get("todas", False))
            if not isinstance(antigo, str) or not antigo:
                raise ErroEdicao("cada troca precisa de `antigo` (texto não vazio)")
            if not isinstance(novo, str):
                raise ErroEdicao("cada troca precisa de `novo` (texto)")
            if antigo == novo:
                avisos.append(f"troca ignorada (antigo igual ao novo): {antigo[:40]!r}")
                continue
            achados = self._achar(lt, antigo)
            if not achados:
                if antigo in lt.onmd or antigo in L.juntar(lt.itens, True):
                    raise ErroEdicao(f"o trecho atravessa mais de um bloco, edite um bloco por vez: {antigo[:60]!r}")
                raise ErroEdicao(f"trecho não encontrado (copie exatamente do ler_pagina): {antigo[:80]!r}")
            if not todas and (len(achados) > 1 or achados[0][1] > 1):
                raise ErroEdicao(f"trecho ambíguo, aparece {sum(a[1] for a in achados)} vezes: "
                                 f"{self._contextos(achados, antigo)}. Use um trecho maior ou todas=true")
            for b, _, campo in achados:
                por_bloco.setdefault(lt.blocos.index(b), []).append((antigo, novo, todas, campo))
        if not por_bloco:
            return {"ok": True, "titulo": pg.get("title"), "secao": caminho, "blocos": 0, "avisos": avisos}
        novos = [self._aplicar_trocas(lt.blocos[k], por_bloco[k], avisos) for k in sorted(por_bloco)]
        avisos += self._trocar_blocos(pagina_id, lt, novos, "editar")
        return {"ok": True, "titulo": pg.get("title"), "secao": caminho, "blocos": len(novos), "avisos": avisos}

    @staticmethod
    def _aplicar_trocas(b, trocas, avisos):
        """todas as trocas de um bloco valem sobre o texto LIDO (posições calculadas antes de trocar: a 2ª troca
        nunca pega o texto que a 1ª criou; trechos sobrepostos = erro). O texto editado é o ONMD COM ids
        (onmd_ids), para o data-id de item de lista e de célula voltar no HTML novo; se um trecho achado sem ids
        encosta num {id=…} (contagem difere), cai para o ONMD sem ids e avisa"""
        if all(b.onmd_ids.count(a) == getattr(b, campo).count(a) for a, _, _, campo in trocas):
            lido = b.onmd_ids
        elif all(campo == "onmd" for _, _, _, campo in trocas):
            lido = b.onmd
            avisos.append("um trecho encosta num {id=…} interno do bloco: ids de item/célula podem se perder "
                          "(para mantê-los, copie o trecho do ler_pagina com incluir_ids=true)")
        else:
            raise ErroEdicao("trocas em conflito no mesmo bloco (umas com {id=…}, outras sem): copie todos os "
                             "trechos do ler_pagina com incluir_ids=true")
        trechos = []
        for antigo, novo, todas, _ in trocas:
            ini, achou = 0, []
            while (j := lido.find(antigo, ini)) >= 0:
                achou.append(j)
                ini = j + len(antigo)
            trechos += [(j, j + len(antigo), novo) for j in (achou if todas else achou[:1])]
        trechos.sort()
        for (_, fim, _), (ini, _, _) in zip(trechos, trechos[1:]):
            if ini < fim:
                raise ErroEdicao("trocas em conflito no mesmo bloco: os trechos se sobrepõem. Junte numa troca só")
        txt = lido
        for ini, fim, novo in reversed(trechos):
            txt = txt[:ini] + novo + txt[fim:]
        return b, txt, lido

    def marcar_tarefa(self, pagina_id, tarefa, feito=True):
        pg, caminho = self._secao_da_pagina(pagina_id)
        lt = L.ler(self._conteudo(pagina_id))
        b = self._bloco_unico(lt, tarefa, tipos={"tarefa"}, nome="tarefa")
        txt = b.onmd_ids   # com o {id=…}: o data-id da tarefa volta no HTML novo
        marcada = txt.startswith("- [x] ")
        if marcada == bool(feito):
            return {"ok": True, "titulo": pg.get("title"), "secao": caminho,
                    "avisos": [f"a tarefa já estava {'marcada' if feito else 'desmarcada'}: nada enviado"]}
        novo = ("- [x] " if feito else "- [ ] ") + txt[6:]
        avisos = self._trocar_blocos(pagina_id, lt, [(b, novo, txt)], "marcar_tarefa")
        return {"ok": True, "titulo": pg.get("title"), "secao": caminho, "avisos": avisos}

    def renomear_pagina(self, pagina_id, titulo):
        t = sem_controle(re.sub(r"[\r\n\t]+", " ", titulo or "")).strip()
        if not _texto_visivel(t):   # só espaço ou invisível (U+200B, U+FEFF…) também é vazio
            raise ErroEdicao("título vazio recusado")
        if len(t) > 255:
            raise ErroEdicao("título com mais de 255 caracteres")
        pg, caminho = self._secao_da_pagina(pagina_id)
        cmds = [{"target": "title", "action": "replace", "content": _html.escape(t, quote=False)}]
        validar_comandos(cmds)   # antes do diário: o diário não guarda troca que não sai
        D.gravar(self.cfg.historico_dir, pagina_id, "renomear_pagina",
                 [{"alvo": "title", "antes": pg.get("title") or "", "depois": t}])
        self.g.patch_conteudo(pagina_id, cmds)
        return {"ok": True, "titulo": t, "titulo_antigo": pg.get("title"), "secao": caminho, "avisos": []}
