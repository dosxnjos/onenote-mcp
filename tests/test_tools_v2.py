# passo 6: tools v2 + diário local (Graph falso que aplica o PATCH e troca os ids a cada update)
# prova: ids vêm do GET mais recente; trecho ambíguo/ausente/atravessando blocos → erro SEM PATCH;
# novo que esvazia → erro; célula → replace da tabela inteira mantendo data-id; diário grava antes do PATCH
import asyncio
import json
import re

import pytest

from falso import BLOCO, GraphFalso, pagina_de
from onenote_mcp import diario as D
from onenote_mcp.arquivos import ArquivoRecusado
from onenote_mcp.config import Config, carregar
from onenote_mcp.formato.escrita import ErroFormato
from onenote_mcp.formato.leitura import ler
from onenote_mcp.graph import ErroGraph
from onenote_mcp.onenote import ErroEdicao, OneNote

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 30

PAGINA = """# Reunião {id=topo}

Resumo da reunião com a Ana.

O preço é R$ 99 na loja.

O frete é R$ 99 também.

> frase citada

- [ ] Fechar orçamento
- [x] Enviar fotos
- [ ] Ligar fornecedor

<tabela id=precos>
<linha>
<celula>Camiseta</celula>
<celula>R$ 49</celula>
</linha>
</tabela>

| Item | Valor |
| --- | --- |
| Boné | R$ 30 |

```py
x = 1
```

<secao id=resumo>
dentro da seção
</secao>

fim da página"""


def _on(tmp_path, paginas=None, **cfg):
    g = GraphFalso(paginas={"P1": pagina_de(PAGINA, "Reunião"), **(paginas or {})})
    c = Config(client_id="x", permitidos=[f"{BLOCO}/Grupo/Notas"], cache_dir=tmp_path / "cache", **cfg)
    return OneNote(g, c)


def _patches(on):
    return [c for c in on.g.chamadas if c[0] == "PATCH"]


def _onmd(on, pid="P1"):
    return ler(on.g._saida(pid), incluir_ids=True).onmd


# ---------- editar ----------
def test_tools_editar_troca_simples_pelo_id_gerado_atual(tmp_path):
    on = _on(tmp_path)
    r = on.editar("P1", [{"antigo": "Resumo da reunião", "novo": "Resumo **curto** da reunião"}])
    assert r["ok"] and r["blocos"] == 1
    (_, _, cmds, _), = _patches(on)
    assert len(cmds) == 1 and cmds[0]["action"] == "replace" and cmds[0]["target"].startswith("p:{00000000-")
    assert "Resumo **curto** da reunião com a Ana." in _onmd(on)


def test_tools_editar_usa_ids_do_get_mais_recente(tmp_path):
    on = _on(tmp_path)
    antes = ler(on.g._saida("P1")).blocos[1].id_gerado
    on.editar("P1", [{"antigo": "Resumo", "novo": "Sumário"}])
    on.editar("P1", [{"antigo": "fim da página", "novo": "fim do texto"}])   # 2º PATCH, ids já trocaram
    t1, t2 = (c[2][0]["target"] for c in _patches(on))
    assert t1.split("}")[0] != t2.split("}")[0]   # guid diferente: cada PATCH usou o GET de antes dele
    with pytest.raises(ErroGraph, match="id velho"):
        on.g.patch_conteudo("P1", [{"target": antes, "action": "replace", "content": "<p>x</p>"}])
    gets = [c for c in on.g.chamadas if c[0] == "GET" and "/content" in c[1]]
    assert len(gets) == 2 and all("includeIDs=true" in c[1] for c in gets)


@pytest.mark.parametrize("trocas,msg", [
    ([{"antigo": "R$ 99", "novo": "R$ 89"}], "ambíguo"),
    ([{"antigo": "não existe na página", "novo": "x"}], "não encontrado"),
    ([{"antigo": "Ana.\n\nO preço", "novo": "x"}], "atravessa"),
    ([{"antigo": "Resumo da reunião com a Ana.", "novo": ""}], "esvaziaria"),
    ([{"antigo": "", "novo": "x"}], "antigo"),
    ([{"antigo": "x"}], "novo"),
    ([], "trocas"),
    ([{"antigo": "Resumo", "novo": "A"}, {"antigo": "inexistente", "novo": "B"}], "não encontrado"),
])
def test_tools_editar_erro_nao_envia_patch(tmp_path, trocas, msg):
    on = _on(tmp_path)
    with pytest.raises(ErroEdicao, match=msg):
        on.editar("P1", trocas)
    assert _patches(on) == []
    assert not (tmp_path / "cache" / "historico").exists()


def test_tools_editar_todas_e_lote_atomico_num_patch(tmp_path):
    on = _on(tmp_path)
    r = on.editar("P1", [{"antigo": "R$ 99", "novo": "R$ 89", "todas": True},
                         {"antigo": "Resumo", "novo": "Sumário"}])
    assert r["blocos"] == 3
    (_, _, cmds, _), = _patches(on)
    assert len(cmds) == 3 and {c["action"] for c in cmds} == {"replace"}
    o = _onmd(on)
    assert "R$ 99" not in o and o.count("R$ 89") == 2 and "Sumário da reunião" in o


def test_tools_editar_celula_regrava_a_tabela_inteira_com_data_id(tmp_path):
    on = _on(tmp_path)
    on.editar("P1", [{"antigo": "R$ 49", "novo": "R$ 59"}])
    (_, _, cmds, _), = _patches(on)
    assert cmds[0]["target"].startswith("table:") and cmds[0]["content"].startswith('<table ')
    assert cmds[0]["content"].split(">")[0].count('data-id="precos"') == 1   # o id da tabela volta (do ONMD)
    assert "<tabela id=precos>\n<linha>\n<celula>Camiseta</celula>\n<celula>R$ 59</celula>" in _onmd(on)


def test_tools_editar_tabela_gfm_e_codigo_e_citacao_mantem_forma(tmp_path):
    on = _on(tmp_path)
    on.editar("P1", [{"antigo": "R$ 30", "novo": "R$ 35"}, {"antigo": "x = 1", "novo": "x = 2"},
                     {"antigo": "frase citada", "novo": "frase **citada**"}])
    o = _onmd(on)
    assert "| Boné | R$ 35 |" in o and "```py\nx = 2\n```" in o and "> frase **citada**" in o
    cmds = _patches(on)[0][2]
    assert any('data-id="on-cod-1-py"' in c["content"] for c in cmds)
    assert any('data-id="on-cit-1-1"' in c["content"] for c in cmds)


def test_tools_editar_trecho_com_id_lido_com_incluir_ids(tmp_path):
    on = _on(tmp_path)
    on.editar("P1", [{"antigo": "# Reunião {id=topo}", "novo": "# Reunião de outubro {id=topo}"}])
    assert "# Reunião de outubro {id=topo}" in _onmd(on)


def test_tools_editar_imagem_existente_recusada(tmp_path):
    from simulador import Simulador
    from onenote_mcp.arquivos import Anexo
    from onenote_mcp.formato.escrita import escrever
    from falso import G0
    e = escrever("antes\n\n![Logo](anexo:1)", [Anexo("l.png", "image/png", PNG, "x", True)])
    on = _on(tmp_path, paginas={"P2": Simulador(guid=G0).pagina(e.html, "Img")})
    with pytest.raises(ErroFormato, match="não se recria"):
        on.editar("P2", [{"antigo": "![Logo]", "novo": "![Logo novo]"}])
    assert _patches(on) == []


# ---------- diário ----------
def test_tools_diario_grava_antes_do_patch(tmp_path):
    on = _on(tmp_path)
    original = on.g.patch_conteudo
    visto = []

    def patch(pid, cmds, partes=None):
        visto.append(D.ler(on.cfg.historico_dir, pid))
        return original(pid, cmds, partes)
    on.g.patch_conteudo = patch
    on.editar("P1", [{"antigo": "Resumo da reunião", "novo": "Sumário"}])
    (linhas,) = visto
    assert len(linhas) == 1 and linhas[0]["acao"] == "editar"
    it = linhas[0]["itens"][0]
    assert "Resumo da reunião com a Ana." in it["antes"] and it["antes"].startswith("<p ")
    assert "Sumário" in it["depois"] and it["alvo"] == _patches(on)[0][2][0]["target"]


def test_tools_diario_sem_password_e_com_rotacao(tmp_path, monkeypatch):
    pasta = tmp_path / "h"
    D.gravar(pasta, "0-A!1-B", "editar", [{"alvo": "p:1", "antes": '<p data-tag="password">segredo</p>'}])
    (l,) = D.ler(pasta, "0-A!1-B")
    assert "segredo" not in json.dumps(l) and "omitido" in l["itens"][0]["antes"]
    assert D.arquivo(pasta, "0-A!1-B").name == "0-A_1-B.jsonl"
    monkeypatch.setattr(D, "ROTACAO", 10)
    D.gravar(pasta, "0-A!1-B", "editar", [{"alvo": "p:2", "antes": "x"}])
    assert (pasta / "0-A_1-B.1.jsonl").exists() and len(D.ler(pasta, "0-A!1-B")) == 1


def test_tools_diario_indisponivel_bloqueia_a_troca(tmp_path):
    on = _on(tmp_path)
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "historico").write_text("arquivo no lugar da pasta")
    with pytest.raises(D.DiarioIndisponivel):
        on.editar("P1", [{"antigo": "Resumo", "novo": "Sumário"}])
    assert _patches(on) == []


# ---------- marcar_tarefa / renomear ----------
def test_tools_marcar_tarefa(tmp_path):
    on = _on(tmp_path)
    on.marcar_tarefa("P1", "Fechar orçamento")
    assert "- [x] Fechar orçamento" in _onmd(on)
    (_, _, cmds, _), = _patches(on)
    assert 'data-tag="to-do:completed"' in cmds[0]["content"]
    r = on.marcar_tarefa("P1", "Enviar fotos", feito=True)
    assert "já estava" in r["avisos"][0] and len(_patches(on)) == 1
    on.marcar_tarefa("P1", "Enviar fotos", feito=False)
    assert "- [ ] Enviar fotos" in _onmd(on)
    with pytest.raises(ErroEdicao, match="outro tipo"):
        on.marcar_tarefa("P1", "Resumo")   # existe, mas não é tarefa
    with pytest.raises(ErroEdicao, match="ambíguo"):
        on.marcar_tarefa("P1", "- [")


def test_tools_renomear_pagina(tmp_path):
    on = _on(tmp_path)
    r = on.renomear_pagina("P1", "  Reunião <final>\n")
    assert r["titulo"] == "Reunião <final>"
    (_, _, cmds, _), = _patches(on)
    assert cmds == [{"target": "title", "action": "replace", "content": "Reunião &lt;final&gt;"}]
    assert D.ler(on.cfg.historico_dir, "P1")[0]["itens"][0]["alvo"] == "title"
    with pytest.raises(ErroEdicao, match="vazio"):
        on.renomear_pagina("P1", "  \n ")


# ---------- inserir / acrescentar ----------
def test_tools_inserir_depois_de_titulo_e_antes_por_id(tmp_path):
    on = _on(tmp_path)
    on.inserir("P1", "# Reunião", "Parágrafo novo {id=novo}")
    on.inserir("P1", "#novo", "## Antes do novo", posicao="antes")
    o = _onmd(on)
    assert o.startswith("# Reunião {id=topo}\n\n## Antes do novo\n\nParágrafo novo {id=novo}\n\nResumo")
    assert [c[2][0]["action"] for c in _patches(on)] == ["insert", "insert"]
    with pytest.raises(ErroEdicao, match="posicao"):
        on.inserir("P1", "# Reunião", "x", posicao="meio")


def test_tools_acrescentar_em_secao_inicio_e_onde_invalido(tmp_path):
    on = _on(tmp_path)
    on.acrescentar("P1", "mais um", onde="#resumo")
    on.acrescentar("P1", "primeiro de todos", onde="inicio")
    o = _onmd(on)
    assert "<secao id=resumo>\ndentro da seção\n\nmais um\n</secao>" in o and o.startswith("primeiro de todos")
    with pytest.raises(ErroEdicao, match="#resumo"):
        on.acrescentar("P1", "x", onde="#naoexiste")


def test_tools_acrescentar_com_fonte_da_pagina(tmp_path):
    html = re.sub(r"(<p[^>]*>)([^<]+)</p>", r'\1<span style="font-family:Segoe UI">\2</span></p>',
                  pagina_de("a\n\nb", "F"))
    on = _on(tmp_path, paginas={"P3": html})
    on.acrescentar("P3", "c")
    assert _patches(on)[0][2][0]["content"] == '<p style="font-family:Segoe UI">c</p>'


# ---------- criar_pagina ----------
def test_tools_criar_pagina_com_anexo_e_data(tmp_path):
    pasta = tmp_path / "anexos"
    pasta.mkdir()
    (pasta / "logo.png").write_bytes(PNG)
    on = _on(tmp_path, pastas_arquivos=[str(pasta)])
    r = on.criar_pagina("S-NOTAS", "Com logo", "![Logo](anexo:1){largura=50%}",
                        anexos=[{"caminho": str(pasta / "logo.png")}], criado_em="2026-10-01")
    metodo, _, html, partes = on.g.chamadas[-1]
    assert metodo == "POST" and partes == [("img1", "image/png", PNG)]
    assert '<img src="name:img1" alt="Logo" width="312" />' in html
    assert '<meta name="created" content="2026-10-01T00:00:00" />' in html
    assert any("logo.png" in a and "KB" in a for a in r["avisos"])


def test_tools_criar_pagina_anexo_desligado_e_caminho_no_texto(tmp_path):
    on = _on(tmp_path)
    with pytest.raises(ArquivoRecusado, match="desligados"):
        on.criar_pagina("S-NOTAS", "x", "![a](anexo:1)", anexos=[{"caminho": str(tmp_path)}])
    with pytest.raises(ErroFormato):
        on.criar_pagina("S-NOTAS", "x", "![a](C:/Users/x/secreto.png)")
    with pytest.raises(ErroEdicao, match="criado_em"):
        on.criar_pagina("S-NOTAS", "x", "y", criado_em="ontem")
    assert not any(c[0] == "POST" for c in on.g.chamadas)


def test_tools_link_para_pagina_so_da_lista(tmp_path):
    from onenote_mcp.permitidos import ForaDaLista
    on = _on(tmp_path)
    on.criar_pagina("S-NOTAS", "x", "[ver](pagina:P1)")
    assert '<a href="onenote:https://d.docs.live.net/P1">ver</a>' in on.g.chamadas[-1][2]
    with pytest.raises(ForaDaLista):
        on.criar_pagina("S-NOTAS", "x", "[ver](pagina:PSENHA)")


# ---------- busca, spec, imagem ----------
def test_tools_buscar_paginas_so_no_indice_e_escapa_aspas(tmp_path):
    on = _on(tmp_path)
    r = on.buscar_paginas("D'Ávila Vitrine")
    urls = [c[1] for c in on.g.chamadas if "$filter" in c[1]]
    assert len(urls) == 1 and "/sections/S-NOTAS/pages" in urls[0] and " " not in urls[0]
    assert "d%27%27%C3%A1vila%20vitrine" in urls[0]
    assert r["paginas"][0]["id"] == "P1" and r["paginas"][0]["secao"].endswith("Notas")


def test_tools_buscar_paginas_com_secoes_demais(tmp_path, monkeypatch):
    from onenote_mcp import onenote as O
    monkeypatch.setattr(O, "MAX_SECOES_BUSCA", 0)
    on = _on(tmp_path)
    with pytest.raises(ErroEdicao, match="restrinja"):
        on.buscar_paginas("x")


def test_tools_listar_paginas_com_nivel(tmp_path):
    on = _on(tmp_path)
    r = on.listar_paginas("S-NOTAS", com_nivel=True)
    assert r["paginas"][0]["nivel"] == 0 and any("pagelevel=true" in c[1] for c in on.g.chamadas)


def test_tools_ler_spec_e_ler_pagina(tmp_path):
    on = _on(tmp_path)
    assert "ONMD" in on.ler_spec()
    r = on.ler_pagina("P1")
    assert r["conteudo"].startswith("# Reunião\n\nResumo") and "{id=topo}" not in r["conteudo"]
    assert "{id=topo}" in on.ler_pagina("P1", incluir_ids=True)["conteudo"]


def test_tools_ver_imagem_so_recurso_da_pagina(tmp_path):
    from simulador import Simulador
    from onenote_mcp.arquivos import Anexo
    from onenote_mcp.formato.escrita import escrever
    from falso import G0
    e = escrever("![Logo](anexo:1)", [Anexo("l.png", "image/png", PNG, "x", True)])
    on = _on(tmp_path, paginas={"P2": Simulador(guid=G0).pagina(e.html, "Img")})
    rid = re.search(r"recurso:([^)]+)\)", on.ler_pagina("P2")["conteudo"]).group(1)
    on.g.recursos[rid] = PNG
    dados, fmt = on.ver_imagem("P2", rid)
    assert dados == PNG and fmt == "png"
    assert any(c[1] == f"/me/onenote/resources/{rid}/content" for c in on.g.chamadas)
    on.g.recursos["0-outro"] = PNG
    n = len(on.g.chamadas)
    with pytest.raises(ErroEdicao, match="não é uma imagem desta página"):
        on.ver_imagem("P2", "0-outro")
    with pytest.raises(ErroEdicao, match="inválido"):
        on.ver_imagem("P2", "../../me/drive")
    assert not any("/resources/" in c[1] for c in on.g.chamadas[n:])


# ---------- servidor ----------
def test_tools_servidor_lista_13_tools_e_recurso():
    from onenote_mcp import server
    nomes = [t.name for t in asyncio.run(server.mcp.list_tools())]
    assert nomes == ["listar_blocos", "listar_secoes", "listar_paginas", "buscar_paginas", "ler_spec", "ler_pagina",
                     "ver_imagem", "criar_pagina", "acrescentar", "inserir", "editar", "marcar_tarefa",
                     "renomear_pagina"]
    tools = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    for n in ("criar_pagina", "acrescentar", "inserir", "editar", "marcar_tarefa", "renomear_pagina"):
        assert tools[n].description.startswith("Antes de escrever, leia a spec (ler_spec)")
    assert "leitor" in tools["criar_pagina"].description
    assert tools["ver_imagem"].outputSchema is None   # Image volta como conteúdo de imagem, não estruturado
    assert "Leia ler_spec antes de escrever" in server.INSTRUCOES and "PARA O LEITOR" in server.INSTRUCOES
    recursos = [str(r.uri) for r in asyncio.run(server.mcp.list_resources())]
    assert recursos == ["onenote://docs/formato"]


def test_tools_instrucoes_base_sem_nomes_de_pessoas():
    from onenote_mcp import server
    base = server.INSTRUCOES
    # o que era do dono (nome, leitor de exemplo, voz) saiu da base: vai em [servidor].instrucoes do config dele
    for trecho in ("OneNote do ", "(ex.:", "Voz:", "pedido do ", "quando ele assina"):
        assert trecho not in base, trecho
    assert base.startswith("OneNote: só nas seções da lista permitida.")
    for regra in ("lista permitida", "Nenhuma tool apaga", "ONMD", "ler_spec", "PARA O LEITOR", "defina quem vai ler",
                  "TODOS os pontos pertinentes", "notas", "recado interno do autor", "A1, B2"):
        assert regra in base, regra


def test_tools_instrucoes_do_config_sao_acrescentadas_a_base(tmp_path):
    from onenote_mcp import server
    p = tmp_path / "c.toml"
    p.write_text('[servidor]\ninstrucoes = """\nQuem lê: a equipe.\nTom: "direto".\n"""\n', encoding="utf-8")
    cfg = carregar(p)
    assert cfg.instrucoes == 'Quem lê: a equipe.\nTom: "direto".'
    assert server.instrucoes(cfg) == server.INSTRUCOES + "\n\n" + 'Quem lê: a equipe.\nTom: "direto".'


def test_tools_instrucoes_sem_extra_e_so_a_base(tmp_path):
    from onenote_mcp import server
    p = tmp_path / "c.toml"
    p.write_text('[microsoft]\nclient_id = "x"\n', encoding="utf-8")
    assert carregar(p).instrucoes == ""
    assert server.instrucoes(carregar(p)) == server.INSTRUCOES
    assert server.instrucoes(Config(instrucoes="   \n")) == server.INSTRUCOES
    assert server.instrucoes(None) == server.INSTRUCOES


def test_tools_instrucoes_config_quebrado_nao_derruba_a_subida(tmp_path, monkeypatch):
    from onenote_mcp import server
    p = tmp_path / "c.toml"
    p.write_text("[servidor\ninstrucoes = ", encoding="utf-8")
    monkeypatch.setenv("ONENOTE_MCP_CONFIG", str(p))
    assert server._instrucoes_do_config() == server.INSTRUCOES


@pytest.mark.parametrize("toml,trecho", [
    ('servidor = "x"\n', "[servidor] tem que ser uma tabela"),          # erro mais provável de quem copia o exemplo
    ('[[servidor]]\ninstrucoes = "x"\n', "[servidor] tem que ser uma tabela"),
    ('microsoft = 1\n', "[microsoft] tem que ser uma tabela"),
    ('[lista]\npermitidos = 5\n', "[lista].permitidos tem que ser uma lista"),
    ('[lista]\npermitidos = "Meu Bloco"\n', "[lista].permitidos tem que ser uma lista"),
    ('[arquivos]\npastas = "C:/x"\n', "[arquivos].pastas tem que ser uma lista"),
    ('[servidor]\ninstrucoes = ["linha 1", "linha 2"]\n', "[servidor].instrucoes tem que ser texto"),
    ('[servidor]\ninstrucoes = true\n', "[servidor].instrucoes tem que ser texto"),
    ('cache_dir = 5\n', "cache_dir tem que ser um caminho"),
])
def test_tools_config_com_tipo_errado_sobe_e_a_tool_explica(tmp_path, monkeypatch, toml, trecho):
    """tipo errado no toml: o servidor sobe com a base e a 1ª tool devolve 'pedido recusado: …' legível"""
    from mcp.server.fastmcp.exceptions import ToolError
    from onenote_mcp import server
    p = tmp_path / "c.toml"
    p.write_text(toml, encoding="utf-8")
    monkeypatch.setenv("ONENOTE_MCP_CONFIG", str(p))
    with pytest.raises(ValueError, match=re.escape(trecho)):
        carregar()
    assert server._instrucoes_do_config() == server.INSTRUCOES
    monkeypatch.setattr(server, "_on", None)
    monkeypatch.setattr(server, "_mtime", None)
    with pytest.raises(ToolError, match="pedido recusado: config.toml: " + re.escape(trecho)):
        server._executar(server._cliente)


def test_tools_servidor_ver_imagem_devolve_imagem_mcp(monkeypatch, tmp_path):
    from mcp.types import ImageContent
    from simulador import Simulador
    from onenote_mcp import server
    from onenote_mcp.arquivos import Anexo
    from onenote_mcp.formato.escrita import escrever
    from falso import G0
    cfg = tmp_path / "c.toml"
    cfg.write_text('[microsoft]\nclient_id="x"\n', encoding="utf-8")
    monkeypatch.setenv("ONENOTE_MCP_CONFIG", str(cfg))
    e = escrever("![Logo](anexo:1)", [Anexo("l.png", "image/png", PNG, "x", True)])
    on = _on(tmp_path, paginas={"P2": Simulador(guid=G0).pagina(e.html, "Img")})
    rid = re.search(r"recurso:([^)]+)\)", on.ler_pagina("P2")["conteudo"]).group(1)
    on.g.recursos[rid] = PNG
    monkeypatch.setattr(server, "_on", on)
    monkeypatch.setattr(server, "_mtime", cfg.stat().st_mtime)
    r = asyncio.run(server.mcp.call_tool("ver_imagem", {"pagina_id": "P2", "recurso_id": rid}))
    conteudo = r[0] if isinstance(r, tuple) else r
    imgs = [c for c in conteudo if isinstance(c, ImageContent)]
    assert len(imgs) == 1 and imgs[0].mimeType == "image/png"


def test_tools_servidor_editar_e_erro_orientador(monkeypatch, tmp_path):
    from mcp.server.fastmcp.exceptions import ToolError
    from onenote_mcp import server
    cfg = tmp_path / "c.toml"
    cfg.write_text('[microsoft]\nclient_id="x"\n', encoding="utf-8")
    monkeypatch.setenv("ONENOTE_MCP_CONFIG", str(cfg))
    on = _on(tmp_path)
    monkeypatch.setattr(server, "_on", on)
    monkeypatch.setattr(server, "_mtime", cfg.stat().st_mtime)
    r = asyncio.run(server.editar("P1", [server.Troca(antigo="Resumo", novo="Sumário")]))
    assert r["ok"]
    with pytest.raises(ToolError, match="ambíguo"):
        asyncio.run(server.editar("P1", [server.Troca(antigo="R$ 99", novo="x")]))
    with pytest.raises(ToolError, match="não se recria"):
        asyncio.run(server.criar_pagina("S-NOTAS", "x", "![a](recurso:0-x)"))
    with pytest.raises(ToolError, match="pedido recusado"):
        on.g.patch_conteudo = lambda *a, **k: (_ for _ in ()).throw(ValueError("ação recusada: 'delete'"))
        asyncio.run(server.renomear_pagina("P1", "x"))
