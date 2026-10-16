# ARMADILHAS do onenote-mcp

Sintoma → causa. Ler antes de mexer em login, escrita ou lista permitida.

## Login e registro

- **Sessão cai em ~1 h com conta pessoal.** Causa: authority `common`; a renovação do token de conta
  pessoal só funciona com `https://login.microsoftonline.com/consumers` (observado pelo Softeria, `src/auth.ts`).
- **`ValueError` ao pedir `offline_access`.** Causa: o MSAL Python põe `offline_access`, `openid` e `profile`
  sozinho e recusa repetidos. Escopo é só `Notes.ReadWrite`.
- **Código do device code nunca aparece.** Causa: dentro do MCP o stderr não chega ao usuário (o mesmo bug
  do danosb, issue #6). O login é só pelo comando à parte `python -m onenote_mcp login`.
- **Login app-only devolve 401.** Causa: a Microsoft desligou app-only para OneNote em 31/03/2025 (MC1011142).
- **Conta pessoal não consegue "Novo registro" no Entra.** Causa: criar app fora de diretório foi
  descontinuado (medido em 15/10/2026). O app mora no diretório de uma conta Azure gratuita (registrar app
  não custa nada), tipo "Somente contas pessoais da Microsoft", fluxo de cliente público ligado (README, passo 1).
- **O login pede código por e-mail.** Causa: a Microsoft pede verificação de identidade da conta no device
  code ("informações confidenciais"); o código chega no e-mail da conta, que só o dono dela lê.
- **`No module named onenote_mcp` no `serve`.** Causa: pacote não instalado no venv, ou registro com o `python`
  do sistema. `uv pip install -e .` e registrar com o Python do venv: `<pasta>\.venv\Scripts\python.exe -I -m
  onenote_mcp serve` (o `-I` tira a pasta atual do caminho de import).
- **Servidor não sobe (o cliente MCP só mostra falha de conexão) com `config.toml` de tipo errado.** Causa: o
  `carregar()` roda no import do `server.py` (para as `instrucoes`), e `servidor = "x"`, `[[servidor]]` ou
  `permitidos = 5` davam `AttributeError`/`TypeError`, que o try não pegava. Agora o `config.py` valida o tipo de
  cada seção e lista e levanta `ValueError` legível; a subida fica com as instruções base e a 1ª tool devolve
  "pedido recusado: config.toml: …" (15/10/2026).
- **Aviso de sub-item calado quando o 1º item da lista é o mais recuado.** Causa: comparava o recuo de cada item
  com o do 1º, mas a árvore aninha pelo item anterior (`"  - a\n- b\n  - c"` aninha c sob b). Agora decide pela
  árvore (`escrita._lista`), e a recusa de etiqueta em sub-item também (15/10/2026).

## Bloco compartilhado

- **Bloco compartilhado por outra conta não aparece em `/me/onenote/notebooks`.** Causa: a lista só traz o que a
  conta abriu no OneNote; `getRecentNotebooks` mostra o nome mas não o id. O bloco entra por
  `[lista].blocos_extra` com o id (`0-<cid>!s<guid>`, o `resid` do link do OneDrive com `0-` na frente), e
  `GET /me/onenote/notebooks/{id}` responde (`userRole: Contributor` para a conta que fez login, em 15/10/2026).
  Id montado à mão a partir do link sai errado se o `%21` não virar `!`: cole o link inteiro (o `config.py`
  decodifica). Id errado derruba o `eu` inteiro; o erro agora cita o id de `blocos_extra` que falhou.
- **Mesmo bloco, papel diferente por conta.** Uma conta via o bloco compartilhado com `userRole: Reader`; outra,
  com `Contributor` (depende de como o dono compartilhou). Escrita só foi provada com `Contributor`.

## Escrita

- **Página criada vazia, sem erro.** Causa: HTML parcial no POST. Sempre XHTML bem-formado e completo
  (`formato/escrita.py`, `<br />`; o HTML final passa no `xml.dom.minidom` nos testes).
- **`acrescentar` dá 400 "_default is not a valid updateable element".** Causa: o regex pegava o `data-id="_default"`
  (o `\bid=` casa dentro de `data-id`). Usar `\sid="div:...`.
- **Página criada fica sem título e `GET /content` dá 404 por muitos minutos.** Causa: falha de processamento
  do lado da Microsoft (medido 15/10/2026: a mesma página recriada ficou legível em 52 s; a travada continuou 404
  depois de 10 min). Mesmo sem travar, página grande leva ~50 s para o conteúdo existir: ler ou editar antes disso
  dá 404. O servidor devolve essa dica no erro 404; passou de alguns minutos sem título, crie de novo.
- **`acrescentar` logo depois de `criar_pagina` dá 504.** Causa: a página recém-criada ainda está sendo
  provisionada. Esperar uns segundos e tentar de novo (a 2ª tentativa passou em 15/10/2026). O PATCH não é
  repetido sozinho para não duplicar conteúdo.
- **`body` como alvo do PATCH cai no meio da página.** Causa: `body` é a PRIMEIRA div; o código mira a última
  `div:{...}` de `/content?includeIDs=true`.
- **Negrito/itálico somem na leitura.** Causa: o OneNote devolve `<span style="font-weight:bold">`, não `<b>`;
  `formato/leitura.py` lê o `style` do span (negrito, itálico, cor, fundo, fonte) e omite os padrões medidos
  (títulos h1–h6, fonte dominante da página), senão `{fonte="Segoe UI"}` aparece em todo bloco.
- **Formato que o OneNote aceita e devolve diferente.** `pre` some (quebra vira U+FFFC; código = 1 `<p>` Consolas
  por linha), `bgcolor` na `table` some (fundo vai no `td`), `width:200` volta `199`, `cite` perde o estilo,
  `call-back` vira `schedule-meeting` (fora da spec), `definition` volta `remember-for-later`, item de lista com
  etiqueta vira `<li>` solto. Tabela completa: [provas-v2.md](provas-v2.md).

## Edição v2 (revisão de 15/10/2026)

- **Parágrafo regravado aparece depois da lista que vinha logo abaixo dele.** Causa: o OneNote guarda o bloco
  que antecede um `<ul>`/`<ol>` grudado na lista (no GET o id da lista é menor que o do parágrafo); `replace` nele
  põe o novo depois da lista, mesmo regravando a lista no mesmo PATCH. `editar`/`marcar_tarefa` recusam esse
  bloco (`onenote._antes_de_lista`). Medido em página real, 15/10 ([provas-v2](provas-v2.md) § Parágrafo grudado).

- **`editar` recusa um bloco "que o ONMD não representa".** Causa: a leitura omitiu algo dentro dele (imagem,
  vídeo, tabela no texto ou na célula; etiqueta fora da lista); regravar o bloco apagaria isso. É de propósito
  (`Bloco.perdas` em `formato/leitura.py`): edite outro bloco ou use `inserir`.
- **Troca vira "esvaziaria" com texto aparentemente presente.** Causa: sobra só caractere invisível (U+200B,
  U+FEFF, `&#8203;`), espaço ou tabela sem texto; `graph.tem_conteudo` trata como apagar.
- **`id=x` recusado com "já existe na página".** Causa: o alvo `#id` precisa ser único (com dois iguais o Graph
  escolhe um sem dizer qual); `acrescentar`/`inserir` em `#id` repetido também recusam.
- **data-id de página de terceiro nunca vai cru para o PATCH.** O `_reaplicar_id` roda antes do sanitizador e só
  aceita id no padrão `ID_PROPRIO`; atributo de terceiro com `\n` (href, fonte, etiqueta) é normalizado na leitura,
  senão viraria bloco ONMD vivo ao reescrever.

- **Espaço a mais depois de `<br>` a cada regravação.** Causa: o OneNote devolve `<br />\n\ntexto`; a leitura
  trocava a quebra de formatação por espaço. `formato/leitura.py` (`runs`) descarta essa quebra (prova real 15/10).
- **Imagem pequena ignora `largura`.** Medido: PNG de 48 px voltou sem `width` tanto com `312` quanto com `31`;
  PNG de 800 px com `312` voltou com `width` e `height`. Regra do OneNote não identificada (`docs/provas-v2.md` § Vitrine); a escrita avisa sempre que há `largura`.
- **Lista aninhada aparece com uma linha em branco antes de cada sub-nível.** Causa: limite da Microsoft no
  Graph (10 variantes de HTML testadas, todas com o parágrafo vazio; o GET não mostra esse parágrafo, então não dá
  para removê-lo; o editor do site salva por outro protocolo). A escrita avisa; prefira títulos ou lista de um
  nível (`docs/provas-v2.md` § Listas aninhadas).

## Lista permitida

- **A lista limita a ferramenta, não a chave.** O token cifrado (DPAPI do usuário) é legível por qualquer processo
  do mesmo usuário Windows, inclusive um `python -c` do próprio Claude pelo Bash. Defesa real: fazer login com
  uma conta que só enxerga o que for compartilhado com ela; senha não deve morar em bloco compartilhado.
- **Seção liberada em `permitidos` some do `secoes`.** Causa: o bloqueio compara por TRECHO do nome normalizado,
  em qualquer parte do caminho (bloco, grupo ou seção): "Resenhas" contém `senha` e cai (`permitidos.bloqueado`).
  De propósito: falha fechada. Renomeie no OneNote se for inocente.
- **Seção compartilhada não aparece.** Causa: `/me/onenote/sections` não garante incluir bloco de outra
  conta; o índice percorre bloco por bloco (`/notebooks/{id}/sections` e `/sectionGroups`).
- **Id com `!` quebra a URL.** Causa: ids do OneNote têm `!`; o `quote` mantém `!` e `-`.
- **Espaço na query derruba o urllib (`InvalidURL`).** Causa: `$orderby=x desc` cru; o Graph recusa URL com
  espaço antes de sair da máquina. Sem `$orderby` (a ordem padrão já é a última alteração primeiro).
