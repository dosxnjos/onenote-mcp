# passo 2: graph.py endurecido (sem rede). Prova: nenhum caminho envia DELETE ou action fora do enum
import io
import json

import pytest

from onenote_mcp import graph as G
from onenote_mcp.graph import ErroGraph, Graph, montar_multipart, validar_comandos

GU = "{00000000-0000-4000-8000-0000000000a1}"


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Gravador:
    """opener falso: guarda cada Request e responde 204/json"""
    def __init__(self, corpo=b""):
        self.reqs, self.corpo = [], corpo

    def open(self, req, timeout):
        self.reqs.append(req)
        return _Resp(self.corpo)


def _g(op=None, **kw):
    return Graph(lambda: "T", opener=op or Gravador(), dormir=lambda s: None, **kw)


@pytest.mark.parametrize("acao", ["delete", "DELETE", "remove", "", None])
def test_graph_acao_fora_do_enum_recusada(acao):
    with pytest.raises(ValueError, match="ação recusada"):
        validar_comandos([{"target": f"p:{GU}{{3}}", "action": acao, "content": "<p>x</p>"}])


def test_graph_patch_delete_nao_sai():
    op = Gravador()
    with pytest.raises(ValueError):
        _g(op).patch_conteudo("P1", [{"target": f"p:{GU}{{3}}", "action": "delete", "content": "<p>x</p>"}])
    assert op.reqs == []


@pytest.mark.parametrize("alvo", ["div:{x}{1}", "p:{abc}{1}", "#_default", "_default", "#", "span:" + GU + "{1}",
                                  "td:" + GU + "{2}", "pre:" + GU + "{2}", "#a b", "p:" + GU, "", None, "body;x"])
def test_graph_alvo_malformado(alvo):
    with pytest.raises(ValueError):
        validar_comandos([{"target": alvo, "action": "insert", "content": "<p>x</p>"}])


@pytest.mark.parametrize("alvo", [f"div:{GU}{{143}}:{GU}{{27}}", f"table:{GU}{{96}}", f"h3:{GU}{{19}}", "#secaoA",
                                  f"ul:{GU}{{29}}", f"img:{GU}{{160}}"])
def test_graph_alvos_validos(alvo):
    acao = "append" if alvo.startswith(("div", "ul", "#")) else "replace"
    validar_comandos([{"target": alvo, "action": acao, "content": "<p>x</p>"}])


@pytest.mark.parametrize("conteudo", ["", "   ", "<p></p>", "<p> </p>", "<span></span>", None])
def test_graph_conteudo_vazio_e_apagar(conteudo):
    with pytest.raises(ValueError, match="vazio|apagar"):
        validar_comandos([{"target": f"p:{GU}{{3}}", "action": "replace", "content": conteudo}])


def test_graph_conteudo_so_imagem_ou_tabela_passa():
    validar_comandos([{"target": f"p:{GU}{{3}}", "action": "insert", "content": '<img src="name:img1" />'}])
    validar_comandos([{"target": f"p:{GU}{{3}}", "action": "replace", "content": "<table><tr><td>x</td></tr></table>"}])


def test_graph_replace_exige_id_gerado_e_title_so_replace():
    with pytest.raises(ValueError):
        validar_comandos([{"target": "#par1", "action": "replace", "content": "<p>x</p>"}])
    with pytest.raises(ValueError):
        validar_comandos([{"target": "body", "action": "replace", "content": "<p>x</p>"}])
    with pytest.raises(ValueError):
        validar_comandos([{"target": "title", "action": "append", "content": "x"}])
    with pytest.raises(ValueError):
        validar_comandos([{"target": f"p:{GU}{{3}}", "action": "append", "content": "<p>x</p>"}])
    with pytest.raises(ValueError, match="position"):
        validar_comandos([{"target": f"p:{GU}{{3}}", "action": "insert", "position": "middle", "content": "x"}])
    with pytest.raises(ValueError, match="chave"):
        validar_comandos([{"target": f"p:{GU}{{3}}", "action": "insert", "content": "x", "extra": 1}])
    with pytest.raises(ValueError):
        validar_comandos([])


def test_graph_lote_inteiro_recusado_se_um_comando_e_ruim():
    op = Gravador()
    bons = {"target": f"p:{GU}{{3}}", "action": "replace", "content": "<p>x</p>"}
    with pytest.raises(ValueError):
        _g(op).patch_conteudo("P1", [bons, {"target": f"p:{GU}{{4}}", "action": "delete", "content": "<p>y</p>"}])
    assert op.reqs == []


def test_graph_sem_delete_no_cliente():
    g = _g()
    assert not any(hasattr(g, n) for n in ("delete", "patch_json", "post_html", "deletar", "apagar"))
    with pytest.raises(ValueError, match="método"):
        g._req("DELETE", "/me/onenote/pages/P1")
    with pytest.raises(ValueError, match="método"):
        g._req("PUT", "/me/onenote/pages/P1/content")


@pytest.mark.parametrize("metodo,caminho", [
    ("GET", "/me/drive/root"), ("GET", "/me/messages"), ("POST", "/me/onenote/notebooks"),
    ("POST", "/me/onenote/pages/P1/copyToSection"), ("PATCH", "/me/onenote/pages/P1"),
    ("PATCH", "/me/onenote/sections/S1"), ("POST", "/me/onenote/sections/S1/pages/x"),
])
def test_graph_rota_fora_da_lista(metodo, caminho):
    op = Gravador()
    with pytest.raises(ValueError, match="rota"):
        _g(op)._req(metodo, caminho, "x")
    assert op.reqs == []


def test_graph_nextlink_absoluto_do_graph_passa():
    op = Gravador(b'{"value": [1]}')
    _g(op).get("https://graph.microsoft.com/v1.0/users('a@b.c')/onenote/sections/S1/pages?$skip=20")
    _g(op).get("https://graph.microsoft.com/v1.0/me/onenote/notebooks?$skip=20")
    assert len(op.reqs) == 2
    with pytest.raises(ValueError):
        _g(op).get("https://graph.microsoft.com/v1.0/me/drive/root")


def test_graph_multipart_ouro():
    corpo, tipo = montar_multipart(("Presentation", "text/html", "<html>á</html>"),
                                   [("img1", "image/png", b"\x89PNG\r\n\x1a\nDADOS")], fronteira="FRONT")
    assert tipo == "multipart/form-data; boundary=FRONT"
    assert corpo == (b'--FRONT\r\nContent-Disposition: form-data; name="Presentation"\r\n'
                     b"Content-Type: text/html\r\n\r\n<html>\xc3\xa1</html>\r\n"
                     b'--FRONT\r\nContent-Disposition: form-data; name="img1"\r\n'
                     b"Content-Type: image/png\r\n\r\n\x89PNG\r\n\x1a\nDADOS\r\n--FRONT--\r\n")


def test_graph_multipart_recusa_fronteira_no_conteudo_e_nome_ruim():
    with pytest.raises(ValueError):
        montar_multipart(("Presentation", "text/html", "--X"), [], fronteira="X")
    with pytest.raises(ValueError):
        montar_multipart(("Presentation", "text/html", "a"), [('img1"; x="', "image/png", b"")])


def test_graph_post_e_patch_multipart_nome_da_parte_igual_a_referencia():
    op = Gravador(b'{"id": "N"}')
    g = _g(op)
    g.post_pagina("0-ABC!s1", '<html><body><img src="name:img1" /></body></html>', [("img1", "image/png", b"PNG")])
    req = op.reqs[-1]
    assert req.get_method() == "POST" and req.full_url.endswith("/me/onenote/sections/0-ABC!s1/pages")
    ct = req.get_header("Content-type")
    assert ct.startswith("multipart/form-data; boundary=onenote-mcp-")
    assert b'name="Presentation"' in req.data and b'name="img1"' in req.data
    cmds = [{"target": f"p:{GU}{{3}}", "action": "insert", "content": '<img src="name:img1" />'}]
    g.patch_conteudo("P1", cmds, [("img1", "image/png", b"PNG")])
    req = op.reqs[-1]
    assert req.get_method() == "PATCH" and req.full_url.endswith("/me/onenote/pages/P1/content")
    primeira = req.data.split(b"\r\n\r\n", 1)
    assert b'name="Commands"' in primeira[0] and b"Content-Type: application/json" in primeira[0]
    assert json.loads(primeira[1].split(b"\r\n--")[0]) == cmds


def test_graph_patch_sem_partes_e_json():
    op = Gravador()
    _g(op).patch_conteudo("P1", [{"target": "title", "action": "replace", "content": "Novo"}])
    req = op.reqs[-1]
    assert req.get_header("Content-type") == "application/json"
    assert json.loads(req.data) == [{"target": "title", "action": "replace", "content": "Novo"}]


def test_graph_cota_120_por_minuto_espera_a_mais_velha():
    agora = [0.0]
    dormiu = []

    def dormir(s):
        dormiu.append(s)
        agora[0] += s
    g = Graph(lambda: "T", opener=Gravador(b"{}"), dormir=dormir, relogio=lambda: agora[0])
    for k in range(G.POR_MINUTO):
        agora[0] = k * 0.1
        g.get("/me/onenote/notebooks")
    assert dormiu == []
    g.get("/me/onenote/notebooks")
    assert len(dormiu) == 1 and dormiu[0] == pytest.approx(60 - 11.9)


def test_graph_erro_guarda_codigo():
    import urllib.error

    class Op:
        def open(self, req, timeout):
            raise urllib.error.HTTPError("https://graph.microsoft.com/x", 400, "x", {},
                                         io.BytesIO(b'{"error": {"code": "20117", "message": "nome repetido"}}'))
    with pytest.raises(ErroGraph) as e:
        _g(Op()).post_pagina("S1", "<html/>")
    assert e.value.codigo == "20117" and e.value.status == 400
