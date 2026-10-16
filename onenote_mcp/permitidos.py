# lista permitida: o caminho de uma seção é "Bloco/Grupo/.../Seção"
# permitido = algum item de `permitidos` é prefixo do caminho (por partes, nome normalizado)
# bloqueado = alguma parte do caminho CONTÉM um termo de `bloqueados` (normalizado); bloqueio vence permissão
# normalizar = NFKC + sem acento + espaços (inclusive NBSP) colapsados + sem caixa: "Logins  e Senhas 🔒" casa "senha"
# lista vazia = nada permitido (falha fechada)
import re
import unicodedata


def normalizar(texto):
    t = unicodedata.normalize("NFKC", str(texto))
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t).strip().casefold()


def _partes(caminho):
    return [normalizar(p) for p in str(caminho).split("/") if normalizar(p)]


def bloqueado(caminho, bloqueados):
    termos = [normalizar(b) for b in bloqueados if normalizar(b)]
    return any(t in p for p in _partes(caminho) for t in termos)


def permitido(caminho, permitidos, bloqueados):
    if bloqueado(caminho, bloqueados):
        return False
    alvo = _partes(caminho)
    for item in permitidos:
        pref = _partes(item)
        if pref and alvo[: len(pref)] == pref:
            return True
    return False


def bloco_visivel(nome_bloco, permitidos, bloqueados):
    """o bloco aparece na listagem se algum item permitido começa por ele"""
    if bloqueado(nome_bloco, bloqueados):
        return False
    alvo = normalizar(nome_bloco)
    return any(_partes(item)[:1] == [alvo] for item in permitidos)


class ForaDaLista(Exception):
    pass
