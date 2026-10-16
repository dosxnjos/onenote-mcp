"""uso: python -m onenote_mcp <login|sair|eu|secoes [bloco]|serve>

login   mostra o código para entrar na conta Microsoft (uma vez; o login fica no cache cifrado)
sair    apaga o login do cache
eu      conta logada e os NOMES de todos os blocos, marcando os liberados (para montar a lista)
secoes  seções liberadas pela lista, com o caminho
serve   servidor MCP (stdio), usado pelo Claude Code
"""
import json
import sys
import urllib.error

from . import auth
from .config import carregar
from .graph import ErroGraph, Graph


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "ajuda"
    if cmd == "serve":
        from .server import rodar
        return rodar()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")
    try:
        cfg = carregar()
        if cmd == "login":
            print(f"conectado como {auth.login(cfg, saida=sys.stdout)}")
        elif cmd == "sair":
            auth.sair(cfg)
            print("login apagado do cache")
        elif cmd in ("eu", "secoes"):
            from . import permitidos as P
            from .onenote import OneNote
            on = OneNote(Graph(lambda: auth.token(cfg)), cfg)
            if cmd == "eu":
                blocos = [{"nome": b["displayName"], "papel": b.get("userRole"),
                           "liberado": P.bloco_visivel(b["displayName"], cfg.permitidos, cfg.bloqueados)}
                          for b in on._todos_blocos()]
                saida = {"conta": auth.conta_atual(cfg), "blocos": blocos}
            else:
                saida = {"secoes": on.listar_secoes(argv[1] if len(argv) > 1 else None), "avisos": on.avisos}
            print(json.dumps(saida, ensure_ascii=False, indent=1))
        else:
            print(__doc__)
            return 2
    except (auth.SemRegistro, auth.SemLogin, ErroGraph, ValueError) as e:   # ValueError: toml malformado ou tipo errado
        print(f"erro: {e}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"erro: sem conexão com a Microsoft ({type(e).__name__})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
