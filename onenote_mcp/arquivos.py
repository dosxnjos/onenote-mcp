# anexos por PARÂMETRO (nunca caminho dentro do texto: crítica §3.1, texto de página de terceiro não pode
# disparar leitura de arquivo local). Cada item de `anexos` é {"caminho": ...} ou {"data_url": ...} (+ "nome")
# - falha fechada: [arquivos].pastas vazio = imagem/anexo desligados
# - pasta dedicada: a home, o que está acima dela (C:\Users), pasta que contém AppData ou o cache do MCP e a raiz
#   de um disco não valem como pasta permitida
# - caminho UNC (\\host, //host, \\?\) recusado ANTES de tocar no disco (abrir UNC autentica SMB: vazamento)
# - resolve(strict) + is_relative_to: ".." e link simbólico/junção que saem da pasta são recusados
# - imagem confere pelos bytes mágicos (PNG, JPEG, GIF, BMP, TIFF), não pela extensão; executável (MZ) nunca
# - data URL decodificada AQUI (o "data:" não chega à Microsoft); teto de tamanho (padrão 3,5 MB por pedido)
import base64
import binascii
import os
import re
from dataclasses import dataclass
from pathlib import Path

TETO_PADRAO_MB = 3.5
MAX_PARTES = 5        # 6 partes por POST contando a Presentation (IF)
MAX_OBJETOS = 1       # conservador até prova (desenho, correção 1)

MAGICOS = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"BM": "image/bmp",
    b"II*\x00": "image/tiff",
    b"MM\x00*": "image/tiff",
}
IMAGENS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"}
# anexos (object): extensão → (MIME, assinatura exigida ou None)
ANEXOS = {
    ".pdf": ("application/pdf", b"%PDF"),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK\x03\x04"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK\x03\x04"),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", b"PK\x03\x04"),
    ".zip": ("application/zip", b"PK\x03\x04"),
    ".txt": ("text/plain", None),
    ".csv": ("text/csv", None),
}
_PROIBIDO_NOME = set('\\/:*?<>|"')


class ArquivoRecusado(ValueError):
    pass


@dataclass
class Anexo:
    nome: str
    mime: str
    dados: bytes
    origem: str     # caminho ou "data URL"
    imagem: bool

    def resumo(self):
        return f"{self.origem} ({len(self.dados) / 1024:.1f} KB)"


def tipo_imagem(dados):
    for m, t in MAGICOS.items():
        if dados.startswith(m):
            return t
    return None


def _eh_unc(texto):
    t = str(texto).strip().replace("/", "\\")
    return t.startswith("\\\\")


def _resolvidas(caminhos):
    saida = []
    for p in caminhos:
        try:
            saida.append(Path(p).expanduser().resolve())
        except (OSError, RuntimeError):
            continue
    return saida


def pastas_validas(pastas, protegidas=()):
    """pastas do config → [Path resolvido]. Recusa: a home e o que está acima dela, raiz de disco, pasta que
    CONTÉM AppData\\Local|LocalLow|Roaming ou o cache do MCP (token cifrado e diário), pasta DENTRO do cache,
    UNC e inexistente. `protegidas` = caches extras (o cache_dir do config)"""
    home = Path.home()
    caches = [Path(os.environ["LOCALAPPDATA"]) / "onenote-mcp"] if os.environ.get("LOCALAPPDATA") else []
    caches = _resolvidas(caches + list(protegidas or ()))
    contidas = _resolvidas([home / "AppData" / x for x in ("Local", "LocalLow", "Roaming")]) + caches
    home = home.resolve()
    boas = []
    for p in pastas or []:
        if _eh_unc(p):
            continue
        try:
            r = Path(p).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if not r.is_dir() or r.parent == r or home.is_relative_to(r):
            continue
        if any(x.is_relative_to(r) for x in contidas) or any(r.is_relative_to(c) for c in caches):
            continue
        boas.append(r)
    return boas


def _do_caminho(caminho, pastas, teto, protegidas=()):
    if not isinstance(caminho, str) or not caminho.strip():
        raise ArquivoRecusado("caminho vazio")
    if _eh_unc(caminho):
        raise ArquivoRecusado("caminho de rede (UNC) recusado")
    permitidas = pastas_validas(pastas, protegidas)
    if not permitidas:
        raise ArquivoRecusado("anexos desligados: config.toml sem [arquivos].pastas (pasta dedicada)")
    try:
        p = Path(caminho).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        raise ArquivoRecusado(f"arquivo não encontrado: {caminho}") from None
    if not any(p.is_relative_to(base) for base in permitidas):
        raise ArquivoRecusado(f"arquivo fora das pastas permitidas: {caminho}")
    if not p.is_file():
        raise ArquivoRecusado(f"não é arquivo: {caminho}")
    if p.stat().st_size > teto:
        raise ArquivoRecusado(f"arquivo acima de {teto / 2**20:.1f} MB: {caminho}")
    dados = p.read_bytes()
    ext = p.suffix.lower()
    if dados.startswith(b"MZ"):
        raise ArquivoRecusado(f"executável recusado: {caminho}")
    if ext in IMAGENS:
        t = tipo_imagem(dados)
        if not t:
            raise ArquivoRecusado(f"o conteúdo não é imagem PNG/JPEG/GIF/BMP/TIFF: {caminho}")
        return Anexo(p.name, t, dados, str(p), True)
    if ext in ANEXOS:
        mime, assinatura = ANEXOS[ext]
        if assinatura and not dados.startswith(assinatura):
            raise ArquivoRecusado(f"o conteúdo não bate com a extensão {ext}: {caminho}")
        if assinatura is None and b"\x00" in dados[:4096]:
            raise ArquivoRecusado(f"arquivo de texto com conteúdo binário: {caminho}")
        return Anexo(p.name, mime, dados, str(p), False)
    raise ArquivoRecusado(f"extensão não aceita: {ext or '(sem)'} (imagens {', '.join(sorted(IMAGENS))}; "
                          f"anexos {', '.join(sorted(ANEXOS))})")


_DATA_URL = re.compile(r"^data:(image/(?:png|jpeg|gif|bmp|tiff));base64,([A-Za-z0-9+/=\s]+)$")


def _do_data_url(url, teto):
    m = _DATA_URL.match(url.strip() if isinstance(url, str) else "")
    if not m:
        raise ArquivoRecusado("data URL inválida: só data:image/(png|jpeg|gif|bmp|tiff);base64,…")
    if len(m.group(2)) > teto * 4 / 3 + 16:
        raise ArquivoRecusado(f"data URL acima de {teto / 2**20:.1f} MB")
    try:
        dados = base64.b64decode(re.sub(r"\s", "", m.group(2)), validate=True)
    except (binascii.Error, ValueError):
        raise ArquivoRecusado("data URL com base64 inválido") from None
    t = tipo_imagem(dados)
    if t != m.group(1):
        raise ArquivoRecusado(f"data URL diz {m.group(1)} mas o conteúdo é {t or 'outra coisa'}")
    ext = {"image/jpeg": "jpg"}.get(t, t.split("/")[1])
    return Anexo(f"imagem.{ext}", t, dados, "data URL", True)


def carregar(item, pastas, max_mb=TETO_PADRAO_MB, protegidas=()):
    """{"caminho"|"data_url", "nome"?} → Anexo, ou ArquivoRecusado com o motivo"""
    teto = int(max_mb * 2**20)
    if not isinstance(item, dict):
        raise ArquivoRecusado("cada anexo é {\"caminho\": …} ou {\"data_url\": …}")
    if bool(item.get("caminho")) == bool(item.get("data_url")):
        raise ArquivoRecusado("informe caminho OU data_url em cada anexo")
    ax = (_do_caminho(item["caminho"], pastas, teto, protegidas) if item.get("caminho")
          else _do_data_url(item["data_url"], teto))
    nome = item.get("nome")
    if nome:
        if any(c in _PROIBIDO_NOME for c in nome) or not nome.strip() or len(nome) > 120:
            raise ArquivoRecusado(f"nome de anexo inválido (sem \\ / : * ? < > | \"): {nome!r}")
        ax.nome = nome.strip()
    return ax


def conferir_limites(partes, max_mb=TETO_PADRAO_MB, html=""):
    """partes = [(nome, mime, bytes)]; html = o conteúdo que vai junto (Presentation/Commands). O teto vale para
    o PEDIDO inteiro (o Graph corta em 4 MB com 413): partes + HTML + ~1 KB de cabeçalho por parte.
    Acima do limite = erro orientador (não divide sozinho: crítica §3.6)"""
    total = sum(len(d) for _, _, d in partes) + len((html or "").encode("utf-8")) + 1024 * (len(partes) + 1)
    objetos = sum(1 for n, _, _ in partes if n.startswith("arq"))
    if len(partes) > MAX_PARTES:
        raise ArquivoRecusado(f"{len(partes)} arquivos num pedido só (máximo {MAX_PARTES}): crie com parte deles "
                              "e use acrescentar para o resto")
    if objetos > MAX_OBJETOS:
        raise ArquivoRecusado(f"{objetos} anexos (<anexo>) num pedido só (máximo {MAX_OBJETOS} por enquanto): "
                              "mande um por vez com acrescentar")
    if total > max_mb * 2**20:
        raise ArquivoRecusado(f"o pedido soma {total / 2**20:.1f} MB entre texto e arquivos (máximo {max_mb} MB "
                              "por pedido): divida em mais de uma chamada")
