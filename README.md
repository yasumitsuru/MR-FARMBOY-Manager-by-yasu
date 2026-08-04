# MR FARMBOY Manager by yasu

## Status do Projeto

⚠️ **Em fase inicial de desenvolvimento**

Este projeto está em sua primeira versão e ainda não possui funcionalidades implementadas.

---

## Objetivo

O MR FARMBOY Manager é um painel desktop projetado para análise financeira e gerenciamento da fazenda no jogo MR FARMBOY. O sistema planeja as seguintes funcionalidades:

- **Leitura do Save**: Ler o save do MR FARMBOY em modo somente leitura;
- **Identificação de dados**: Identificar plantações, estoque, trabalhadores e quando esses dados estiverem disponíveis;
- **Cálculos financeiros**:
  - Calcular receita bruta;
  - Calcular custos de plantio;
  - Calcular custos de mão de obra;
  - Calcular lucro líquido;
- **Indicador de saúde financeira**: Informar se a fazenda está no azul, no vermelho ou no ponto de equilíbrio;
- **Atualização automática**: Atualizar os dados automaticamente a cada 5 minutos;
- **Atualização manual**: Possuir um botão para atualização manual.

---

## Tecnologias Planejadas

- Python 3.12
- PySide6 (Qt para Python)
- SQLite (banco de dados local)
- pytest (testes unitários)

---

## Segurança do Save

> ⚠️ **IMPORTANTE**: A integridade e segurança dos seus saves é fundamental.

- O aplicativo será projetado para operar em **modo somente leitura** sobre o save;
- A implementação deverá garantir que o **save original nunca seja modificado**;
- A análise deverá ser realizada sobre uma **cópia temporária** do arquivo de save;
- **Saves não devem ser enviados ao GitHub** por motivos de segurança e privacidade.

---

## Recursos do Jogo

> ⚠️ **ATENÇÃO**: Não distribuímos recursos protegidos de direitos autorais.

- Ícones e recursos originais **não serão distribuídos** neste repositório;
- Futuramente, o programa poderá **localizar recursos na instalação pertencente ao usuário**;
- O projeto **não inclui arquivos extraídos do jogo**.

---

## Sobre o Jogo

[MR FARMBOY](https://store.steampowered.com/app/2795090/MR_FARMBOY/) na Steam

Um jogo de gestão de fazenda desenvolvido e publicado por mrdboy.

---

## Aviso Legal

Este projeto **não é oficial** e:

- Não é afiliado aos desenvolvedores ou publicadores do MR FARMBOY;
- MR FARMBOY e seus recursos pertencem aos respectivos proprietários.

Este é um projeto independente feito por fãs para fins de análise pessoal.

---

## Instalação

🚧 **Em desenvolvimento**

## Executando o projeto durante o desenvolvimento

### Pré-requisitos
- Python 3.12 ou superior

### Passos para execução

1. **Criar ou ativar o ambiente virtual**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Instalar o projeto com dependências de desenvolvimento**:
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

3. **Executar a aplicação**:
   ```bash
   python -m mr_farmboy_manager
   ```

4. **Executar os testes**:
   ```bash
   pytest tests/ -v
   ```

---

## Instalação

🚧 **Em desenvolvimento**

As instruções de instalação e os requisitos definitivos serão documentados quando existir uma versão executável do projeto.

---

## Licença

📜 **Ainda não definida**

Este projeto ainda não possui uma licença oficial. Aguardando definição dos termos de uso e distribuição.