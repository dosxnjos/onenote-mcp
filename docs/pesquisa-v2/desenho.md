# onenote-mcp v2: desenho

> **Nota histórica.** Este doc e os vizinhos de `docs/pesquisa-v2/` são notas de pesquisa e desenho, escritas antes
> do código da v2. Não são manual: chaves, comandos e passos citados aqui podem não existir (ex.: `[teste]` no
> config e o comando `prova`, que não foram feitos). O que vale para usar é o [README](../../README.md) e a
> [spec](../../onenote_mcp/formato/spec.md).

Nenhum arquivo do projeto foi alterado. O desenho se apoia no código atual (`onenote_mcp/*.py`, `README.md`, `docs/ARMADILHAS.md`), nas três pesquisas e em três páginas da Microsoft que reli para ter os detalhes de transmissão: [IF], [UP] e [IO].

**Nota sobre o pedido repassado** ("acabei de dar consent nas 3 na nova conta"): ele não pede nenhuma ação nesta etapa. Mas a escrita só foi provada com a conta de teste (`Contributor` no bloco compartilhado) [ARM]. Por isso o passo 0 do plano confere com qual conta o login vale antes de qualquer prova.

## Fontes (o código entre colchetes aparece em cada afirmação)

| código | URL |
|---|---|
| IO | https://learn.microsoft.com/en-us/graph/onenote-input-output-html |
| CP | https://learn.microsoft.com/en-us/graph/onenote-create-page |
| IF | https://learn.microsoft.com/en-us/graph/onenote-images-files |
| NT | https://learn.microsoft.com/en-us/graph/onenote-note-tags |
| AP | https://learn.microsoft.com/en-us/graph/onenote-abs-pos |
| UP | https://learn.microsoft.com/en-us/graph/onenote-update-page |
| PCC | https://learn.microsoft.com/en-us/graph/api/resources/patchcontentcommand?view=graph-rest-1.0 |
| ERR | https://learn.microsoft.com/en-us/graph/onenote-error-codes |
| GC | https://learn.microsoft.com/en-us/graph/onenote-get-content |
| CTS | https://learn.microsoft.com/en-us/graph/api/page-copytosection?view=graph-rest-1.0 |
| OP | https://learn.microsoft.com/en-us/graph/api/onenoteoperation-get?view=graph-rest-1.0 |
| NPS | https://learn.microsoft.com/en-us/graph/api/notebook-post-sections?view=graph-rest-1.0 |
| SGS | https://learn.microsoft.com/en-us/graph/api/sectiongroup-post-sections?view=graph-rest-1.0 |
| RG | https://learn.microsoft.com/en-us/graph/api/resource-get?view=graph-rest-1.0 |
| DEP | https://devblogs.microsoft.com/microsoft365dev/onenote-get-pagessearch-api-deprecation |
| THR | https://learn.microsoft.com/en-us/graph/throttling-limits |
| NFM | https://developers.notion.com/guides/data-apis/notion-flavored-markdown |
| WMC | https://developers.notion.com/guides/data-apis/working-with-markdown-content |
| NMT | https://developers.notion.com/docs/mcp-supported-tools |
| NMR | https://github.com/makenotion/notion-mcp-server |
| WCR | https://github.com/OneNoteDev/WebClipper/blob/main/src/scripts/renderer.ts |
| ARM | [`docs/ARMADILHAS.md`](../ARMADILHAS.md) (neste repo) |

**Graus de prova usados abaixo:**
- **DOC**: está em tabela ou lista oficial.
- **EX**: aparece só em exemplo oficial.
- **ND**: não documentado.
- **CONTRA**: a própria documentação se contradiz.
- **PROVA**: depende de teste real, que é o passo 1 do plano.

### Correções às pesquisas (relendo a fonte primária)

1. **Limite de `object` por pedido.** O texto literal de [IF] é "up to five **img** elements that use **data-render-src** and one **object** elements that uses **data-render-src**". Ele não diz "1 object por pedido" de forma geral; a frase é ambígua. O desenho fica conservador (1 anexo por pedido) até a prova 1.12.
2. **Exemplos de [IF] com nomes que não batem.** Num exemplo, a imagem usa `src="name:image-block-name"` e a parte se chama `MyAppPictureId`; no outro, `data="name:image-block-name"` e a parte se chama `logo1-file`. Não servem de modelo. O montador de multipart do MCP cria o nome e a referência a partir da mesma variável.
3. **Riscado não é valor de `text-decoration`.** A tabela de estilos de [IO] diz `text-decoration` "none or underline only" e põe o riscado numa linha à parte, `text-decoration:line-through` ("strike-through"). Na escrita, o riscado vai como `<del>`, que é DOC [IO].
4. **A cor pode voltar com outro nome.** O exemplo de saída de [IO] devolve `color:#ff0000` como `color:red`. A leitura precisa normalizar cor nomeada para hex antes de reconhecer a paleta.
5. **`<body style>` é DOC.** A entrada aceita `style` no body (menos `background-color`), e a saída devolve `font-family`/`font-size` no body [IO]. Isso permite fonte padrão por página.

---

# 1. Formato de conteúdo: "ONMD" (markdown do OneNote)

## 1.0 Princípios (copiados do Notion, adaptados)

- **Base:** CommonMark/GFM. O que é próprio do OneNote vira tag em pt-BR (`<destaque>`, `<colunas>`, `<tabela>`, `<anexo>`, `<secao>`, `<caixa>`) ou um bloco de atributos `{…}` no fim do bloco. O Notion faz o mesmo e proíbe HTML cru [NFM]. Aqui, **HTML cru do modelo também não passa**: tag fora da spec vira texto literal e gera um aviso.
- **Um dialeto nos dois sentidos.** `ler_pagina` devolve ONMD, e `editar` procura o trecho nesse mesmo ONMD. O Notion lê e escreve no mesmo formato pelo mesmo motivo [NMT][WMC]. Hoje a leitura usa markdownify e a escrita usa python-markdown; esse descompasso acaba.
- **A spec é texto curto, escrito para IA,** com um exemplo completo no fim. Ela é exposta como recurso MCP `onenote://docs/formato` e também pela tool `ler_spec()`. Toda tool de escrita diz na descrição "leia a spec antes; não invente sintaxe" [NMT].
- **Título nunca vai no corpo.** Vai no parâmetro `titulo`, que vira `<title>` [CP]. O Notion tem a mesma regra [NMT].

## 1.1 Bloco de atributos `{…}` (vale para todo bloco)

O bloco de atributos fica no fim da linha do bloco, separado por espaço:

```
Texto do parágrafo {id=resumo cor=azul fundo=amarelo fonte="Segoe UI" tamanho=14 alinhar=centro tags=important,idea}
```

| chave | HTML gerado | grau |
|---|---|---|
| `id=x` | `data-id="x"`. Regex `[a-z0-9][a-z0-9_-]{0,47}`; o prefixo `on-` é reservado | DOC [IO][UP] |
| `cor=` | `color:<hex>` | DOC [IO] |
| `fundo=` | `background-color:<hex>` | DOC [IO] |
| `fonte=` | `font-family:<nome>` | DOC [IO] |
| `tamanho=` | `font-size:<n>pt`. O valor é normalizado para n.0 ou n.5 entre 6 e 72; o OneNote arredonda assim [IO] | DOC [IO] |
| `alinhar=esquerda/centro/direita` | `text-align:left/center/right`, só em bloco | DOC [IO] |
| `tags=a,b` | `data-tag="a, b"`, só com valores da lista oficial (§1.6) | DOC [NT] |

`id` vale em `p`, `h1`–`h6`, `ul`, `ol`, `li`, `table`, `img`, `object` e `div` [IO][UP]. Em `table`, só `id` e as chaves próprias de `<tabela>` (§1.7).

**Paleta fechada.** O modelo erra menos com nomes, e a página fica coerente; o Notion usa paleta fechada pelo mesmo motivo [NFM]. Hex `#rrggbb` também é aceito como saída de emergência.

| nome | `cor` (texto) | `fundo` (caixa ou célula) |
|---|---|---|
| cinza | #595959 | #EDEDED |
| marrom | #843C0C | #EFE3D9 |
| laranja | #C55A11 | #FCE4D6 |
| amarelo | #BF8F00 | #FFF2CC |
| verde | #548235 | #E2EFDA |
| azul | #2E75B6 | #DDEBF7 |
| roxo | #7030A0 | #E9DDF4 |
| rosa | #C2185B | #FADBE7 |
| vermelho | #C00000 | #F8D7DA |

O realce de marca-texto é o `==x==` (§1.3).

## 1.2 Página e blocos de texto

| construção | sintaxe | HTML exato gerado | grau |
|---|---|---|---|
| título | parâmetro `titulo` | `<title>Título</title>` | DOC [CP] |
| fonte padrão da página | parâmetro `fonte_padrao={"fonte":"Segoe UI","tamanho":11}` | `<body style="font-family:Segoe UI;font-size:11pt">`. Cor de fundo da página não é suportada | DOC [IO] |
| parágrafo | texto solto | `<p>texto</p>` | DOC [CP] |
| linha em branco extra | `<vazio/>` | `<br />` | EX [IO] |
| títulos | `#` … `######` | `<h1>`…`<h6>`; com `{…}` ganham `style`/`data-id`/`data-tag` | DOC [CP][IO]. Estilo padrão: h1 = 16pt #1e4e79 (EX [IO]); h2–h6 em PROVA |
| divisória | `---` | `<p style="color:#BFBFBF">────────────────────────────────</p>`. `hr` não é suportado; o Clipper descarta [WCR] | emulação; o `<p>` com cor é DOC [IO] |

## 1.3 Estilos dentro da linha

| sintaxe | HTML | grau |
|---|---|---|
| `**x**` | `<b>x</b>` | DOC [IO] |
| `*x*` | `<i>x</i>` | DOC [IO] |
| `<u>x</u>` | `<u>x</u>` | DOC [IO] |
| `~~x~~` | `<del>x</del>` | DOC [IO] |
| `<sup>x</sup>` / `<sub>x</sub>` | idem | DOC [IO] |
| `<cite>x</cite>` | idem | DOC [IO] |
| `==x==` (marca-texto) | `<span style="background-color:#FFFF00">x</span>` | DOC [IO][NT] |
| `` `x` `` (código na linha) | `<span style="font-family:Consolas;font-size:10pt">x</span>` (`<code>` é ND) | DOC [IO] |
| `<span cor=vermelho fundo=amarelo fonte="Segoe UI Black" tamanho=16>x</span>` | `<span style="color:#C00000;background-color:#FFF2CC;font-family:Segoe UI Black;font-size:16pt">x</span>` | DOC [IO] (exemplo literal de span com essas propriedades) |
| `[texto](https://…)` | `<a href="https://…">texto</a>` | EX [IO]; `a` não aceita PATCH [UP] |
| `[texto](pagina:<id>)` (link para página) | o servidor confere se a página está na lista permitida, lê `links.oneNoteClientUrl.href` dela e gera `<a href="onenote:https://…">texto</a>` | os links da página são DOC (pesquisa html-entrada: [OC][PG]). Clicar o `onenote:` no corpo é **PROVA** |

## 1.4 Listas

| sintaxe | HTML | grau |
|---|---|---|
| `- item` | `<ul><li>item</li></ul>` | DOC [IO] |
| `1. item` | `<ol><li>…</li></ol>` (decimal) | DOC [IO] |
| `a.` / `A.` / `i.` / `I.` no 1º item | `<ol style="list-style-type:lower-alpha / upper-alpha / lower-roman / upper-roman">` | DOC [IO] |
| `{marcador=circulo/quadrado/nenhum}` sozinho na linha antes de uma lista `-` | `<ul style="list-style-type:circle/square/none">` | DOC [IO] |
| `{numero=nenhum}` antes de uma lista numerada | `<ol style="list-style-type:none">` | DOC [IO] |
| sub-item (recuo de 2 espaços) | `<li>pai<ul><li>filho</li></ul></li>` | **PROVA** (nada documentado) |
| item com estilo próprio `- x {cor=verde}` | `<li style="color:#548235">x</li>`. Com tipo não padrão, o `list-style-type` se repete no `li`, porque é o `li` que guarda o tipo na saída [IO][UP] | DOC |

## 1.5 Tarefas (to-do)

| sintaxe | HTML | grau |
|---|---|---|
| `- [ ] Comprar X` | `<p data-tag="to-do">Comprar X</p>` | DOC [NT]. A Microsoft recomenda `p` em vez de `li` para tarefa |
| `- [x] Feito` | `<p data-tag="to-do:completed">Feito</p>` | DOC [NT] |
| `- [ ] Ligar {tags=call-back}` | `<p data-tag="call-back">Ligar</p>`; com `[x]` vira `call-back:completed` | DOC [NT] |
| tarefa com outra etiqueta `- [ ] X {tags=important}` | `<p data-tag="to-do, important">X</p>` | DOC [NT] (várias tags separadas por vírgula) |

As caixas marcáveis valem para `to-do`, `discuss-with-person-a`, `discuss-with-person-b`, `discuss-with-manager`, `schedule-meeting`, `call-back`, `to-do-priority-1`, `to-do-priority-2` e `client-request` [NT].

## 1.6 Etiquetas sem caixa (note tags)

Formato: `Texto {tags=important,idea}` → `<p data-tag="important, idea">Texto</p>`. Também vale em `h1`–`h6`, `li` e `img` [NT].

Valores aceitos [NT]: `important`, `question`, `definition`, `highlight`, `contact`, `address`, `phone-number`, `web-site-to-visit`, `idea`, `password`, `critical`, `project-a`, `project-b`, `remember-for-later`, `movie-to-see`, `book-to-read`, `music-to-listen-to`, `source-for-article`, `remember-for-blog`, `send-in-email`.

**Ficam fora:**
- tag personalizada, que não é suportada [NT];
- `password`, que só gera um aviso: é nome de etiqueta, não um cofre.

**Pegadinha:** `definition` volta na leitura como `remember-for-later` [NT]. A escrita avisa sobre isso, e a leitura não "corrige" de volta.

**Regras em listas:**
- `data-tag` no `ul`/`ol` sobrepõe a do `li` [NT]. Por isso a spec só põe tag no item.
- Itens com tags diferentes saem como `<li>` soltos, e o OneNote os embrulha numa lista [NT].

## 1.7 Tabelas

| sintaxe | HTML | grau |
|---|---|---|
| tabela GFM `\| a \| b \|` | `<table><tr><td><p><b>a</b></p></td>…</tr><tr><td><p>…</p></td></tr></table>`. A linha de cabeçalho vira `<td>` com `<b>`, porque `th` está fora da lista básica [CP] | DOC [CP][IO] |
| tabela rica (bloco abaixo) | atributos e estilos como descritos depois do bloco | ver detalhes |

Tabela rica:

```
<tabela borda=1 largura=624 fundo=cinza id=precos>
<linha fundo=azul>
<celula largura=200 alinhar=centro>**Item**</celula>
<celula>**Preço**</celula>
</linha>
<linha>
<celula>Camiseta</celula>
<celula alinhar=direita cor=verde>R$ 99</celula>
</linha>
</tabela>
```

O que cada parte gera:
- `<tabela borda=1 largura=624 fundo=cinza id=precos>` → `<table border="1" bgcolor="#EDEDED" style="width:624px" data-id="precos">`.
  - `border`, `width` e `bgcolor` são atributos DOC da table [IO].
  - `style` com `border` é **proibido** [IO].
- `<linha fundo=…>`: o OneNote empurra o fundo da linha para as células [IO]. O MCP já gera `background-color` em cada `<td>`.
- `<celula largura=200 alinhar=centro cor=…>` → `<td style="width:200px;text-align:center;color:…">`. `width`, `background-color` e `text-align` no `td` são DOC [IO].
- Dentro da célula vale markdown de bloco: parágrafo, lista e tabela aninhada (aninhar é DOC [IO]).
- **Borda visível: CONTRA.** O exemplo de entrada manda `border="1"` e a saída mostra `border:0px` [IO]. O padrão da spec é `borda=1`, e a prova 1.3 decide.
- **Fora:** `rowspan`/`colspan` não são suportados [IO]. A spec rejeita, com aviso.
- **Edição:** `tr` e `td` não aceitam PATCH; editar uma célula regrava a tabela inteira pelo id gerado [UP]. O MCP faz isso por trás (§2).

## 1.8 Destaque (callout), citação e código

O OneNote não tem bloco nativo para nenhum dos três. Os três são **emulações com peças DOC**. Cada um leva um `data-id` com prefixo reservado, para a leitura reconstruir a construção (§1.11).

| construção | sintaxe | HTML exato | grau |
|---|---|---|---|
| destaque | `<destaque cor=amarelo icone="💡">`<br>`**Atenção:** texto em markdown`<br>`</destaque>` | `<table border="0" style="width:624px" data-id="on-dst-<n>"><tr><td style="background-color:#FFF2CC"><p>💡 <b>Atenção:</b> texto…</p></td></tr></table>` | table com `td` colorido e largura é DOC [IO]. A caixa de borda não é prometida (CONTRA acima). O ícone é só texto Unicode |
| citação | `> texto` (várias linhas viram vários parágrafos) | `<table border="0" style="width:624px" data-id="on-cit-<n>"><tr><td style="width:6px;background-color:#BFBFBF"><p> </p></td><td><p style="color:#595959"><i>texto</i></p></td></tr></table>` | DOC nas peças [IO]. A barra lateral é **PROVA** (célula estreita com fundo); se falhar, o plano B é `<p style="color:#595959"><i>“texto”</i></p>`. `<blockquote>` é ND |
| bloco de código | ```` ```py ```` … ```` ``` ```` | `<table border="0" style="width:624px" data-id="on-cod-<n>"><tr><td style="background-color:#F3F3F3"><pre style="font-family:Consolas;font-size:10pt">…texto escapado…</pre></td></tr></table>` | `pre` preserva espaços (DOC [CP]); fonte DOC [IO]. `pre` dentro de `td` é **PROVA**; se falhar, o plano B é `<pre>` solto |

## 1.9 Imagens e anexos (só arquivo local ou data URL; nunca URL)

| construção | sintaxe | o que o servidor do MCP faz | HTML exato | grau |
|---|---|---|---|---|
| imagem de arquivo | `![legenda](arquivo:C:/Users/voce/OneNote-anexos/foto.png){largura=400 id=foto1 tags=important}` | resolve o caminho dentro de `[arquivos].pastas`, confere os bytes mágicos (PNG, JPEG, GIF, BMP ou TIFF), cria a parte `img1` | `<img src="name:img1" alt="legenda" width="400" data-id="foto1" data-tag="important" />` + parte `Content-Disposition: form-data; name="img1"` / `Content-Type: image/png` com os bytes crus | DOC [IF][IO][UP] |
| imagem de data URL | `![legenda](data:image/png;base64,…)` | decodifica **no MCP** e manda como parte binária, igual à linha de cima. O `data:` nunca chega à Microsoft | igual | DOC (parte nomeada). Isso dispensa provar data URL no POST |
| PDF como imagens | `![](arquivo:C:/…/doc.pdf){render=pdf largura=600}` | parte `pdf1` com `application/pdf` | `<img data-render-src="name:pdf1" width="600" />` | DOC [IF]. Cada página vira uma imagem; a saída traz `data-options="printout"` [IO] |
| anexo | `<anexo arquivo="C:/…/relatorio.xlsx" nome="Relatório.xlsx" id=rel1 />` | MIME pela extensão, de uma lista; parte `arq1` | `<object data="name:arq1" data-attachment="Relatório.xlsx" type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" data-id="rel1" />` | DOC [IF][IO]. Os três atributos são obrigatórios, e `data` não aceita URL [IF] |
| imagem ou anexo que já existe (só na leitura) | `![legenda](recurso:<id>){largura=… id=…}` / `<anexo recurso="<id>" nome="…" tipo="…" />` | marca estável, no estilo do `notion-file-block://` [NMT] | — | Não dá para recriar um recurso pelo id (ND). Uma escrita que contenha `recurso:` gera **erro orientador**: "imagem existente não se recria; edite o bloco vizinho". Como a imagem é bloco próprio, editar o texto ao lado não toca nela |

**Limites que o montador respeita (DOC [IF]):**
- pedido de até **4 MB** no total, senão 413; o MCP corta em 3,5 MB por margem;
- **6 partes** por POST, contando a Presentation (ou Commands);
- 30 imagens por POST e 150 por página;
- 5 `data-render-src` por pedido;
- **1 anexo por pedido**: conservador por causa da ambiguidade em "Correções", até a prova 1.12.

Quando o conteúdo passa desses limites, o MCP divide sozinho: o POST cria a página, e PATCHes de `append` mandam o resto. A resposta avisa que dividiu.

**Formato no fio (verbatim de [IF][UP]):** `Content-Type: multipart/form-data; boundary=…`, partes separadas por CRLF.
- Criação: 1ª parte `Content-Disposition: form-data; name="Presentation"` + `Content-Type: text/html` [IF].
- Edição: 1ª parte `name="Commands"` + `Content-Type: application/json` [UP].

**Vídeo (`<iframe data-original-src>`)** fica **fora**: o servidor da Microsoft buscaria a URL [IF].

## 1.10 Colunas e layout

| modo | sintaxe | HTML | grau | edição depois |
|---|---|---|---|---|
| **padrão: colunas por tabela sem borda** | `<colunas>`<br>`<coluna largura=40%>`…markdown…`</coluna>`<br>`<coluna largura=60%>`…`</coluna>`<br>`</colunas>` | `<table border="0" style="width:624px" data-id="on-col-<n>"><tr><td style="width:250px">…</td><td style="width:374px">…</td></tr></table>`. A % vira px sobre 624, que é a largura da div padrão (EX [IO]) | DOC [IO] | substitui a tabela inteira [UP]; o MCP regera a partir do ONMD |
| experimental: caixas livres (só em `criar_pagina(layout="livre")`) | `<caixa x=48 y=120 largura=300 id=esq>`…`</caixa>` | `<body data-absolute-enabled="true">` + `<div data-id="esq" style="position:absolute;left:48px;top:120px;width:300px">…</div>` como filho direto do body | DOC [AP][IO]; em conta pessoal é **PROVA**, porque [AP] não traz o aviso de consumidor | a div posicionada só aceita `append` [UP]. Sem altura, sem z-index, sem aninhar [AP] |

## 1.11 Seções nomeadas, `data-id` e o que a leitura reconstrói

- `<secao id=resumo>` … `</secao>` → `<div data-id="resumo">…</div>`.
  - A div só sobrevive porque tem `data-id`; sem ele, é achatada [IO].
  - Vira alvo de `acrescentar(onde="#resumo")`, porque `append` em div aceita `#data-id` [UP].
- **Prefixos reservados** `on-dst-`, `on-cit-`, `on-cod-`, `on-col-`:
  - a leitura usa esses prefixos para devolver `<destaque>`, `>`, ```` ``` ```` e `<colunas>`;
  - sem prefixo, uma tabela volta como `<tabela>` ou como pipe table.
  - Se o `data-id` sobrevive a uma edição pelo site é **PROVA** (1.9). Se não sobreviver, a leitura cai em `<tabela>`: não perde conteúdo, só a forma.
- **Página feita à mão no OneNote** tem várias "caixas" (divs absolutas). A leitura devolve `<caixa x y largura>` envolvendo cada uma, para o modelo ver a estrutura; a saída marca `position:absolute`, `left`, `top` e `width` na div [IO].

## 1.12 Leitura (HTML de saída → ONMD): o mapeamento inverso

A saída devolve quase tudo em `<span style>`, e as listas trazem estilo e tag no `li`/`span` [IO][NT]. Regras:

1. **Spans:**
   - `font-weight:bold` → `**`; `font-style:italic` → `*`; `text-decoration:underline` → `<u>`; `line-through` → `~~`;
   - `background-color:#FFFF00`/`yellow` → `==x==`;
   - `font-family:Consolas` sozinho → `` ` ``;
   - o resto vira `<span cor fundo fonte tamanho>`, com a cor normalizada (nome CSS → hex → nome da paleta quando bate exato). Ver correção 4.
2. **Padrões do OneNote são omitidos:**
   - `font-family:Calibri`, `font-size:11pt` e o que vier no `<body style>` [IO];
   - os estilos padrão de `h1`–`h6`: h1 = `16pt #1e4e79 margin…` [IO]; h2–h6 conforme a medição 1.1.
3. **`<li style="list-style-type:…">`** repetido em todos os itens → um único `{marcador=…}` ou `a.`/`i.` no começo [IO].
4. **Note tags:**
   - `<p data-tag="to-do">` → `- [ ]`;
   - o tag no `span` dentro de `li` → `- item {tags=…}` [NT].
5. **Tabelas:**
   - prefixo reservado → a construção correspondente;
   - `td` com estilo → `<tabela>`;
   - sem estilo → pipe table;
   - `border:0px` em toda saída é ruído e é ignorado [IO].
6. **Imagens e anexos:** `img`/`object` → `recurso:` com o id tirado de `…/resources/{id}/$value` [IO]. Imagens fatiadas (mesmo `data-id`, `data-index`) viram uma só marca [IO].
7. **O que se perde** volta em `avisos[]`: tinta, áudio, iframe, `data-render-original-src`.

**Contrato:** `escrever(ler(x))` regera um HTML equivalente. O teste do passo 4 é "ler → escrever → ler" sem diferença.

---

# 2. Tools v2 (nenhuma apaga)

**Regras comuns a todas:**
- Toda tool resolve a lista permitida antes de qualquer chamada, como hoje (`_secao`, `_secao_da_pagina`).
- Toda escrita devolve `avisos[]` com o que o sanitizador descartou ou ajustou, em vez de descartar em silêncio. Isso copia os `warnings` do Notion [NMT].
- **Cota:** 400 requisições por hora, 5 simultâneas, e o 429 vem sem `Retry-After` [THR]. Uma edição custa 4 requisições: página, seção ao vivo, GET com ids e PATCH. Isso dá cerca de 100 edições por hora. O desenho manda várias trocas num único PATCH.

**Texto padrão no início de toda tool de escrita** (inspirado nas instruções literais do Notion [NMT]):

> "Antes de escrever, leia a spec (`ler_spec`) — não invente sintaxe. Antes de editar, leia a página (`ler_pagina`) se ainda não leu; imite títulos, cores e padrões vizinhos. Faça a menor edição possível. Depois de edição estrutural, releia. Relate os `avisos`. Título vai no parâmetro, nunca no corpo."

| # | assinatura | descrição para o modelo | Graph por trás |
|---|---|---|---|
| 1 | `listar_blocos()` | igual à v1 | igual |
| 2 | `listar_secoes(bloco="")` | igual à v1 | igual |
| 3 | `listar_paginas(secao)` | igual à v1 | igual |
| 4 | `buscar_paginas(texto, secao="", limite=20)` | "Procura páginas pelo **título** (contém, sem diferenciar maiúsculas). O OneNote não permite busca no texto das páginas. Sem `secao`, procura em todas as seções permitidas." | `GET /sections/{id}/pages?$filter=contains(tolower(title),'<x>')&$top=…` em cada seção do índice [GC][LP]. O `?search` foi desligado em 05/05/2024 [DEP]. Escapar `'` e usar `%20` [GC] |
| 5 | `ler_spec()` | "Spec do formato ONMD. Leia antes da primeira escrita." (também como recurso `onenote://docs/formato`) | — |
| 6 | `ler_pagina(pagina_id, incluir_ids=False)` | "Página em ONMD, o mesmo formato que as tools de escrita aceitam. Imagens e anexos vêm como `recurso:<id>`; mantenha essas marcas como estão." Com `incluir_ids`, cada bloco traz `{id=…}` quando tem um | `GET /pages/{id}/content` [GC] |
| 7 | `ver_imagem(pagina_id, recurso_id)` | "Mostra uma imagem da página (`recurso:` lido em `ler_pagina`)." Devolve conteúdo de imagem MCP | `GET /resources/{id}/content` [RG], **só** se o `recurso_id` aparece no HTML daquela página permitida e casa com a regex de id. Nunca recebe URL |
| 8 | `criar_pagina(secao, titulo, conteudo, fonte_padrao=None, layout="fluxo")` | "Cria página nova. `conteudo` em ONMD. `layout="livre"` habilita `<caixa>` (experimental)." Devolve `{id, link, avisos, dividido}` | POST `/sections/{id}/pages`: `application/xhtml+xml` ou multipart com `Presentation` [CP][IF] |
| 9 | `acrescentar(pagina_id, conteudo, onde="fim")` | "Acrescenta ONMD. `onde`: `fim` (última caixa), `inicio`, `#id-de-secao` ou `#id-de-lista`." | `append` na última `div:{…}` gerada (ARM), `prepend` em `body`, ou `append` em `#data-id` [UP] |
| 10 | `inserir(pagina_id, ancora, conteudo, posicao="depois")` | "Insere ONMD antes/depois de um bloco. `ancora` = trecho que aparece em **um** bloco só, ou `#id`." | `insert` + `position` [UP], com alvo pelo id gerado resolvido na hora ou por `#data-id` (`insert` aceita os dois [UP]) |
| 11 | `editar(pagina_id, trocas=[{"antigo":"…","novo":"…","todas":false}])` | "Troca trechos. Cada `antigo` precisa aparecer em exatamente um bloco (ou use `todas`). Tudo é validado antes de enviar; se um falhar, nada é enviado. `novo` não pode esvaziar um bloco inteiro: para remover texto, troque por outro texto." Exemplo: `[{"antigo":"R$ 99","novo":"<span cor=vermelho>R$ 89</span>"}]` | o algoritmo vem logo abaixo da tabela |
| 12 | `marcar_tarefa(pagina_id, tarefa, feito=True)` | "Marca ou desmarca uma caixa de tarefa (`tarefa` = trecho único ou `#id`)." | `replace` do `p`/`li` pelo id gerado, reenviando o texto com `data-tag="to-do:completed"` e o `data-id` original [UP][NT] |
| 13 | `renomear_pagina(pagina_id, titulo)` | "Muda o título." Recusa título vazio | `{"target":"title","action":"replace","content":"…"}` [UP] |
| 14 | `criar_secao(onde, nome)` | "Cria seção num bloco ou grupo (`onde` = caminho). Só cria se o caminho final estiver na lista permitida." | POST `/notebooks/{id}/sections` [NPS] ou `/sectionGroups/{id}/sections` [SGS]. Nome com até 50 caracteres, sem `?*/:<>\|&#''%~`, sem espaço no início; erros 20117, 20152–20155 [NPS][ERR] |
| 15 | `copiar_pagina(pagina_id, secao_destino)` | "Copia a página para outra seção permitida. A original fica." | POST `/pages/{id}/copyToSection` `{"id":…}`, 202 + `Operation-Location` [CTS]; acompanha `GET /operations/{id}` até `completed`/`failed` [OP], com no máximo 30 s e espera crescente |

**Algoritmo de `editar`, `inserir` e `marcar_tarefa`** (as alterações parciais):
1. `GET …/content?includeIDs=true` **imediatamente antes**, sem nunca guardar id em cache, porque "Generated id values might change after a page update" [UP].
2. Montar a lista de blocos editáveis: `p`, `h1`–`h6`, `li`, `table`, `img`, `object`, `pre`, cada um com seu ONMD (pelo mesmo conversor do §1.12) e seu id gerado [UP].
3. Achar cada `antigo` no ONMD dos blocos. As respostas possíveis:
   - em mais de um bloco, sem `todas` → erro com os contextos;
   - fora de todos → erro com o trecho;
   - atravessando dois blocos → erro "edite um bloco por vez".
4. Montar o ONMD novo do bloco, converter para HTML, **reaplicar o `data-id` original** e enviar `{"target":"<id gerado>","action":"replace","content":…}`.
   - `replace` exige o id gerado, salvo `title` e `img`/`object` dentro de div [UP].
   - Em `td` o alvo é a tabela inteira, porque `tr`/`td` não aceitam ação [UP].
5. Mandar todas as trocas num **único array** de PATCH, que só sai se todas foram validadas. A atomicidade do lado da Microsoft é ND, e por isso existe a prova 1.11.
6. Antes do PATCH, gravar o HTML antigo dos blocos trocados num diário local (`%LOCALAPPDATA%\onenote-mcp\historico\<pagina>.jsonl`). Isso garante reversão, já que o Graph não expõe o histórico de versões.
7. Opcional `reler=True`: devolve o ONMD dos blocos tocados.

**Sem tool de "regravar a página inteira"** (o `replace_content` do Notion [WMC]). Página do OneNote não tem filhas a proteger; o análogo seguro é simplesmente não existir a tool.

**Ficam de fora de propósito:**
- `apagar_*`;
- `mover_pagina`, que mudaria o recuo da página. `level`/`order` são somente leitura na v1.0 (pesquisa html-update §6);
- criar grupo de seções. Seria o mesmo padrão do `criar_secao`; fica para quando for pedido (YAGNI).

---

# 3. Segurança

## 3.1 "Nenhuma tool apaga": garantido na estrutura, não só no nome

- **O risco existe:** `PatchContentCommand.action` aceita `delete` [PCC].
- **`graph.py` ganha `patch_conteudo(pagina_id, comandos, partes=None)`, e o `patch_json` cru sai.** Cada comando é validado:
  - `action ∈ {append, insert, prepend, replace}`;
  - `position ∈ {before, after}` ou ausente;
  - `target` casa `^(title|body|#[a-z0-9][a-z0-9_-]{0,47}|(p|div|table|img|object|ol|ul|li|h[1-6]|pre):\{[0-9a-f-]{36}\}\{\d+\})$`;
  - `content` não vazio: depois de tirar as tags, sobra texto, ou há `img`/`object`/`table`.
- **`replace` com conteúdo vazio equivale a apagar:** é recusado. `title` vazio também.
- **Lista de rotas permitidas** em `_req`, por método e regex:
  - GET só em `/me/onenote/…`;
  - POST só em `/sections/{id}/pages`, `/notebooks/{id}/sections`, `/sectionGroups/{id}/sections` e `/pages/{id}/copyToSection`;
  - PATCH só em `/pages/{id}/content`;
  - **nenhum DELETE**: o método nem existe no cliente.
- O host fixo `graph.microsoft.com` e o "sem seguir redirecionamento" continuam como estão.

## 3.2 Sanitizador v2 (`sanitizar.py`): lista de tags × atributos × CSS

O sanitizador roda **no HTML final** gerado pelo conversor. Ele é a segunda barreira: o conversor já só emite o que a spec define.

| tag | atributos permitidos |
|---|---|
| `p`, `h1`–`h6` | `style`, `data-id`, `data-tag` |
| `ul`, `ol`, `li` | `style`, `data-id`, `data-tag` |
| `span` | `style` |
| `b i u em strong strike del sup sub cite br` | — |
| `pre` | `style` |
| `table` | `border` (0–3), `bgcolor`, `style`, `data-id` |
| `tr` | — |
| `td` | `style` |
| `a` | `href` (só `https:`, `http:`, `onenote:`) |
| `div` | `data-id`, `style` (posição só quando `layout="livre"` e filha direta do body) |
| `img` | `src`, `data-render-src`, `alt`, `width`, `height`, `data-id`, `data-tag`. `src` e `data-render-src` só podem ser `name:<parte criada nesta chamada>` |
| `object` | `data` (só `name:<parte criada nesta chamada>`), `data-attachment`, `type` (lista de MIME), `data-id` |

As tags vêm de [CP][IO]; `data-tag` de [NT]; `img` e `object` de [IF].

**Propriedades CSS permitidas e validação do valor** (todas de [IO]):

| propriedade | valor aceito |
|---|---|
| `color`, `background-color` | `#[0-9a-f]{6}` ou nome de cor CSS de uma lista |
| `font-family` | `[A-Za-z0-9 \-]{1,40}` |
| `font-size` | número + `pt`, entre 6 e 72 |
| `font-weight` | `normal` ou `bold` |
| `font-style` | `normal` ou `italic` |
| `text-decoration` | `none`, `underline` ou `line-through` |
| `text-align` | `left`, `center` ou `right`, só em bloco |
| `list-style-type` | os 10 valores DOC |
| `width` | px ou %, só em `table`, `td` e `img` |
| `max-width`, `max-height` | só em `img` |
| `position`, `left`, `top` | só em `div` livre |

Valor com `url(`, `expression`, `\`, `@` ou `;` dentro de outro valor → a declaração inteira cai, com aviso.

**Sempre descartados, com aviso:**
- `<style>`, `<script>`, `<iframe>`, `<form>`, `<link>`;
- `data-original-src`, `data-render-method`, `data-render-fallback`;
- `data-render-src`/`src`/`data` com qualquer valor que não seja uma parte criada pelo próprio MCP. Isso cobre `http(s):`, `data:` e `name:` digitado pelo modelo;
- `id` (seria descartado pela Microsoft de qualquer jeito [UP]);
- `data-absolute-enabled`, salvo em `layout="livre"`;
- `rowspan`/`colspan`.

**`data-tag`:** só os valores oficiais, com `:completed` só nos marcáveis. Tag fora disso cai e gera aviso; uma tag inválida daria erro 20139 [ERR].

**Renderizar HTML como imagem (`data-render-src` de parte HTML) fica fora.** O renderizador busca as URLs que estiverem dentro da parte, como mostra o próprio exemplo de [IF].

## 3.3 Arquivos locais (`arquivos.py`)

- **`config.toml` ganha `[arquivos]`:** `pastas = [...]` (lista vazia = imagem e anexo desligados: falha fechada), `max_mb = 3.5` e `mimes = [...]`.
- **Caminho:** `Path.resolve(strict=True)` e depois `is_relative_to(pasta)` em alguma pasta permitida. São recusados:
  - caminhos UNC (`\\servidor` ou `//`), porque abrir um caminho UNC no Windows faz autenticação SMB e é um canal de vazamento;
  - links simbólicos e junções que, depois de resolvidos, saem da pasta;
  - arquivos fora da lista de extensões.
- **Imagem:** os bytes mágicos têm de bater com PNG, JPEG, GIF, BMP ou TIFF [IF]. O nome da extensão não basta.
- **Data URL:** só `image/(png|jpeg|gif|bmp|tiff)`, base64 válido e o mesmo teto de tamanho. É decodificada no MCP.
- **O nome da parte** é gerado pelo MCP (`img1`, `arq1`, `pdf1`), nunca pelo modelo. Nome e referência saem da mesma variável (correção 2).

## 3.4 Lista permitida em cada superfície nova

| tool | o que confere |
|---|---|
| `buscar_paginas` | só itera as seções do índice. Isso evita o erro 20266 [ERR] e a lacuna do bloco compartilhado (ARM) |
| `copiar_pagina` | origem **e** destino |
| `criar_secao` | o caminho final `onde/nome` passa por `P.permitido()` **antes** do POST, e o índice é invalidado depois |
| link `pagina:` | só resolve página permitida |
| `ver_imagem` | o id do recurso precisa estar no HTML da página permitida. Nunca baixa uma URL, porque o bearer vazaria |

---

# 4. Plano de implementação (cada passo com prova)

Cada passo traz duas provas: um **teste unitário** (pytest com o Graph falso, como hoje) e um **teste real** numa seção de teste sua (por exemplo "Bloco/MCP-teste"; a chave `[teste].secao` pensada aqui não foi implementada, o `config.py` não a lê). Toda prova real faz POST ou PATCH, depois `GET /content?includeIDs=true`, e guarda o HTML em `provas/AAAA-MM-DD/<n>.html` (pasta no `.gitignore`). Nada é apagado: as páginas de teste ficam, e o dono apaga à mão se quiser.

### Passo 0: base

- `[teste].secao` no config (não implementado).
- Comando `python -m onenote_mcp prova <n>` (não implementado: as provas reais ficaram em `docs/provas-v2.md`).
- Confirmar qual conta está logada. A conta de teste (`Contributor`) é a única com escrita provada (ARM).
- **Prova:** `prova 0` cria a página "MCP-teste 0" e lê de volta.

### Passo 1: sondagem (antes de escrever o conversor; o resultado ajusta a spec)

| item | o que medir | se falhar |
|---|---|---|
| 1.1 | estilo padrão de h2–h6 | omitir os estilos medidos na leitura |
| 1.2 | lista aninhada | sub-item vira item com recuo emulado + aviso |
| 1.3 | `border="1"` aparece? | destaque e tabela sem promessa de borda |
| 1.4 | `bgcolor` + `td width` | — |
| 1.5 | `pre` dentro de `td` | código vira `<pre>` solto |
| 1.6 | barra da citação (célula de 6px) | plano B do §1.8 |
| 1.7 | `<a href="onenote:…">` clicável | link vira `https` (oneNoteWebUrl) |
| 1.8 | `data-id` em p, table e div volta no GET, e `#id` → id gerado → `replace` mantém o `data-id` | inferência a partir de [UP][IO]; se falhar, `editar` só por trecho |
| 1.9 | `data-id` sobrevive a uma edição manual no site | passo manual do dono; se não sobreviver, a leitura cai em `<tabela>` |
| 1.10 | `layout="livre"` em conta pessoal | a tool recusa `livre` |
| 1.11 | PATCH com 2 comandos, o 2º inválido: o 1º foi aplicado? | documentar como "não atômico" e mandar 1 comando por PATCH quando houver risco |
| 1.12 | POST com 2 `<object>` | manter 1 anexo por pedido |
| 1.13 | `img name:` no POST e no PATCH multipart | — |
| 1.14 | PDF `data-render-src name:` | — |
| 1.15 | `data-tag` variados + `definition` | — |
| 1.16 | spans: cor hex → nome? px → pt? | regras da leitura |
| 1.17 | `criar_secao` e `copyToSection` no bloco compartilhado (Contributor) | tool recusa com mensagem clara |

**Prova:** um fixture HTML salvo por item mais uma tabela de resultados em `docs/provas-v2.md`.

### Passo 2: `graph.py` endurecido

- `patch_conteudo` com o enum de ações, a regex de alvo e o conteúdo não vazio.
- Lista de rotas.
- Montador multipart com CRLF.
- Retirada do `patch_json`.

**Unit:**
- `action:"delete"` → `ValueError`;
- alvo `div:…` malformado → erro;
- `DELETE` não existe no cliente;
- teste de ouro dos bytes do multipart (nomes de parte iguais à referência).

**Real:** PATCH multipart com 1 imagem na página do passo 0.

### Passo 3: `sanitizar.py`

**Unit:** uma tabela de ataques:
- `style="background:url(http://x)"` cai;
- `color:red;position:absolute` → fica a cor, sai a posição, e há aviso;
- `<img src="https://">` cai;
- `name:` digitado pelo modelo cai;
- `data-tag="custom"` cai;
- `data-render-src` de parte HTML cai;
- `<iframe>` cai;
- `href="javascript:"` cai.

Tudo descartado aparece em `avisos`.

**Real:** uma página com o HTML já limpo dessa tabela; o GET mostra que nada externo foi buscado (nenhum `data-render-original-src` http).

### Passo 4: `formato/escrita.py` + `formato/leitura.py` + `paleta.py`

- O conversor próprio substitui python-markdown e markdownify.
- O inline pode usar `markdown-it-py`; os blocos próprios (`<destaque>` etc.) têm parser próprio.

**Unit:**
- um teste de ouro por linha das tabelas do §1 (ONMD → HTML exato);
- volta com os fixtures do passo 1 (HTML de saída → ONMD esperado);
- **ida e volta:** `ler(simular_saida(escrever(x))) == x` para a página-vitrine.

**Real:**
1. `criar_pagina` com a "Vitrine ONMD", que usa todas as construções;
2. `ler_pagina`;
3. recriar a partir da leitura;
4. ler de novo: diff vazio, exceto as perdas documentadas.
5. O dono olha a vitrine no site, que é o aceite visual.

### Passo 5: `arquivos.py`

**Unit:**
- `..\..\` fora da pasta;
- UNC;
- link simbólico para fora;
- PNG com extensão `.jpg` aceito pelo conteúdo;
- `.exe` renomeado para `.png` recusado;
- data URL inválida;
- 7 imagens → divisão em POST + PATCHes;
- mais de 3,5 MB → divisão ou erro orientador.

**Real:** página com 2 imagens locais, 1 data URL, 1 PDF renderizado e 1 anexo xlsx.

### Passo 6: tools de edição (`editar`, `inserir`, `acrescentar(onde)`, `marcar_tarefa`, `renomear_pagina`) + diário local

**Unit** (Graph falso):
- os ids vêm do GET mais recente, e o falso troca os ids a cada PATCH;
- trecho ambíguo, ausente ou atravessando blocos → erro sem PATCH;
- `novo` que esvazia o bloco → erro;
- célula de tabela → `replace` da tabela inteira mantendo o `data-id`;
- o diário grava antes do PATCH.

**Real** na Vitrine:
- marcar 2 tarefas;
- trocar uma célula de preço;
- inserir parágrafo depois de um título;
- `acrescentar(onde="#resumo")`;
- renomear;
- o GET confere cada mudança;
- `historico/*.jsonl` tem o antes.

### Passo 7: `buscar_paginas`, `criar_secao`, `copiar_pagina`, `ver_imagem`

**Unit:**
- busca só em seções do índice;
- `'` escapado;
- `criar_secao` fora da lista → `ForaDaLista` sem POST;
- regras de nome;
- cópia com destino proibido → recusa;
- acompanhamento termina em `failed` com o diagnóstico;
- `ver_imagem` com id que não está na página → recusa.

**Real:**
- criar "MCP-teste/Sub" dentro da área permitida;
- copiar a Vitrine para ela;
- buscar "vitrine";
- ver uma imagem.

### Passo 8: spec, descrições e documentação

- `spec/formato.md`, servido como recurso e por `ler_spec`.
- Descrições das tools com o texto padrão do §2.
- Atualizar `README.md` (15 tools) e `ARMADILHAS.md` (achados do passo 1).

**Prova:** um eval com uma sessão limpa do Claude: "monte uma página de reunião com pauta, tarefas, tabela de responsáveis e um destaque". A página sai sem `avisos` de sintaxe inventada, e o dono aprova no site.

### Passo 9: cota

- Contador de requisições por hora, que avisa em `avisos` a partir de 300 de 400 [THR].
- Cache curto da conferência da seção por página dentro de uma mesma chamada.

**Unit:** o contador.

**Real:** `editar` com 10 trocas gasta 4 requisições, não 40.

## O que o pedido não dizia

- **Diário local do antes de cada `replace`.** O Graph não expõe o histórico de versões, e "igual ou melhor" que o site exige poder desfazer. É barato e reversível.
- **Recusa de caminho UNC e de link simbólico.** Ler `\\host\x` no Windows dispara autenticação SMB, que é um vazamento que a regra "só arquivo local" sozinha não fecha.
- **Data URL decodificada no MCP.** Elimina uma prova (data URL no POST, ND) e mantém o `data:` longe da Microsoft.
- **Prefixos `on-` em `data-id`.** São o que permite a ida e volta de destaque, citação, código e colunas, que não existem no OneNote nativo.
- **"Igual ou melhor" não é alcançável por inteiro, e a spec diz isso.** Ficam fora de alcance pela API:
  - mesclar células [IO];
  - cor de fundo da página [IO];
  - etiqueta personalizada [NT];
  - subpágina/recuo (somente leitura na v1.0);
  - tinta e equação (ND);
  - toggle, que também não existe no OneNote.

  O "melhor" que o site fica por conta de destaque, colunas, código e citação com um comando só, edição por trecho e cópia entre seções sem abrir o app.