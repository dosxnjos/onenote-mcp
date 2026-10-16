# ONMD: markdown do OneNote (spec para IA)

ONMD é o formato que `ler_pagina` devolve e que `criar_pagina`, `acrescentar`, `inserir` e `editar` aceitam.
Base: markdown comum. O que é do OneNote vira tag em português ou atributos `{…}` no fim do bloco.
**Não invente sintaxe.** HTML cru (`<b>`, `<div>`, `<img>`…) não passa: vira texto literal e gera aviso.
O título da página vai no parâmetro `titulo`, nunca no corpo.

## Blocos (cada linha é um bloco; linha em branco separa)

| escreva | vira |
| --- | --- |
| `texto` | parágrafo (cada linha = 1 parágrafo) |
| `#` … `######` `texto` | título nível 1 a 6 |
| `---` | linha divisória cinza |
| `> texto` (linhas seguidas = mesma citação) | citação (cinza itálico; `*…*` dentro dela não aparece) |
| ```` ```py ```` … ```` ``` ```` | bloco de código (Consolas, fundo cinza) |
| `- item` · `1. item` · `a. item` · `A.` · `i.` · `I.` | lista; sub-item = 2 espaços a mais de recuo (o OneNote põe uma linha em branco antes de cada sub-nível: prefira títulos ou lista de um nível); a numeração sempre começa do 1 (`3.` vira `1.`, com aviso) |
| `- [ ] tarefa` · `- [x] feita` | caixa de tarefa (não aninha) |
| tabela `\| a \| b \|` + `\| --- \| --: \|` | tabela com borda; 1ª linha em negrito (célula vazia vale); `:--` `:-:` `--:` alinham; `\|` dentro da célula, também em `` `código` ``, se escreve `\|`; linha com mais células que o cabeçalho é recusada |

## Atributos de bloco `{…}` (no fim da linha, separados por espaço)

`Texto {id=resumo cor=azul fundo=amarelo fonte="Segoe UI" tamanho=14 alinhar=centro tags=important,idea}`

- `id=` letras, números, `-`, `_` (o prefixo `on-` é reservado). Vira alvo `#id`, então é único: id que já
  existe na página ou aparece duas vezes no conteúdo é recusado.
- `cor=` (texto) e `fundo=`: `cinza marrom laranja amarelo verde azul roxo rosa vermelho` ou `#rrggbb`.
- `fonte=` nome da fonte; `tamanho=` em pontos; `alinhar=esquerda|centro|direita`.
- `tags=` etiquetas oficiais, separadas por vírgula: `important question definition highlight contact address
  phone-number web-site-to-visit idea critical project-a project-b remember-for-later movie-to-see book-to-read
  music-to-listen-to source-for-article remember-for-blog send-in-email password`.
  `definition` volta como `remember-for-later`. `call-back` não existe aqui. `password` é só nome de etiqueta.
- Tarefa: `- [ ] Ligar {tags=schedule-meeting}` usa essa caixa no lugar da padrão. Caixas: `to-do
  discuss-with-person-a discuss-with-person-b discuss-with-manager schedule-meeting to-do-priority-1
  to-do-priority-2 client-request`.
- Lista: `{marcador=circulo|quadrado|nenhum}` no 1º item de uma lista `-`. Item com `tags=` faz a lista virar
  itens soltos (perde numeração e marcador): prefira parágrafo com etiqueta. Etiqueta em sub-item é recusada
  (o OneNote não a guarda).

## Dentro da linha

`**negrito**` · `*itálico*` · `~~riscado~~` · `<u>sublinhado</u>` · `==marca-texto==` · `` `código` `` ·
`x<sup>2</sup>` · `H<sub>2</sub>O` · `<span cor=vermelho fundo=amarelo fonte="Segoe UI" tamanho=16>texto</span>` ·
`[texto](https://…)` (parênteses da URL valem se fecham: `…/Python_(linguagem)`) ·
`[texto](pagina:<id da página>)` (só página da lista permitida) · `linha um<br>linha dois` (quebra de linha
dentro do mesmo parágrafo).
Escape: `\` antes do caractere (`\*`, `\<`, `\{`, `\[`, `` \` ``, `\|`, `\#`, `1\.`) deixa literal.

## Caixas (abre e fecha em linha própria)

```
<destaque cor=amarelo icone="💡">
**Atenção:** texto do destaque (aceita listas e parágrafos)
</destaque>

<colunas>
<coluna largura=40%>
conteúdo da esquerda
</coluna>
<coluna largura=60%>
conteúdo da direita
</coluna>
</colunas>

<tabela borda=1 largura=100% id=precos>
<linha fundo=azul>
<celula largura=60%>**Item**</celula>
<celula alinhar=direita>**Preço**</celula>
</linha>
<linha>
<celula>Camiseta</celula>
<celula alinhar=direita fundo=verde>R$ 99</celula>
</linha>
</tabela>

<secao id=pendencias>
blocos que depois recebem acrescentar(onde="#pendencias")
</secao>
```

- `largura` sempre em % da página. `borda=0` tira a borda. Célula aceita várias linhas (listas, parágrafos).
- Não existe: mesclar células, cor de fundo da página, etiqueta personalizada, subpágina, tinta, vídeo.
- `<caixa x y largura>` aparece na leitura de página feita à mão; na escrita o conteúdo entra no fluxo normal.

## Imagens e anexos (só pelo parâmetro `anexos`)

`anexos=[{"caminho": "C:/pasta-permitida/foto.png"}, {"caminho": "C:/pasta-permitida/plano.xlsx", "nome": "Plano.xlsx"}]`

```
![Foto da vitrine](anexo:1){largura=50% id=foto1}
<anexo n=2 nome="Plano.xlsx"/>
```

- `anexo:N` = posição em `anexos` (começa em 1). Imagem: PNG, JPEG, GIF, BMP, TIFF ou `{"data_url": "data:image/png;base64,…"}`.
  Anexo: pdf, xlsx, docx, pptx, zip, txt, csv. Até 5 arquivos e 3,5 MB por chamada; 1 `<anexo>` por chamada.
- Caminho ou URL dentro do texto não são aceitos. Imagem e anexo lidos voltam como `recurso:<id>`:
  mantenha como estão; não se recriam nem se editam (use `ver_imagem` para olhar).

## Edição

- `editar` troca trechos exatos do ONMD lido; cada trecho em um bloco só. Bloco = parágrafo, título, tarefa,
  linha de citação, lista inteira, tabela inteira (destaque, código e colunas também são tabela).
  Várias trocas no mesmo bloco valem sobre o texto LIDO (uma não pega o que a outra criou); trechos que se
  sobrepõem são recusados.
- Bloco com algo que o ONMD não mostra (imagem, vídeo ou tabela dentro do texto ou da célula: o `ler_pagina`
  avisa) não aceita `editar` nem `marcar_tarefa`: regravá-lo apagaria isso. Use `inserir` ao lado.
- Bloco que vem logo antes de uma lista também é recusado: o OneNote o moveria para depois da lista.
- `inserir` põe blocos antes/depois de uma âncora (trecho único ou `#id`). `acrescentar`: `fim`, `inicio`, `#secao`.
- `marcar_tarefa` marca/desmarca. `renomear_pagina` muda o título. O antes de cada troca fica num diário local.

## Exemplo completo (conteúdo de `criar_pagina`, título "Reunião de vitrine 15/10")

```
## Resumo {id=resumo}

Reunião com a Ana sobre a vitrine de novembro. **Decisão:** manter o tema de corrida.

<destaque cor=azul icone="📌">
**Prazo:** montagem até 03/11 (segunda-feira).
</destaque>

## Pauta

1. Tema da vitrine
2. Orçamento: materiais e frete
3. Responsáveis

## Tarefas

- [ ] Fechar orçamento com o fornecedor {tags=important}
- [ ] Ligar para a loja do centro {tags=schedule-meeting}
- [x] Enviar fotos da vitrine anterior

## Responsáveis

| Pessoa | Tarefa | Prazo |
| --- | --- | --: |
| Ana | aprovar layout | 20/10 |
| Bruno | orçamento | 24/10 |

<colunas>
<coluna largura=50%>
### O que funcionou
- manequins em movimento
- luz quente
</coluna>
<coluna largura=50%>
### O que mudar
- preço mais visível
- menos texto
</coluna>
</colunas>

> "vitrine boa é a que para o cliente na calçada"

---

Notas: **GMROI** = margem bruta sobre o estoque médio. Perguntas para responder pelo código: A1 (orçamento máximo?).
```
