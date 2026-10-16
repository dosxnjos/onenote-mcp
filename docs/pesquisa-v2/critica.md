**Crítica adversarial do onenote-mcp v2: o que mudar no desenho**

> Nota histórica de pesquisa, escrita antes do código da v2; não é manual (ver o [README](../../README.md)).

Conferi tudo na documentação oficial. Nenhum arquivo do projeto foi alterado. O desenho está quase todo certo, mas tem quatro erros de fato:
- `pre` não aceita edição;
- a regex de id do `ver_imagem` recusaria todo recurso real;
- o desenho diz que "toggle não existe no OneNote", e existe;
- `copyToSection` em conta pessoal tem documentação que se contradiz.

O maior risco novo é a sintaxe `arquivo:` dentro do markdown. Abaixo vêm as provas, seguidas da lista de correções.

## (1) Conferência das afirmações mais arriscadas

1. **`pre` editável e alvo `pre:` na regex: ERRADO.** A tabela de elementos e ações de [UP] lista só body, div, img/object, ol/ul, table, p/li/h1–h6 e title. `pre` não aparece. https://learn.microsoft.com/en-us/graph/onenote-update-page
   - O bloco de código só é editável enquanto o `pre` está dentro da tabela `on-cod-`, porque aí se substitui a tabela pelo id gerado.
   - Se a prova 1.5 falhar e o plano B for `<pre>` solto, o código fica impossível de editar. O desenho precisa dizer isso.
2. **CSS aceito.** A tabela de [IO] lista `background-color`, `color`, `font-family`, `font-size`, `font-style` ("normal or italic only"), `font-weight`, `text-decoration:line-through` (como "strike-through"), `text-align` ("for block elements only") e `text-decoration` ("none or underline only"). https://learn.microsoft.com/en-us/graph/onenote-input-output-html
   - `max-width` e `max-height` em `img` são DOC em [IF]. https://learn.microsoft.com/en-us/graph/onenote-images-files
   - `width` em table e td aceita "pixels or percentage of page width" (DOC). Converter % em px é opcional. https://learn.microsoft.com/en-us/graph/onenote-input-output-html
   - `border` dentro de `style` na table "is not supported" (DOC), e a saída mostra `border:0px` (CONTRA, confirmado). Mesma URL.
   - **Limite de tamanho 6–72: ND.** A documentação só diz que o serviço arredonda para n.0/n.5 e converte px em pt. Mesma URL.
   - **Dois tamanhos padrão diferentes (CONTRA).** O exemplo de saída do body mostra `font-size:11px` uma vez e `11pt` noutra. A leitura deve tratar os dois como padrão. Mesma URL.
   - **margin: ND como entrada.** Só aparece na saída do h1, então não há controle de espaçamento. Mesma URL.
3. **Note tags.** A lista e as caixas marcáveis do desenho batem com [NT]. https://learn.microsoft.com/en-us/graph/onenote-note-tags
   - **Corrigir a regra de lista.** "The `data-tag` setting for a `ul` or `ol` overrides all settings on child `li` elements. This applies even when the `ul` or `ol` doesn't specify a `data-tag`". "Pôr tag só no item" não basta: se um único item tem tag, o gerador tem de emitir `<li>` solto, sem `ul`/`ol` por fora. Isso quebra o `data-id` da lista e o aninhamento. Mesma URL.
   - **`title` aceita `data-tag` (DOC)**, mas a saída não devolve a tag. Mesma URL.
   - `definition` volta como `remember-for-later`: confere. Mesma URL.
   - Tag inválida dá 20139; `:completed` num tag sem caixa dá 20140. https://learn.microsoft.com/en-us/graph/onenote-error-codes
4. **`data-id` próprio.** É DOC em p/h, listas, table, img, object e div. Uma div só sobrevive se tiver `data-id`. https://learn.microsoft.com/en-us/graph/onenote-input-output-html
   - `replace` exige o id gerado, salvo `title` e img/object dentro de div. "Generated id values might change after a page update". https://learn.microsoft.com/en-us/graph/onenote-update-page
   - **Unicidade: ND.** Imagens fatiadas compartilham o mesmo `data-id` por desenho, então um alvo `#id` pode ficar ambíguo. https://learn.microsoft.com/en-us/graph/onenote-input-output-html
   - **Bloco dentro de célula.** Um p dentro de td ter alvo próprio é ND, porque tr/td "do not support any update actions". O passo 2 do `editar` deve mapear todo descendente de table para a table mais externa. https://learn.microsoft.com/en-us/graph/onenote-update-page
5. **Colunas e posicionamento.**
   - [AP] não tem a linha "Applies to" de consumidor; [IO], [UP], [IF] e [NT] têm. https://learn.microsoft.com/en-us/graph/onenote-abs-pos
   - Só div, img e object podem ser posicionados, sempre filhos diretos do body. Height em div é ignorado, z-index é ignorado e não há aninhamento. Mesma URL.
   - Div absoluta só aceita append, e nenhuma ação de PATCH cria elemento posicionado: a forma só nasce no POST. https://learn.microsoft.com/en-us/graph/onenote-update-page
   - As colunas por tabela usam peças que são DOC (tabelas aninhadas são suportadas). https://learn.microsoft.com/en-us/graph/onenote-input-output-html
6. **`copyToSection`: CONTRA, não só PROVA.**
   - A v1.0 lista "Delegated (personal Microsoft account): Notes.Create | Notes.ReadWrite". https://learn.microsoft.com/en-us/graph/api/page-copytosection?view=graph-rest-1.0
   - A página arquivada de cópia diz "not for consumer notebooks on OneDrive" e "as long as the source and destination are in the same tenant". https://learn.microsoft.com/previous-versions/office/office-365-api/how-to/onenote-copy
   - Nesse mesmo exemplo arquivado, o `Operation-Location` aponta para `www.onenote.com`. Mesma URL.
   - O desenho deve tirar o id da operação do cabeçalho e fazer o GET em `/me/onenote/operations/{id}`, sem seguir a URL do cabeçalho. https://learn.microsoft.com/en-us/graph/api/onenoteoperation-get?view=graph-rest-1.0
7. **Criar seção em bloco compartilhado de conta pessoal: ND.**
   - [NPS] lista conta pessoal, mas não fala de bloco que pertence a outra conta. https://learn.microsoft.com/en-us/graph/api/notebook-post-sections?view=graph-rest-1.0
   - A [ARM] só provou GET nesse bloco, com papel `Contributor`. Hoje não existe prova de escrita nele.
   - Regras de nome: unir NPS e 20153, ou seja, `? * \ / : < > | & # " % ~` e também `'`. 20152 = vazio ou só espaços; 20154 = começa com espaço; 20155 = mais de 50 caracteres. https://learn.microsoft.com/en-us/graph/onenote-error-codes
8. **Limites de imagem e anexo.** Valem 4 MB / 413, 6 partes "per POST", 30 imagens e 150 por página. https://learn.microsoft.com/en-us/graph/onenote-images-files
   - O limite de 6 partes é só para POST. Para PATCH, o limite é ND.
   - A frase "five img… data-render-src and one object… data-render-src" é ambígua, então a cautela do desenho se justifica. 10005 trata do excesso de `data-render-src` com PDF. https://learn.microsoft.com/en-us/graph/onenote-error-codes
   - `data-attachment` não pode conter `\ / : * ? < > | "` (20119). Mesma URL.
   - No PATCH, o serviço recusa imagem por link web: "won't try to download random resources"; aceita data URL ou parte nomeada. https://learn.microsoft.com/en-us/graph/onenote-update-page
9. **Cota.** O desenho só cita 400 por hora. A tabela também tem 120 por minuto, 5 requisições simultâneas e nenhum `Retry-After`. https://learn.microsoft.com/en-us/graph/throttling-limits
10. **`buscar_paginas`.** `contains` e `tolower` são DOC, `top` vai até 100, e espaço vira `%20`. https://learn.microsoft.com/en-us/graph/onenote-get-content
    - O `?search` de bloco pessoal acabou em 05/05/2024, sem substituto. https://devblogs.microsoft.com/microsoft365dev/onenote-get-pagessearch-api-deprecation
11. **Fontes erradas no próprio desenho.**
    - [WCR] usa `blob/main`, que dá 404. O certo é https://github.com/OneNoteDev/WebClipper/blob/master/src/scripts/renderer.ts#L1377, onde o `hr` está na lista de não suportados.
    - [RG]: o caminho `/resources/{id}/content` está certo (https://learn.microsoft.com/en-us/graph/api/resource-get?view=graph-rest-1.0). [GC] mostra `$value`; os dois servem.
    - "`level`/`order` somente leitura": confirmado, mas a página que abriu foi a de beta. https://learn.microsoft.com/en-us/graph/api/resources/onenotepage?view=graph-rest-beta

## (2) O que o site faz e o desenho não cobre

- **Recolher e expandir (outline de até 5 níveis): CORREÇÃO.** O OneNote tem esse recurso nativo. https://support.microsoft.com/en-us/OneNote/onenote-help-and-learning/create-an-outline-to-structure-notes
  - Recuo sem marcador e recolher não têm elemento documentado na entrada HTML (ND). A única tentativa possível é lista aninhada, que é a prova 1.2.
  - A frase "toggle não existe no OneNote" sai do desenho.
- **Impossível pela API:**
  - cor de fundo da página (https://learn.microsoft.com/en-us/graph/onenote-input-output-html);
  - rowspan/colspan (mesma URL);
  - tag personalizada (https://learn.microsoft.com/en-us/graph/onenote-note-tags);
  - subpágina, porque `level`/`order` são somente leitura (https://learn.microsoft.com/en-us/graph/api/resources/onenotepage?view=graph-rest-beta);
  - tinta, áudio e equação: nenhum elemento na lista de [CP] (https://learn.microsoft.com/en-us/graph/onenote-create-page);
  - espaçamento de parágrafo (ND);
  - busca no texto das páginas (https://devblogs.microsoft.com/microsoft365dev/onenote-get-pagessearch-api-deprecation);
  - mover página sem apagar a original.
- **Fora por regra da casa, não por limite da API:** vídeo por `iframe data-original-src`. https://learn.microsoft.com/en-us/graph/onenote-images-files
- **Possível e barato, mas ausente do desenho:**
  - `<meta name="created">` para data retroativa (https://learn.microsoft.com/en-us/graph/onenote-create-page);
  - `pagelevel=true` em `listar_paginas`, para mostrar a hierarquia de subpáginas;
  - `/pages/{id}/preview` (até 300 caracteres) como trecho no resultado de busca (https://learn.microsoft.com/en-us/graph/onenote-get-content);
  - `data-tag` no título (https://learn.microsoft.com/en-us/graph/onenote-note-tags);
  - imagem posicionada (https://learn.microsoft.com/en-us/graph/onenote-abs-pos).
- **Erros que `criar_pagina` deve explicar ao usuário:** 10004 (seção com senha), 507 / 30102 (seção cheia) e 20117 (nome duplicado). https://learn.microsoft.com/en-us/graph/onenote-error-codes e https://learn.microsoft.com/en-us/graph/onenote-create-page

## (3) Riscos de segurança novos

1. **`arquivo:` dentro do markdown é um canal de vazamento (o mais grave).**
   - Texto de um bloco compartilhado por terceiro, por exemplo `![x](arquivo:C:/…)`, volta pelo `ler_pagina`.
   - Se o modelo recria a página a partir da leitura (o próprio passo 4 do plano faz isso), o MCP lê o arquivo local e o sobe para o OneNote.
   - **Correção:**
     - o caminho sai do texto e vai para um parâmetro explícito `anexos=[...]`, e o corpo só cita `anexo:1`;
     - a leitura escapa toda sintaxe ONMD que vier literal da página (`{…}`, `<destaque>`, `arquivo:`, `recurso:`);
     - `pastas` aponta para uma pasta dedicada, nunca para o perfil inteiro;
     - os `avisos` listam cada arquivo enviado, com caminho e tamanho.
2. **"Nenhuma tool apaga" é só nominal.** `editar` com `novo="."` esvazia o conteúdo na prática. O que protege de verdade é o diário local.
   - Para bloco de terceiro: config `editar_so_paginas_do_mcp`, conferindo `createdByAppId` (https://learn.microsoft.com/en-us/graph/onenote-get-content), ou separar a lista permitida em seções de leitura e de escrita.
3. **O diário não garante reversão de imagem nem de anexo.** O HTML guardado tem `src` apontando para `graph.microsoft.com/…/$value`. O sanitizador recusa esse link, e o PATCH não baixa link web (https://learn.microsoft.com/en-us/graph/onenote-update-page).
   - Documentar que o diário reverte só texto e tabela.
   - Guardar em texto puro é um risco local: aplicar rotação e não gravar conteúdo com a tag `password`.
4. **`ver_imagem`.**
   - Id de recurso real tem `!` e `-` (ex.: `0-f717b5fa…!1-73DBAF9B7E5C4B4C!10456`, em https://learn.microsoft.com/en-us/graph/onenote-input-output-html). A regex de `data-id` recusaria todos.
   - Precisa de regex própria e de aceitar só ids de `img`, nunca de `object`.
   - O tipo deve vir de `data-src-type` e dos bytes mágicos, porque a resposta chega como `application/octet-stream` (https://learn.microsoft.com/en-us/graph/api/resource-get?view=graph-rest-1.0). Pôr teto de tamanho.
   - Texto dentro da imagem é dado, não instrução.
5. **Lista de rotas.** `@odata.nextLink` e `Operation-Location` são URLs absolutas.
   - A regra "GET só em `/me/onenote/…`" precisa aceitar a forma absoluta depois que o `_url` checar o host.
   - Nunca fazer GET no `resourceLocation`; usar o `resourceId` (https://learn.microsoft.com/en-us/graph/api/onenoteoperation-get?view=graph-rest-1.0).
6. **Divisão automática em POST + PATCH esbarra na [ARM]** ("PATCH logo depois de criar dá 504", e hoje não se repete para não duplicar).
   - A divisão precisa de espera, e de conferir por `data-id` se o trecho já entrou antes de repetir.
   - Sem isso, é melhor recusar com erro orientador do que dividir.

## (4) Via negativa: o que cortar

- **Escrita com `layout="livre"` / `<caixa>`.** Consumidor não está documentado, a caixa só aceita append e não nasce por PATCH (https://learn.microsoft.com/en-us/graph/onenote-abs-pos, https://learn.microsoft.com/en-us/graph/onenote-update-page). Manter `<caixa>` só na leitura. Sai a prova 1.10.
- **Barra lateral da citação (célula de 6 px).** Ir direto ao plano B (`<p>` cinza em itálico; `<cite>` é DOC em https://learn.microsoft.com/en-us/graph/onenote-input-output-html). Sai a prova 1.6.
- **Normalização de `tamanho` no MCP.** O serviço já arredonda (mesma URL). Ficam só o tipo e um teto largo.
- **`copiar_pagina` e `criar_secao`.** Adiar até a prova 1.17 passar nas duas contas (doc CONTRA e ND acima). A v1 já permite ler e criar, então o ganho é pequeno.
- **`buscar_paginas` sem `secao`.** Com N seções são N requisições, e a cota é de 120 por minuto (https://learn.microsoft.com/en-us/graph/throttling-limits). Limitar a cerca de 20 seções ou exigir o bloco.
- **Prefixos `on-` e a ida e volta.** Tudo depende da prova 1.9 (o `data-id` sobreviver a uma edição manual). Se falhar, o contrato `escrever(ler(x))` fica só aproximado. Marcar como dependente de prova, não como contrato.
- **`{marcador=…}` / `{numero=nenhum}` soltos numa linha.** É sintaxe extra para um ganho pequeno. Melhor só o `{…}` no fim do primeiro item.

## Correções concretas ao desenho

1. Tirar `pre` dos blocos editáveis e da regex de alvo. Código editável só dentro da tabela `on-cod-`; plano B = não editável, com aviso.
2. No `editar`, todo bloco com ancestral `table` vira alvo da table mais externa.
3. Gerador de lista: se algum item tem `tags`, emitir `<li>` solto, sem `ul`/`ol`, e o `{id}` da lista se perde. A spec deve avisar.
4. Regex própria para id de recurso (com `!` e `-`). `ver_imagem` aceita só img, com tipo e tamanho validados.
5. Validar `data-attachment` contra `\ / : * ? < > | "` (20119).
6. Nome de seção: unir os caracteres proibidos de NPS e 20153, mais `'`; até 50 caracteres; sem espaço no início.
7. `copyToSection`: grau CONTRA. A tool fica adiada e, se entrar, faz polling por id em `/me/onenote/operations/{id}`, nunca pela URL do cabeçalho nem pelo `resourceLocation`.
8. `criar_secao` em bloco de outra conta: grau ND, adiada até a prova 1.17.
9. Cota: 120/min + 400/h + 5 simultâneas, sem `Retry-After`. Contar também a reconstrução do índice. Limitar `buscar_paginas`.
10. Lista de rotas aceita URL absoluta do Graph (nextLink).
11. Arquivos: `anexos=[...]` como parâmetro, nunca caminho dentro do texto. A leitura escapa sintaxe ONMD literal. Pasta dedicada.
12. Diário: documentar "só texto e tabela"; rotação; nada com a tag `password`.
13. Divisão POST + PATCH: só com espera e checagem de idempotência por `data-id`; senão, erro orientador.
14. Leitura: tratar `font-size:11px` e `11pt` no body como padrão. Normalizar cor nomeada para hex (já previsto).
15. Remover "toggle não existe" e incluir o outline/recolher como lacuna real, com tentativa por lista aninhada (prova 1.2).
16. Acrescentar: `criado_em` (meta), `pagelevel` em `listar_paginas`, `tags` no título, e mensagens para 10004, 507/30102 e 20117.
17. Cortar: escrita em `livre`/`<caixa>`, barra da citação, normalização de tamanho; adiar copiar e criar seção.
18. Corrigir a fonte [WCR] para `blob/master` (linha 1377). Citar [onenotePage] como beta ou trocar por uma fonte v1.0.

Faltam três provas reais que a documentação não resolve:
- a 1.9, que diz se o `data-id` sobrevive a uma edição pelo site;
- a 1.17, que diz se `copyToSection` e `criar_secao` funcionam em conta pessoal e em bloco de outra conta;
- a 1.2, que diz se lista aninhada gera os níveis de outline.

O pedido "acabei de dar consent nas 3 na nova conta" não pede ação nesta etapa. O passo 0 continua valendo: conferir qual conta está logada antes de qualquer prova, porque a escrita só foi provada com a conta de teste (`Contributor` no bloco compartilhado).