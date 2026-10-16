# passo 4: formato/ (escrita, leitura, paleta, spec). Prova: 1 teste de ouro por construção, HTML gerado passa
# no xml.dom.minidom, e ida e volta ler(simular_saida(escrever(x))) == x na vitrine
import xml.dom.minidom
from pathlib import Path

import pytest

from onenote_mcp.arquivos import Anexo
from onenote_mcp.formato import ler_spec, paleta
from onenote_mcp.formato.escrita import AVISO_SUBITEM, ErroFormato, escrever
from onenote_mcp.formato.leitura import ler
from onenote_mcp.sanitizar import sanitizar
from simulador import simular_saida

AQUI = Path(__file__).parent
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20
CODE = 'style="font-family:Consolas;font-size:10pt"'

OURO = [
    ("# T {id=topo cor=azul}", '<h1 data-id="topo" style="color:#2E75B6">T</h1>'),
    ("###### seis", "<h6>seis</h6>"),
    ("texto", "<p>texto</p>"),
    ("um\ndois", "<p>um</p><p>dois</p>"),
    ("x {fundo=amarelo fonte=\"Segoe UI\" tamanho=14 alinhar=centro}",
     '<p style="background-color:#FFF2CC;font-family:Segoe UI;font-size:14pt;text-align:center">x</p>'),
    ("x {tags=important,idea}", '<p data-tag="important, idea">x</p>'),
    ("---", f'<p style="color:#BFBFBF">{"─" * 32}</p>'),
    ("> a\n> b", '<p data-id="on-cit-1-1" style="color:#595959"><i>a</i></p>'
                 '<p data-id="on-cit-1-2" style="color:#595959"><i>b</i></p>'),
    ("```py\na  b\n\n```", '<table border="0" style="width:624px" data-id="on-cod-1-py"><tr>'
                           f'<td style="background-color:#F3F3F3"><p {CODE}>a\xa0\xa0b</p><p {CODE}>\xa0</p>'
                           "</td></tr></table>"),
    ("- a\n  - b\n- c", "<ul><li>a<ul><li>b</li></ul></li><li>c</li></ul>"),
    ("1. a\n2. b", "<ol><li>a</li><li>b</li></ol>"),
    ("a. x\nb. y", '<ol style="list-style-type:lower-alpha"><li style="list-style-type:lower-alpha">x</li>'
                   '<li style="list-style-type:lower-alpha">y</li></ol>'),
    ("I. x", '<ol style="list-style-type:upper-roman"><li style="list-style-type:upper-roman">x</li></ol>'),
    ("- x {marcador=circulo}", '<ul style="list-style-type:circle"><li style="list-style-type:circle">x</li></ul>'),
    ("- x {cor=verde}", '<ul><li style="color:#548235">x</li></ul>'),
    ("- x {tags=important}\n- y", '<li data-tag="important">x</li><li>y</li>'),
    ("- [ ] a", '<p data-tag="to-do">a</p>'),
    ("- [x] a {tags=important}", '<p data-tag="to-do:completed, important">a</p>'),
    ("- [x] ligar {tags=schedule-meeting}", '<p data-tag="schedule-meeting:completed">ligar</p>'),
    ("| a | b |\n| :-: | --: |\n| 1 | 2 |",
     '<table border="1"><tr><td style="text-align:center"><b>a</b></td><td style="text-align:right"><b>b</b></td>'
     '</tr><tr><td style="text-align:center">1</td><td style="text-align:right">2</td></tr></table>'),
    ('<destaque cor=verde icone="✅">\nfeito\n</destaque>',
     '<table border="0" style="width:624px" data-id="on-dst-1"><tr><td style="background-color:#E2EFDA">✅ feito'
     "</td></tr></table>"),
    ("<destaque>\n- a\n- b\n</destaque>",
     '<table border="0" style="width:624px" data-id="on-dst-1"><tr><td style="background-color:#FFF2CC">'
     "<ul><li>a</li><li>b</li></ul></td></tr></table>"),
    ("<colunas>\n<coluna largura=25%>a</coluna>\n<coluna>b</coluna>\n</colunas>",
     '<table border="0" style="width:624px" data-id="on-col-1"><tr><td style="width:156px">a</td>'
     '<td style="width:468px">b</td></tr></table>'),
    ("<tabela borda=0 largura=50% id=t1>\n<linha fundo=cinza>\n<celula largura=10% alinhar=direita>x</celula>\n"
     "<celula fundo=rosa>y</celula>\n</linha>\n</tabela>",
     '<table border="0" style="width:312px" data-id="t1"><tr>'
     '<td style="width:62px;background-color:#EDEDED;text-align:right">x</td>'
     '<td style="background-color:#FADBE7">y</td></tr></table>'),
    ("<tabela>\n<linha>\n<celula>\n- a\n- b\n</celula>\n</linha>\n</tabela>",
     '<table border="1" data-id="on-tab-1"><tr><td><ul><li>a</li><li>b</li></ul></td></tr></table>'),
    ("<secao id=resumo>\nx\n</secao>", '<div data-id="resumo"><p>x</p></div>'),
    ("**b** *i* ~~d~~ <u>u</u> ==r== `c` x<sup>2</sup>H<sub>2</sub>",
     '<p><b>b</b> <i>i</i> <del>d</del> <u>u</u> <span style="background-color:#FFFF00">r</span> '
     f"<span {CODE}>c</span> x<sup>2</sup>H<sub>2</sub></p>"),
    ("<span cor=vermelho fundo=amarelo fonte=\"Segoe UI Black\" tamanho=16>x</span>",
     '<p><span style="color:#C00000;background-color:#FFF2CC;font-family:Segoe UI Black;font-size:16pt">x</span></p>'),
    ("[a](https://x.com/?q=1&b=2) [b](onenote:https://d.docs.live.net/y)",
     '<p><a href="https://x.com/?q=1&amp;b=2">a</a> <a href="onenote:https://d.docs.live.net/y">b</a></p>'),
    ("\\*não\\* \\<u> \\{x=1} 1\\. a", "<p>*não* &lt;u&gt; {x=1} 1. a</p>"),
    ("\\# não é título", "<p># não é título</p>"),
    ("**negrito *e itálico***", "<p><b>negrito <i>e itálico</i></b></p>"),
    ("2*3*4 e a * b", "<p>2<i>3</i>4 e a * b</p>"),
]


@pytest.mark.parametrize("onmd,html", OURO)
def test_formato_ouro(onmd, html):
    e = escrever(onmd)
    assert e.html == html
    xml.dom.minidom.parseString(f"<body>{e.html}</body>")
    limpo, avisos = sanitizar(e.html)
    assert limpo == e.html, avisos   # o sanitizador não mexe no que a spec gera


def _anexos():
    return [Anexo("logo.png", "image/png", PNG, "C:/x/logo.png", True),
            Anexo("Plano.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK\x03\x04",
                  "C:/x/Plano.xlsx", False)]


def test_formato_imagem_e_anexo_por_parametro():
    e = escrever('![Logo](anexo:1){largura=50% id=logo tags=important}\n<anexo n=2 nome="Plano 2026.xlsx"/>',
                 _anexos())
    assert e.html == ('<img src="name:img1" alt="Logo" width="312" data-id="logo" data-tag="important" />'
                      '<object data="name:arq2" data-attachment="Plano 2026.xlsx" '
                      'type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" />')
    assert [p[0] for p in e.partes] == ["img1", "arq2"] and e.partes[0][2] == PNG
    assert sanitizar(e.html, ["img1", "arq2"])[0] == e.html
    assert any("largura de imagem" in a for a in e.avisos)


def test_formato_imagem_sem_largura_nao_avisa():
    e = escrever("![Logo](anexo:1)", _anexos()[:1])
    assert not any("largura" in a for a in e.avisos)


@pytest.mark.parametrize("onmd,msg", [
    ("![x](recurso:0-abc!1-X)", "não se recria"),
    ('<anexo recurso="0-abc" nome="a.pdf"/>', "não se recria"),
    ("![x](https://atacante/x.png)", "anexo:N"),
    ("![x](arquivo:C:/Users/x/segredo.png)", "anexo:N"),
    ("![x](C:/foto.png)", "anexo:N"),
    ("![x](anexo:3)", "não existe"),
    ("texto ![x](anexo:1) no meio", "sozinha"),
    ("<anexo n=1/>", "é imagem"),
    ("![x](anexo:2)", "não é imagem"),
    ("x {cor=fucsia}", "cor desconhecida"),
    ("<colunas>\n</colunas>", "coluna"),
    ("<tabela largura=300%>\n<linha><celula>x</celula></linha>\n</tabela>", "largura"),
])
def test_formato_erro_orientador(onmd, msg):
    with pytest.raises(ErroFormato, match=msg):
        escrever(onmd, _anexos())


def test_formato_avisos_de_perdas():
    e = escrever("x {tags=definition}\n\n- [ ] y {tags=call-back}\n\n<caixa x=1>z</caixa>\n\nw {foo=1}")
    texto = " ".join(e.avisos)
    for t in ("remember-for-later", "call-back", "caixa", "foo"):
        assert t in texto
    assert 'data-tag="to-do"' in e.html and "<p>z</p>" in e.html


def test_formato_id_reservado_e_anexo_nao_citado():
    e = escrever("x {id=on-dst-9}", _anexos())
    assert "data-id" not in e.html and any("reservado" in a for a in e.avisos)
    assert any("anexo:1 não foi citado" in a for a in e.avisos)


def test_formato_pagina_link_resolvido_pela_lista():
    e = escrever("[ver](pagina:P9)", resolver_pagina=lambda pid: f"onenote:https://d/{pid}")
    assert e.html == '<p><a href="onenote:https://d/P9">ver</a></p>'


def test_formato_ids_reservados_continuam_a_contagem():
    e = escrever("> a", ids_existentes={"on-cit-4-1", "on-dst-2"})
    assert 'data-id="on-cit-5-1"' in e.html


def test_formato_fonte_padrao_so_em_paragrafo_e_item():
    e = escrever("# t\n\np\n\n- i", fonte_padrao="Segoe UI")
    assert e.html == ('<h1>t</h1><p style="font-family:Segoe UI">p</p>'
                      '<ul><li style="font-family:Segoe UI">i</li></ul>')


# ---------- paleta ----------
def test_formato_paleta():
    assert paleta.cor_texto("azul") == "#2E75B6" and paleta.cor_fundo("azul") == "#DDEBF7"
    assert paleta.cor_texto("#abcdef") == "#ABCDEF"
    assert paleta.nome_texto("#c00000") == "vermelho" and paleta.nome_fundo("#fff2cc") == "amarelo"
    assert paleta.nome_texto("red") == "#ff0000" and paleta.para_hex("yellow") == paleta.REALCE
    with pytest.raises(paleta.CorInvalida):
        paleta.cor_texto("url(x)")


# ---------- leitura ----------
def test_formato_leitura_da_pagina_real_da_sondagem():
    """HTML devolvido pela Microsoft na sondagem (provas-v2), com o e-mail trocado por me"""
    lt = ler((AQUI / "fixtures" / "sonda-1-criada.html").read_text(encoding="utf-8"), incluir_ids=True)
    o = lt.onmd
    assert lt.fonte == "Segoe UI" and "Segoe" not in o and "Calibri" not in o
    for esperado in [
        "# Título 1 {id=t1}\n\n## Título 2\n\n### Título 3\n\n#### Título 4\n\n##### Título 5\n\n###### Título 6",
        "parágrafo com <span cor=vermelho>vermelho</span>, ==realce==, `codigo`, "
        "<span cor=#ff0000 tamanho=12>16px red</span>, <u>sub</u> ~~riscado~~ ~~strike~~ <sup>2</sup> cit {id=par1}",
        "- pai A\n  - filho A1\n    - neto\n- pai B",
        "a. alfa\nb. beta",
        "- [ ] tarefa aberta\n- [x] tarefa feita",
        "importante+ideia {tags=important,idea}",
        "definicao {tags=remember-for-later}",
        "<secao id=secaoA>\ndentro da secao A\n</secao>",
        "[link onenote](onenote:https://d.docs.live.net/teste) e [link web](https://example.com)",
        "\n\n---\n\n",
        "![quadrado](recurso:0-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!1-AAAAAAAAAAAAAAAA!sbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb)"
        "{id=img1}",
    ]:
        assert esperado in o, esperado
    assert "users(" not in o and "graph.microsoft.com" not in o
    assert lt.secoes == ["secaoA"] and lt.ultima_div.startswith("div:{00000000-0000-4000-8000-0000000000a1}")
    tipos = [b.tipo for b in lt.blocos]
    assert tipos.count("tit") == 6 and tipos.count("lista") == 2 and tipos.count("tabela") == 3
    assert all(b.id_gerado for b in lt.blocos)


def test_formato_leitura_ids_mudam_depois_do_patch():
    lt = ler((AQUI / "fixtures" / "sonda-2-editada.html").read_text(encoding="utf-8"), incluir_ids=True)
    assert "inserido depois do t1" in lt.onmd and "parágrafo trocado {id=par1}" in lt.onmd
    assert "<secao id=secaoA>\ndentro da secao A\n\napendado na secao A\n</secao>" in lt.onmd
    par1 = next(b for b in lt.blocos if b.data_id == "par1")
    assert par1.id_gerado == "p:{00000000-0000-4000-8000-0000000000a2}{14}"


def test_formato_leitura_escapa_sintaxe_de_terceiro():
    """texto de página alheia que parece ONMD volta escapado: reescrever não vira comando nem anexo"""
    h = ('<html><body><div><p>![x](anexo:1) &lt;destaque&gt; {id=x} **a** `b`</p><p>- [ ] não é tarefa</p>'
         "<p># nem título</p><p>1. nem lista</p><p>&gt; nem citação</p></div></body></html>")
    o = ler(h).onmd
    assert o == ("!\\[x](anexo:1) \\<destaque> \\{id=x} \\*\\*a\\*\\* \\`b\\`\n\n\\- \\[ ] não é tarefa\n\n"
                 "\\# nem título\n\n1\\. nem lista\n\n\\> nem citação")
    e = escrever(o)
    assert e.partes == [] and "<img" not in e.html and "data-tag" not in e.html and "<h1" not in e.html
    assert ler(simular_saida(e.html)).onmd == o


@pytest.mark.parametrize("dentro,esperado", [
    ('a<span style="font-weight:bold"> </span>b', "a b"),
    ('a<span style="font-weight:bold"> x </span>b', "a **x** b"),
    ('<span style="font-style:italic">a </span><span style="font-style:italic;font-weight:bold">b</span>',
     "*a* ***b***"),
])
def test_formato_leitura_espaco_na_borda_do_negrito(dentro, esperado):
    o = ler(f"<html><body><div><p>{dentro}</p></div></body></html>").onmd
    assert o == esperado and "****" not in escrever(o).html


def test_formato_leitura_negrito_italico_volta_igual():
    assert escrever("*a* ***b***").html == "<p><i>a</i> <b><i>b</i></b></p>"


def test_formato_leitura_caixas_livres_e_omitidos():
    h = ('<html><body data-absolute-enabled="true">'
         '<div style="position:absolute;left:48px;top:120px;width:300px"><p>a</p></div>'
         '<div style="position:absolute;left:400px;top:120px;width:200px"><p>b</p><iframe src="x"></iframe></div>'
         "</body></html>")
    lt = ler(h)
    assert lt.onmd == "<caixa x=48 y=120 largura=300>\na\n</caixa>\n\n<caixa x=400 y=120 largura=200>\nb\n</caixa>"
    assert any("caixa" in a for a in lt.avisos) and any("iframe" in a for a in lt.avisos)


def test_formato_leitura_tabela_feita_a_mao_e_codigo_antigo_com_fffc():
    h = ('<html><body><div><table style="border:1px solid"><tr><td style="background-color:#ffff00">'
         "<p>a</p><p>b</p></td><td>c</td></tr></table>"
         '<table data-id="on-cod-1-sh" style="border:0px"><tr><td>'
         '<span style="font-family:Consolas;font-size:10pt">ls</span>'
         '<span style="font-family:Consolas;font-size:10pt">\ufffc  -la</span></td></tr></table>'
         "</div></body></html>")
    o = ler(h).onmd
    assert "<tabela>\n<linha>\n<celula fundo=#ffff00>\na\n\nb\n</celula>\n<celula>c</celula>\n</linha>\n</tabela>" in o
    assert o.endswith("```sh\nls\n  -la\n```")


# ---------- ida e volta ----------
def test_formato_ida_e_volta_da_vitrine():
    x = (AQUI / "vitrine.onmd").read_text(encoding="utf-8").strip()
    e = escrever(x)
    assert e.avisos == [AVISO_SUBITEM]   # a vitrine cobre lista aninhada de propósito
    xml.dom.minidom.parseString(f"<body>{e.html}</body>")
    limpo, avisos = sanitizar(e.html)
    assert limpo == e.html and avisos == []
    saida = simular_saida(limpo)
    assert ler(saida, incluir_ids=True).onmd == x
    # e de novo, a partir do que foi lido (ler → escrever → ler)
    assert ler(simular_saida(escrever(ler(saida, incluir_ids=True).onmd).html), incluir_ids=True).onmd == x


def test_formato_ida_e_volta_com_imagem_vira_recurso():
    e = escrever("antes\n\n![Logo](anexo:1){largura=50% id=logo}", _anexos()[:1])
    o = ler(simular_saida(e.html), incluir_ids=True).onmd
    assert o.startswith("antes\n\n![Logo](recurso:0-") and o.endswith("{id=logo largura=50%}")


# prova real 15/10 (docs/provas-v2.md § Listas aninhadas): linha em branco antes de cada sub-nível, sem saída
@pytest.mark.parametrize("onmd", ["- a\n  - b", "1. um\n   1. sub", "a. alfa\n  i. sub", "- a\n  - b\n    - c\n- d",
                                  "<destaque>\n- a\n  - b\n</destaque>",
                                  # 1º item mais recuado que os seguintes: c aninha sob b (recuo do anterior)
                                  "  - a\n- b\n  - c", "   1. a\n1. b\n   1. c"])
def test_formato_lista_aninhada_avisa_uma_vez_sem_mudar_o_html(onmd):
    e = escrever(onmd + "\n\ntexto\n\n- x\n  - y")
    assert e.avisos.count(AVISO_SUBITEM) == 1
    assert "linha em branco" in AVISO_SUBITEM and "prefira títulos ou lista de um nível" in AVISO_SUBITEM
    assert escrever("- a\n  - b").html == "<ul><li>a<ul><li>b</li></ul></li></ul>"


def test_formato_lista_de_um_nivel_nao_avisa_aninhada():
    for onmd in ("- a\n- b", "1. um\n2. dois", "a. alfa\nb. beta", "- [ ] t\n  - [ ] t2"):
        assert AVISO_SUBITEM not in escrever(onmd).avisos


def test_formato_spec_exemplo_completo_converte_sem_aviso():
    s = ler_spec()
    assert "## Exemplo completo" in s and "Não invente sintaxe" in s
    ex = s.split("## Exemplo completo")[1]
    ex = ex[ex.index("```\n") + 4: ex.rindex("\n```")]
    e = escrever(ex)
    assert e.avisos == []
    xml.dom.minidom.parseString(f"<body>{e.html}</body>")
    assert sanitizar(e.html)[1] == []
    for marca in ("on-dst-1", "on-col-1", "data-tag=\"to-do, important\"", "schedule-meeting", "<ol>", "on-cit-1-1"):
        assert marca in e.html
    # e o que a leitura devolve da página do exemplo volta a escrever igual (ONMD canônico estável)
    o = ler(simular_saida(e.html)).onmd
    assert ler(simular_saida(escrever(o).html)).onmd == o
