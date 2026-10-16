# Plano — onenote-mcp v2: formatação rica e edição por trecho (2026-10-15)

Pedido: onenote-mcp-v2 | "alto nível de personalização, o mais próximo possível do site do OneNote, igual ou melhor" | de: dono | desde: 2026-10-15 | origem: dono

## Entendimento do pedido

O dono quer que o Claude crie e edite páginas do OneNote "bem detalhadas e bonitas", perto do que o site
faz, usando o MCP do Notion como referência de UX. A v1 (`onenote_mcp/`, commit `e59d103`) só cria página com
markdown básico e acrescenta no fim. Material de base, LER ANTES:

- desenho: `docs/pesquisa-v2/desenho.md` (formato ONMD, tools, segurança, plano original)
- crítica: `docs/pesquisa-v2/critica.md` (18 correções; valem SOBRE o desenho)
- provas reais: `docs/provas-v2.md` (valem SOBRE desenho e crítica: o que o OneNote aceitou de fato)
- pesquisas: `docs/pesquisa-v2/html-entrada.md`, `html-update.md`, `notion-mcp.md`
- `CLAUDE.md`, `docs/ARMADILHAS.md`, `README.md`, código atual e `tests/test_onenote.py`

Fora do escopo (via negativa, crítica §4 + provas): apagar qualquer coisa, criar seção, copiar página, layout
livre/`<caixa>` na escrita, barra lateral de citação, etiqueta `call-back`, `cite`, `pre`.

## O que o pedido não dizia

- **feito:** sondagem real antes do conversor (`docs/provas-v2.md`): evita spec que o OneNote ignora.
- **feito:** PATCH é atômico (provado) → `editar` manda todas as trocas num array só.
- **+ diário local** do HTML anterior a cada troca (`%LOCALAPPDATA%\onenote-mcp\historico\`), porque o Graph não
  tem histórico; reverte texto e tabela, não imagem (crítica §3.3).
- **+ anexos por parâmetro**, nunca caminho dentro do texto (crítica §3.1: texto de página de terceiro não pode
  disparar leitura de arquivo local).
- **proposto:** publicar no GitHub público depois da v2 (já decidido: sim).

## O que NÃO muda (guardrails)

- Nenhuma tool apaga; o cliente HTTP não tem DELETE; `patch_conteudo` valida `action ∈ {append,insert,prepend,replace}`,
  alvo por regex e conteúdo não vazio.
- Lista permitida em toda tool, conferência ao vivo da seção (v1) e bloqueio por termo ("senha", "password", "credencia").
- Escopo `Notes.ReadWrite`; host fixo `graph.microsoft.com`; sem redirect; login por device code fora do MCP.
- Nada de URL externa buscada pela Microsoft a partir de texto do modelo (`img src http`, `data-render-src` URL, iframe).
- `INSTRUCOES` do servidor (regra de escrever para o leitor) continuam, acrescidas da regra do formato.
- Os 35 testes da v1 continuam passando (adaptar só o que mudou de assinatura).

## Abordagem / arquitetura

Módulos novos (todos em `onenote_mcp/`):

| módulo | papel |
| --- | --- |
| `formato/escrita.py` | ONMD → HTML (XHTML bem-formado). Parser próprio de blocos; inline com regex/markdown-it-py se precisar |
| `formato/leitura.py` | HTML do OneNote → ONMD (inverso), omitindo padrões medidos; escapa sintaxe ONMD literal vinda da página |
| `formato/paleta.py` | 9 cores nomeadas (desenho §1.1) + normalização nome CSS→hex |
| `formato/spec.md` | spec curta para IA, com exemplo completo; servida por `ler_spec()` e recurso `onenote://docs/formato` |
| `sanitizar.py` | 2ª barreira no HTML final: tags × atributos × CSS (desenho §3.2, corrigido pela crítica) |
| `arquivos.py` | anexos por parâmetro: pastas permitidas (`[arquivos].pastas`, vazio = desligado), sem UNC, sem symlink pra fora, bytes mágicos, teto 3,5 MB |
| `graph.py` | + `patch_conteudo` validado, + multipart (POST e PATCH) com CRLF, rotas permitidas, cota 120/min |
| `onenote.py` / `server.py` | tools v2 |

**Formato ONMD (resumo; spec completa no desenho §1, corrigida):**
- blocos: `#`…`######`, parágrafo, `---` (linha cinza), `> citação` (p cinza itálico), ```` ``` ```` código (tabela
  `on-cod-` com 1 `<p>` Consolas por linha), listas `-`/`1.`/`a.`/`i.` com aninhamento por 2 espaços,
  `- [ ]`/`- [x]` (p com `data-tag=to-do`), tabela GFM (cabeçalho em `<td><b>`, borda 1), `<tabela borda largura>`
  `<linha fundo>` `<celula largura alinhar cor fundo>`, `<destaque cor icone>`, `<colunas><coluna largura>`, `<secao id>`
- bloco de atributos no fim do bloco: `{id= cor= fundo= fonte= tamanho= alinhar= tags=}`; paleta fechada + `#hex`
- inline: `**`, `*`, `~~`, `<u>`, `==realce==`, `` `código` ``, `<span cor fundo fonte tamanho>`, `[t](https://)`,
  `[t](pagina:<id>)` (só página permitida → `onenote:` link)
- imagens/anexos: `![legenda](anexo:1){largura=}` e `<anexo n=2 nome="x.xlsx"/>`, com `anexos=[{"caminho":...}|{"data_url":...}]`
- leitura devolve imagem/anexo existente como `recurso:<id>`; escrever `recurso:` dá erro orientador
- tags oficiais menos `call-back`; `definition` avisa que volta como `remember-for-later`; item de lista com tag →
  `<li>` solto (crítica correção 3)

**Tools v2:** `listar_blocos`, `listar_secoes`, `listar_paginas(secao, com_nivel=False)`, `buscar_paginas(texto, bloco)`,
`ler_spec`, `ler_pagina(pagina_id, incluir_ids=False)`, `ver_imagem(pagina_id, recurso_id)`,
`criar_pagina(secao, titulo, conteudo, anexos=[], criado_em=None)`, `acrescentar(pagina_id, conteudo, onde="fim", anexos=[])`,
`inserir(pagina_id, ancora, conteudo, posicao="depois", anexos=[])`, `editar(pagina_id, trocas)`,
`marcar_tarefa(pagina_id, tarefa, feito=True)`, `renomear_pagina(pagina_id, titulo)`. Toda escrita devolve `avisos[]`.

## Decisões e trade-offs

- Parser próprio em vez de python-markdown/markdownify: um dialeto nos dois sentidos (ler → editar). Custo: mais
  código e testes de ouro. Reverte se a ida e volta não fechar: volta ao markdown simples na leitura.
- `editar` por trecho único (estilo `str_replace`) no ONMD do bloco, alvo pelo id gerado lido NA HORA (ids mudam
  após update); descendente de tabela → a tabela inteira (tr/td não aceitam ação).
- Divisão automática POST+PATCH quando passa de 6 partes/3,5 MB: só com espera e checagem por `data-id`; na dúvida,
  erro orientador (crítica §3.6).
- Conceitos: via negativa (cortes da crítica §4); antifragilidade: sondagem real barata antes de investir no
  conversor.

## Passos

1. [x] Sondagem real — **prova:** `docs/provas-v2.md` tem a tabela com 25 itens e veredito
   **reprova se:** algum item da tabela sem veredito.
2. [x] `graph.py`: `patch_conteudo` validado, multipart, rotas, sem `patch_json` cru — **prova:** `pytest -k graph` passa com
   `action:"delete"` → `ValueError`, alvo malformado → erro, teste de ouro do multipart
   **reprova se:** existe caminho no cliente que envia DELETE ou `action` fora do enum.
3. [x] `sanitizar.py` — **prova:** `pytest -k sanitiz` com a tabela de ataques do desenho §Passo 3
   **reprova se:** algum ataque (url( no style, img http, name: digitado, iframe, javascript:) sobrevive.
4. [x] `formato/` escrita + leitura + paleta + spec — **prova:** `pytest -k formato` com 1 teste de ouro por construção
   e ida e volta `ler(simular_saida(escrever(x))) == x` para a vitrine
   **reprova se:** HTML gerado não passa no `xml.dom.minidom` ou a ida e volta muda o ONMD.
5. [x] `arquivos.py` — **prova:** `pytest -k arquivos` (.. para fora, UNC, symlink, .exe renomeado, data URL ruim)
   **reprova se:** algum desses é aceito.
6. [x] tools v2 em `onenote.py`/`server.py` + diário local — **prova:** `pytest -q` inteiro verde; sonda MCP lista 13 tools
   **reprova se:** alguma tool nova sem teste ou `editar` envia PATCH com trecho ambíguo.
7. [x] (15/10: `docs/provas-v2.md` § Vitrine; bug do `<br>` corrigido com teste) prova real: página "Vitrine ONMD (pode apagar)" com todas as construções + edições (marcar tarefa, trocar célula,
   inserir depois de título, acrescentar em `#secao`, renomear) — **prova:** GET confere cada mudança; `ler_pagina`
   devolve ONMD equivalente ao enviado
   **reprova se:** alguma construção some ou volta diferente sem aviso.
   Itens que a revisão de 15/10 deixou sem medida (registrar o resultado em `docs/provas-v2.md` e ajustar
   `tests/simulador.py` ao medido; hoje o simulador devolve `<li>` solto como veio):
   - lista com etiqueta no POST (`- x {tags=important}\n- y`): o OneNote embrulha os `<li>` soltos num `<ul>`? funde
     duas listas soltas seguidas? A leitura já trata `<li>` solto como lista (sem id: não editável);
   - `editar` que acrescenta etiqueta num item: PATCH `replace` de `ul:{…}` por `<li>` soltos é aceito?
   - `<br />` dentro de `<p>` (a leitura devolve `<br>` e a escrita regera): volta igual no GET?
8. [x] (15/10: README reescrito, ARMADILHAS sem referência ao `conteudo.py` removido, CLAUDE.md e hub) doc: README (13 tools, formato), ARMADILHAS (provas), CLAUDE.md, hub — **prova:** `grep -c "editar" README.md` ≥ 1
   **reprova se:** README ainda diz "6 tools".

## Riscos / o que pode dar errado

- Leitura de página feita à mão (várias caixas, estilos misturados) não fecha a ida e volta: aceitar ONMD aproximado e
  avisar; editar por trecho continua valendo.
- Cota 120/min e 400/h: índice + conferência ao vivo custam requisições; `editar` em lote.
- `data-id` pode não sobreviver a edição manual no site (não provado): a leitura cai em `<tabela>` sem perder conteúdo.
