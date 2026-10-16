# diário local do ANTES de cada troca (editar, marcar_tarefa, renomear): o Graph não expõe histórico de versões
# %LOCALAPPDATA%\onenote-mcp\historico\<pagina>.jsonl, gravado ANTES do PATCH; sem diário, a troca não sai
# reverte texto e tabela, NÃO imagem/anexo (o src guardado aponta para o Graph e o PATCH não baixa link: crítica §3.3)
# bloco com etiqueta password não é gravado (nem o antes nem o depois); arquivo passa de 512 KB → roda para
# .1.jsonl (guarda 1 geração). Quem chama valida o PATCH ANTES de gravar: o diário não guarda troca que não sai
import json
import re
from datetime import datetime, timezone

ROTACAO = 512 * 1024


class DiarioIndisponivel(Exception):
    pass


def arquivo(pasta, pagina_id):
    return pasta / (re.sub(r"[^A-Za-z0-9_-]", "_", str(pagina_id))[:150] + ".jsonl")


def gravar(pasta, pagina_id, acao, itens):
    """itens = [{"alvo": id gerado ou "title", "antes": html/texto antigo, "depois": html novo}]"""
    limpos = []
    for it in itens:
        it = dict(it)
        for campo in ("antes", "depois"):   # vale para o HTML antigo E o novo (crítica §3.3)
            if re.search(r'data-tag="[^"]*password', str(it.get(campo, "") or "")):
                it[campo] = "[omitido: bloco com etiqueta password]"
        limpos.append(it)
    linha = {"quando": datetime.now(timezone.utc).isoformat(timespec="seconds"), "pagina": pagina_id,
             "acao": acao, "itens": limpos}
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        p = arquivo(pasta, pagina_id)
        if p.exists() and p.stat().st_size > ROTACAO:
            p.replace(p.with_name(p.stem + ".1.jsonl"))
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except OSError as e:
        raise DiarioIndisponivel(f"diário local indisponível ({type(e).__name__}): a troca não foi enviada") from None
    return p


def ler(pasta, pagina_id):
    p = arquivo(pasta, pagina_id)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
