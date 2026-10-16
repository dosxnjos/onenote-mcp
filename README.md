# onenote-mcp

> **In English:** an MCP server that lets Claude (Claude Code, Claude Desktop or any MCP client) read, create and
> edit OneNote pages of a personal Microsoft account through Microsoft Graph, restricted to an allowlist of sections
> and with no delete operation. Docs are in Brazilian Portuguese; commands and config keys are the same in any language.

Servidor MCP que deixa o Claude ler, criar e editar páginas do OneNote de uma **conta pessoal da Microsoft**
(Outlook.com, Live), pelo Microsoft Graph. Ele só enxerga as seções de uma **lista permitida** que você
escreve no `config.toml` e **não tem nenhuma função de apagar**.

O conteúdo das páginas vai e volta num formato próprio, o **ONMD** (OneNote + MD, "markdown do OneNote"): markdown
comum mais o que é do OneNote (cores, etiquetas, caixas de tarefa, tabelas com fundo, destaques, colunas, imagens e
anexos). Arquivo nesse formato usa a extensão `.onmd`.

## Sumário

1. [O que o Claude ganha (13 tools)](#o-que-o-claude-ganha-13-tools)
2. [Requisitos](#requisitos)
3. [Passo 1: registrar o app na Microsoft](#passo-1-registrar-o-app-na-microsoft-uma-vez)
4. [Passo 2: instalar](#passo-2-instalar)
5. [Passo 3: configurar](#passo-3-configurar-configtoml)
6. [Passo 4: login e conferência](#passo-4-login-e-conferência)
7. [Passo 5: registrar no Claude](#passo-5-registrar-no-claude)
8. [Como usar](#como-usar)
9. [Formato ONMD](#formato-onmd-resumo)
10. [Segurança](#segurança)
11. [Limites conhecidos](#limites-conhecidos)
12. [Solução de problemas](#solução-de-problemas)
13. [Testes, licença e créditos](#testes)

## O que o Claude ganha (13 tools)

| tool | faz |
| --- | --- |
| `listar_blocos` | blocos de anotações que estão na lista permitida |
| `listar_secoes(bloco)` | seções permitidas, com id e caminho `Bloco/Grupo/Seção` |
| `listar_paginas(secao, com_nivel)` | páginas da seção (id ou caminho), mais recente primeiro; `com_nivel` traz subpágina |
| `buscar_paginas(texto, bloco, limite)` | procura pelo **título** nas seções permitidas (o Graph não busca no texto) |
| `ler_spec` | a spec do formato ONMD (também no recurso `onenote://docs/formato`) |
| `ler_pagina(pagina_id, incluir_ids)` | conteúdo em ONMD; imagem e anexo vêm como `recurso:<id>` |
| `ver_imagem(pagina_id, recurso_id)` | devolve a imagem para o Claude ver |
| `criar_pagina(secao, titulo, conteudo, anexos, criado_em)` | página nova em ONMD, com imagens/arquivos e data retroativa |
| `acrescentar(pagina_id, conteudo, onde, anexos)` | no fim, no início ou dentro de uma `<secao id>` |
| `inserir(pagina_id, ancora, conteudo, posicao)` | antes ou depois de um bloco (trecho único ou `#id`) |
| `editar(pagina_id, trocas)` | troca trechos, estilo "localizar e substituir"; tudo ou nada |
| `marcar_tarefa(pagina_id, tarefa, feito)` | marca ou desmarca caixa de tarefa |
| `renomear_pagina(pagina_id, titulo)` | muda o título |

Toda escrita devolve `avisos[]` (o que o OneNote vai mudar ou perder). O "antes" de cada edição fica num diário
local (`%LOCALAPPDATA%\onenote-mcp\historico\<pagina>.jsonl`), porque o Graph não guarda histórico de versões.

## Requisitos

- **Windows** (é onde foi feito e testado). O token fica num cache cifrado pelo `msal-extensions`: DPAPI no
  Windows; no macOS e no Linux a biblioteca usa Keychain e libsecret, mas isso **não foi testado** aqui. Nos
  exemplos abaixo, em macOS/Linux troque `.venv\Scripts\python.exe` por `.venv/bin/python`.
- **Python 3.12 ou mais novo.**
- **[uv](https://docs.astral.sh/uv/)** ou o `pip` que vem com o Python.
- **Conta pessoal da Microsoft** com OneNote (conta corporativa/escolar não foi testada: o login usa o endereço
  `consumers`, só de contas pessoais).
- **Conta Azure gratuita** para registrar o app (passo 1 explica por quê).
- **Claude Code**, Claude Desktop ou outro cliente MCP que rode servidor por stdio.

## Passo 1: registrar o app na Microsoft (uma vez)

O servidor faz login **em seu nome** (login delegado). Para isso a Microsoft exige um "app registrado", que dá
um **ID do aplicativo (cliente)**. Não há segredo nem senha de app: é um cliente público.

**Por que precisa de conta Azure:** uma conta pessoal não consegue mais registrar app "fora de um diretório" (o
portal diz que a capacidade foi preterida e manda se inscrever no Azure; conferido em outubro de 2026). A conta Azure **gratuita** basta. A inscrição pode pedir cartão
de crédito só para verificar identidade; **registrar um app não custa nada** e não exige assinatura paga (não
mude para "pagamento conforme o uso").

1. Crie a conta Azure gratuita em <https://azure.microsoft.com/free> entrando com a sua conta pessoal da
   Microsoft (a mesma do OneNote ou outra; o app só precisa morar em algum diretório).
2. Abra o **Microsoft Entra** em <https://entra.microsoft.com> → **Aplicativos** → **Registros de aplicativo** →
   **Novo registro**. (O menu do Entra muda de lugar de tempos em tempos, às vezes dentro de **Identidade**; se não
   achar, digite "Registros de aplicativo" na busca do topo do portal.)
   - **Nome:** `onenote-mcp` (ou outro).
   - **Tipos de conta com suporte:** **Somente contas pessoais da Microsoft**.
   - **URI de redirecionamento:** deixe em branco.
   - Clique em **Registrar**.
3. No app criado, menu **Autenticação** → **Configurações avançadas** → **Permitir fluxos de cliente público** =
   **Sim** → **Salvar**. Na tela nova de Autenticação, a mesma chave fica na aba **Configurações**. (Sem isso, o
   login por código dá erro.)
4. Menu **Permissões de API** → **Adicionar uma permissão** → **Microsoft Graph** → **Permissões delegadas** →
   marque **`Notes.ReadWrite`** → **Adicionar permissões**. Não precisa de mais nada: o `offline_access` (manter o
   login) vem sozinho.
5. Menu **Visão geral**: copie o **ID do aplicativo (cliente)** (um GUID como `00000000-0000-0000-0000-000000000000`).
   Ele vai no `client_id` do passo 3.

Os nomes dos menus estão como aparecem no portal em português; em inglês são *App registrations*, *New
registration*, *Personal Microsoft accounts only*, *Authentication* → *Allow public client flows* (aba *Settings*
na tela nova), *API permissions* → *Delegated permissions*, *Application (client) ID*.

## Passo 2: instalar

```
git clone https://github.com/dosxnjos/onenote-mcp.git
cd onenote-mcp
```

Com **uv**:

```
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -e .
```

(O `--python 3.12` faz o uv usar o Python 3.12 da máquina, ou baixar um se não houver; sem ele, o uv pega o
primeiro Python que achar, e um 3.11 daria erro de `requires-python`. Versão mais nova também serve: `--python 3.13`.)

Ou com **pip**:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

(No Windows, se o `python` do terminal for outra versão ou não existir, use o lançador: `py -3.12 -m venv .venv`.)

Instale com `-e` (modo editável): todos os comandos (`login`, `eu`, `secoes`, `serve`) procuram o `config.toml` na
pasta do projeto. Se instalar de outro jeito, ou guardar o `config.toml` em outro lugar, aponte o arquivo pela
variável de ambiente `ONENOTE_MCP_CONFIG` (caminho completo). Ela vale para **todos** os comandos: defina no
terminal antes do `login`, `eu` e `secoes` (no PowerShell: `$env:ONENOTE_MCP_CONFIG = "C:\caminho\config.toml"`;
no macOS/Linux: `export ONENOTE_MCP_CONFIG=/caminho/config.toml`) e no registro do servidor (passo 5). Sem ela,
esses comandos dizem "falta o client_id" mesmo com o config preenchido.

## Passo 3: configurar (`config.toml`)

```
copy config.exemplo.toml config.toml
```

(`cp` no macOS/Linux.) O `config.toml` fica fora do git. Chaves:

| seção / chave | o que é |
| --- | --- |
| `[microsoft]` `client_id` | o ID do aplicativo (cliente) do passo 1. **Obrigatório.** |
| `[microsoft]` `authority` | deixe `https://login.microsoftonline.com/consumers` (nunca `common`: derruba a renovação do login de conta pessoal) |
| `[microsoft]` `conta` | opcional: e-mail da conta, se o cache tiver mais de uma |
| `[lista]` `permitidos` | prefixos `Bloco/Grupo/Seção` que o Claude pode ler e escrever. Vazio = nada |
| `[lista]` `bloqueados` | termos sempre fora. Vale **qualquer trecho** do nome (sem caixa e sem acento), em bloco, grupo ou seção: o termo `senha` derruba "Senhas antigas" e também "Resenhas". `senha`, `password` e `credencia` já são bloqueados no código; o toml só soma termos |
| `[lista]` `blocos_extra` | bloco **compartilhado por outra conta** (não aparece na lista da Microsoft): o id `0-<cid>!s<guid>` ou o link do OneDrive que tem `resid=` |
| `[arquivos]` `pastas` | pastas de onde imagens e anexos podem sair. Vazio = desligado |
| `[arquivos]` `max_mb` | teto por pedido, até 3.5 (a Microsoft corta em 4 MB) |
| `[servidor]` `instrucoes` | opcional: texto seu, acrescentado ao fim das instruções que o servidor entrega ao Claude |
| `cache_dir` | opcional: pasta do cache do token e do diário. Tem que ficar **antes da linha `[microsoft]`** (depois dela, vira chave de outra seção e é ignorada); o exemplo já traz a linha comentada. Padrão: `%LOCALAPPDATA%\onenote-mcp` no Windows, `~/onenote-mcp` no macOS e no Linux |

**Como achar o caminho para `permitidos`:** faça o login (passo 4) e rode
`.venv\Scripts\python.exe -m onenote_mcp eu`: ele lista os **nomes de todos os blocos** da conta e marca os já
liberados. Ponha o nome do bloco em `permitidos` (libera o bloco inteiro, menos as seções bloqueadas) e rode
`.venv\Scripts\python.exe -m onenote_mcp secoes`: ele mostra o caminho completo de cada seção liberada. Para
liberar só algumas, troque o nome do bloco pelos caminhos `Bloco/Grupo/Seção` que quiser. Maiúsculas e acentos
não importam na comparação.

```toml
[lista]
permitidos = [
  "Meu Bloco/Trabalho/Reuniões",
  "Meu Bloco/Pessoal",
]
```

**Bloco compartilhado por outra pessoa:** abra o bloco no OneNote para a Web e copie o endereço do OneDrive que
tem `resid=...`. Cole o **link inteiro** em `blocos_extra`: o servidor tira o id dele sozinho. (Se preferir montar o
id à mão, é `0-` + o valor do `resid`, trocando `%21` por `!`: no link ele vem codificado.) Depois rode `eu`: o
bloco aparece na lista com o **nome** a pôr em `permitidos`. Se o `eu` der erro 404, o id em `blocos_extra` está
errado. O papel da sua conta (`Reader` ou `Contributor`) decide se dá para escrever: `listar_blocos` mostra.

```toml
[lista]
permitidos = ["Bloco da Equipe"]
blocos_extra = ["0-XXXXXXXXXXXXXXXX!sxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"]
```

**Imagens e anexos:** crie uma pasta só para isso e ponha em `[arquivos].pastas`. A home inteira, a raiz do disco
e pastas que contêm o `AppData` ou o cache do servidor são recusadas. Tipos aceitos: imagens PNG, JPEG, GIF, BMP e
TIFF (conferidas pelo conteúdo do arquivo, não só pela extensão) e anexos `.pdf`, `.docx`, `.xlsx`, `.pptx`,
`.zip`, `.txt` e `.csv`. Outro tipo é recusado com erro.

```toml
[arquivos]
pastas = ["C:/Users/voce/OneNote-anexos"]
```

**Instruções suas para o Claude:** o servidor já diz ao Claude para ficar na lista permitida, ler a spec antes de
escrever e escrever para o leitor da página. Para acrescentar regras suas (quem costuma ler, tom de voz):

```toml
[servidor]
instrucoes = """
Quem lê estas páginas: a equipe de vendas; explique toda sigla.
Tom: direto, frases curtas.
"""
```

O servidor relê o `config.toml` quando o arquivo muda (sem reiniciar); só as `instrucoes` pedem reiniciar o
servidor, porque vão ao Claude na conexão.

## Passo 4: login e conferência

```
.venv\Scripts\python.exe -m onenote_mcp login
```

Ele mostra um endereço da Microsoft e um código. Abra o endereço no navegador, cole o código e entre com a conta
pessoal. A Microsoft pode pedir um **código de verificação enviado por e-mail** à conta antes de liberar: é normal.
Em seguida vem a tela de **consentimento**: o app `onenote-mcp` (o seu, do passo 1, marcado como **não
verificado** porque foi você que registrou) pede para ler e gravar suas anotações e manter o acesso. Aceite: é o
escopo `Notes.ReadWrite` mais o `offline_access` do passo 1. No fim aparece `conectado como <sua conta>`. O login fica no cache cifrado e se renova sozinho.

Confira o que a lista libera:

```
.venv\Scripts\python.exe -m onenote_mcp eu        (conta logada e nomes de todos os blocos)
.venv\Scripts\python.exe -m onenote_mcp secoes    (seções liberadas, com o caminho; aceita um prefixo de bloco)
```

Para apagar o login: `.venv\Scripts\python.exe -m onenote_mcp sair`.

## Passo 5: registrar no Claude

**Claude Code** (troque o caminho pela pasta onde você clonou):

```
claude mcp add -s user onenote -- C:\caminho\onenote-mcp\.venv\Scripts\python.exe -I -m onenote_mcp serve
```

O `-I` impede o Python de importar arquivos da pasta atual. Confira com `claude mcp list` ou `/mcp` dentro do
Claude Code. Depois de atualizar o código ou as `instrucoes`, reinicie o Claude Code (ou `/mcp` → reconectar).

**Claude Desktop:** em Configurações → Desenvolvedor → Editar configuração (`claude_desktop_config.json`), acrescente:

```json
{
  "mcpServers": {
    "onenote": {
      "command": "C:\\caminho\\onenote-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-I", "-m", "onenote_mcp", "serve"]
    }
  }
}
```

Se o `config.toml` estiver em outro lugar, acrescente `"env": {"ONENOTE_MCP_CONFIG": "C:\\caminho\\config.toml"}`.
Outros clientes MCP: o comando é o mesmo, sempre com o Python do `.venv`
(`C:\caminho\onenote-mcp\.venv\Scripts\python.exe -I -m onenote_mcp serve`, transporte stdio). O `python` do
sistema não tem o pacote instalado e dá `No module named onenote_mcp`.

## Como usar

Peça em linguagem natural; o Claude escolhe as tools. Exemplos:

- "Lista as seções que você enxerga no meu OneNote."
- "Lê a página mais recente da seção Reuniões e me resume as pendências."
- "Cria uma página 'Reunião 15/10' em Meu Bloco/Trabalho/Reuniões com pauta, tarefas e uma tabela de responsáveis."
- "Na página X, troca o prazo de 20/10 para 24/10 e marca a tarefa 'enviar orçamento' como feita."
- "Acrescenta esta foto no fim da página" (com a foto numa pasta de `[arquivos].pastas`).

## Formato ONMD (resumo)

Markdown comum mais o que é do OneNote: títulos, cores (paleta de 9 nomes ou `#hex`), fundo, fonte, tamanho,
alinhamento, realce, etiquetas oficiais, caixas de tarefa, listas (`-`, `1.`, `a.`, `i.`), tabela simples e
`<tabela>` rica (largura, fundo por célula), `<destaque>`, `<colunas>`, citação, bloco de código, divisória,
`<secao id>` como alvo, links para página (`pagina:<id>`), imagens e anexos.

```
## Pendências {cor=azul}

- [ ] Fechar orçamento {tags=important}
- [x] Enviar fotos

<destaque cor=amarelo icone="💡">
**Prazo:** 03/11.
</destaque>
```

ONMD = OneNote + MD (markdown); arquivo nesse formato usa a extensão `.onmd`.

Spec completa (é o que o Claude lê pela tool `ler_spec`): [onenote_mcp/formato/spec.md](onenote_mcp/formato/spec.md).
Exemplo com toda a sintaxe: [tests/vitrine.onmd](tests/vitrine.onmd), a "vitrine" do formato, usada no teste de
ida e volta (ONMD → HTML do OneNote → ONMD tem que voltar igual). Provas contra o OneNote real:
[docs/provas-v2.md](docs/provas-v2.md).

Por dentro: `formato/escrita.py` (ONMD → XHTML) e `formato/leitura.py` (HTML do OneNote → ONMD), com ida e volta
testada; `sanitizar.py` é a 2ª barreira no HTML final; `editar` lê a página na hora, acha o bloco pelo trecho e
regrava só ele (PATCH atômico), e recusa bloco com algo que o ONMD não mostra, para não apagar o que não aparece.

## Segurança

- **Nada se apaga:** nenhuma tool apaga; o cliente HTTP não tem DELETE e o PATCH só aceita `append`, `insert`,
  `prepend` e `replace` com conteúdo visível (trocar por vazio ou por caractere invisível é recusado).
- **A lista permitida limita a ferramenta, não a chave.** O token vale para todos os blocos da conta, e qualquer
  programa rodando com o seu usuário consegue ler o cache cifrado. Senha não deveria morar no OneNote; bloco, grupo
  ou seção com "senha", "password" ou "credencia" em **qualquer trecho** do nome é bloqueado no código (o que
  também derruba nomes inocentes como "Resenhas": renomeie no OneNote se precisar). Para isolar de verdade, faça o login com uma
  conta separada que só recebe compartilhado o que o Claude pode ver.
- **Token** em cache cifrado em `%LOCALAPPDATA%\onenote-mcp\token_cache.bin`, nunca no repositório.
  `python -m onenote_mcp sair` apaga o login; para revogar o acesso do app, use account.microsoft.com →
  Privacidade → aplicativos com acesso.
- Escopo único `Notes.ReadWrite`; host fixo `graph.microsoft.com`, sem seguir redirecionamento; até 120 pedidos/min.
- Arquivo local só sai pelo parâmetro `anexos` e só de `[arquivos].pastas`; caminho escrito no texto da página
  nunca é lido.
- Texto lido de página é dado, não instrução (para o Claude e para o código).

## Limites conhecidos

- **Lista aninhada** (sub-item) aparece com uma linha em branco antes de cada sub-nível: limite da Microsoft no
  Graph, sem contorno. A escrita avisa; prefira títulos ou lista de um nível.
- **Parágrafo logo antes de uma lista não se edita:** o OneNote o moveria para depois da lista ao regravá-lo;
  `editar` recusa e sugere `inserir`.
- **Busca só pelo título** das páginas: o Graph não oferece busca no texto.
- **Imagem pequena ignora a `largura`** pedida (fica no tamanho natural).
- **Página nova leva até ~1 min** para existir de fato: ler ou editar logo depois pode dar 404 ou 504. Às vezes a
  criação trava do lado da Microsoft (página sem título, 404 por minutos): crie de novo.
- **Sem apagar** página, seção ou bloco (de propósito); também não cria seção nem copia página.
- Numeração de lista sempre começa do 1; etiqueta em sub-item não é guardada; não há mesclar células.

## Solução de problemas

| sintoma | o que fazer |
| --- | --- |
| `falta o client_id no config.toml` | faça o passo 1 e preencha `[microsoft].client_id` |
| `sem login` ou `login vencido` | rode `python -m onenote_mcp login` num terminal (o login não aparece dentro do Claude) |
| `secoes` volta vazio | `permitidos` não casa com nenhum caminho: confira os nomes dos blocos com `eu` |
| `secoes` não mostra uma seção que está em `permitidos` | o nome da seção, do grupo ou do bloco contém `senha`, `password` ou `credencia` (ou um termo seu de `bloqueados`), em qualquer trecho: "Resenhas" também cai |
| `config.toml: [x] tem que ser uma tabela` (ou `… tem que ser uma lista`) | tipo errado no `config.toml`: seção se escreve `[servidor]` numa linha e as chaves embaixo, nunca `servidor = "…"`; listas vão entre colchetes |
| bloco compartilhado não aparece | ele entra por `blocos_extra` (passo 3) |
| `eu` dá 404 citando `blocos_extra` | o id do bloco compartilhado está errado: cole o link inteiro do OneDrive (passo 3) |
| erro 403 "só como leitura" | sua conta é `Reader` naquele bloco: peça permissão de edição ao dono |
| erro 404 logo depois de criar | espere ~1 min; se a página ficar sem título por minutos, crie de novo |
| `No module named onenote_mcp` | instale com `pip install -e .` no `.venv` e registre o Python **do `.venv`** (`.venv\Scripts\python.exe -I -m onenote_mcp serve`), não o do sistema |
| `falta o client_id` com o config preenchido | o comando não achou o seu `config.toml`: instale com `-e` ou defina `ONENOTE_MCP_CONFIG` (passo 2) |
| anexo recusado | tipo fora da lista (passo 3, imagens e anexos) ou arquivo fora de `[arquivos].pastas` |

Mais sintomas e causas: [docs/ARMADILHAS.md](docs/ARMADILHAS.md).

## Testes

Instale o pytest com o mesmo instalador do passo 2 e rode:

```
uv pip install --python .venv\Scripts\python.exe -e ".[teste]"     (com uv)
.venv\Scripts\python.exe -m pip install -e ".[teste]"             (com pip)
.venv\Scripts\python.exe -m pytest -q
```

Sem rede: um Graph falso e um simulador imitam o OneNote (341 testes; o de link simbólico é pulado no Windows sem
permissão para criar link).

## Licença

[MIT](LICENSE).

## Créditos

O mapa de endpoints e as pegadinhas de conta pessoal vieram do estudo do
[Softeria/ms-365-mcp-server](https://github.com/Softeria/ms-365-mcp-server) (MIT). O desenho das tools de
edição e da spec se inspirou nas instruções do MCP do Notion. Nenhum código copiado.
