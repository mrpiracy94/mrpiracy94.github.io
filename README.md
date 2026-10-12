# MrStore · Website oficial da comunidade

Website público da MrStore: https://mrpiracy94.github.io/

## Interface e integração

- Ícones da UI (categorias, pesquisa, favoritos, filtros, avisos e ações) são SVG locais em `assets/ui-icons.svg`, sem bibliotecas externas.
- A secção de plataformas exibe **apenas ZimaOS**, com o logótipo original e a indicação de que o formato App Store v2 existe, mas necessita de testes de instalação por aplicação.
- As imagens/logótipos das próprias aplicações são mantidos no catálogo de descoberta e não são confundidos com logótipos de sistemas operativos.
- A implantação preserva os 254 registos do catálogo e não altera Docker Compose nem os relatórios de segurança.


Este repositório publica apenas a **montra de descoberta**. O projeto, os manifests e as auditorias continuam no [repositório principal](https://github.com/mrpiracy94/MrStore).

## Publicação inicial

Se ainda estiver a aparecer um 404, abre **Settings → Pages** e seleciona **Deploy from a branch → main → /(root)**. O `index.html` na raiz permite a publicação sem build. Em alternativa, seleciona **GitHub Actions** para ativar o workflow de atualização periódica da seleção de aplicações.

## Fonte do catálogo e segurança

- Todas as aplicações são descobertas diretamente de `MrStore/Apps/*/docker-compose.yml` e comparadas com o catálogo técnico `MrStore/gh-pages/index.json`.
- O website mostra **as 254 aplicações atuais**, sem filtrar candidatas com alertas CVE. As próximas apps são incluídas automaticamente assim que existam manifests válidos.
- Se uma nova app ainda não tiver sido publicada no índice técnico, é identificada como candidata editorial com metadados do próprio manifest; nunca é apresentada como certificada.
- A ausência de um `release-status.json` coerente na fonte produz um estado de **candidatas em avaliação**, sem aprovação de segurança.
- Mesmo com relatório de aprovação, o website serve para descoberta, e não instala aplicações remotamente.

O workflow faz uma nova leitura da fonte a cada 15 minutos e pode ser executado manualmente. No modo Pages `main/(root)`, a página usa o snapshot presente neste repositório; no modo **GitHub Actions**, é reconstruída com a seleção atual.

## Desenvolvimento

Sem framework ou infraestrutura de servidor: `index.html` + `assets/site.css` + `assets/site.js`. O catálogo é carregado a partir de `index.json` e a indicação de segurança a partir de `release-status.json`.

O visual é mantido alinhado com a identidade laranja e preta da MrStore. Recursos multimédia e links de manifests são provenientes do repositório principal, e não representam certificação de instalação.
