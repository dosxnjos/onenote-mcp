# passo 5: arquivos.py. Prova: .. para fora, UNC, symlink/junção, .exe renomeado, data URL ruim são recusados
import base64
import os
import sys

import pytest

from onenote_mcp import arquivos as A
from onenote_mcp.arquivos import ArquivoRecusado, carregar, conferir_limites

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 30
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 30


@pytest.fixture
def pasta(tmp_path):
    p = tmp_path / "anexos"
    p.mkdir()
    (p / "foto.png").write_bytes(PNG)
    (p / "foto_errada.jpg").write_bytes(PNG)        # PNG com extensão .jpg: vale pelo conteúdo
    (p / "virus.png").write_bytes(b"MZ\x90\x00" + b"\x00" * 30)
    (p / "falso.png").write_bytes(b"isto nao e imagem")
    (p / "plano.xlsx").write_bytes(b"PK\x03\x04resto")
    (p / "plano_falso.xlsx").write_bytes(b"texto")
    (p / "nota.txt").write_text("oi", encoding="utf-8")
    (p / "script.ps1").write_text("rm -r", encoding="utf-8")
    (tmp_path / "fora.png").write_bytes(PNG)
    return p


def test_arquivos_imagem_dentro_da_pasta(pasta):
    ax = carregar({"caminho": str(pasta / "foto.png")}, [str(pasta)])
    assert ax.imagem and ax.mime == "image/png" and ax.dados == PNG and ax.nome == "foto.png"
    assert "foto.png" in ax.resumo() and "KB" in ax.resumo()


def test_arquivos_png_com_extensao_jpg_aceito_pelo_conteudo(pasta):
    assert carregar({"caminho": str(pasta / "foto_errada.jpg")}, [str(pasta)]).mime == "image/png"


@pytest.mark.parametrize("nome,msg", [("virus.png", "executável"), ("falso.png", "não é imagem"),
                                      ("plano_falso.xlsx", "não bate"), ("script.ps1", "extensão")])
def test_arquivos_conteudo_errado_recusado(pasta, nome, msg):
    with pytest.raises(ArquivoRecusado, match=msg):
        carregar({"caminho": str(pasta / nome)}, [str(pasta)])


def test_arquivos_anexo_xlsx_e_txt(pasta):
    ax = carregar({"caminho": str(pasta / "plano.xlsx"), "nome": "Plano 2026.xlsx"}, [str(pasta)])
    assert not ax.imagem and ax.nome == "Plano 2026.xlsx" and "spreadsheetml" in ax.mime
    assert carregar({"caminho": str(pasta / "nota.txt")}, [str(pasta)]).mime == "text/plain"


def test_arquivos_ponto_ponto_para_fora(pasta):
    with pytest.raises(ArquivoRecusado, match="fora das pastas"):
        carregar({"caminho": str(pasta / ".." / "fora.png")}, [str(pasta)])
    with pytest.raises(ArquivoRecusado, match="fora das pastas"):
        carregar({"caminho": str(pasta / "..\\..\\" / pasta.parent.name / "fora.png")}, [str(pasta)])


@pytest.mark.parametrize("caminho", ["\\\\servidor\\c$\\x.png", "//servidor/share/x.png", "\\\\?\\C:\\x.png",
                                     "\\\\.\\C:\\x.png"])
def test_arquivos_unc_recusado_antes_de_tocar_no_disco(pasta, caminho, monkeypatch):
    tocou = []
    monkeypatch.setattr(A.Path, "resolve", lambda self, strict=False: tocou.append(self) or self)
    with pytest.raises(ArquivoRecusado, match="UNC"):
        carregar({"caminho": caminho}, [str(pasta)])
    assert tocou == []


def test_arquivos_link_simbolico_para_fora(pasta, tmp_path):
    link = pasta / "atalho.png"
    try:
        os.symlink(tmp_path / "fora.png", link)
    except (OSError, NotImplementedError):
        pytest.skip("sem permissão para criar link simbólico neste Windows")
    with pytest.raises(ArquivoRecusado, match="fora das pastas"):
        carregar({"caminho": str(link)}, [str(pasta)])


@pytest.mark.skipif(sys.platform != "win32", reason="junção é do Windows")
def test_arquivos_juncao_para_fora(pasta, tmp_path):
    import _winapi
    externa = tmp_path / "externa"
    externa.mkdir()
    (externa / "x.png").write_bytes(PNG)
    _winapi.CreateJunction(str(externa), str(pasta / "junc"))
    with pytest.raises(ArquivoRecusado, match="fora das pastas"):
        carregar({"caminho": str(pasta / "junc" / "x.png")}, [str(pasta)])


def test_arquivos_desligado_sem_pasta_e_pasta_ruim(pasta, tmp_path):
    with pytest.raises(ArquivoRecusado, match="desligados"):
        carregar({"caminho": str(pasta / "foto.png")}, [])
    with pytest.raises(ArquivoRecusado, match="desligados"):
        carregar({"caminho": str(pasta / "foto.png")}, [str(A.Path.home()), "C:\\", "\\\\srv\\x", str(tmp_path / "nao")])


def test_arquivos_teto_de_tamanho(pasta):
    (pasta / "grande.png").write_bytes(PNG + b"\x00" * 2_000_000)
    with pytest.raises(ArquivoRecusado, match="acima"):
        carregar({"caminho": str(pasta / "grande.png")}, [str(pasta)], max_mb=1)


def _du(dados, tipo="image/png"):
    return f"data:{tipo};base64," + base64.b64encode(dados).decode()


def test_arquivos_data_url_boa():
    ax = carregar({"data_url": _du(PNG)}, [])
    assert ax.imagem and ax.dados == PNG and ax.origem == "data URL" and ax.nome == "imagem.png"


@pytest.mark.parametrize("url,msg", [
    ("data:image/png;base64,@@@@", "inválida"),
    ("data:image/png;base64,AAA", "base64"),
    (_du(JPG, "image/png"), "conteúdo"),
    (_du(b"MZ" + b"\x00" * 10, "image/png"), "conteúdo"),
    ("data:image/svg+xml;base64,PHN2Zz4=", "inválida"),
    ("data:text/html;base64,PGh0bWw+", "inválida"),
    ("https://atacante/x.png", "inválida"),
])
def test_arquivos_data_url_ruim(url, msg):
    with pytest.raises(ArquivoRecusado, match=msg):
        carregar({"data_url": url}, [])


@pytest.mark.parametrize("item", [{}, {"caminho": "a", "data_url": "b"}, "C:/x.png", {"caminho": ""}])
def test_arquivos_item_mal_formado(item):
    with pytest.raises(ArquivoRecusado):
        carregar(item, [])


def test_arquivos_nome_com_caractere_proibido(pasta):
    with pytest.raises(ArquivoRecusado, match="nome"):
        carregar({"caminho": str(pasta / "plano.xlsx"), "nome": "a/b.xlsx"}, [str(pasta)])


def test_arquivos_limites_do_pedido():
    conferir_limites([("img1", "image/png", b"x")] * 5)
    with pytest.raises(ArquivoRecusado, match="máximo 5"):
        conferir_limites([("img1", "image/png", b"x")] * 6)
    with pytest.raises(ArquivoRecusado, match="anexos"):
        conferir_limites([("arq1", "application/pdf", b"x"), ("arq2", "application/pdf", b"x")])
    with pytest.raises(ArquivoRecusado, match="MB"):
        conferir_limites([("img1", "image/png", b"x" * (3 * 2**20)), ("img2", "image/png", b"x" * 2**20)])
