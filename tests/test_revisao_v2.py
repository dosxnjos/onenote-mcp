# regressão da revisão adversarial da v2 (15/10/2026): um teste por achado confirmado, que falhava antes da
# correção. Os nomes seguem o prefixo da área (formato/tools/graph/arquivos/sanitiz) para o `pytest -k` do plano
import json
import xml.dom.minidom

import pytest

from falso import BLOCO, G0, GraphFalso, pagina_de
from onenote_mcp import arquivos as A
from onenote_mcp import diario as D
from onenote_mcp.arquivos import ArquivoRecusado, conferir_limites, pastas_validas
from onenote_mcp.config import Config
from onenote_mcp.formato.escrita import ErroFormato, escrever
from onenote_mcp.formato.leitura import ler
from onenote_mcp.graph import ErroGraph, validar_comandos
from onenote_mcp.onenote import ErroEdicao, OneNote
from onenote_mcp.sanitizar import sanitizar
from simulador import simular_saida

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 30
REC = "https://graph.microsoft.com/v1.0/me/onenote/resources/0-abc!1-X/$value"


def _id(tag, n):
    return f"{tag}:{{{G0}}}{{{n}}}"


def _crua(corpo, titulo="t"):
    """página "como o OneNote devolve" montada à mão (para casos que o escritor não gera)"""
    return (f'<html lang="en-US"><head><title>{titulo}</title></head>'
            '<body data-absolute-enabled="true" style="font-family:Calibri;font-size:11pt">'
            f'<div id="{_id("div", 1)}" data-id="_default" style="position:absolute;left:48px;top:120px;'
            f'width:624px">{corpo}</div></body></html>')


def _on(tmp_path, paginas, **cfg):
    g = GraphFalso(paginas=paginas)
    c = Config(client_id="x", permitidos=[f"{BLOCO}/Grupo/Notas"], cache_dir=tmp_path / "cache", **cfg)
    return OneNote(g, c)


def _patches(on):
    return [c for c in on.g.chamadas if c[0] == "PATCH"]


def _sem_envio(on):
    assert _patches(on) == [] and not on.cfg.historico_dir.exists()


# ---------- achado 1: data-id da página reaplicado sem validação, depois do sanitizador ----------
def test_tools_rev_data_id_de_terceiro_nao_injeta_html(tmp_path):
    ruim = ('x&quot;&gt;&lt;img src=&quot;https://evil.example/t.png&quot; '
            'data-render-src=&quot;https://evil.example/r&quot;/&gt;&lt;span x=&quot;')
    on = _on(tmp_path, {"P9": _crua(f'<p id="{_id("p", 12)}" data-id="{ruim}">texto alvo</p>')})
    r = on.editar("P9", [{"antigo": "texto alvo", "novo": "texto novo"}])
    (_, _, cmds, _), = _patches(on)
    assert cmds[0]["content"] == "<p>texto novo</p>"
    assert "evil" not in json.dumps(D.ler(on.cfg.historico_dir, "P9")[0]["itens"][0]["depois"])
    assert any("data-id" in a for a in r["avisos"])


# ---------- achados 2 e 18: editar apagava o que a leitura omitiu dentro do bloco ----------
@pytest.mark.parametrize("corpo,antigo", [
    (f'<p id="{_id("p", 12)}">legenda <img src="{REC}" /> fim</p>', "legenda"),
    (f'<table id="{_id("table", 20)}" style="border:1px solid"><tr id="{_id("tr", 21)}">'
     f'<td id="{_id("td", 22)}"><p>celula A</p></td><td id="{_id("td", 23)}"><p>video</p>'
     '<iframe data-original-src="https://www.youtube.com/watch?v=x"></iframe></td></tr></table>', "celula A"),
    (f'<ul id="{_id("ul", 30)}"><li id="{_id("li", 31)}">item um <img src="{REC}" /></li>'
     f'<li id="{_id("li", 32)}">item dois</li></ul>', "item dois"),
    (f'<ul id="{_id("ul", 30)}"><li id="{_id("li", 31)}">item um<table><tr><td>t</td></tr></table></li>'
     f'<li id="{_id("li", 32)}">item dois</li></ul>', "item dois"),
])
def test_tools_rev_editar_recusa_bloco_com_conteudo_omitido(tmp_path, corpo, antigo):
    on = _on(tmp_path, {"P9": _crua(corpo + f'<p id="{_id("p", 90)}">outro bloco</p>')})
    with pytest.raises(ErroEdicao, match="não representa"):
        on.editar("P9", [{"antigo": antigo, "novo": antigo + " novo"}])
    _sem_envio(on)
    on.editar("P9", [{"antigo": "outro bloco", "novo": "outro bloco editado"}])   # o resto da página edita
    assert len(_patches(on)) == 1


def test_tools_rev_marcar_tarefa_recusa_bloco_com_imagem(tmp_path):
    on = _on(tmp_path, {"P9": _crua(f'<p id="{_id("p", 12)}" data-tag="to-do">ligar <img src="{REC}" /></p>')})
    with pytest.raises(ErroEdicao, match="não representa"):
        on.marcar_tarefa("P9", "ligar")
    _sem_envio(on)


def test_tools_rev_etiqueta_no_span_do_paragrafo_nao_some(tmp_path):
    """vizinho dos achados 2 e 18 (sonda tag_em_span): data-tag num <span> do <p> sumia na leitura e no editar"""
    on = _on(tmp_path, {"P9": _crua(f'<p id="{_id("p", 12)}"><span data-tag="important">item um</span></p>')})
    assert on.ler_pagina("P9")["conteudo"] == "item um {tags=important}"
    on.editar("P9", [{"antigo": "item um", "novo": "item 1"}])
    assert _patches(on)[0][2][0]["content"] == '<p data-tag="important">item 1</p>'


# ---------- achado 3: tabela vazia contava como conteúdo ----------
@pytest.mark.parametrize("novo", ["<tabela>\n<linha>\n<celula></celula>\n</linha>\n</tabela>",
                                  "| |\n| --- |\n| |"])
def test_tools_rev_editar_nao_troca_bloco_por_tabela_vazia(tmp_path, novo):
    on = _on(tmp_path, {"P9": pagina_de("um paragrafo longo e importante\n\noutro")})
    with pytest.raises(ErroEdicao, match="esvaziaria"):
        on.editar("P9", [{"antigo": "um paragrafo longo e importante", "novo": novo}])
    _sem_envio(on)


def test_graph_rev_tabela_vazia_recusada_e_com_imagem_aceita():
    alvo = "p:{" + G0 + "}{1}"
    with pytest.raises(ValueError, match="sem texto"):
        validar_comandos([{"target": alvo, "action": "replace", "content": '<table border="1"><tr><td></td></tr></table>'}])
    validar_comandos([{"target": alvo, "action": "replace",
                       "content": '<table border="0"><tr><td><img src="name:img1" /></td></tr></table>'}])


# ---------- achado 4: caractere invisível passava como texto ----------
@pytest.mark.parametrize("novo", ["​", "﻿", "⁠", "­", "​ 　"])
def test_tools_rev_editar_nao_troca_por_invisivel(tmp_path, novo):
    on = _on(tmp_path, {"P9": pagina_de("um paragrafo longo e importante\n\noutro")})
    with pytest.raises(ErroEdicao, match="esvaziaria"):
        on.editar("P9", [{"antigo": "um paragrafo longo e importante", "novo": novo}])
    _sem_envio(on)


@pytest.mark.parametrize("conteudo", ["<p>​</p>", "<p>&#8203;</p>", "<p>&#x200B;</p>", "<p>﻿&nbsp;</p>"])
def test_graph_rev_invisivel_recusado(conteudo):
    with pytest.raises(ValueError, match="sem texto"):
        validar_comandos([{"target": "p:{" + G0 + "}{1}", "action": "replace", "content": conteudo}])


def test_tools_rev_renomear_invisivel_recusado(tmp_path):
    on = _on(tmp_path, {"P9": pagina_de("x")})
    with pytest.raises(ErroEdicao, match="vazio"):
        on.renomear_pagina("P9", "​﻿")
    _sem_envio(on)


# ---------- achado 5: atributo de terceiro (href, fonte, tag) virava estrutura ONMD ----------
def test_formato_rev_href_com_quebra_de_linha_nao_vira_bloco():
    h = _crua('<p><a href="https://a.example/&#10;# TITULO INJETADO&#10;&lt;anexo n=1/&gt;&#10;">clique</a> '
              "resto aqui</p>")
    o = ler(h).onmd
    assert "\n" not in o and o.startswith("[clique](https://a.example/") and o.endswith(") resto aqui")
    e = escrever(o)   # antes: ErroFormato "anexo:1 não existe" (a linha injetada virava referência viva)
    assert e.partes == [] and "<h1" not in e.html and e.html.count("<p>") == 1


def test_formato_rev_fonte_com_quebra_de_linha_nao_vira_bloco():
    h = _crua('<p><span style="font-family:Calibri">texto comum bem longo para dominar a página</span></p>'
              '<p>meio <span style="font-family:Arial&#10;&lt;secao id=x&gt;&#10;&lt;destaque&gt;">xx</span> fim</p>'
              '<p><span style="font-family:Arial&#10;&lt;secao id=y&gt;">bloco inteiro</span></p>')
    lt = ler(h, incluir_ids=True)
    assert "\n<" not in lt.onmd and "secao" not in lt.onmd and "destaque" not in lt.onmd
    html = escrever(lt.onmd).html
    assert "data-id" not in html and "<table" not in html and "<div" not in html
    assert any("fonte" in a for a in lt.avisos)


def test_formato_rev_fonte_dominante_fora_do_padrao_nao_quebra_a_escrita():
    h = _crua('<p><span style="font-family:Meu Font!&#10;x">bastante texto aqui</span></p>')
    lt = ler(h)
    assert lt.fonte is None
    escrever("novo", fonte_padrao=lt.fonte)   # antes: fonte_padrao inválida → ErroFormato em todo acrescentar


def test_formato_rev_lista_de_fontes_vira_a_primeira():
    lt = ler(_crua('<p><span style="font-family:\'Segoe UI\', sans-serif">texto longo da página</span></p>'))
    assert lt.fonte == "Segoe UI"


def test_formato_rev_id_e_etiqueta_de_terceiro_fora_do_padrao_omitidos():
    h = _crua('<p data-id="a b}&#10;&lt;destaque&gt;">x</p>'
              '<p data-tag="important}&#10;&lt;secao id=z&gt;">y</p><p data-tag="idea">z</p>')
    o = ler(h, incluir_ids=True).onmd
    assert o == "x\n\ny\n\nz {tags=idea}"


def test_formato_rev_nome_de_anexo_com_quebra_de_linha():
    h = _crua('<object data="https://graph.microsoft.com/v1.0/me/onenote/resources/0-a!1-B/$value" '
              'data-attachment="a.pdf&#10;&lt;destaque&gt;" type="application/pdf" />')
    o = ler(h).onmd
    assert "\n" not in o and "<destaque" not in o and o.startswith('<anexo recurso="0-a!1-B"')


# ---------- achado 6: linha ```` dentro do código fechava a cerca ----------
def test_formato_rev_cerca_do_codigo_maior_que_qualquer_crase():
    x = "`````\na ```` b\n````\n## injetado\n[l](https://phish.example)\n`````"
    e = escrever(x)
    lido = ler(simular_saida(e.html)).onmd
    assert lido == x
    de_novo = escrever(lido)
    assert de_novo.html == e.html and "<h2" not in de_novo.html and "<a " not in de_novo.html


@pytest.mark.parametrize("linha", ["```", "````", "`````"])
def test_formato_rev_codigo_com_crases_ida_e_volta(linha):
    corpo = f"x\n{linha}\ny"
    e = escrever(f"``````\n{corpo}\n``````")
    lido = ler(simular_saida(e.html)).onmd
    assert escrever(lido).html == e.html


# ---------- achado 7: pasta acima da home e AppData valiam como pasta de anexos ----------
def test_arquivos_rev_pasta_acima_da_home_e_appdata_recusadas(tmp_path, monkeypatch):
    home = tmp_path / "usuarios" / "fulano"
    for p in ("AppData/Local/onenote-mcp", "AppData/Roaming", "anexos", "Documentos"):
        (home / p).mkdir(parents=True)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("LOCALAPPDATA", str(home / "AppData" / "Local"))
    for ruim in (tmp_path / "usuarios", tmp_path, home, home / "AppData", home / "AppData" / "Local",
                 home / "AppData" / "Roaming", home / "AppData" / "Local" / "onenote-mcp"):
        assert pastas_validas([str(ruim)]) == [], ruim
    assert pastas_validas([str(home / "anexos")]) == [(home / "anexos").resolve()]
    cache = home / "Documentos" / "cache"
    cache.mkdir()
    assert pastas_validas([str(home / "Documentos")], protegidas=[cache]) == []


# ---------- achado 8: lista de anexos sem teto, tudo lido antes de conferir ----------
def test_tools_rev_anexos_demais_recusados_antes_de_ler_disco(tmp_path, monkeypatch):
    pasta = tmp_path / "anexos"
    pasta.mkdir()
    (pasta / "a.png").write_bytes(PNG)
    on = _on(tmp_path, {"P9": pagina_de("x")}, pastas_arquivos=[str(pasta)])
    lidos = []
    original = A.carregar
    monkeypatch.setattr(A, "carregar", lambda *a, **k: lidos.append(1) or original(*a, **k))
    with pytest.raises(ErroEdicao, match="anexos"):
        on.acrescentar("P9", "texto\n\n![x](anexo:1)", anexos=[{"caminho": str(pasta / "a.png")}] * 200)
    assert lidos == [] and _patches(on) == []
    on.acrescentar("P9", "texto\n\n![x](anexo:1)", anexos=[{"caminho": str(pasta / "a.png")}] * 3)
    assert len(lidos) == 1   # só o anexo citado é lido do disco


# ---------- achado 9: | dentro de código em célula GFM cortava a célula ----------
def test_formato_rev_pipe_em_codigo_de_celula_gfm():
    h = _crua('<table style="border:1px solid"><tr><td><span style="font-weight:bold">H</span></td></tr>'
              '<tr><td><span style="font-family:Consolas;font-size:10pt">a|b</span></td></tr></table>')
    o = ler(h).onmd
    assert o == "| H |\n| --- |\n| `a\\|b` |"
    e = escrever(o)
    assert e.avisos == [] and '<span style="font-family:Consolas;font-size:10pt">a|b</span>' in e.html


def test_formato_rev_linha_gfm_com_celula_a_mais():
    with pytest.raises(ErroFormato, match="células"):
        escrever("| a |\n| --- |\n| x | y |")
    assert escrever("| a |\n| --- |\n| x | |").html == '<table border="1"><tr><td><b>a</b></td></tr><tr><td>x</td></tr></table>'


# ---------- achado 10: caractere de controle chegava ao XHTML ----------
@pytest.mark.parametrize("c", ["\x0b", "\x00", "\x0c", "\x1f", "￾"])
def test_formato_rev_caractere_de_controle_sai_do_html(c):
    e = escrever(f"ctrl {c} vt")
    xml.dom.minidom.parseString(f"<body>{e.html}</body>")
    assert c not in e.html and any("controle" in a for a in e.avisos)
    limpo, avisos = sanitizar(f"<p>a{c}b</p>")
    assert limpo == "<p>ab</p>" and any("controle" in a for a in avisos)


def test_tools_rev_titulo_sem_caractere_de_controle(tmp_path):
    on = _on(tmp_path, {"P9": pagina_de("x")})
    on.criar_pagina("S-NOTAS", "Título\x00 com\x0b controle", "corpo")
    html = on.g.chamadas[-1][2]
    assert "\x00" not in html and "\x0b" not in html and "<title>Título com controle</title>" in html
    on.renomear_pagina("P9", "novo\x01 nome")
    assert _patches(on)[0][2][0]["content"] == "novo nome"


# ---------- achado 11: etiqueta em sub-item ficava dentro de <ul> e se perdia ----------
def test_formato_rev_etiqueta_em_sub_item_recusada():
    with pytest.raises(ErroFormato, match="sub-item"):
        escrever("- pai\n  - filho {tags=important}\n- pai B")
    with pytest.raises(ErroFormato, match="sub-item"):   # 1º item mais recuado: c ainda é sub-item de b
        escrever("  - a\n- b\n  - c {tags=important}")
    with pytest.raises(ErroFormato, match="sub-item"):   # neto também conta
        escrever("- a\n  - b\n    - c {tags=important}")
    e = escrever("- x {tags=important}\n- y")
    assert e.html == '<li data-tag="important">x</li><li>y</li>' and any("soltos" in a for a in e.avisos)


# ---------- achado 12: <li> solto (o OneNote embrulharia num ul) era lido como parágrafo grudado ----------
def test_formato_rev_li_solto_lido_como_lista():
    lt = ler(_crua('<li data-tag="important">x</li><li>y</li><p>depois</p>'))
    assert lt.onmd == "- x {tags=important}\n- y\n\ndepois"
    assert lt.blocos[0].tipo == "lista" and lt.blocos[0].id_gerado is None   # sem id: não é alvo de editar


# ---------- achado 13: U+FFFC literal no ONMD ----------
def test_formato_rev_fffc_vira_quebra_de_linha():
    from pathlib import Path
    fx = Path(__file__).parent / "fixtures"
    for nome in ("sonda-1-criada.html", "sonda-2-editada.html"):
        assert "￼" not in ler((fx / nome).read_text(encoding="utf-8")).onmd
    o = ler(_crua("<p>def f():￼return 1</p>")).onmd
    assert o == "def f():<br>return 1"
    assert escrever(o).html == "<p>def f():<br />return 1</p>"


# ---------- achado 14: link com ) na URL era truncado ----------
@pytest.mark.parametrize("url", ["https://ex.com/a_(b)", "https://en.wikipedia.org/wiki/Python_(programming_language)"])
def test_formato_rev_link_com_parenteses(url):
    assert escrever(f"[x]({url}) e mais").html == f'<p><a href="{url}">x</a> e mais</p>'
    o = ler(_crua(f'<p><a href="{url}">x</a> fim</p>')).onmd
    assert escrever(o).html.startswith("<p><a href=") and "</a> fim</p>" in escrever(o).html
    assert ler(simular_saida(escrever(o).html)).onmd == o


# ---------- achado 15: lista numerada perdia o número inicial sem aviso ----------
def test_formato_rev_lista_que_nao_comeca_em_1_avisa():
    assert any("começa em 3" in a for a in escrever("3. tres\n4. quatro").avisos)
    assert escrever("1. um\n2. dois").avisos == []
    assert escrever("a. um\nb. dois").avisos == []


# ---------- achado 16: parágrafo "Ok." engolido por lista de letras ----------
def test_formato_rev_lista_de_letras_so_aceita_o_mesmo_tipo():
    e = escrever("a. alfa\nb. beta\nOk. texto")
    assert e.html.endswith("</ol><p>Ok. texto</p>")
    assert escrever("a. alfa\nb. beta\n\nEu. sei").html.endswith("</ol><p>Eu. sei</p>")
    e = escrever("i. um\nii. dois\niii. tres\niv. quatro")
    assert e.html.count("<li") == 4 and e.html.startswith('<ol style="list-style-type:lower-roman">')
    assert escrever("a. x\nb. y\nc. z").html.count("<li") == 3


# ---------- achado 17: tabela GFM com canto vazio no cabeçalho ----------
@pytest.mark.parametrize("x", ["| | Q1 |\n| --- | --- |\n| a | 1 |", "| | |\n| --- | --- |\n| a | 1 |"])
def test_formato_rev_gfm_com_cabecalho_vazio_volta_igual(x):
    assert ler(simular_saida(escrever(x).html)).onmd == x


# ---------- achado 19: duas trocas no mesmo bloco ----------
def test_tools_rev_trocas_valem_sobre_o_texto_lido(tmp_path):
    on = _on(tmp_path, {"P9": pagina_de("# T\n\nY e X\n\noutro")})
    on.editar("P9", [{"antigo": "Y", "novo": "X"}, {"antigo": "X", "novo": "Z"}])
    assert ler(on.g._saida("P9")).onmd == "# T\n\nX e Z\n\noutro"


def test_tools_rev_trocas_sobrepostas_recusadas(tmp_path):
    on = _on(tmp_path, {"P9": pagina_de("# T\n\nY e X\n\noutro")})
    with pytest.raises(ErroEdicao, match="sobrep"):
        on.editar("P9", [{"antigo": "Y e", "novo": "A"}, {"antigo": "e X", "novo": "B"}])
    _sem_envio(on)


# ---------- achado 20: _reaplicar_id incondicional ----------
def test_tools_rev_troca_de_linguagem_do_codigo(tmp_path):
    on = _on(tmp_path, {"P9": pagina_de("```py\nx = 1\n```")})
    on.editar("P9", [{"antigo": "```py", "novo": "```js"}])
    assert 'data-id="on-cod-1-js"' in _patches(on)[0][2][0]["content"]
    assert ler(on.g._saida("P9")).onmd == "```js\nx = 1\n```"


def test_tools_rev_troca_de_forma_e_de_id(tmp_path):
    on = _on(tmp_path, {"P9": pagina_de("abc {id=x}\n\ndef {id=velho}")})
    on.editar("P9", [{"antigo": "abc {id=x}", "novo": "<destaque cor=azul>\nabc\n</destaque>"},
                     {"antigo": "def {id=velho}", "novo": "def {id=novo}"}])
    o = ler(on.g._saida("P9"), incluir_ids=True).onmd
    assert o == "<destaque cor=azul>\nabc\n</destaque>\n\ndef {id=novo}"


def test_tools_rev_lista_sem_id_no_texto_mantem_o_data_id_do_ul(tmp_path):
    corpo = (f'<ul id="{_id("ul", 30)}" data-id="compras"><li id="{_id("li", 31)}">a</li>'
             f'<li id="{_id("li", 32)}">b</li></ul>')
    on = _on(tmp_path, {"P9": _crua(corpo)})
    on.editar("P9", [{"antigo": "- b", "novo": "- c"}])
    assert _patches(on)[0][2][0]["content"].startswith('<ul data-id="compras">')


# ---------- achado 21: data-id repetido ----------
def test_formato_rev_id_repetido_recusado():
    with pytest.raises(ErroFormato, match="repetido|já existe"):
        escrever("p1 {id=b}\n\np2 {id=b}")
    with pytest.raises(ErroFormato, match="já existe"):
        escrever("<secao id=resumo>\nz\n</secao>", ids_existentes={"resumo"})


def test_tools_rev_secao_repetida_na_pagina_recusa_alvo(tmp_path):
    corpo = (f'<div id="{_id("div", 2)}" data-id="resumo"><p id="{_id("p", 3)}">a</p></div>'
             f'<div id="{_id("div", 4)}" data-id="resumo"><p id="{_id("p", 5)}">b</p></div>')
    on = _on(tmp_path, {"P9": _crua(corpo)})
    with pytest.raises(ErroEdicao, match="mais de um"):
        on.acrescentar("P9", "x", onde="#resumo")
    with pytest.raises(ErroEdicao, match="mais de um"):
        on.inserir("P9", "#resumo", "x")
    with pytest.raises(ErroFormato, match="já existe"):
        _on(tmp_path, {"P8": pagina_de("<secao id=resumo>\na\n</secao>")}).acrescentar(
            "P8", "<secao id=resumo>\nb\n</secao>")
    assert _patches(on) == []


# ---------- achado 22: diário gravava troca que a validação local recusaria ----------
@pytest.mark.parametrize("novo", ["<u> </u>", "<span cor=azul> </span>"])
def test_tools_rev_diario_so_depois_da_validacao(tmp_path, novo):
    on = _on(tmp_path, {"P9": pagina_de("abc\n\noutro")})
    with pytest.raises(ErroEdicao, match="esvaziaria"):
        on.editar("P9", [{"antigo": "abc", "novo": novo}])
    _sem_envio(on)


def test_tools_rev_diario_valida_antes_de_gravar(tmp_path, monkeypatch):
    from onenote_mcp import onenote as O
    on = _on(tmp_path, {"P9": pagina_de("abc\n\noutro")})
    monkeypatch.setattr(O, "validar_comandos", lambda c: (_ for _ in ()).throw(ValueError("recusado")))
    with pytest.raises(ValueError):
        on.editar("P9", [{"antigo": "abc", "novo": "abd"}])
    with pytest.raises(ValueError):
        on.renomear_pagina("P9", "novo")
    _sem_envio(on)


# ---------- achado 23: diário guardava o "depois" com etiqueta password ----------
def test_tools_rev_diario_omite_password_no_depois(tmp_path):
    pasta = tmp_path / "h"
    D.gravar(pasta, "P", "editar", [{"alvo": "p:1", "antes": "<p>abc</p>",
                                      "depois": '<p data-tag="password">minha senha 1234</p>'}])
    (l,) = D.ler(pasta, "P")
    assert "1234" not in json.dumps(l) and "omitido" in l["itens"][0]["depois"]


# ---------- achado 24: <br /> dentro de <p> virava espaço e sumia no replace ----------
@pytest.mark.parametrize("br", ["<br />", "<br/>", "<br>"])
def test_tools_rev_quebra_de_linha_no_paragrafo_sobrevive_ao_editar(tmp_path, br):
    on = _on(tmp_path, {"P9": _crua(f'<p id="{_id("p", 12)}">linha um{br}linha dois</p>')})
    assert on.ler_pagina("P9")["conteudo"] == "linha um<br>linha dois"
    on.editar("P9", [{"antigo": "linha um", "novo": "linha 1"}])
    assert _patches(on)[0][2][0]["content"] == "<p>linha 1<br />linha dois</p>"


# ---------- prova real 15/10: parágrafo logo antes de lista cai para depois dela ao ser regravado ----------
def test_tools_real_paragrafo_antes_de_lista_recusado(tmp_path):
    corpo = (f'<p id="{_id("p", 10)}">já dá:</p><br />'
             f'<ol id="{_id("ol", 8)}"><li id="{_id("li", 11)}">um</li></ol>'
             f'<p id="{_id("p", 12)}">depois</p>')
    on = _on(tmp_path, {"P9": _crua(corpo)})
    with pytest.raises(ErroEdicao, match="logo antes de uma lista"):
        on.editar("P9", [{"antigo": "já dá:", "novo": "já dá agora:"}])
    assert not _patches(on)
    on.editar("P9", [{"antigo": "depois", "novo": "no fim"}, {"antigo": "um", "novo": "item um"}])
    assert len(_patches(on)[0][2]) == 2


# ---------- achado 25: data-id de <li>/<p> de célula se perdia ao editar pelo ONMD sem ids ----------
def test_tools_rev_data_id_interno_sobrevive_ao_editar(tmp_path):
    corpo = (f'<ul id="{_id("ul", 30)}"><li id="{_id("li", 31)}" data-id="alvo">item um</li>'
             f'<li id="{_id("li", 32)}">item dois</li></ul>'
             f'<table id="{_id("table", 40)}" style="border:1px solid"><tr id="{_id("tr", 41)}">'
             f'<td id="{_id("td", 42)}"><p id="{_id("p", 43)}" data-id="cel">celula A</p></td>'
             f'<td id="{_id("td", 44)}"><p id="{_id("p", 45)}">celula B</p></td></tr></table>')
    on = _on(tmp_path, {"P9": _crua(corpo)})
    on.editar("P9", [{"antigo": "item um", "novo": "item 1"}, {"antigo": "celula A", "novo": "celula Z"}])
    lista, tabela = (c["content"] for c in _patches(on)[0][2])
    assert '<li data-id="alvo">item 1</li>' in lista and '<p data-id="cel">celula Z</p>' in tabela
    o = ler(on.g._saida("P9"), incluir_ids=True).onmd
    assert "- item 1 {id=alvo}" in o and "celula Z {id=cel}" in o


# ---------- achado 26: teto de 3,5 MB não contava o HTML ----------
def test_arquivos_rev_teto_conta_o_html():
    partes = [("img1", "image/png", b"x" * int(3.4 * 2**20))]
    conferir_limites(partes, 3.5)
    with pytest.raises(ArquivoRecusado, match="MB"):
        conferir_limites(partes, 3.5, "a" * 700_000)
    with pytest.raises(ArquivoRecusado, match="MB"):
        conferir_limites([], 3.5, "a" * int(3.6 * 2**20))


# ---------- achado 27: dicas de erro do Graph sem teste ----------
@pytest.mark.parametrize("status,codigo,dica", [
    (403, "10004", "protegida por senha"), (507, "", "seção está cheia"), (400, "30102", "seção está cheia"),
    (400, "20117", "já existe um item com esse nome"), (403, "", "só como leitura"),
    (504, "", "sendo montada"),
    (404, "20102", "até 1 min para montá-la.*travou do lado da Microsoft: crie de novo"),
])
def test_tools_rev_dicas_de_erro_do_graph(status, codigo, dica):
    from mcp.server.fastmcp.exceptions import ToolError
    from onenote_mcp import server

    def falha():
        raise ErroGraph(status, "m", codigo)
    with pytest.raises(ToolError, match=dica):
        server._executar(falha)


# ---------- prova real 15/10 (passo 7, vitrine): o OneNote devolve <br />\n\ntexto dentro do <p> ----------
def test_formato_real_quebra_de_linha_sem_espaco_fantasma():
    # medido: "Linha um<br />\n\nlinha dois\t\t\t</p>"; a quebra de formatação virava espaço no ONMD
    # ("<br> linha dois") e cada regravação somava um espaço no começo da linha
    h = _crua('<p id="p:{1}{2}">Linha um<br />\n\nlinha dois\t\t\t</p>'
              '<p id="p:{1}{3}"><span style="font-weight:bold">a</span><br />\n\t<span>b</span></p>')
    assert ler(h).onmd == "Linha um<br>linha dois\n\n**a**<br>b"
    x = "Linha um<br>linha dois"
    assert ler(simular_saida(escrever(x).html)).onmd == x
    # espaço que é do texto (sem quebra de formatação) continua
    assert ler(_crua("<p>a<br /> b</p>")).onmd == "a<br> b"


# ---------- prova real 15/10 (passo 7): <li> solto vem embrulhado num <ul>/<ol> com id, etiqueta no span ----------
def test_formato_real_lista_com_etiqueta_volta_embrulhada_e_editavel():
    x = "- x {tags=important}\n- y"
    lt = ler(simular_saida(escrever(x).html))
    assert lt.onmd == x
    assert lt.blocos[0].tipo == "lista" and lt.blocos[0].id_gerado and lt.blocos[0].id_gerado.startswith("ul:")
    # o tipo da lista ordenada fica no <li> e o OneNote embrulha num <ol> (medido no PATCH de "a. alfa")
    x2 = "a. alfa {tags=important}\nb. beta"
    lt2 = ler(simular_saida(escrever(x2).html))
    assert lt2.onmd == x2 and lt2.blocos[0].id_gerado.startswith("ol:")
