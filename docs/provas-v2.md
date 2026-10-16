# Provas reais da v2 (15/10/2026)

Conta que fez login (`Contributor` num bloco compartilhado por outra conta), seção de teste, página "MCP-teste
sondagem v2 (pode apagar)".
HTML de entrada e saída em `provas/` (fora do git). Script: POST multipart (Presentation + 1 PNG) e PATCHes.

| item | entrada | o que o OneNote guardou | veredito |
| --- | --- | --- | --- |
| h1–h6 | sem estilo | h1 16pt #1e4e79 · h2 14pt #2e75b5 · h3 12pt #5b9bd5 · h4 12pt #5b9bd5 itálico · h5 #2e75b5 · h6 #2e75b5 itálico (todos margin 5.5pt) | padrões medidos: a leitura omite |
| fonte da página | `<body style="font-family:Segoe UI">` | body volta Calibri; a fonte desce para cada span | funciona na prática |
| span | color, background, Consolas, 16px, u, del, strike, sup | `color:#c00000`, `background-color:yellow`, 16px→12pt, `red` continua `red`, u/del/strike viram `text-decoration` | ok; leitura normaliza nome→hex |
| cite | `<cite>` | texto fica, estilo some | não usar |
| lista aninhada | ul>li>ul>li>ul | 3 níveis preservados (o pai vira `<p>` dentro do li) | ok |
| ol tipo | `ol style=lower-alpha` | o tipo desce para cada `li` | ok |
| br extra | — | 3 `<br />` apareceram depois do `ul` aninhado | ruído: leitura ignora br solto |
| to-do | `to-do`, `to-do:completed` | iguais | ok |
| várias tags | `important, idea` | `important,idea` | ok |
| definition | `definition` | `remember-for-later` | documentado: avisar |
| call-back | `call-back` | **`schedule-meeting`** | bug: fora da spec |
| tabela borda | `border="1"` | `border:1px solid` na table e nos td | ok |
| bgcolor na table | `bgcolor` | some | usar fundo no td |
| largura td | `width:200px` | `width:199` | ok |
| destaque | table border=0 + td fundo | igual | ok |
| pre em td | `<pre>` com `\n` | `pre` some, quebra vira U+FFFC | código = 1 `<p>` por linha em Consolas |
| div com data-id | `<div data-id=secaoA>` | preservada | ok |
| links | `onenote:` e `https:` | preservados | ok |
| divisória | p cinza com ─ | ok | ok |
| imagem | `img src="name:img1"` + parte PNG | `src` vira `.../resources/{id}/$value`, `data-id` mantido | ok |
| data retroativa | `meta created` | aceita | ok |
| PATCH replace por id gerado | `<p data-id="par1">` novo | data-id mantido | ok |
| PATCH append em `#secaoA` | — | ok | ok |
| PATCH insert after `#t1` | — | ok | ok |
| PATCH com 2 comandos, 2º inválido | — | 400 e **nada aplicado** | atômico |

Fora da v2 por cautela (não provado e mexe em bloco de terceiro): criar seção, copiar página, layout livre.

## Vitrine (passo 7, 15/10/2026)

Página "Vitrine ONMD v2 (pode apagar)", mesma seção, criada pelo `criar_pagina` com todas as construções da spec
(ONMD enviado, HTML criado e final em `provas/vitrine-*`). Edições pelas tools: `marcar_tarefa`, `editar` (célula
da `<tabela>`), `inserir` depois de `## Tabelas`, `acrescentar(onde="#notas")`, `renomear_pagina`: todas
conferidas no GET seguinte, sem aviso.

| item | entrada | o que o OneNote guardou | veredito |
| --- | --- | --- | --- |
| `<li>` soltos (lista com etiqueta) no POST | `<li data-tag>x</li><li>y</li>` | embrulhados num `<ul>` com id gerado; a etiqueta desce para `<span data-tag>` dentro do `li` | ok: a lista volta editável |
| duas listas soltas seguidas | separadas por linha em branco | uma lista só | igual ao markdown (linha em branco não separa lista) |
| `editar` que põe etiqueta num item de `ol` | PATCH `replace` de `ol:{…}` por `<li style=lower-alpha>` soltos | aceito; vira `<ol>` novo, tipo mantido, cada `li` com `value="1"` | ok; numeração na tela não conferida |
| `<br />` dentro de `<p>` | `Linha um<br />linha dois` | `Linha um<br />\n\nlinha dois` | a leitura descarta a quebra de formatação depois do `br` (corrigido) |
| largura da tabela | `table style=width:499px` + 1º `td` 187px | some da `table`; desce para os `td` (186 e 312) | equivalente: a leitura mostra `largura` em cada célula |
| largura de imagem | `width=312` em PNG 800 px · 312 e 31 em PNG 48 px | 800 px: `width=312 height=39` · 48 px: `width` some | imagem pequena fica no tamanho natural |
| link `pagina:` | `<a href="onenote:https://…">` | igual | a leitura devolve o `onenote:` (a escrita aceita de volta) |
| cor em hex da paleta | `color:#7030A0` | `#7030a0` | a leitura devolve o nome (`roxo`) |
| PATCH multipart com 2 imagens | `acrescentar(anexos=[2 PNG])` | 2 `img` com recurso próprio | ok |

## Listas aninhadas (15/10, conferido no site)

Lista aninhada criada pelo Graph aparece no site do OneNote com **um parágrafo vazio antes de cada sub-nível**.
Conferido no site em todas as 10 variantes testadas: `li>ul` (o que a escrita gera), `ul` irmão do `li`,
`li>p+ul`, `ol` aninhada, cópia exata do HTML que o próprio site devolve (`<p style="margin…5.5pt">`), listas
separadas com `margin-left` (viram 4 listas soltas com espaço), `li` sem marcador, `p` com `margin-left` (recuo
ignorado), `span` 11pt, fonte mínima no `ul`, margens zero, e também via PATCH `insert`.

A mesma lista digitada no site não tem o espaço, e o GET devolve HTML igual ao nosso: o parágrafo vazio não
aparece no GET, então não há alvo para removê-lo. O editor do site salva por outro protocolo
(`onenote.officeapps.live.com/o/OneNote.ashx`), fora do Graph. Conclusão: limite da Microsoft. A escrita mantém o
HTML e avisa ("sub-item de lista…"); a spec recomenda títulos ou lista de um nível.

## Parágrafo grudado na lista (15/10, página real com 87 blocos)

`editar` regravou 31 blocos de uma página criada pela v1; 29 ficaram no lugar e os 2 parágrafos que vinham logo
antes de uma `<ol>` ("já dá:", "ainda não:") foram parar **depois** da lista. No GET da página original, cada
`ol`/`ul` tem id gerado menor que o do parágrafo anterior (`p {50}` seguido de `ol {48}`): o OneNote guarda o
parágrafo grudado na lista. Prova isolada numa página nova (`p` + `ol` + `p` + `ol`): `replace` só no parágrafo e
`replace` no parágrafo **e** na lista no mesmo PATCH dão o mesmo resultado (parágrafo depois da lista).
Conclusão: `editar` e `marcar_tarefa` recusam bloco seguido de lista.

## Página que não carrega (15/10)

Uma página criada com 17 KB de HTML ficou sem título e com `GET /content` 404 por mais de 10 min (os metadados
existem). O mesmo conteúdo enviado de novo ficou legível em 52 s. Falha de processamento da Microsoft: recriar.
