# OneNote via Graph: o que a criação de página aceita

> Nota histórica de pesquisa, escrita antes do código da v2; não é manual (ver o [README](../../README.md)).

Este levantamento cobre tudo o que a criação de página aceita e diz, para cada item, se funciona em conta pessoal. Nenhum arquivo do projeto foi alterado.

## Fontes

As afirmações citam a fonte pelo código entre colchetes.

| código | URL |
| --- | --- |
| [IO] | https://learn.microsoft.com/en-us/graph/onenote-input-output-html |
| [CP] | https://learn.microsoft.com/en-us/graph/onenote-create-page |
| [IF] | https://learn.microsoft.com/en-us/graph/onenote-images-files |
| [NT] | https://learn.microsoft.com/en-us/graph/onenote-note-tags |
| [AP] | https://learn.microsoft.com/en-us/graph/onenote-abs-pos |
| [EX] | https://learn.microsoft.com/en-us/graph/onenote-extract-data |
| [UP] | https://learn.microsoft.com/en-us/graph/onenote-update-page |
| [SPP] | https://learn.microsoft.com/en-us/graph/api/section-post-pages?view=graph-rest-1.0 |
| [OC] | https://learn.microsoft.com/en-us/graph/open-onenote-client |
| [PG] | https://learn.microsoft.com/en-us/graph/api/resources/onenotepage?view=graph-rest-1.0 |
| [SEC] | https://learn.microsoft.com/en-us/graph/api/resources/onenotesection?view=graph-rest-1.0 |
| [CTS] | https://learn.microsoft.com/en-us/graph/api/page-copytosection?view=graph-rest-1.0 |
| [WC] | https://github.com/OneNoteDev/WebClipper/blob/main/docs/client-side-migration.md |
| [WCR] | https://github.com/OneNoteDev/WebClipper/blob/main/src/scripts/renderer.ts |

[WC] e [WCR] são do Web Clipper oficial da Microsoft, que grava pela API antiga `www.onenote.com/api/v1.0`, não pelo Graph.

**Graus de prova usados na coluna "grau":**
- **DOC**: está em tabela ou lista oficial.
- **EX**: aparece só em exemplo oficial.
- **ND**: não documentado.
- **CONTRA**: a própria documentação se contradiz.
- **PROVA**: precisa de teste real (POST seguido de GET `/content`).

## 0. Conta pessoal (vale para tudo abaixo)

- Estas páginas trazem o aviso "Applies to Consumer notebooks on OneDrive": [CP], [IF], [NT], [EX] e [UP].
- [IO] e [AP] não trazem esse aviso.
- As tabelas de permissão de [SPP] e [CTS] têm a linha "Delegated (personal Microsoft account): Notes.Create / Notes.ReadWrite". Ou seja, `Notes.ReadWrite` em conta pessoal cria página e copia página.
- Na prática, só foi provado aqui criar página e fazer PATCH de append, com a conta de teste (ver docs/ARMADILHAS.md). Nenhum recurso rico foi testado em conta pessoal; em todas as linhas abaixo, "pessoal: sim" quer dizer "a documentação diz que sim".

## 1. Estrutura do documento e regras gerais

| grau | item | detalhe exato | pessoal | fonte |
| --- | --- | --- | --- | --- |
| DOC | XHTML bem-formado, UTF-8 | toda tag aberta precisa ser fechada; atributo sempre entre aspas | sim | [CP] |
| DOC | Content-Type | `text/html` ou `application/xhtml+xml`; em caso de 400, usar `charset=utf-8`; multipart exige CRLF | sim | [CP] |
| DOC | o que é removido | JavaScript, arquivos incluídos e CSS (bloco `<style>`, `<link>`); formulários somem inteiros | sim | [CP] |
| DOC | tags básicas listadas | head, body, title, meta, h1–h6, p, ul, ol, li, table, tr, td (com tabela aninhada), pre, b, i; tag fora da lista "provavelmente será ignorada" | sim | [CP] |
| DOC | `<title>` | define o título da página; aceita `data-tag`, mas a nota não volta no GET | sim | [CP] [NT] |
| CONTRA | `<meta name="created">` | [CP] e [IO] usam `content="2015-07-22T09:00:00-08:00"`; os exemplos de [IF] usam `value=`. Usar `content=` | sim | [CP] [IO] [IF] |
| DOC | atributos `id` de entrada | descartados; o servidor gera os próprios ids (`?includeIDs=true`) | sim | [UP] |
| DOC | `data-id` | referência estável em div, p, h1–h6, img, object, ul, ol, li e table, usada como alvo `#x` no PATCH | sim | [IO] [UP] |
| DOC | `<div>` sem semântica | o conteúdo é movido para o pai e a div some; ela só fica se tiver `data-id` | sim | [IO] |

## 2. CSS inline: lista fechada

Vale em body, div, p, li, span e em outros elementos do corpo. A lista completa é esta [IO §Styles]:

| grau | propriedade | valores e regra | pessoal | fonte |
| --- | --- | --- | --- | --- |
| DOC | `background-color` | hex ou nome de cor; padrão branco; **não funciona no `body`** | sim | [IO] |
| DOC | `color` | hex ou nome; padrão preto | sim | [IO] |
| DOC | `font-family` | qualquer nome, ex.: `Courier`, `Segoe UI Black`; padrão Calibri | sim | [IO] |
| DOC | `font-size` | aceita pt ou px; px vira pt (o exemplo mostra 16px saindo como 12pt); arredonda para n.0 ou n.5; padrão 11pt | sim | [IO] |
| DOC | `font-style` | só `normal` ou `italic` | sim | [IO] |
| DOC | `font-weight` | só `normal` ou `bold` (sem 600 etc.) | sim | [IO] |
| DOC | `text-decoration` | `none`, `underline` ou `line-through` | sim | [IO] |
| DOC | `text-align` | só em elemento de bloco | sim | [IO] |
| DOC | `list-style-type` | ver seção 4 | sim | [IO] |
| DOC | `width` | em table e td, em px ou %; em div, img e object só no posicionamento absoluto | sim | [IO] [AP] |
| DOC | `max-width`, `max-height` | só em img | sim | [IF] |
| ND | `margin`, `padding`, `border` (fora de table), `line-height`, `font-variant`, sombra, gradiente | não estão na lista. `margin-top`/`margin-bottom` aparecem só na **saída** do h1. Tratar como não suportados na entrada | — | [IO] |

Tags de estilo de caractere documentadas: `b`, `i`, `u`, `em`, `strong`, `strike`, `sup`, `sub`, `del`, `cite` [IO §Styles].

Nas tags, `<span style>` é o caminho documentado para cor, realce e fonte dentro da linha (exemplo `<span style="font-size:16px;color:#ff0000;font-family:Segoe UI Black">`); a saída também devolve tudo em span [IO §Paragraphs and headings].

`<s>`, `<code>`, `<blockquote>` e `<hr>` não são documentados (grau ND). O Web Clipper remove `hr` como "not supported in ONML" [WCR].

## 3. Títulos h1–h6

| grau | item | detalhe | pessoal | fonte |
| --- | --- | --- | --- | --- |
| DOC | h1–h6 | suportados; aceitam `data-id`, `data-tag` e `style` | sim | [CP] [IO] |
| EX | estilo padrão do h1 | a saída mostra `font-size:16pt;color:#1e4e79;margin-top:11pt;margin-bottom:11pt` | sim | [IO] |
| ND | estilo padrão de h2–h6 | não aparece em nenhuma doc. Medir com um POST de h1–h6 seguido de GET `/content` | PROVA | — |
| DOC | estilo próprio no título | `style` com cor, tamanho e fonte da lista da seção 2; a saída pode mover o estilo para spans | sim | [IO] |

## 4. Listas

| grau | item | detalhe | pessoal | fonte |
| --- | --- | --- | --- | --- |
| DOC | `ol`, `ul`, `li` | aceitam `data-id`, `data-tag` e `style` | sim | [IO] |
| DOC | `list-style-type` em ol | `none`, `decimal` (padrão), `lower-alpha`, `lower-roman`, `upper-alpha`, `upper-roman` | sim | [IO] |
| DOC | `list-style-type` em ul | `none`, `disc` (padrão), `circle`, `square` | sim | [IO] |
| DOC | estilo por item | pode ser diferente em cada `li`; o estilo global vai no ol/ul e volta em cada li ou span | sim | [IO] |
| ND | numeração própria (`start`, `value`, `counter-reset`, marcador customizado) | nada documentado; só os seis tipos acima | — | — |
| ND | lista aninhada (ul dentro de li) | nenhum exemplo nem regra na doc | PROVA | — |

## 5. Tabelas

| grau | item | detalhe | pessoal | fonte |
| --- | --- | --- | --- | --- |
| DOC | `table`, `tr`, `td` e tabela aninhada | suportados | sim | [CP] [IO] |
| DOC | `rowspan`, `colspan` (células mescladas) | **não suportados** | — | [IO] |
| DOC | atributos de table | `border` (largura da borda), `width`, `bgcolor` | sim | [IO] |
| DOC | `style="border:..."` na table | **não suportado** na entrada | — | [IO] |
| CONTRA | borda funciona? | o exemplo oficial envia `border="1"`, mas a saída oficial mostra `border:0px` na table e em cada td | PROVA | [IO] |
| DOC | largura | `style="width:..."` em table e td, em px ou %; o exemplo mostra `Width="500"` virando `width:166` em cada uma das 3 colunas, então a largura por coluna é feita pelo td | sim | [IO] |
| DOC | cor de célula | `background-color` em td funciona; em tr é empurrado para os td; `bgcolor` da table pinta todas as células | sim | [IO] |
| DOC | `text-align` em td | funciona | sim | [IO] |
| ND | `th`, `thead`, `tbody`, `caption` | fora da lista; o atual `<th>` → `<td><b>` está certo | — | [CP] |
| DOC | PATCH em tabela | só substitui a tabela inteira pelo id gerado; tr e td não se alteram | sim | [UP] |

## 6. Note tags e checkboxes

**Onde aceita `data-tag`** [NT]:
- em `p`, `ul`, `ol`, `li`, `img`, `h1`–`h6` e `title`;
- várias tags no mesmo elemento, separadas por vírgula: `data-tag="idea, send-in-email, question"`;
- tag customizada **não é suportada**.

**Lista completa de valores** [NT]:
- **Com checkbox** (aceitam `:completed`): `to-do`, `discuss-with-person-a`, `discuss-with-person-b`, `discuss-with-manager`, `schedule-meeting`, `call-back`, `to-do-priority-1`, `to-do-priority-2`, `client-request`.
- **Sem checkbox**: `important` (estrela), `question`, `definition`, `highlight`, `contact`, `address`, `phone-number`, `web-site-to-visit`, `idea`, `password`, `critical`, `project-a`, `project-b`, `remember-for-later`, `movie-to-see`, `book-to-read`, `music-to-listen-to`, `source-for-article`, `remember-for-blog`, `send-in-email`.

**Checkboxes:**
- `<p data-tag="to-do">` cria a caixa vazia e `<p data-tag="to-do:completed">` a marcada.
- A doc recomenda `p` em vez de `li` para listas de tarefas.
- Para marcar depois: PATCH `replace` no `p` pelo id gerado [NT] [UP].

**Regras em listas** [NT]:
- `data-tag` no ul/ol **sobrepõe** as tags dos li.
- Para tags diferentes por item, mandar `li` soltos, sem ul ou ol; a saída os embrulha num ul.
- Na saída, a tag vem em `span` dentro do li.

**Pegadinha** [NT]: `definition` volta no GET como `remember-for-later`.

Pessoal: sim, pelo aviso de [NT].

## 7. Imagens

| grau | forma | detalhe | dentro da restrição? | pessoal | fonte |
| --- | --- | --- | --- | --- | --- |
| DOC | `src="name:parte"` + parte binária no multipart | bytes crus, sem base64 | **sim** | sim | [IF] [CP] |
| DOC (PATCH) / EX (POST antigo) / ND (POST Graph) | `src="data:image/...;base64,..."` | [UP] diz que imagem no PATCH tem de ser "image-data-url or a part-name" e que link www não é baixado. [CP] e [IF] não citam data URL no POST. O Web Clipper mandava `<img src="data:image/jpeg;base64,...">` na parte Presentation da API antiga e trocou por parte binária só por causa dos ~33% a mais do base64 [WC]. Conclusão: **provável no POST, documentado no PATCH, não provado no POST do Graph** | sim | PROVA | [UP] [WC] |
| DOC | `src="https://..."` | o servidor da Microsoft baixa a imagem | **fora** | sim | [IF] |
| DOC | `data-render-src="https://..."` (foto da página web) | o servidor busca a URL | **fora** | sim | [IF] |
| DOC | `data-render-src="name:parte-html"` (HTML vira imagem) | o renderizador da Microsoft desenha uma parte HTML enviada no multipart. **Atenção:** o próprio exemplo da doc põe `<img src="https://cdn...">` dentro dessa parte e o renderizador busca. Para caber na restrição, a parte HTML precisa ser limpa de qualquer URL externa (img, link, `@import`, `url()` no CSS). Sem login nem plugins | **sim, só com HTML limpo** | sim | [IF] |
| DOC | atributos | `alt`, `width` e `height` (pixels sem "px", ex.: `width="400"`), `style` com width, height, max-width e max-height, `data-tag`, `data-id` | — | sim | [IO] [IF] |
| DOC | formatos | TIFF, PNG, GIF, JPEG, BMP; o tipo é detectado sozinho e volta em `data-fullres-src-type` | — | sim | [IF] [IO] |
| DOC | imagem fatiada | o que vem de `data-render-src` pode voltar dividido em várias imagens com o mesmo `data-id` e `data-index` | — | sim | [IO] |

## 8. Anexos e PDF

| grau | item | detalhe | dentro da restrição? | pessoal | fonte |
| --- | --- | --- | --- | --- | --- |
| DOC | anexo de arquivo | `<object data="name:parte" data-attachment="nome.ext" type="mime" />`, os três obrigatórios; **URL em `data` não é aceita** | **sim** | sim | [IO] [IF] |
| DOC | MIME com ícone próprio | application/pdf, .docx, .pptx, .xlsx (openxml), image/png, image/jpeg, image/gif, audio/wav, video/mp4, application/msword, application/mspowerpoint, application/excel; os demais ganham ícone genérico | — | sim | [IF] |
| DOC | `style` no object | só posicionamento absoluto (left e top) | — | sim | [IO] |
| DOC | PDF como imagens | `<img data-render-src="name:parte" />` com a parte em `Content-Type: application/pdf`; cada página do PDF vira uma imagem (saída `data-options="printout"`). Junto com um `<object>` do mesmo arquivo dá "impressão + anexo", mas são duas partes e contam no limite de 4 MB | **sim** | sim | [IF] [IO] |
| DOC | vídeo | `<iframe data-original-src="https://youtube...">`; sites aceitos: Dailymotion, Office Mix, Sway, Sketchfab, TED, YouTube, Vimeo, Vine; tamanho padrão 480×360 | **fora** (URL externa) | sim | [IF] [IO] |
| DOC | extração (`div data-render-method`) | `extract.businesscard` sobre imagem `name:` cabe na restrição; `extract.recipe` e `extract.product` buscam URL, ficam fora. O Clipper deixou de usar o servidor de extração [WC]; não confirmado que ainda funcione | só cartão de visita | sim (aviso [EX]) | [EX] |

## 9. Posicionamento absoluto

Fonte de tudo nesta seção: [AP] e [IO]. [AP] não traz o aviso de conta pessoal, então em conta pessoal está **PROVA**.

**Como ligar:**
- Exige `<body data-absolute-enabled="true">`; sem isso, todas as posições são ignoradas.
- Só `div`, `img` e `object` podem ser posicionados, sempre como **filhos diretos do body** e com `style="position:absolute"`.
- O resto vai para a div `_default`.

**Propriedades aceitas** (todas só em px):

| propriedade | onde vale | padrão |
| --- | --- | --- |
| `top` | div, img, object | 120px |
| `left` | div, img, object | 48px |
| `width` | div e img | — |
| `height` | só img (na div é calculado e ignorado) | — |

**Limites:**
- `z-index` é ignorado.
- Elemento posicionado não pode ser aninhado: a posição interna é ignorada e volta aviso em `api.diagnostics`.
- O ponto 0:0 é o canto de cima à esquerda, acima do título.
- img posicionada aceita `src` ou `data-render-src`.

**PATCH:** div absoluta só aceita append; img e object absolutos não aceitam nenhuma ação [UP].

## 10. Links

| grau | item | detalhe | pessoal | fonte |
| --- | --- | --- | --- | --- |
| EX | `<a href="https://...">` | fora da lista básica de [CP], mas no exemplo oficial de entrada e saída de [IO]; o PATCH não altera `a` | sim | [IO] [UP] |
| DOC | links de página, seção e bloco | `links.oneNoteClientUrl.href` (`onenote:https://...`) e `links.oneNoteWebUrl.href` voltam no POST e GET de página e de bloco; a seção tem `links` (sectionLinks) | sim | [OC] [PG] [SEC] |
| ND | `<a href="onenote:...">` no corpo como link interno | nada documentado. Caminho provável: ler o `links` da página alvo e pôr no href. O sanitizador já aceita `onenote:` | PROVA | — |

## 11. Citação e código

| grau | item | detalhe | fonte |
| --- | --- | --- | --- |
| DOC | `<cite>` | estilo de caractere suportado | [IO] |
| DOC | `<pre>` | preserva espaços e quebras de linha | [CP] |
| ND | `<code>`, `<blockquote>` | não documentados | — |
| DOC | texto monoespaçado | via `style="font-family:Consolas"` (ou Courier); fonte livre está na lista da seção 2 | [IO] |

## 12. Tamanho e layout da página

- **EX:** a div padrão é criada em `left:48px;top:120px;width:624px` [IO]. O Clipper também usa 624px como "OneNotePageWidth" [WC].
- **ND:** não há atributo de tamanho ou orientação da página; a largura útil só se controla com `width` em div absoluta ou em table/td.
- Cor de fundo no `body` **não é suportada** [IO].

## 13. Limites

| grau | limite | fonte |
| --- | --- | --- |
| DOC | pedido de **4 MB** no Graph; acima disso, erro 413 | [IF] |
| DOC | ~70 MB por POST e 25 MB por parte valem **só para a API OneNote por baixo**, que o Graph não alcança | [IF] |
| DOC | **6 partes** por POST, contando a Presentation | [IF] |
| DOC | até **5 img** com `data-render-src` e **1 object** por pedido; o excedente é ignorado | [IF] |
| DOC | **30 imagens** por POST, qualquer que seja o método | [IF] |
| DOC | **150 imagens** por página | [IF] |
| DOC | seção cheia devolve **507** "Exceeded the maximum number of pages allowed per section" (número não publicado) | [CP] |
| DOC | PATCH com binário: multipart com parte `Commands` (application/json) e as partes `name:` | [UP] |

## 14. O que o `conteudo.py` atual deixa de fora

Só leitura, nenhum arquivo foi editado. A diferença entre o que a documentação permite e o que o `conteudo.py` da v1 (removido na v2) deixa passar:

- **Some com todo `style` e com `<span>`:** perde cor, realce (`background-color`), fonte, tamanho, alinhamento, `list-style-type`, largura e cor de célula. São todos documentados [IO].
- **Some com `data-tag`:** não há checkbox nem estrela [NT].
- **Atributos de `<table>` caem:** `border`, `width` e `bgcolor` não passam [IO].
- **Passam tags não documentadas:** `blockquote`, `code`, `hr` e `s`. O `hr` o Clipper trata como não suportado [WCR]. Para riscado, o documentado é `del`, `strike` ou `text-decoration:line-through`.
- **Faltam `cite` e `strike`,** que são documentados [IO].
- **Bloqueio de `img`, `object`, `iframe` e `data-render-src`:** está correto contra texto do modelo. O caminho seguro documentado é `src`/`data`/`data-render-src` = `name:` com bytes que o próprio servidor do MCP monta a partir de arquivo local ou data URL; `name:` digitado pelo modelo não é seguro por si.
- **Parte HTML renderizada como imagem:** se um dia entrar, precisa de limpeza própria contra URL externa, porque o renderizador busca imagens externas (exemplo de [IF]).

## 15. Próximo passo: provas antes de prometer ao dono

Uma página de teste numa seção permitida, depois GET `/content` para ler o que voltou. Itens a provar:
1. h2–h6;
2. lista aninhada;
3. `border="1"` na tabela;
4. `data:` em img no POST;
5. `<a href="onenote:...">`;
6. `hr`, `code` e `blockquote`;
7. posicionamento absoluto em conta pessoal.