# Levantamento: PATCH de conteúdo do OneNote e operações vizinhas (Graph v1.0, conta pessoal, só `Notes.ReadWrite`)

> Nota histórica de pesquisa, escrita antes do código da v2; não é manual (ver o [README](../../README.md)).

Nenhum arquivo do projeto foi editado. Li `onenote_mcp/onenote.py`, `conteudo.py`, `server.py`, `README.md` e `docs/ARMADILHAS.md`. Cada afirmação traz a fonte entre colchetes; a lista de fontes está no fim. Onde a Microsoft não documenta, está escrito **a medir**.

**O que mais pesa para o projeto:**
- **Achado de segurança:** o PATCH aceita a ação `delete`. Toda tool precisa de uma lista de ações permitidas que nunca deixe passar `delete` [2].
- **Imagem por data URL não está documentada.** O caminho documentado é multipart com `src="name:x"` [1][4][7].
- **A busca por texto completo foi desligada em 2024.** Só resta filtrar pelo título [16][18].
- **A cota real é baixa:** 400 requisições por hora e 5 ao mesmo tempo, e o 429 vem sem `Retry-After` [20].
- **Dá para endereçar blocos depois** pelo `data-id` próprio em `append` e `insert`. O `replace` de quase tudo exige o id gerado [1].

## 1. PATCH `/me/onenote/pages/{id}/content`

### Pedido e resposta
- Corpo: um array JSON de comandos `{target, action, position, content}`, com `Content-Type: application/json`. Sucesso devolve 204, sem corpo [1][3].
- Com binário (imagem ou arquivo), o pedido vira `multipart/form-data` e precisa de uma parte chamada `"Commands"` (`application/json`) com o array. As outras partes levam o binário cru, sem Base64 [1].
- Faltar a parte Commands dá erro 20124 [9].
- Permissão para conta pessoal delegada: só `Notes.ReadWrite`; não existe nível acima para conta pessoal [3].
- Os exemplos da documentação usam aspas simples no JSON, que não é JSON válido. Isso é inferência; o `json.dumps` do Python já resolve [1].

### Ações
- `action` aceita `replace`, `append`, **`delete`**, `insert` e `prepend` [2].
- A página explicativa do PATCH não lista `delete` [1]. **Por isso a lista de ações permitidas nas tools é obrigatória**, e `delete` nunca entra.
- O que cada ação faz [1]:

| Ação | Efeito | Onde vale |
| --- | --- | --- |
| `append` | filho, primeiro ou último conforme `position` | só `body`, `div`, `ol`, `ul` |
| `insert` | irmão, antes ou depois do alvo | elementos da tabela abaixo |
| `prepend` | atalho de `append` + `before` | só `body`, `div`, `ol`, `ul` |
| `replace` | troca o alvo pelo conteúdo enviado | elementos da tabela abaixo |

- `position` [1][2]:
  - Padrão `after`. Com `append` é o último filho; com `insert` é o irmão seguinte.
  - `before`: com `append` é o primeiro filho; com `insert` é o irmão anterior.

### Alvos (`target`)
- `#<data-id>`: o `data-id` que nós mesmos definimos no HTML ao criar ou atualizar a página. Precisa do `#` [1]. Esquecer o `#` dá erro 20134 [9].
- **Id gerado**, no formato `p:{guid}{n}`, `div:{…}{n}`, `table:{…}{n}`, `img:{…}{n}`: vai sem `#` e só aparece com `GET …/content?includeIDs=true` [1].
- Qualquer `id` que enviarmos no HTML é descartado [1][4].
- **Ids gerados podem mudar depois de qualquer atualização.** Ler os ids de novo logo antes de cada PATCH [1].
- `body` é a palavra-chave para a **primeira** div da página; `title` é a palavra-chave para o título [1]. O projeto já mira a última `div:{…}` (ARMADILHAS).
- Regra de identificador [1]:
  - `append` e `insert` aceitam `data-id` ou id gerado.
  - `replace` exige o id gerado. Exceções: `title`, e `img`/`object` dentro de uma div, que aceitam também `data-id`.

### O que cada elemento aceita [1]

| Elemento | replace | append (filho) | insert (irmão) |
| --- | --- | --- | --- |
| body (1ª div) | não | sim | não |
| div posicionada (absoluta) | não | sim | não |
| div dentro de div | sim, só id gerado | sim | sim |
| img e object dentro de div | sim, aceita `data-id` | não | sim |
| ol e ul | sim, só id gerado | sim | sim |
| table | sim, só id gerado | não | sim |
| p, li, h1–h6 | sim, só id gerado | não | sim |
| title | sim | não | não |

- **Nenhuma ação** vale para img ou object posicionados, nem para `tr`, `td`, `meta`, `head`, `span`, `a` e `style` [1].
- **Tabela:** não dá para mexer numa linha ou célula isolada. Para editar uma célula, substitui-se a tabela inteira pelo id gerado [1].
  - Se um `p` dentro de `td` ganha id próprio e aceita `replace`: **a medir** (não documentado).
- **Lista:** para acrescentar item, `append` no `ul`/`ol` (aceita `#data-id`). Um item com `list-style-type` fora do padrão precisa repetir o estilo no `li` [1].

### Mudar o título
- `{"target":"title","action":"replace","content":"Novo título"}`; o conteúdo é texto puro [1].
- Dá para pôr `data-tag` no `<title>` ao criar a página, mas a leitura não devolve o tag do título [5].

### Marcar to-do como concluído
- Formato: `<p data-tag="to-do">` (aberto) e `<p data-tag="to-do:completed">` (marcado) [5].
- Para marcar: `replace` no `p` **pelo id gerado**, reenviando o texto e o `data-id`. Exemplo: `{"target":"p:{…}{40}","action":"replace","content":"<p data-tag=\"to-do:completed\" data-id=\"task1\">First task</p>"}` [1][5].
- Também têm caixa marcável: `discuss-with-person-a`, `discuss-with-person-b`, `discuss-with-manager`, `schedule-meeting`, `call-back`, `to-do-priority-1`, `to-do-priority-2` e `client-request` [5].
- Vários tags no mesmo elemento: separar por vírgula, como em `"important, critical"` [5].
- Recomendação da Microsoft: fazer to-do com `p`, não com lista [5].
- Em lista, a leitura põe o `data-tag` num `span` dentro do `li`, e `span` não aceita atualização. Para mudar um item, mira-se o `li` pelo id gerado [5][1].
- Um `data-tag` no `ul`/`ol` sobrescreve o dos itens [5].
- Elementos que aceitam `data-tag`: `p`, `ul`, `ol`, `li`, `img`, `h1`–`h6` e `title` [5].
- **Tag personalizado não é suportado** [5].
- Erros: 20139 (tag inválido) e 20140 (status inválido) [9].

### `data-id` próprio para endereçar blocos depois
- Aceitam `data-id` na entrada: `div`, `img`, `object`, `p`, `h1`–`h6`, `ul`, `ol`, `li` e `table`. A leitura devolve o `data-id` junto [4].
- **Uma div sem `data-id` é achatada** e o conteúdo sobe para a div pai. Com `data-id` ela é preservada e vira alvo de `append`/`insert` por `#id` [4].
  - Isso permite criar "seções nomeadas" na página, por exemplo `<div data-id="resumo">`, e acrescentar nelas depois.
- `replace` por `data-id` só funciona em img e object [1]. Para trocar um bloco de texto, o caminho é: ler com `includeIDs=true`, achar o id gerado do elemento que tem aquele `data-id`, e fazer `replace` por esse id. É inferência a partir de [1][4].
- Imagens divididas em pedaços compartilham o mesmo `data-id` [4].
- O `_default` não é alvo válido (ARMADILHAS).
- **A medir:** se o `data-id` sobrevive quando alguém edita a página no site ou no app. A documentação não cobre. Teste sugerido: criar com `data-id`, editar no site, ler de novo e tentar o PATCH por `#id`.

### Layout com vários contêineres posicionados (cara de página nativa)
- `<body data-absolute-enabled="true">` com filhos diretos `div`, `img` ou `object` em `style="position:absolute;top:…px;left:…px;width:…px"` [6].
  - Altura de div é ignorada. `z-index` é ignorado. Não aninha. Padrão `top:120px` e `left:48px` [6].
- Erros: 20146, 20147 e 20148 [9].
- Uma div posicionada só aceita `append` (nem `insert`, nem `replace`) [1].

### Estilo permitido (base para ampliar a lista do sanitizador)
- **CSS em linha:** `background-color`, `color`, `font-family`, `font-size` (pt ou px, arredondado a 0,5pt), `font-style` (normal ou italic), `font-weight` (normal ou bold), `text-decoration` (none, underline ou line-through) e `text-align` (só em bloco) [4].
- **Tags de formatação:** `b`, `i`, `u`, `em`, `strong`, `strike`, `sup`, `sub`, `del` e `cite` [4].
- **Marca-texto:** `<span style="background-color:yellow">` [5].
- **Elementos básicos:** `h1`–`h6`, `p`, `ul`, `ol`, `li`, `table`, `tr`, `td` (tabela aninhada vale) e `pre` [8].
- **Listas:**
  - `ol`: `none`, `decimal`, `lower-alpha`, `lower-roman`, `upper-alpha`, `upper-roman`.
  - `ul`: `none`, `disc`, `circle`, `square` [4].
- **Tabela:**
  - Atributos `border`, `width` e `bgcolor` [4].
  - `width` e `background-color` em `td` [4].
  - Sem `rowspan`/`colspan`; `border` dentro de `style` não é aceito [4].
- **Não aceita:** cor de fundo no `body` [4].
- O `_TAGS` atual deixa passar `code`, `blockquote` e `hr`, que **não** estão nas listas da Microsoft [4][8]. Provavelmente são achatados ou ignorados. **A medir.**

### Limites e armadilhas
- **Cota OneNote** por app e por usuário: 120 requisições por minuto, **400 por hora**, **5 simultâneas**. **O 429 não traz `Retry-After`** [20]. O código do erro é 20166 [9].
  - Cada `acrescentar` hoje faz cerca de 4 a 5 chamadas (conferência da página, conferência da seção, GET com ids, PATCH). Isso dá **cerca de 80 a 100 edições por hora**. É estimativa a partir de [20].
- **Tamanho:**
  - O Graph corta pedidos acima de **4 MB** com 413; os ~70 MB e 25 MB por parte valem só na camada do OneNote, inalcançável pelo Graph [7]. Esses números foram documentados para POST; para o PATCH, valer o mesmo é inferência.
  - Em POST: no máximo 6 partes, 30 imagens por pedido e 150 imagens por página [7].
  - Erros de multipart: 20014 (parte acima de 25 MB), 20015 (mais de 500 partes) e 20016 (mais de 75 MB) [9].
- **Erros de PATCH** [9]:
  - 20109: corpo mal montado.
  - 20120 e 20149: alvo não encontrado.
  - 20121: argumento inválido.
  - 20122: ação não suportada.
  - 20123 e 20137: a página não aceita PATCH.
  - 20125: nenhuma ação no corpo.
  - 20133 e 20135: alvo ou tipo não suportado.
  - 20138: o elemento não aceita `append`.
  - 20141: o alvo não aceita aquela ação.
- **Erros transitórios** (tentar de novo): 10002, 10003 (excesso de requisições ativas da conta) e 10007 [9].
- **504 logo depois de criar a página:** **não há documentação** da Microsoft. Vale a observação do projeto: esperar, tentar uma segunda vez, e não repetir o PATCH sozinho para não duplicar conteúdo (ARMADILHAS).
- Uma seção cheia de páginas devolve 507 [8].

## 2. Imagens

### Escrever
- Caminho documentado:
  - **No PATCH:** multipart com a parte `Commands` e `<img src="name:parte">` [1].
  - **No POST:** a parte `Presentation` e as partes de dados [7].
  - Tipos aceitos: TIFF, PNG, GIF, JPEG e BMP [7].
  - Atributos: `alt`, `width`, `height`, e no style `width`/`height`/`max-width`/`max-height` [4][7].
- `<img data-render-src="name:parte">` transforma uma parte HTML ou PDF local em imagem; continua local e respeita a restrição [7]. O limite é de 5 desses por pedido [7].
- Anexo de arquivo: `<object data="name:parte" data-attachment="x.pdf" type="application/pdf">` [7]. Sobre ele valem `replace` e `insert` quando está dentro de div [1].
- **Data URL (`data:image/png;base64,…`):** a única pista é a nota do PATCH, que diz que a imagem precisa vir "by an image-data-url or a part-name" [1]. A lista de formas de `src` não traz `data:` [4], e a página de imagens só fala de URL pública e de parte nomeada [7]. **A medir.** Mesmo funcionando, o Base64 incha cerca de 33% e bate antes no teto de 4 MB [7].
- **Precisam ficar bloqueados pela restrição** (o servidor da Microsoft buscaria a URL externa):
  - `img src="https://…"` [7]
  - `data-render-src="https://…"` [7]
  - `iframe data-original-src` de vídeo (YouTube, Vimeo e outros) [4][7]
  - `data-render-method` de extração [4]
- `img` e `object` posicionados não aceitam nenhuma ação depois de criados [1].

### Ler
- A leitura da página traz, em cada `img`:
  - `src`: a versão otimizada, apontando para `…/onenote/resources/{id}/$value`.
  - `data-fullres-src`: o original.
  - `data-src-type` e `data-fullres-src-type`: os tipos de cada uma [4].
- O `object` traz `data=` apontando para o recurso [4].
- `GET /me/onenote/resources/{id}/content` devolve o binário (`application/octet-stream`). Conta pessoal: `Notes.Read` ou `Notes.ReadWrite` [19].
- A forma `…/resources/{id}/$value` também está documentada. Não precisa de cabeçalho `Accept`. Não existe listagem de recursos [16].
- Implicação de segurança, inferida: a tool deve receber **só o id** do recurso, validar o formato, e só baixar se esse id aparecer no HTML de uma página da lista permitida. **Nunca** deve buscar uma URL arbitrária com o token, porque isso vazaria o bearer.

## 3. Copiar página (`copyToSection`): escreve, não apaga
- `POST /me/onenote/pages/{id}/copyToSection` com corpo `{"id":"<seção destino>"}`. O `groupId` serve só para grupo do M365 [10].
- Conta pessoal: `Notes.Create` ou `Notes.ReadWrite` [10].
- É assíncrono: devolve **202 com o cabeçalho `Operation-Location`** [10].
- Acompanhamento: `GET /me/onenote/operations/{id}` até `status` ser `completed` (com `resourceLocation` e `resourceId`) ou `failed` (com `error` e `@api.diagnostics`) [11].
- Existem cópias de outro nível (`CopyNotebook`, `CopyToNotebook`, `CopyToSectionGroup`) com o mesmo padrão [11].
- A lista permitida tem de valer para a origem **e** para o destino. Isso é regra do projeto.
- **A medir:** se a cópia funciona para dentro ou para fora do bloco compartilhado por outra conta pessoal. A documentação não cobre.

## 4. Criar seção e grupo de seções
- Seção num bloco: `POST /me/onenote/notebooks/{id}/sections` com `{"displayName":"…"}`, devolve 201 [12].
- Seção num grupo: `POST /me/onenote/sectionGroups/{id}/sections` [13]. O texto diz 201; o exemplo mostra 200.
- Grupo de seções num bloco: `POST /me/onenote/notebooks/{id}/sectionGroups` [14].
- Grupo dentro de grupo: `POST /me/onenote/sectionGroups/{id}/sectionGroups` [15].
- Conta pessoal: `Notes.Create` ou `Notes.ReadWrite` em todos [12][13][14][15].
- **Regras do nome:**
  - Único no mesmo nível, até 50 caracteres, sem `?*/:<>|&#''%~` [12].
  - Nome repetido: 20117. Caractere inválido: 20153. Começar com espaço: 20154. Comprido demais: 20155 (bloco 128, o resto 50). Vazio: 20152 [9].
- **Bloco compartilhado de conta pessoal:**
  - `userRole: Contributor` significa leitura e escrita [21].
  - A rota `me` cobre conteúdo próprio e compartilhado [22], e a conta de teste aparece como Contributor (ARMADILHAS).
  - Mas não há documentação de criar seção ou grupo em bloco de outra conta. **A medir** com um teste ao vivo.
  - Alternativa documentada a testar se `me` falhar: a rota `users/{id}` [22].
- Decisão de design (inferência): uma seção nova só nasce se o caminho "Bloco/Grupo/Seção" resultante passar na lista permitida.

## 5. Pesquisa
- **Desligada:** `GET pages?search` para blocos pessoais deixou de funcionar em **05/05/2024**. Devolve 400 e **não tem substituto** [18].
- O que resta é filtrar por propriedade.
  - Exemplo: `…/pages?$filter=contains(tolower(title),'x')` [16].
  - Funções aceitas: `contains`, `startswith`, `endswith`, `tolower` e outras; operadores `eq`, `ne`, `gt`, `ge`, `lt`, `le`, `and`, `or`, `not` [16].
  - Diferencia maiúscula de minúscula; por isso usar `tolower`. Espaço vira `%20` [16].
  - `top` padrão 20, máximo 100. O `$orderby` funciona [16][17].
  - Erro 20129 se `top` passar do máximo [9].
  - Funciona também por seção: `/sections/{id}/pages?$filter=…` [16].
  - Isso evita o 20266 (excesso de seções) [9] e o problema do bloco compartilhado que não aparece em `/me/onenote/sections` (ARMADILHAS).
- Trecho de texto barato: `GET pages/{id}/preview` devolve `previewText` com até 300 caracteres [16].
- **Não existe busca no texto da página.** Só lendo o conteúdo, e isso gasta a cota de 400 por hora [20].

## 6. Fora do alcance na v1.0 (diferenças para o site)
- Mudar o nível de recuo da página (subpágina) só existe na API beta antiga `onenote.com/api/beta` (2016) [23]. Na v1.0, `level` e `order` são somente leitura [24], e só se leem com `pagelevel=true` [16].
- Tags personalizados não são suportados [5].
- Mesclar células (`rowspan`/`colspan`) não é suportado [4].
- Linhas e células de tabela não se editam isoladamente [1].
- Cor de fundo da página não é suportada [4].

## Fontes
1. https://learn.microsoft.com/en-us/graph/onenote-update-page
2. https://learn.microsoft.com/en-us/graph/api/resources/patchcontentcommand?view=graph-rest-1.0
3. https://learn.microsoft.com/en-us/graph/api/page-update?view=graph-rest-1.0
4. https://learn.microsoft.com/en-us/graph/onenote-input-output-html
5. https://learn.microsoft.com/en-us/graph/onenote-note-tags
6. https://learn.microsoft.com/en-us/graph/onenote-abs-pos
7. https://learn.microsoft.com/en-us/graph/onenote-images-files
8. https://learn.microsoft.com/en-us/graph/onenote-create-page
9. https://learn.microsoft.com/en-us/graph/onenote-error-codes
10. https://learn.microsoft.com/en-us/graph/api/page-copytosection?view=graph-rest-1.0
11. https://learn.microsoft.com/en-us/graph/api/onenoteoperation-get?view=graph-rest-1.0
12. https://learn.microsoft.com/en-us/graph/api/notebook-post-sections?view=graph-rest-1.0
13. https://learn.microsoft.com/en-us/graph/api/sectiongroup-post-sections?view=graph-rest-1.0
14. https://learn.microsoft.com/en-us/graph/api/notebook-post-sectiongroups?view=graph-rest-1.0
15. https://learn.microsoft.com/en-us/graph/api/sectiongroup-post-sectiongroups?view=graph-rest-1.0
16. https://learn.microsoft.com/en-us/graph/onenote-get-content
17. https://learn.microsoft.com/en-us/graph/api/onenote-list-pages?view=graph-rest-1.0
18. https://devblogs.microsoft.com/microsoft365dev/onenote-get-pagessearch-api-deprecation
19. https://learn.microsoft.com/en-us/graph/api/resource-get?view=graph-rest-1.0
20. https://learn.microsoft.com/en-us/graph/throttling-limits (seção "OneNote service limits")
21. https://learn.microsoft.com/en-us/graph/api/resources/notebook?view=graph-rest-1.0
22. https://learn.microsoft.com/en-us/graph/api/resources/onenote-api-overview?view=graph-rest-1.0
23. https://learn.microsoft.com/en-us/archive/blogs/onenotedev/change-page-level
24. https://learn.microsoft.com/en-us/graph/api/resources/onenotepage (o link da v1.0 abriu a versão beta)
- ARMADILHAS: [`docs/ARMADILHAS.md`](../ARMADILHAS.md) (neste repo)