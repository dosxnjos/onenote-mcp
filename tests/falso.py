# Graph falso (sem rede): imita um bloco compartilhado (com seção de senhas) e um bloco pessoal
# as páginas guardam o HTML "como o OneNote devolve" (simulador.py); cada PATCH é validado pela MESMA função
# do cliente real (graph.validar_comandos), aplicado na árvore e TROCA o guid de todos os ids gerados
# (os ids mudam a cada update: quem usa id velho recebe 400, como no Graph)
import json
import uuid

from onenote_mcp.formato.escrita import escrever
from onenote_mcp.formato.leitura import achar, arvore, serializar
from onenote_mcp.graph import ErroGraph, validar_comandos
from simulador import Simulador

BLOCO = "Bloco Compartilhado"
SECOES = {"S-SENHA": "Senhas", "S-COMO": "Como Fazer", "S-NOTAS": "Notas", "S-RASC": "Rascunhos"}
PAI = {"S-SENHA": None, "S-COMO": None, "S-NOTAS": "Grupo", "S-RASC": "Grupo"}
G0 = "00000000-0000-4000-8000-000000000000"   # guid "guardado"; sai trocado pela versão


def pagina_de(onmd, titulo="t"):
    return Simulador(guid=G0).pagina(escrever(onmd).html, titulo)


class GraphFalso:
    def __init__(self, blocos=None, paginas=None):
        self.chamadas = []
        self.nomes = dict(SECOES)
        self.blocos = blocos or [
            {"id": "NB1", "displayName": BLOCO, "isShared": True, "userRole": "Reader"},
            {"id": "NB2", "displayName": "Bloco Pessoal", "isShared": False, "userRole": "Owner"},
        ]
        self.secao_de = {"P1": "S-NOTAS", "PSENHA": "S-SENHA"}
        self.html = {"P1": pagina_de("# Perguntas\n\n**1** \\- verba", "Vitrine"),
                     "PSENHA": pagina_de("segredo", "Senhas")}
        self.html.update(paginas or {})
        for p in paginas or {}:
            self.secao_de.setdefault(p, "S-NOTAS")
        self.versao = 0
        self.recursos = {}
        self.n = 5000

    # ---- ids que mudam a cada update ----
    def _guid(self):
        return str(uuid.UUID(int=self.versao + 1))

    def _saida(self, pid):
        return self.html[pid].replace(G0, self._guid())

    def _lista(self, caminho):
        c = caminho.split("?")[0]
        if c == "/me/onenote/notebooks":
            return self.blocos
        if c.endswith("/NB1/sections"):
            return [{"id": i, "displayName": self.nomes[i]} for i in ("S-SENHA", "S-COMO")]
        if c.endswith("/NB1/sectionGroups"):
            return [{"id": "G-GRUPO", "displayName": "Grupo"}]
        if c.endswith("/G-GRUPO/sections"):
            return [{"id": i, "displayName": self.nomes[i]} for i in ("S-NOTAS", "S-RASC")]
        if c.endswith("/S-NOTAS/pages"):
            return [{"id": "P1", "title": "Vitrine", "lastModifiedDateTime": "2026-10-15", "level": 0}]
        return []

    def get_todos(self, caminho):
        self.chamadas.append(("GET", caminho))
        return self._lista(caminho)

    def get(self, caminho):
        self.chamadas.append(("GET", caminho))
        c = caminho.split("?")[0]
        if c.startswith("/me/onenote/sections/") and c.endswith("/pages"):
            return {"value": self._lista(caminho)}
        if c.startswith("/me/onenote/sections/"):
            sid = c.rsplit("/", 1)[-1]
            g = PAI[sid]
            return {"id": sid, "displayName": self.nomes[sid], "parentNotebook": {"id": "NB1"},
                    "parentSectionGroup": {"id": "G-GRUPO", "displayName": g} if g else None}
        pid = c.rsplit("/", 1)[-1]
        return {"id": pid, "title": "t", "parentSection": {"id": self.secao_de.get(pid)},
                "links": {"oneNoteClientUrl": {"href": f"onenote:https://d.docs.live.net/{pid}"},
                          "oneNoteWebUrl": {"href": f"https://onedrive.live.com/{pid}"}}}

    def get_html(self, caminho):
        self.chamadas.append(("GET", caminho))
        pid = caminho.split("/pages/")[1].split("/")[0]
        return self._saida(pid)

    def get_bytes(self, caminho):
        self.chamadas.append(("GET", caminho))
        rid = caminho.split("/resources/")[1].split("/")[0]
        return self.recursos[rid]

    def post_pagina(self, secao_id, html, partes=None):
        self.chamadas.append(("POST", f"/me/onenote/sections/{secao_id}/pages", html, partes))
        return {"id": "NOVA", "title": "x", "links": {"oneNoteWebUrl": {"href": "https://exemplo"}}}

    # ---- PATCH aplicado na árvore ----
    def patch_conteudo(self, pagina_id, comandos, partes=None):
        validar_comandos(comandos)
        self.chamadas.append(("PATCH", f"/me/onenote/pages/{pagina_id}/content", json.loads(json.dumps(comandos)),
                              partes))
        raiz = arvore(self.html[pagina_id])
        g = self._guid()
        for c in comandos:
            alvo = c["target"]
            if alvo == "title":
                t = achar(raiz, "title")
                t.filhos = [type(t)(texto=c["content"], pai=t)]
                continue
            if alvo == "body":
                no = next(d for d in achar(raiz, "body").filhos if d.tag == "div")
            elif alvo.startswith("#"):
                no = _por(raiz, lambda n: n.attrs.get("data-id") == alvo[1:])
            else:
                if g not in alvo:
                    raise ErroGraph(400, "The specified target was not found (id velho)", "20120")
                no = _por(raiz, lambda n: n.attrs.get("id") == alvo.replace(g, G0))
            if no is None:
                raise ErroGraph(400, "The specified target was not found", "20120")
            self.n += 100
            novos = Simulador(guid=G0, inicio=self.n).nos(c["content"])
            pos = c.get("position", "after")
            if c["action"] in ("append", "prepend"):
                if c["action"] == "prepend" or pos == "before":
                    no.filhos[0:0] = novos
                else:
                    no.filhos.extend(novos)
            else:
                irmaos = no.pai.filhos
                k = irmaos.index(no)
                if c["action"] == "replace":
                    irmaos[k:k + 1] = novos
                elif pos == "before":
                    irmaos[k:k] = novos
                else:
                    irmaos[k + 1:k + 1] = novos
            for x in novos:
                x.pai = no if c["action"] in ("append", "prepend") else no.pai
        self.html[pagina_id] = "".join(serializar(f) for f in raiz.filhos)
        self.versao += 1
        return {}


def _por(no, cond):
    if no.tag and cond(no):
        return no
    for f in no.filhos:
        r = _por(f, cond)
        if r:
            return r
    return None
