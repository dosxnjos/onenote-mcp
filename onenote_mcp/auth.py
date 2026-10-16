# login delegado (device code) com cache de token cifrado (DPAPI no Windows), fora de qualquer repo
# DPAPI protege contra OUTRO usuário do Windows, não contra processo do mesmo usuário (ARMADILHAS § Lista permitida)
# nunca imprimir token; nunca print em stdout no modo servidor (é o canal do MCP)
import sys
import threading

import msal
from msal_extensions import PersistedTokenCache, build_encrypted_persistence

from .config import ESCOPOS

_TIMEOUT = (10, 30)
_apps = {}
_trava = threading.Lock()


class SemRegistro(Exception):
    pass


class SemLogin(Exception):
    pass


def _app(cfg):
    if not cfg.client_id:
        raise SemRegistro(
            "falta o client_id no config.toml: o app ainda não foi registrado na Microsoft (README, passo 1)"
        )
    chave = (cfg.client_id, cfg.authority, str(cfg.cache_dir))
    with _trava:
        if chave not in _apps:
            cfg.cache_dir.mkdir(parents=True, exist_ok=True)
            persist = build_encrypted_persistence(str(cfg.cache_dir / "token_cache.bin"))
            _apps[chave] = msal.PublicClientApplication(
                cfg.client_id, authority=cfg.authority, token_cache=PersistedTokenCache(persist), timeout=_TIMEOUT)
        return _apps[chave]


def _conta(app, cfg):
    contas = app.get_accounts(username=cfg.conta) if cfg.conta else app.get_accounts()
    if not contas:
        raise SemLogin("sem login: rode `python -m onenote_mcp login` num terminal")
    return contas[0]


def conta_atual(cfg):
    try:
        return _conta(_app(cfg), cfg).get("username")
    except SemLogin:
        return None


def token(cfg):
    """token válido em silêncio (renova pelo refresh token); sem conta no cache = SemLogin"""
    app = _app(cfg)
    r = app.acquire_token_silent_with_error(ESCOPOS, account=_conta(app, cfg))
    if r and "access_token" in r:
        return r["access_token"]
    erro = (r or {}).get("error") or "sem_token"
    desc = ((r or {}).get("error_description") or "token expirado ou revogado").splitlines()[0]
    if erro in ("invalid_grant", "interaction_required", "sem_token"):
        raise SemLogin(f"login vencido ({erro}: {desc}): rode `python -m onenote_mcp login`")
    raise SemLogin(f"falha ao renovar o login ({erro}: {desc}); confira a rede e tente de novo")


def login(cfg, saida=sys.stderr):
    app = _app(cfg)
    for c in app.get_accounts():  # servidor de conta única: login novo substitui o anterior
        app.remove_account(c)
    fluxo = app.initiate_device_flow(scopes=ESCOPOS)
    if "user_code" not in fluxo:
        raise SemLogin(f"a Microsoft recusou o login: {fluxo.get('error_description', fluxo.get('error'))}")
    print(fluxo["message"], file=saida, flush=True)
    r = app.acquire_token_by_device_flow(fluxo)
    if "access_token" not in r:
        raise SemLogin(f"login não concluído: {r.get('error_description', r.get('error'))}")
    return (r.get("id_token_claims") or {}).get("preferred_username", "?")


def sair(cfg):
    app = _app(cfg)
    for c in app.get_accounts():
        app.remove_account(c)
