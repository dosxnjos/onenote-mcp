# testes da v1 (adaptados à v2 só no que mudou de assinatura): lista permitida, operações, HTTP e servidor
# sem rede: o Graph falso (falso.py) imita um bloco compartilhado (com seção de senhas) e um bloco pessoal
import asyncio
import io
import json
import urllib.error
import xml.dom.minidom

import pytest

from falso import BLOCO, GraphFalso, pagina_de
from onenote_mcp import permitidos as P
from onenote_mcp.config import Config, carregar
from onenote_mcp.formato.escrita import escrever
from onenote_mcp.formato.leitura import ler
from onenote_mcp.graph import ErroGraph, Graph, _espera
from onenote_mcp.onenote import OneNote


def _on(permitidos=(f"{BLOCO}/Grupo/Notas",), bloqueados=("senha",), g=None, tmp=None):
    cfg = Config(client_id="x", permitidos=list(permitidos), bloqueados=list(bloqueados))
    if tmp:
        cfg.cache_dir = tmp
    return OneNote(g or GraphFalso(), cfg)


# ---------- lista permitida ----------
def test_allowlist_prefixo_e_bloqueio():
    perm, bloq = [BLOCO], ["senha"]
    assert P.permitido(f"{BLOCO}/Grupo/Notas", perm, bloq)
    assert not P.permitido(f"{BLOCO}/Senhas", perm, bloq)
    assert not P.permitido("Outro bloco/Seção", perm, bloq)
    assert not P.permitido(f"{BLOCO}/Grupo/Notas", [], bloq)
    assert not P.permitido(f"{BLOCO} extra/X", perm, bloq)


@pytest.mark.parametrize("nome", ["LOGINS E SENHAS", "Logins e Senha 🔒", "LOGINS\xa0E SENHA", "LOGINS  E SENHA",
                                  "LOGINS & SENHA", "LOGINS E SENHA (1)", "Senhas", "SÉNHA", "Passwords", "credenciais"])
def test_variantes_do_nome_de_senha_bloqueadas(nome):
    assert not P.permitido(f"{BLOCO}/{nome}", [BLOCO], carregar("C:/nao/existe.toml").bloqueados)


def test_bloqueio_padrao_mesmo_sem_config_e_toml_nao_remove(tmp_path):
    assert "senha" in carregar("C:/caminho/que/nao/existe.toml").bloqueados
    p = tmp_path / "c.toml"
    p.write_text('[lista]\npermitidos = ["A"]\nbloqueados = []\n', encoding="utf-8")
    assert "senha" in carregar(p).bloqueados


def test_bloco_extra_com_id_errado_diz_qual_id_falhou():
    class G(GraphFalso):
        def get(self, caminho):
            if caminho.startswith("/me/onenote/notebooks/"):
                raise ErroGraph(404, "The specified resource ID does not exist.", "20102")
            return super().get(caminho)
    on = _on(g=G())
    on.cfg.blocos_extra = ["0-ERRADO!sxyz"]
    with pytest.raises(ErroGraph, match=r"0-ERRADO!sxyz de \[lista\]\.blocos_extra não abriu") as e:
        on._todos_blocos()
    assert e.value.status == 404 and e.value.codigo == "20102"


def test_indice_so_com_o_permitido():
    assert [s["caminho"] for s in _on().listar_secoes()] == [f"{BLOCO}/Grupo/Notas"]


def test_bloco_inteiro_permitido_ainda_esconde_senhas():
    on = _on(permitidos=(BLOCO,))
    caminhos = {s["caminho"] for s in on.listar_secoes()}
    assert f"{BLOCO}/Senhas" not in caminhos and f"{BLOCO}/Grupo/Rascunhos" in caminhos
    assert [b["nome"] for b in on.listar_blocos()] == [BLOCO]


def test_bloco_com_nome_repetido_fica_fora():
    g = GraphFalso(blocos=[{"id": "NB1", "displayName": BLOCO}, {"id": "NB9", "displayName": BLOCO}])
    on = _on(permitidos=(BLOCO,), g=g)
    assert on.listar_secoes() == [] and on.avisos


def test_secao_renomeada_para_senha_e_barrada_ao_vivo():
    on = _on()
    assert on.listar_secoes()
    on.g.nomes["S-NOTAS"] = "Notas senhas"
    with pytest.raises(P.ForaDaLista):
        on.ler_pagina("P1")
    with pytest.raises(P.ForaDaLista):
        on.criar_pagina("S-NOTAS", "x", "y")


def test_ler_pagina_fora_da_lista_recusa_sem_baixar():
    on = _on(permitidos=(BLOCO,))
    with pytest.raises(P.ForaDaLista):
        on.ler_pagina("PSENHA")
    assert not any("/content" in c[1] for c in on.g.chamadas)


# ---------- operações ----------
def test_ler_pagina_permitida_em_onmd():
    r = _on().ler_pagina("P1")
    assert r["secao"] == f"{BLOCO}/Grupo/Notas" and "# Perguntas" in r["conteudo"]
    assert "**1** - verba" in r["conteudo"]


def test_listar_paginas_sem_espaco_na_url():
    on = _on()
    on.listar_paginas("S-NOTAS")
    url = [c[1] for c in on.g.chamadas if "/pages" in c[1]][-1]
    assert " " not in url and "$top" not in url


def test_criar_pagina_xhtml_bem_formado():
    on = _on()
    r = on.criar_pagina(f"{BLOCO}/grupo/notas", "Teste <MCP>",
                        "# Título\n\nlinha1\nlinha2\n\n---\n\n1. um\n2. dois\n\n**negrito**\n\n| a | b |\n|---|---|\n| 1 | 2 |")
    metodo, caminho, html, partes = on.g.chamadas[-1]
    assert metodo == "POST" and caminho == "/me/onenote/sections/S-NOTAS/pages" and partes is None
    xml.dom.minidom.parseString(html.replace("<!DOCTYPE html>", ""))
    assert "<title>Teste &lt;MCP&gt;</title>" in html and "<p>linha1</p><p>linha2</p>" in html
    assert "<th" not in html and "<td><b>a</b></td>" in html and r["link"] == "https://exemplo"
    assert "<hr" not in html and "────" in html  # divisória é parágrafo cinza (hr não existe no OneNote)


def test_html_perigoso_vira_texto():
    e = escrever('oi <img src="https://atacante/x.png?d=S"> <iframe src="https://a"></iframe>'
                 '<p data-render-src="https://a">z</p> [ok](https://site) [ruim](javascript:alert(1))')
    h = e.html
    assert "<img" not in h and "<iframe" not in h and "<p data" not in h and "javascript" not in h
    assert '<a href="https://site">ok</a>' in h and "&lt;img" in h
    assert any("virou texto" in a for a in e.avisos) and any("link ignorado" in a for a in e.avisos)


def test_acrescentar_mira_a_ultima_div_do_body_nao_a_secao():
    on = _on(g=GraphFalso(paginas={"P1": pagina_de("x\n\n<secao id=resumo>\ny\n</secao>")}))
    on.acrescentar("P1", "mais uma linha")
    metodo, caminho, corpo, _ = on.g.chamadas[-1]
    assert metodo == "PATCH" and caminho == "/me/onenote/pages/P1/content"
    assert corpo[0]["action"] == "append" and corpo[0]["content"] == "<p>mais uma linha</p>"
    alvo = corpo[0]["target"]
    assert alvo.startswith("div:") and ":{" not in alvo[4:]  # a div da página, não a <secao> (id composto)
    assert ler(on.g._saida("P1")).onmd.endswith("mais uma linha")


def test_criar_em_secao_bloqueada_recusa():
    on = _on(permitidos=(BLOCO,))
    with pytest.raises(P.ForaDaLista):
        on.criar_pagina(f"{BLOCO}/Senhas", "x", "y")
    assert not any(c[0] == "POST" for c in on.g.chamadas)


def test_ids_com_exclamacao_nao_escapam():
    from onenote_mcp.onenote import quote
    assert quote("0-AAAAAAAAAAAAAAAA!sbbbb") == "0-AAAAAAAAAAAAAAAA!sbbbb"


def test_leitura_le_negrito_do_onenote():
    h = ('<html><body><div><ol><li>item <span style="font-weight:bold">negrito</span> e '
         '<span style="font-style:italic">it&#225;lico</span></li></ol></div></body></html>')
    md = ler(h).onmd
    assert "**negrito**" in md and "*itálico*" in md


def test_leitura_sem_linhas_vazias_em_excesso():
    assert ler("<html><body><div><p>a</p><p></p><p></p><p>b</p></div></body></html>").onmd == "a\n\nb"


def test_pagina_titulo_vazio():
    on = _on()
    on.criar_pagina("S-NOTAS", "", "x")
    assert "<title>Sem título</title>" in on.g.chamadas[-1][2]


# ---------- HTTP ----------
class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_erro(code, headers=None, corpo=b"{}"):
    return urllib.error.HTTPError("https://graph.microsoft.com/x", code, "x", headers or {}, io.BytesIO(corpo))


def test_retry_after_em_data_e_decimal():
    assert _espera("0.5", 0) == 0.5
    assert _espera("Wed, 21 Oct 2015 07:28:00 GMT", 1) == 0.0
    assert _espera("lixo", 2) == 4.0


def test_429_repete_e_post_nao_repete_em_503():
    seq = [_http_erro(429, {"Retry-After": "1"}), _Resp(b'{"ok":1}')]

    class Op:
        def open(self, req, timeout):
            x = seq.pop(0)
            if isinstance(x, Exception):
                raise x
            return x
    dormiu = []
    g = Graph(lambda: "T", opener=Op(), dormir=dormiu.append)
    assert g.get("/me/onenote/notebooks") == {"ok": 1} and dormiu == [1.0]

    class Op503:
        n = 0

        def open(self, req, timeout):
            Op503.n += 1
            raise _http_erro(503)
    with pytest.raises(ErroGraph):
        Graph(lambda: "T", opener=Op503(), dormir=lambda s: None).post_pagina("S1", "<html/>")
    assert Op503.n == 1


def test_link_fora_do_graph_recusado_e_espaco_recusado():
    g = Graph(lambda: "T")
    with pytest.raises(ErroGraph):
        g.get("https://atacante.exemplo/me")
    with pytest.raises(ValueError):
        g.get("/me/onenote/pages?$orderby=a desc")


def test_token_pedido_uma_vez_por_requisicao():
    n = []
    seq = [_http_erro(429, {"Retry-After": "0"}), _http_erro(429, {"Retry-After": "0"}), _Resp(b"{}")]

    class Op:
        def open(self, req, timeout):
            x = seq.pop(0)
            if isinstance(x, Exception):
                raise x
            return x
    Graph(lambda: n.append(1) or "T", opener=Op(), dormir=lambda s: None).get("/me/onenote/notebooks")
    assert len(n) == 1


# ---------- servidor ----------
def test_server_erro_vira_toolerror(monkeypatch, tmp_path):
    from mcp.server.fastmcp.exceptions import ToolError
    from onenote_mcp import server
    cfg = tmp_path / "c.toml"
    cfg.write_text('[microsoft]\nclient_id="x"\n', encoding="utf-8")
    monkeypatch.setenv("ONENOTE_MCP_CONFIG", str(cfg))
    monkeypatch.setattr(server, "_on", _on(permitidos=(BLOCO,)))
    monkeypatch.setattr(server, "_mtime", cfg.stat().st_mtime)
    with pytest.raises(ToolError, match="fora da lista"):
        asyncio.run(server.ler_pagina("PSENHA"))


def test_server_sem_client_id_nao_guarda_cliente(monkeypatch, tmp_path):
    from mcp.server.fastmcp.exceptions import ToolError
    from onenote_mcp import server
    cfg = tmp_path / "c.toml"
    cfg.write_text('[microsoft]\nclient_id=""\n', encoding="utf-8")
    monkeypatch.setenv("ONENOTE_MCP_CONFIG", str(cfg))
    monkeypatch.setattr(server, "_on", None)
    with pytest.raises(ToolError, match="client_id"):
        asyncio.run(server.listar_blocos())
    assert server._on is None


def test_sem_registro_avisa(tmp_path):
    from onenote_mcp import auth
    with pytest.raises(auth.SemRegistro):
        auth.token(Config(client_id="", cache_dir=tmp_path))


def test_json_serializavel():
    json.dumps(_on().listar_paginas("S-NOTAS"))
