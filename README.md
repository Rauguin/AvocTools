<p align="center">
  <img src="caramelo.jpeg" alt="Caramelo Storm" width="160">
</p>

# AvocTools

Gerenciador interativo de **arsenal de ferramentas** para pentest / red team.
Mantém um diretório de ferramentas documentado automaticamente em um `README.md`
organizado por módulos, com **sincronização opcional para o GitHub**.

Pensado para quem trabalha em várias máquinas/VMs e quer manter o mesmo conjunto
de ferramentas versionado e documentado, sem esforço manual.

## ✨ Recursos

- **Setup interativo na primeira execução** — pergunta onde salvar as ferramentas,
  se você quer sincronizar com o GitHub, qual método de autenticação (SSH ou
  HTTPS/token) e se o repositório já existe ou deve ser criado pelo script.
- **Adicionar ferramentas** via `wget` ou `git clone` (remove o `.git` interno
  para evitar submódulos).
- **Documentação automática** em `README.md`, agrupada por módulo e em ordem
  alfabética.
- **Remoção com tripla confirmação** (sim/não + soma aleatória + digitar o nome).
- **Listagem e busca** por nome, módulo ou descrição.
- **Sincronização bidirecional** com o repositório remoto (push e pull), com
  tratamento de upstream e de rejeições (faz pull antes de reenviar).
- **Zero dados pessoais embutidos** — todas as configurações ficam em
  `~/.config/avoctools/config.json` (criado localmente, fora do repositório).

## 📦 Requisitos

- Python 3.8+ (somente biblioteca padrão)
- `git`
- `wget` (para baixar ferramentas via download direto)
- Opcional: [GitHub CLI (`gh`)](https://cli.github.com/) para criar o repositório
  automaticamente

## 🚀 Uso

```bash
git clone https://github.com/<seu-usuario>/AvocTools.git
cd AvocTools
python3 avoctools.py
```

Na primeira execução, o assistente de configuração cuida do resto:

```
============================================================
  AvocTools - Configuração inicial
============================================================
Onde deseja salvar as ferramentas [/home/voce/tools]:
Deseja sincronizar com um repositório no GitHub? (S/n):
Método de autenticação com o GitHub:
  1 - Chave SSH (recomendado)
  2 - HTTPS com senha/token (Personal Access Token)
Usuário ou organização do GitHub:
Nome do repositório [Tools]:
O repositório JÁ existe no GitHub? (S/n):
```

A partir daí, o menu principal fica disponível:

```
=== AvocTools - Gerenciador de Ferramentas ===
1 - Adicionar nova ferramenta
2 - Remover ferramenta existente
3 - Listar ferramentas
4 - Buscar ferramenta
5 - Sincronizar repositório
6 - Configuração
0 - Sair
```

## 🔐 Autenticação

- **SSH (recomendado):** use uma chave SSH cadastrada no GitHub. O remoto é
  configurado como `git@github.com:usuario/repo.git`.
- **HTTPS + token:** o GitHub não aceita mais senha de conta. Quando o `git`
  pedir a senha, informe um **Personal Access Token (PAT)**. O token **não é
  armazenado** por este script — quem cuida disso é o gerenciador de credenciais
  do próprio git.

## ⚙️ Configuração

A configuração fica em `~/.config/avoctools/config.json`:

```json
{
  "tools_dir": "/home/voce/tools",
  "github_sync": true,
  "auth_method": "ssh",
  "github_user": "seu-usuario",
  "repo_name": "Tools",
  "branch": "main"
}
```

Você pode alterar o caminho do arquivo definindo a variável de ambiente
`AVOCTOOLS_CONFIG_DIR`. Use a opção **6 - Configuração** no menu para ajustar
qualquer valor depois.

## 📁 Estrutura do diretório de ferramentas

```
tools/
├── README.md          # gerado e mantido pelo AvocTools
├── Recon/
│   └── nome-da-tool/
├── Exploitation/
│   └── outra-tool/
└── ...
```

## 📝 Licença

MIT. Veja [LICENSE](LICENSE).

---

<p align="center">
  <sub>⚡ <strong>Caramelo Storm</strong> ·
  <a href="https://www.linkedin.com/in/rafael-raugi/">LinkedIn</a> ·
  <a href="https://www.youtube.com/@avocado-shell">YouTube @avocado-shell</a></sub>
</p>
