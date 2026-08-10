# MR FARMBOY Manager by yasu

Gerenciador desktop independente para localizar saves do MR FARMBOY, consultar
detalhes sanitizados e manter backups locais com operações confirmadas.

## Status

**MVP 0.1.0 utilizável no Windows.**

O MVP inclui:

- descoberta de slots `save_<n>`;
- leitura de progresso do jogador e cultivos em arquivos Godot `.tres`;
- configuração persistente das pastas de saves e do jogo;
- atualização ao configurar a pasta, manual e automática a cada cinco minutos;
- criação, listagem, restauração e exclusão de backups;
- backup preventivo antes de toda restauração;
- mensagens sanitizadas e logging operacional rotativo;
- executável Windows que não exige instalação manual do Python.

Dados financeiros e inventário detalhado continuam indisponíveis enquanto o schema
correspondente do jogo não estiver confirmado.

## Instalação no Windows

1. Baixe e extraia o pacote completo da release. Não separe o `.exe` da pasta
   `_internal`.
2. Execute `MR-FARMBOY-Manager.exe`.
3. Em **Pasta dos saves**, selecione a pasta `game_data` do jogo.
4. Selecione um slot para consultar detalhes ou criar um backup.

O executável é distribuído em formato `onedir` e não requer Python instalado.
O MVP usa um ícone genérico; nenhum ícone ou recurso extraído do jogo é distribuído.

## Localização dos dados

No Windows, a pasta padrão dos saves é:

```text
%APPDATA%\Godot\app_userdata\MR FARMBOY\game_data
```

Backups e logs ficam na pasta local privada da aplicação, normalmente:

```text
%LOCALAPPDATA%\yasu\MR FARMBOY Manager\backups
%LOCALAPPDATA%\yasu\MR FARMBOY Manager\logs
```

Os caminhos configurados são persistidos pelo `QSettings` do Qt.

## Segurança e privacidade

- A inspeção trata saves e instalação do jogo como somente leitura.
- Arquivos externos têm limites de tamanho, parsing e quantidade de avisos.
- Links simbólicos, junctions/reparse points e mudanças concorrentes são rejeitados nas
  operações sensíveis.
- Criar um backup grava somente no diretório privado de backups.
- Restaurar substitui o slot ativo apenas após confirmação e criação de backup
  preventivo.
- Excluir exige confirmação e atua somente sobre um backup íntegro e identificado.
- Logs não armazenam o conteúdo integral dos saves.
- Saves e recursos extraídos do jogo não devem ser enviados ao repositório.

## Desenvolvimento

Pré-requisito: Python 3.12 ou superior.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -e ".[dev]"
python -m mr_farmboy_manager
pytest -q
```

Com `uv`, o ambiente travado pode ser reproduzido com:

```powershell
uv sync --extra dev --locked
```

## Build e smoke test Windows

```powershell
.venv\Scripts\python.exe -m tools.build_windows
.venv\Scripts\python.exe -m tools.smoke_windows_build
```

O build é gravado em:

```text
dist\MR-FARMBOY-Manager\MR-FARMBOY-Manager.exe
```

O smoke test inicia o executável com `APPDATA`, `LOCALAPPDATA`, configuração, logs e
backups isolados em um diretório temporário.

## Sobre o jogo

[MR FARMBOY](https://store.steampowered.com/app/2795090/MR_FARMBOY/) é
desenvolvido e publicado por mrdboy.

Este projeto não é oficial nem afiliado aos desenvolvedores ou publicadores do jogo.
MR FARMBOY e seus recursos pertencem aos respectivos proprietários.

## Licença

O projeto ainda não possui uma licença de redistribuição definida. Na ausência de uma
licença explícita, permanecem reservados os direitos aplicáveis ao código.
