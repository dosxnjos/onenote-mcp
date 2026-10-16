## Notion MCP como referência de UX para o onenote-mcp

> Nota histórica de pesquisa, escrita antes do código da v2; não é manual (ver o [README](../../README.md)).

**Lacuna:** não consegui ler o recurso `notion://docs/enhanced-markdown-spec` direto do MCP hospedado. Na primeira chamada `notion-fetch` veio o erro "needs you to sign in again" e o servidor desconectou. Usei no lugar a página pública v2, que diz: "The specification below comes from the same source as the Notion MCP server's Markdown spec. It is written for AI agents, so it is terse." (https://developers.notion.com/guides/data-apis/notion-flavored-markdown). As descrições e schemas das tools hospedadas `notion-create-pages`, `notion-update-page` e `notion-fetch` eu li inteiras via ToolSearch antes da queda; são fonte primária.

### 1. Tools

**MCP hospedado (o servidor que o Notion recomenda):** são cerca de 50 tools em 7 grupos (https://developers.notion.com/docs/mcp-supported-tools):
- **Busca e leitura:** `notion-search`, `notion-fetch`, `notion-get-self`, `notion-get-users`, `notion-get-teams`, `notion-get-groups`, `notion-get-tool-access`, `notion-get-async-task`.
- **Barra lateral:** `notion-list-private-pages`, `notion-list-shared-pages`, `notion-list-favorite-pages`, `notion-list-recent-pages`, `notion-list-page-backlinks`.
- **Escrita de página:** `notion-create-pages`, `notion-update-page`, `notion-move-pages`, `notion-duplicate-page`, `notion-delete-pages`, `notion-restore-pages`.
- **Arquivos:** `notion-create-file-upload`, `notion-create-attachment`, `notion-get-file-download-urls`.
- **Bancos e views:** `notion-create-database`, `notion-update-data-source`, `notion-create-view`, `notion-update-view`, `notion-query-data-sources`.
- **Comentários:** `notion-create-comment`, `notion-get-comments`, `notion-update-comment`, `notion-delete-comment`, `notion-set-discussion-resolved`, `notion-set-comment-reaction`.
- **Agents/sessions:** 10 tools de agentes e sessões.

Toda a escrita de conteúdo passa por só duas tools:
- `notion-create-pages` recebe `pages[].content` em markdown, mais `icon`, `cover` e `allow_async`.
- `notion-update-page` tem `command` ∈ {`update_properties`, `update_content`, `replace_content`, `insert_content`, `apply_template`, `update_verification`}.

**Repo `makenotion/notion-mcp-server`:** é OpenAPI→MCP. Tem 24 operationIds em `scripts/notion-openapi.json`, como `post-page`, `patch-block-children`, `update-a-block`, `delete-a-block`, `retrieve-page-markdown` e `update-page-markdown` (https://github.com/makenotion/notion-mcp-server). O próprio README admite os limites:
- "no longer actively maintained or supported. Please use Remote Notion MCP instead"
- "Basic API-derived tools"
- "Limited to two page-content tools"

O custo de gerar tools direto da API aparece no schema carregado aqui: `$defs.blockObjectRequest` só descreve `paragraph` e `bulleted_list_item`. Na prática o modelo não tem como saber montar callout, tabela, toggle etc. pelas tools em bloco.

### 2. Como o formato é especificado para o modelo

- **A spec é um recurso separado, e toda tool de escrita aponta para ele.** A descrição de `notion-create-pages` e `notion-update-page` diz: "Before writing page content, read the MCP resource `notion://docs/enhanced-markdown-spec` … or call the Notion "fetch" tool with this URI if your client does not support reading MCP resources … Do NOT guess or hallucinate Markdown syntax." O `notion-fetch` aceita `notion://docs/*` como `id`. São dois caminhos para o mesmo texto: recurso MCP ou tool.
- **A base é CommonMark + GFM, e o que é próprio do Notion vira tag XML.** A spec v2 diz: "Never write other HTML tags (e.g. <div>, <details>…); they are saved as literal text." (https://developers.notion.com/guides/data-apis/notion-flavored-markdown)
- **Recursos da v2:**
  - `<callout icon color>`, `<toggle heading="h1..h4">`, `<columns><column ratio="50">`.
  - Cor: `color="blue"` ou `"blue_bg"`, de uma paleta fechada de 9 cores, com `_bg` para fundo. `<span color>` só para palavras.
  - Inline: `<b> <i> <s> <u>`.
  - Menção e data: `<mention url>` e `<date start end start-time time-zone/>`.
  - To-do: `- [ ]` / `- [x]`, ou `<todo checked color>`.
  - Tabela: `<table header-row header-column fit-page-width>` com `<col width color>`, `<tr color>`, `<td color>`. Pipe table fica para tabela simples ("never mix the two").
  - Outros: `<equation>`, `<table-of-contents/>`, `<image source color>`, `<page url>`.
- **Um formato só para todo container:** "The title/label is body text right after the opening tag… Children follow a blank line." Há ainda regras de escape (`\<tag>`), de cerca de código ("Triple-backtick content requires four-backtick outer fences") e "Each image must be its own block" (mesma URL).
- **A v1 (enhanced markdown) traz um exemplo completo no fim** (https://developers.notion.com/guides/data-apis/enhanced-markdown). Ela também é tolerante: "Headings 5 and 6 are converted to heading 4" e "Plain blank lines are stripped. Use `<empty-block/>`".
- **Leitura e escrita usam o mesmo dialeto.** O `notion-fetch` diz "Pages use enhanced Markdown format". Arquivos aparecem como referências estáveis `notion-file-block://`, com a instrução "keep them when editing or copying Markdown". Por isso o modelo consegue editar o que acabou de ler (descrição da tool hospedada).

### 3. Atualizar só parte da página

- **`update_content` é localizar e substituir sobre o markdown da página** (https://developers.notion.com/guides/data-apis/working-with-markdown-content):
  - Recebe `content_updates[]` com `{old_str, new_str, replace_all_matches}`, até 100 por chamada.
  - Cada `old_str` "must be a non-empty string that matches exactly one location"; se casar em mais de um lugar, dá `validation_error`.
  - A busca diferencia maiúsculas de minúsculas.
- **O lote é atômico:** "If any such operation's `old_str` doesn't match … the call returns a validation error naming the unmatched value and the page is left unchanged". Operação com `old_str == new_str` é ignorada (https://developers.notion.com/docs/mcp-supported-tools).
- **`replace_content` regrava a página toda.** `insert_content` (com `after` no formato reticências `"início...fim"` ou `position: start|end`) e `replace_content_range` estão marcados como legados: "less precise than the search-and-replace approach" (mesma URL do guia).
- **Proteção contra apagar sem querer:** "By default, the update endpoint refuses to delete child pages or databases… set `allow_deleting_content: true`". O erro devolve a lista do que seria apagado.
- **Toda atualização devolve a página inteira em markdown.** Atualização v2 com tag desconhecida devolve `warnings[]` com `code`/`category`/`autofix` (ex.: `unsupported_tag`, "lines dropped due to incorrect indentation").

### 4. Como evitam que o modelo erre

Estes trechos estão literais nas descrições das tools hospedadas:
- "Before changing content, fetch unless already loaded. Match nearby headings, block types, nesting, list or table patterns, and prose style."
- "Make the smallest edit… Avoid full-page "replace_content" when a targeted command is sufficient."
- "use the smallest exact old_str that uniquely identifies the target. If the edit would remove material content the user did not identify, ask for confirmation first."
- "After a multi-part or structural edit, fetch the page again and verify… Skip this extra read for a simple exact edit."
- "Never retry with "allow_deleting_content": true without confirmation. Report any "warnings" in the result."
- "Do not put the page title at the top of content; set it in properties."

A validação no servidor completa as instruções: lote atômico, unicidade do `old_str`, `warnings` (que a doc manda ler antes de dar a edição por concluída) e limite de 5.000 blocos na criação, com erro que orienta dividir a página (guia de markdown). O schema também ajuda: `command` é um enum e cada campo explica quando é obrigatório.

### 5. O que vale copiar para o OneNote

**Primeiro, dois problemas do onenote-mcp atual (lidos no código):**
- `ler_pagina` usa markdownify e `criar_pagina` usa python-markdown, ou seja, dialetos diferentes. Localizar e substituir só funciona se o que o modelo lê é o que ele pode mandar de volta.
- `conteudo.py` descarta todo atributo (lista de tags sem `style`). É isso que hoje impede cor, fonte e etiquetas.

**Tabela Notion → OneNote:**

| Notion | OneNote via Graph | Fonte |
|---|---|---|
| cor de texto/fundo (`color`, `_bg`, `<span color>`) | `style` com `color`, `background-color`, `font-family`, `font-size` (pt/px), `font-weight`, `font-style`, `text-decoration`, `text-align`; também `<u>`, `<sup>`, `<sub>`, `<strike>`, `<cite>` | https://learn.microsoft.com/en-us/graph/onenote-input-output-html |
| to-do `- [ ]` / `- [x]` | `data-tag="to-do"` e `"to-do:completed"`, mais ~30 etiquetas nativas (important, question, idea, critical, priority-1…), várias por elemento separadas por vírgula | https://learn.microsoft.com/en-us/graph/onenote-note-tags |
| tabela estilizada `<table header-row>`, `<td color>` | `<table border width bgcolor>` e `style` por `td`/`tr` (largura em px ou %), tabela aninhada; **sem** rowspan/colspan | input-output-html |
| lista numerada/marcadores | `list-style-type`: decimal, lower/upper-alpha, lower/upper-roman, none; disc, circle, square | input-output-html |
| colunas `<columns>` | só por emulação: `div` com posição absoluta (`left`/`top`/`width`) e `data-absolute-enabled` no body | input-output-html |
| callout | sem bloco nativo; emular com tabela de 1 célula com `bgcolor` ou parágrafo com `background-color` | (inferência) |
| imagem/arquivo | `<img src="name:parte">` ou data URL; `<object data="name:parte" data-attachment type>` | https://learn.microsoft.com/en-us/graph/onenote-update-page |
| toggle, menção, bloco sincronizado | não existem na API | (ausentes nas duas páginas acima) |
| embed de vídeo | `<iframe data-original-src>` existe, mas **fica bloqueado** pela regra de não buscar URL externa | input-output-html |

**O que copiar:**

1. **Uma spec em markdown estendido escrita para IA**, curta e com um exemplo completo no fim, exposta de dois jeitos: recurso MCP `onenote://docs/markdown` e tool `ler_spec()` (o Claude Code nem sempre lê recursos). Toda tool de escrita diz na descrição: "leia a spec antes; não invente sintaxe".
   - Sintaxe sugerida, no estilo da v2: `<callout cor="amarelo" icone="💡">`, `<colunas><coluna largura="50">`, `<span cor fundo fonte tamanho>`, `{tag="important,idea"}` no fim da linha e `- [ ]` / `- [x]` → `data-tag`.
   - Paleta fechada de cores com nome (como as 9 do Notion), em vez de hex livre: o modelo erra menos e a página fica coerente.
2. **Ler e escrever no mesmo dialeto.** Um conversor próprio nos dois sentidos substitui markdownify e python-markdown soltos. Imagem existente volta como referência estável (`<imagem id="...">`) para sobreviver a uma edição, como o `notion-file-block://`.
3. **Edição parcial por localizar e substituir, resolvida no cliente.** A Graph não faz isso; o PATCH exige alvo por id e não aceita reticências. Fluxo:
   1. `GET /content?includeIDs=true`.
   2. Montar o mapa bloco → markdown → id gerado.
   3. Achar o `trecho_antigo`, que tem que casar em exatamente 1 bloco.
   4. Mandar `PATCH replace` com o `id`.

   Restrições da Graph que moldam isso (https://learn.microsoft.com/en-us/graph/onenote-update-page):
   - `replace` exige o id gerado, exceto `title` e img/object dentro de div.
   - `tr`, `td`, `span` e `a` não aceitam nenhuma ação, então editar uma célula significa substituir a tabela inteira.
   - "Generated id values might change after a page update": refazer o GET antes de todo PATCH, nunca guardar id em cache.
   - Vários comandos num único array de PATCH dão o lote atômico do `content_updates`.
4. **Inserir antes/depois de um trecho** (`inserir(pagina, ancora, posicao="antes|depois")`). A Graph tem `insert` de irmão antes/depois de forma nativa, e é mais preciso que o `after` com reticências que o Notion abandonou.
5. **Mesmo contrato de erro e aviso:**
   - Trecho não encontrado, ou ambíguo sem `todas=true`: falha a chamada inteira e diz qual trecho falhou.
   - Trecho vazio: rejeita.
   - A resposta traz `avisos[]` sempre que o sanitizador descartar ou ajustar algo (tag fora da lista, CSS ignorado, imagem por URL removida), em vez de descartar em silêncio como hoje.
   - Toda escrita devolve a página relida em markdown.
6. **Sem `replace_content` de página inteira.** No Notion o `allow_deleting_content` protege subpáginas; página do OneNote não tem filhas, então o análogo é não ter a tool. Substituição só por bloco, recusando `novo` vazio quando o `antigo` tiver conteúdo relevante. Isso mantém a regra de "nenhuma tool apaga" de fato, e não só no nome.
7. **Instruções de comportamento literais nas descrições**, adaptadas de §4: ler antes de editar, menor edição possível, imitar o estilo vizinho, reler depois de edição estrutural, relatar avisos, título no parâmetro e não no corpo. O teto de tamanho vira erro que orienta: "divida em páginas" (o limite exato do OneNote eu não medi).
8. **Imagem por upload, devolvendo o trecho pronto para colar.** No Notion, `notion-create-file-upload` devolve `suggested_markdown`. O equivalente aqui: `anexar_imagem(caminho_local)` devolve `<imagem ref="parte-1">`, que entra no multipart da próxima escrita. Isso bate com a Graph: "you can't use www links. The service won't try to download random resources… image-data-url or a part-name of a multipart request" (onenote-update-page).
9. **O sanitizador vira lista de atributos/CSS por tag**, não só de tags:
   - `style` com só as 9 propriedades da tabela de estilos da Graph.
   - `data-tag` só com os valores da lista oficial.
   - `data-id` livre.
   - `src` só `name:` ou `data:`.
   - `data-render-src` e `<iframe>` sempre fora.
10. **Não copiar o repo `makenotion`:** expor a API crua gerada de OpenAPI dá schemas pobres, e o próprio Notion abandonou esse caminho (README). As tools continuam escritas à mão, poucas e orientadas a tarefa.

Arquivos de apoio que baixei, todos numa pasta temporária da sessão de pesquisa (não versionada):
- `enhanced-markdown.md`
- `notion-flavored-markdown.md`
- `working-with-markdown-content.md`
- `tools.md`
- `readme.md`
- `openapi.json`

Nenhum arquivo do projeto foi editado e nada foi criado no Notion.