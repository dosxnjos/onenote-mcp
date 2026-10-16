# onenote-mcp

MCP próprio do OneNote (Python, Graph, login delegado da conta pessoal). Pegadinhas:
[docs/ARMADILHAS.md](docs/ARMADILHAS.md) · plano v2: [roadmap/](roadmap/2026-10-15-v2-formato-rico.md). Links para
notas privadas do dono, se houver, ficam no `CLAUDE.local.md` (fora do git).

- Nunca tool que apaga; nunca escopo `*.All`; authority `consumers` (ARMADILHAS § Login).
- Toda tool passa pela lista permitida (`onenote.py`); nome com "senha"/"password"/"credencia" bloqueado no
  código (`config.BLOQUEADOS_PADRAO`), o toml só soma.
- Token só no cache cifrado de `%LOCALAPPDATA%`; `config.toml` fora do git; nunca print em stdout no `serve`.
- Página se escreve para o leitor dela: todos os pontos pertinentes + notas de contexto, sem recado interno
  (base genérica `INSTRUCOES` em `server.py` + `[servidor].instrucoes` do `config.toml`, que o dono preenche).
- Repo público: nada de nome, e-mail, client ID ou id real de bloco em código, teste, fixture ou doc
  (fato de conta vai para o hub privado).
- Conteúdo é ONMD (`formato/spec.md`); construção nova só entra com prova real em `docs/provas-v2.md` e
  teste de ida e volta. `editar` nunca regrava bloco com `perdas` (o que a leitura omitiu se apagaria).
- Arquivo local só pelo parâmetro `anexos` e de `[arquivos].pastas`; nunca caminho lido do texto da página.
- Prova: `.venv\Scripts\python.exe -m pytest -q` (sem rede). Plano v2: [roadmap/](roadmap/2026-10-15-v2-formato-rico.md).
