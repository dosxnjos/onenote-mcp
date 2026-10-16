# cliente HTTP mínimo do Microsoft Graph (stdlib): GET com paginação, POST de página, PATCH de conteúdo
# só fala com https://graph.microsoft.com e não segue redirecionamento (o Bearer não sai para outro host)
# 429 (e 503 só em GET): espera o Retry-After (segundos ou data HTTP) e tenta de novo, até 3 vezes
# NENHUM DELETE: o cliente não tem o método, e `_req` só aceita GET/POST/PATCH em rotas da lista abaixo
# PATCH só por `patch_conteudo`, que valida cada comando: action ∈ {append, insert, prepend, replace}
# (o Graph aceita "delete" no PatchContentCommand: aqui ele não passa), alvo por regex, conteúdo não vazio
# "vazio" = sem texto VISÍVEL (U+200B, &#8203;, tabela sem texto também contam como vazio) e sem img/object
# cota do OneNote: 120 req/min e 5 simultâneas (throttling-limits); o 429 vem sem Retry-After
import email.utils
import html as _html
import json
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from collections import deque
from datetime import datetime, timezone
from urllib.parse import quote as _quote
from urllib.parse import urlsplit

BASE = "https://graph.microsoft.com/v1.0"
HOST = "graph.microsoft.com"
POR_MINUTO = 120
SIMULTANEAS = 5

# rotas permitidas, por método (caminho sem a base; a forma absoluta do nextLink também passa, depois do host)
_ROTAS = {
    "GET": re.compile(r"^/(me|users/[^/]+|users\('[^']+'\))/onenote/"),
    "POST": re.compile(r"^/me/onenote/sections/[^/?]+/pages$"),
    "PATCH": re.compile(r"^/me/onenote/pages/[^/?]+/content$"),
}
ACOES = {"append", "insert", "prepend", "replace"}
POSICOES = {"before", "after"}
_GUID = r"\{[0-9a-fA-F-]{36}\}\{\d+\}"
# id gerado (div aninhada tem id composto: "div:{g}{143}:{g}{27}", provas-v2), #data-id próprio, title ou body
ALVO = re.compile(r"^(title|body|#[A-Za-z0-9][A-Za-z0-9_-]{0,47}|(p|div|table|img|object|ol|ul|li|h[1-6]):"
                  + _GUID + r"(:" + _GUID + r")*)$")


class ErroGraph(Exception):
    def __init__(self, status, mensagem, codigo=""):
        super().__init__(f"Graph {status}: {mensagem}")
        self.status = status
        self.codigo = str(codigo or "")


class _SemRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_SemRedirect)


def quote(x):
    # ids do OneNote têm "!" (ex.: 0-ABC!s123): mantém legível, escapa o resto
    return _quote(str(x), safe="!-")


def _espera(valor, tentativa):
    if valor:
        try:
            return max(0.0, float(valor))
        except ValueError:
            try:
                quando = email.utils.parsedate_to_datetime(valor)
                return max(0.0, (quando - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError):
                pass
    return float(2 ** tentativa)


# invisíveis: espaço de qualquer tipo, formatação (U+200B, U+FEFF, U+2060, U+00AD), controle e marca combinante
_INVISIVEIS = {"Cf", "Cc", "Zs", "Zl", "Zp", "Mn", "Me"}


def _texto_visivel(html):
    """texto que aparece na página: sem tags, entidades decodificadas (&#8203; também), sem invisíveis"""
    t = _html.unescape(re.sub(r"<[^>]*>", "", html or ""))
    return "".join(c for c in t if not c.isspace() and unicodedata.category(c) not in _INVISIVEIS)


def tem_conteudo(html):
    """o bloco ainda mostra algo: texto visível, imagem ou anexo. Tabela vazia não conta (equivale a apagar)"""
    return bool(_texto_visivel(html)) or bool(re.search(r"<(img|object)\b", html or ""))


def validar_comandos(comandos):
    """recusa (ValueError) qualquer comando que apague ou mire fora do formato; devolve a lista validada"""
    if not isinstance(comandos, list) or not comandos:
        raise ValueError("PATCH precisa de pelo menos um comando")
    for c in comandos:
        if not isinstance(c, dict) or set(c) - {"target", "action", "position", "content"}:
            raise ValueError(f"comando com chave fora do formato: {c!r:.120}")
        acao, alvo, conteudo = c.get("action"), c.get("target"), c.get("content")
        if acao not in ACOES:
            raise ValueError(f"ação recusada: {acao!r} (só {', '.join(sorted(ACOES))}; nada apaga)")
        if "position" in c and c["position"] not in POSICOES:
            raise ValueError(f"position inválida: {c['position']!r}")
        if not isinstance(alvo, str) or not ALVO.match(alvo):
            raise ValueError(f"alvo malformado: {alvo!r:.80}")
        if acao in ("append", "prepend") and not (alvo in ("body",) or alvo.startswith(("#", "div:", "ul:", "ol:"))):
            raise ValueError(f"{acao} só em body, div, ul/ol ou #id: {alvo!r:.80}")
        if acao == "replace" and alvo == "body" or acao == "replace" and alvo.startswith("#"):
            raise ValueError("replace só pelo id gerado (ou title): ler a página com includeIDs antes")
        if alvo == "title" and acao != "replace":
            raise ValueError("title só aceita replace")
        if acao == "insert" and alvo == "body":
            raise ValueError("insert precisa de um bloco como alvo (body só aceita append/prepend)")
        if not isinstance(conteudo, str) or not conteudo.strip():
            raise ValueError("conteúdo vazio recusado (equivale a apagar)")
        if alvo != "title" and not tem_conteudo(conteudo):
            raise ValueError("conteúdo sem texto, imagem ou anexo recusado (equivale a apagar)")
        if alvo == "title" and not _texto_visivel(conteudo):
            raise ValueError("título vazio recusado")
    return comandos


def montar_multipart(primeira, partes, fronteira=None):
    """primeira = (nome, content-type, bytes|str); partes = [(nome, mime, bytes)] → (corpo, content-type)
    CRLF em tudo (IF/UP); o nome da parte é o mesmo texto que o HTML cita em name:"""
    blocos = [primeira] + list(partes or [])
    dados = [(n, t, c.encode("utf-8") if isinstance(c, str) else bytes(c)) for n, t, c in blocos]
    fronteira = fronteira or f"onenote-mcp-{uuid.uuid4().hex}"
    if any(fronteira.encode() in c for _, _, c in dados):
        raise ValueError("fronteira do multipart aparece no conteúdo")
    for n, t, _ in dados:
        if not re.match(r"^[A-Za-z][A-Za-z0-9]{0,30}$", n) or "\r" in t or "\n" in t:
            raise ValueError(f"parte inválida: {n!r}")
    corpo = b""
    for n, t, c in dados:
        corpo += (f"--{fronteira}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n"
                  f"Content-Type: {t}\r\n\r\n").encode("ascii") + c + b"\r\n"
    corpo += f"--{fronteira}--\r\n".encode("ascii")
    return corpo, f"multipart/form-data; boundary={fronteira}"


class Graph:
    def __init__(self, obter_token, base=BASE, opener=None, dormir=time.sleep, relogio=time.monotonic):
        self._token = obter_token
        self.base = base
        self._abrir = (opener or _opener).open
        self._dormir = dormir
        self._relogio = relogio
        self._janela = deque()
        self._trava = threading.Lock()
        self._vagas = threading.BoundedSemaphore(SIMULTANEAS)

    def _url(self, metodo, caminho):
        if metodo not in _ROTAS:
            raise ValueError(f"método recusado: {metodo}")
        if caminho.startswith("http"):
            partes = urlsplit(caminho)
            if self.base == BASE and (partes.scheme != "https" or partes.hostname != HOST):
                raise ErroGraph(0, f"link fora do Graph recusado: {partes.scheme}://{partes.hostname}")
            rota = re.sub(r"^/v1\.0", "", partes.path)
            url = caminho
        else:
            rota = caminho.split("?")[0]
            url = self.base + caminho
        if not _ROTAS[metodo].match(rota):
            raise ValueError(f"rota fora da lista: {metodo} {rota[:80]}")
        if any(c in url for c in " \t\r\n"):
            raise ValueError(f"URL com espaço (use %20): {url}")
        return url

    def _cota(self):
        """janela deslizante de 60 s: na 121ª requisição do minuto, espera a mais velha sair"""
        with self._trava:
            agora = self._relogio()
            while self._janela and agora - self._janela[0] >= 60:
                self._janela.popleft()
            if len(self._janela) >= POR_MINUTO:
                espera = 60 - (agora - self._janela[0])
                if espera > 0:
                    self._dormir(espera)
                agora = self._relogio()
                self._janela.popleft()
            self._janela.append(agora)

    def _req(self, metodo, caminho, corpo=None, tipo=None, bruto=False):
        url = self._url(metodo, caminho)
        dados = corpo.encode("utf-8") if isinstance(corpo, str) else corpo
        tok = self._token()
        for tentativa in range(4):
            self._cota()
            req = urllib.request.Request(url, data=dados, method=metodo)
            req.add_unredirected_header("Authorization", f"Bearer {tok}")
            if tipo:
                req.add_header("Content-Type", tipo)
            try:
                with self._vagas, self._abrir(req, timeout=60) as r:
                    cru = r.read()
                    if bruto == "bytes":
                        return cru
                    texto = cru.decode("utf-8", "replace")
                    if bruto:
                        return texto
                    return json.loads(texto) if texto.strip() else {}
            except urllib.error.HTTPError as e:
                repetir = e.code == 429 or (e.code == 503 and metodo == "GET")
                if repetir and tentativa < 3:
                    self._dormir(min(_espera(e.headers.get("Retry-After"), tentativa), 60))
                    continue
                corpo_erro = e.read().decode("utf-8", "replace")
                codigo = ""
                try:
                    err = json.loads(corpo_erro).get("error", {})
                    msg, codigo = err.get("message") or corpo_erro, err.get("code", "")
                except (ValueError, AttributeError):
                    msg = corpo_erro
                if e.code == 429:
                    msg = "limite de requisições do OneNote, tente de novo em instantes"
                raise ErroGraph(e.code, msg[:500], codigo) from None
        raise AssertionError("inalcançável")

    def get(self, caminho):
        return self._req("GET", caminho)

    def get_todos(self, caminho):
        itens, url = [], caminho
        while url:
            r = self.get(url)
            itens.extend(r.get("value", []))
            url = r.get("@odata.nextLink")
        return itens

    def get_html(self, caminho):
        return self._req("GET", caminho, bruto=True)

    def get_bytes(self, caminho):
        return self._req("GET", caminho, bruto="bytes")

    def post_pagina(self, secao_id, html, partes=None):
        """cria página: XHTML puro, ou multipart (Presentation + partes binárias) quando há imagem/anexo"""
        caminho = f"/me/onenote/sections/{quote(secao_id)}/pages"
        if partes:
            corpo, tipo = montar_multipart(("Presentation", "text/html", html), partes)
            return self._req("POST", caminho, corpo, tipo=tipo)
        return self._req("POST", caminho, html, tipo="application/xhtml+xml; charset=utf-8")

    def patch_conteudo(self, pagina_id, comandos, partes=None):
        """PATCH validado (nada apaga); com partes, multipart com Commands (UP)"""
        validar_comandos(comandos)
        caminho = f"/me/onenote/pages/{quote(pagina_id)}/content"
        js = json.dumps(comandos, ensure_ascii=False)
        if partes:
            corpo, tipo = montar_multipart(("Commands", "application/json", js), partes)
            return self._req("PATCH", caminho, corpo, tipo=tipo)
        return self._req("PATCH", caminho, js, tipo="application/json")
