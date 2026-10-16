# passo 3: sanitizar.py, tabela de ataques do desenho §Passo 3. Tudo o que cai aparece em avisos
import xml.dom.minidom

import pytest

from onenote_mcp.sanitizar import sanitizar

ATAQUES = [
    # (entrada, o que NÃO pode sobrar no HTML, trecho esperado nos avisos)
    ('<p style="background:url(http://x)">a</p>', "url(", "perigoso"),
    ('<p style="background-color:url(http://x)">a</p>', "url(", "perigoso"),
    ('<p style="color:expression(alert(1))">a</p>', "expression", "perigoso"),
    ('<img src="https://atacante/x.png" />', "<img", "externa"),
    ('<img src="http://atacante/x.png" />', "<img", "externa"),
    ('<img src="data:image/png;base64,AAAA" />', "<img", "externa"),
    ('<img src="name:digitado" />', "<img", "externa"),
    ('<img data-render-src="https://x/y.html" />', "data-render-src", "data-render-src"),
    ('<img src="name:img1" data-render-src="name:pag1" />', "data-render-src", "data-render-src"),
    ('<object data="https://x/a.pdf" data-attachment="a.pdf" type="application/pdf" />', "<object", "externa"),
    ('<object data="name:arq1" data-attachment="a.exe" type="application/x-msdownload" />', "<object", "tipo"),
    ('<object data="name:arq1" data-attachment="..\\a.pdf" type="application/pdf" />', "<object", "nome de anexo"),
    ('<iframe data-original-src="https://youtube.com/x"></iframe>', "iframe", "iframe"),
    ('<p><a href="javascript:alert(1)">x</a></p>', "javascript", "esquema"),
    ('<p><a href=" JaVaScRiPt:alert(1)">x</a></p>', "alert", "esquema"),
    ('<p><a href="file:///C:/x">x</a></p>', "file:", "esquema"),
    ('<p data-tag="custom">a</p>', "custom", "fora da lista"),
    ('<p data-tag="important:completed">a</p>', "important", "estado"),
    ('<script>alert(1)</script><p>ok</p>', "alert", "script"),
    ('<style>p{color:red}</style><p>ok</p>', "color:red", "style"),
    ('<form action="https://x"><input name="s"/></form>', "form", "form"),
    ('<link rel="stylesheet" href="https://x"/>', "https://x", "link"),
    ('<pre>código</pre>', "<pre", "pre"),
    ('<table bgcolor="#ff0000"><tr><td rowspan="2">a</td></tr></table>', "bgcolor", "bgcolor"),
    ('<p data-id="ok" id="x" onclick="alert(1)">a</p>', "onclick", "onclick"),
    ('<div style="position:absolute;left:0">a</div>', "position", "style"),
]


@pytest.mark.parametrize("entrada,proibido,aviso", ATAQUES)
def test_sanitizar_ataque_cai_com_aviso(entrada, proibido, aviso):
    html, avisos = sanitizar(entrada, partes=["img1", "arq1"])
    assert proibido.lower() not in html.lower()
    assert any(aviso in a for a in avisos), avisos
    xml.dom.minidom.parseString(f"<body>{html}</body>")


def test_sanitizar_cor_fica_posicao_sai():
    html, avisos = sanitizar('<p style="color:red;position:absolute">a</p>')
    assert html == '<p style="color:red">a</p>'
    assert any("position" in a for a in avisos)


def test_sanitizar_mantem_o_que_a_spec_gera():
    ok = ('<h1 data-id="topo" style="color:#2E75B6">T</h1>'
          '<p data-tag="to-do:completed, important" style="font-family:Segoe UI;font-size:14pt;text-align:center">'
          '<b>a</b><i>b</i><u>c</u><del>d</del><sup>e</sup><sub>f</sub>'
          '<span style="background-color:#FFFF00">g</span><a href="onenote:https://d.docs.live.net/x">h</a></p>'
          '<ul style="list-style-type:square"><li style="list-style-type:square">i</li></ul>'
          '<table border="1" style="width:499px" data-id="on-tab-1"><tr><td style="width:187px;'
          'background-color:#DDEBF7;text-align:right">j</td></tr></table>'
          '<div data-id="resumo"><p>k</p></div>'
          '<img src="name:img1" alt="x" width="312" data-id="foto" />'
          '<object data="name:arq2" data-attachment="Plano.xlsx" '
          'type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" />')
    html, avisos = sanitizar(ok, partes=["img1", "arq2"])
    assert html == ok and avisos == []


def test_sanitizar_texto_escapado_e_xhtml():
    html, _ = sanitizar("<p>a &lt;b&gt; &amp; c<br></p>")
    assert html == "<p>a &lt;b&gt; &amp; c<br /></p>"


def test_sanitizar_tag_desconhecida_fica_so_o_texto():
    html, avisos = sanitizar("<p><blink>pisca</blink></p>")
    assert html == "<p>pisca</p>" and any("blink" in a for a in avisos)


def test_sanitizar_name_so_de_parte_desta_chamada():
    html, _ = sanitizar('<img src="name:img1" />', partes=["img2"])
    assert html == ""
    html, _ = sanitizar('<img src="name:img2" />', partes=["img2"])
    assert html == '<img src="name:img2" />'


def test_sanitizar_data_id_invalido_e_tamanho_fora():
    html, avisos = sanitizar('<p data-id="a b" style="font-size:500pt;width:10px">x</p>')
    assert html == "<p>x</p>" and len(avisos) == 3
