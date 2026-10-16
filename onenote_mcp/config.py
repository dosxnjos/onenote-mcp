# configuração: config.toml na raiz do projeto (fora do git) ou o caminho em ONENOTE_MCP_CONFIG
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# conta pessoal: "consumers". "common" derruba a renovação do token de conta pessoal (ARMADILHAS)
AUTHORITY_PADRAO = "https://login.microsoftonline.com/consumers"
# offline_access, openid e profile o MSAL põe sozinho; passar de novo dá ValueError
ESCOPOS = ["Notes.ReadWrite"]
# termos bloqueados por CONTER (normalizado, ver permitidos.normalizar). Somam ao toml; o toml não remove
BLOQUEADOS_PADRAO = ["senha", "password", "credencia"]


@dataclass
class Config:
    client_id: str = ""
    authority: str = AUTHORITY_PADRAO
    conta: str = ""
    permitidos: list[str] = field(default_factory=list)
    bloqueados: list[str] = field(default_factory=lambda: list(BLOQUEADOS_PADRAO))
    # bloco compartilhado por outra conta pessoal não aparece em /me/onenote/notebooks: entra pelo id
    blocos_extra: list[str] = field(default_factory=list)
    cache_dir: Path = field(default_factory=lambda: Path(os.environ.get("LOCALAPPDATA", Path.home())) / "onenote-mcp")
    # [arquivos]: pastas de onde imagem/anexo podem sair (vazio = desligado; pasta dedicada, nunca a home)
    pastas_arquivos: list[str] = field(default_factory=list)
    max_mb: float = 3.5
    # [servidor].instrucoes: texto do dono ACRESCENTADO às instruções base do servidor (server.instrucoes)
    instrucoes: str = ""

    @property
    def historico_dir(self):
        """diário local do antes de cada troca (o Graph não tem histórico de versões)"""
        return self.cache_dir / "historico"


def id_do_bloco(valor):
    """aceita o id ("0-<cid>!s<guid>") ou o link do OneDrive com resid=<cid>!s<guid>"""
    v = str(valor).strip()
    if "resid=" in v:
        from urllib.parse import parse_qs, unquote, urlsplit
        resid = parse_qs(urlsplit(v).query).get("resid", [""])[0]
        return f"0-{unquote(resid)}" if resid else ""
    return v


def caminho_config(path=None):
    return Path(path or os.environ.get("ONENOTE_MCP_CONFIG") or RAIZ / "config.toml")


def _tabela(d, nome):
    """[nome] tem que ser tabela: `servidor = "x"` ou `[[servidor]]` viram ValueError legível (não AttributeError)"""
    v = d.get(nome, {})
    if not isinstance(v, dict):
        raise ValueError(f"config.toml: [{nome}] tem que ser uma tabela (linha `[{nome}]` e as chaves embaixo), "
                         f"não `{nome} = …` nem `[[{nome}]]`")
    return v


def _lista_de(tab, secao, chave):
    v = tab.get(chave, [])
    if not isinstance(v, list):
        raise ValueError(f'config.toml: [{secao}].{chave} tem que ser uma lista entre colchetes, ex.: {chave} = ["…"]')
    return v


def carregar(path=None):
    p = caminho_config(path)
    if not p.exists():
        return Config()
    d = tomllib.loads(p.read_text(encoding="utf-8"))
    ms = _tabela(d, "microsoft")
    lista = _tabela(d, "lista")
    arq = _tabela(d, "arquivos")
    srv = _tabela(d, "servidor")
    for chave in ("permitidos", "bloqueados", "blocos_extra"):
        _lista_de(lista, "lista", chave)
    _lista_de(arq, "arquivos", "pastas")
    instr = srv.get("instrucoes", "")
    if not isinstance(instr, str):
        raise ValueError('config.toml: [servidor].instrucoes tem que ser texto entre aspas (use """ … """ para '
                         "várias linhas), não lista nem número")
    cfg = Config(
        client_id=str(ms.get("client_id", "")).strip(),
        authority=str(ms.get("authority", AUTHORITY_PADRAO)).strip() or AUTHORITY_PADRAO,
        conta=str(ms.get("conta", "")).strip(),
        permitidos=[str(x) for x in lista.get("permitidos", [])],
        bloqueados=list(dict.fromkeys(BLOQUEADOS_PADRAO + [str(x) for x in lista.get("bloqueados", [])])),
        blocos_extra=[id_do_bloco(x) for x in lista.get("blocos_extra", []) if id_do_bloco(x)],
        pastas_arquivos=[str(x) for x in arq.get("pastas", [])],
        max_mb=min(float(arq.get("max_mb", 3.5)), 3.5),
        instrucoes=instr.strip(),
    )
    if d.get("cache_dir"):
        if not isinstance(d["cache_dir"], str):
            raise ValueError('config.toml: cache_dir tem que ser um caminho entre aspas, antes da linha [microsoft]')
        cfg.cache_dir = Path(d["cache_dir"])
    return cfg
