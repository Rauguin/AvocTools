#!/usr/bin/env python3
"""
AvocTools - Gerenciador de ferramentas de pentest/red team.

Mantém um diretório de ferramentas documentado em um README.md organizado por
módulos, com sincronização opcional para um repositório GitHub.

Nenhuma informação pessoal fica embutida no código: caminhos, usuário, repositório
e método de autenticação são definidos em uma configuração local criada na primeira
execução (~/.config/avoctools/config.json) ou via variáveis de ambiente.
"""

import json
import os
import random
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

CONFIG_DIR = Path(os.environ.get("AVOCTOOLS_CONFIG_DIR", Path.home() / ".config" / "avoctools"))
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "tools_dir": "",        # diretório onde as ferramentas serão salvas
    "github_sync": False,   # sincronizar com o GitHub?
    "auth_method": "ssh",   # "ssh" ou "https"
    "github_user": "",      # usuário/organização do GitHub
    "repo_name": "",        # nome do repositório
    "branch": "main",       # branch principal
}


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def ask(prompt, default=None):
    """input() com valor padrão opcional."""
    suffix = f" [{default}]" if default not in (None, "") else ""
    resposta = input(f"{prompt}{suffix}: ").strip()
    return resposta or (default if default is not None else "")


def ask_yes_no(prompt, default=True):
    padrao = "S/n" if default else "s/N"
    while True:
        resposta = input(f"{prompt} ({padrao}): ").strip().lower()
        if not resposta:
            return default
        if resposta in ("s", "sim", "y", "yes"):
            return True
        if resposta in ("n", "nao", "não", "no"):
            return False
        print("❌ Responda com 's' ou 'n'.")


def load_config():
    if not CONFIG_PATH.exists():
        return None
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Mescla com os padrões para tolerar versões antigas
        cfg = dict(DEFAULT_CONFIG)
        cfg.update(data)
        return cfg
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ Não foi possível ler a configuração ({e}). Refazendo o setup.")
        return None


def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    # Permissões restritas (não contém segredos, mas é boa prática)
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass
    print(f"💾 Configuração salva em {CONFIG_PATH}")


def remote_url(cfg):
    """Monta a URL do remoto a partir do método de autenticação escolhido."""
    user = cfg["github_user"]
    repo = cfg["repo_name"]
    if cfg["auth_method"] == "ssh":
        return f"git@github.com:{user}/{repo}.git"
    return f"https://github.com/{user}/{repo}.git"


# ---------------------------------------------------------------------------
# Setup interativo (primeira execução)
# ---------------------------------------------------------------------------

def first_run_setup():
    clear()
    print("=" * 60)
    print("  AvocTools - Configuração inicial")
    print("  ⚡ Caramelo Storm · LinkedIn: in/rafael-raugi · YouTube: @avocado-shell")
    print("=" * 60)
    print("Vamos configurar onde suas ferramentas ficam e, se quiser,")
    print("a sincronização com o GitHub. Tudo fica em um arquivo local;")
    print("nada é embutido no código.\n")

    cfg = dict(DEFAULT_CONFIG)

    # 1) Onde salvar as ferramentas
    default_dir = str(Path.home() / "tools")
    tools_dir = ask("Onde deseja salvar as ferramentas", default_dir)
    cfg["tools_dir"] = str(Path(tools_dir).expanduser().resolve())
    Path(cfg["tools_dir"]).mkdir(parents=True, exist_ok=True)
    print(f"📁 Diretório de ferramentas: {cfg['tools_dir']}\n")

    # 2) Sincronizar com o GitHub?
    cfg["github_sync"] = ask_yes_no("Deseja sincronizar com um repositório no GitHub?", default=True)

    if not cfg["github_sync"]:
        print("\nℹ️ Sincronização desativada. Você pode ativar depois pelo menu de configuração.")
        save_config(cfg)
        input("\nPressione ENTER para continuar...")
        return cfg

    # 3) Método de autenticação
    print("\nMétodo de autenticação com o GitHub:")
    print("  1 - Chave SSH (recomendado)")
    print("  2 - HTTPS com senha/token (Personal Access Token)")
    metodo = ask("Escolha (1 ou 2)", "1")
    cfg["auth_method"] = "https" if metodo.strip() == "2" else "ssh"

    if cfg["auth_method"] == "https":
        print("\nℹ️ O GitHub não aceita mais senha de conta via HTTPS.")
        print("   Use um Personal Access Token (PAT) quando o git pedir a senha.")
        print("   O token NÃO é armazenado por este script; quem cuida disso é o")
        print("   gerenciador de credenciais do git.")

    # 4) Usuário e repositório
    print()
    cfg["github_user"] = ask("Usuário ou organização do GitHub")
    while not cfg["github_user"]:
        cfg["github_user"] = ask("Usuário é obrigatório. Informe o usuário/organização do GitHub")
    cfg["repo_name"] = ask("Nome do repositório", "Tools")
    cfg["branch"] = ask("Branch principal", "main")

    # 5) Repositório já existe ou criar agora?
    print(f"\nRepositório alvo: {cfg['github_user']}/{cfg['repo_name']}")
    existe = ask_yes_no("O repositório JÁ existe no GitHub?", default=True)

    setup_git_repo(cfg, repo_exists=existe)

    save_config(cfg)
    input("\nPressione ENTER para continuar...")
    return cfg


def setup_git_repo(cfg, repo_exists):
    """Inicializa o git no diretório de ferramentas e configura o remoto."""
    tools_dir = cfg["tools_dir"]
    url = remote_url(cfg)

    # git init (se necessário)
    if not (Path(tools_dir) / ".git").exists():
        print("🔧 Inicializando repositório git local...")
        run_git(["init"], tools_dir)
        run_git(["branch", "-M", cfg["branch"]], tools_dir)

    # Configurar o remoto origin
    has_origin = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=tools_dir, capture_output=True,
    )
    if has_origin.returncode == 0:
        run_git(["remote", "set-url", "origin", url], tools_dir)
    else:
        run_git(["remote", "add", "origin", url], tools_dir)
    print(f"🔗 Remoto origin: {url}")

    if repo_exists:
        # Tenta trazer o conteúdo existente
        print("🔄 Buscando conteúdo existente do repositório...")
        pull = subprocess.run(
            ["git", "pull", "origin", cfg["branch"], "--allow-unrelated-histories", "--no-rebase"],
            cwd=tools_dir, capture_output=True, text=True,
        )
        if pull.returncode != 0:
            print("⚠️ Não foi possível puxar agora (talvez o repo esteja vazio ou sem acesso).")
            print("   Detalhe:", (pull.stderr or "").strip().splitlines()[-1] if pull.stderr else "")
        else:
            print("✅ Conteúdo remoto sincronizado.")
        return

    # Criar o repositório via gh CLI, se disponível
    if shutil.which("gh"):
        criar = ask_yes_no("Detectei o GitHub CLI (gh). Criar o repositório agora?", default=True)
        if criar:
            visibilidade = ask("Visibilidade (public/private)", "private")
            visibilidade = "public" if visibilidade.lower().startswith("pub") else "private"
            res = subprocess.run(
                ["gh", "repo", "create", f"{cfg['github_user']}/{cfg['repo_name']}",
                 f"--{visibilidade}", "--source", tools_dir, "--remote", "origin"],
                cwd=tools_dir,
            )
            if res.returncode == 0:
                print("✅ Repositório criado no GitHub.")
            else:
                print("⚠️ Falha ao criar via gh. Crie manualmente em github.com/new.")
            return

    print("\nℹ️ Crie o repositório manualmente em https://github.com/new")
    print(f"   Nome: {cfg['repo_name']}  (NÃO inicialize com README)")
    print("   O remoto já está configurado; o primeiro push criará o conteúdo.")


# ---------------------------------------------------------------------------
# Helpers de git e README
# ---------------------------------------------------------------------------

def run_git(args, cwd):
    return subprocess.run(["git"] + args, cwd=cwd, check=False)


def readme_path(cfg):
    tools_dir = cfg["tools_dir"]
    path = os.path.join(tools_dir, "README.md")
    legacy = os.path.join(tools_dir, "Readme.md")
    if not os.path.exists(path) and os.path.exists(legacy):
        return legacy
    return path


def load_readme(cfg):
    """Carrega o README em uma estrutura módulos -> lista de ferramentas."""
    path = readme_path(cfg)
    modules = defaultdict(list)
    if not os.path.exists(path):
        return modules

    current_module = None
    current_tool = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                if current_tool and current_module:
                    modules[current_module].append("".join(current_tool))
                    current_tool = []
                current_module = line.strip()[3:]
            elif line.startswith("### "):
                if current_tool and current_module:
                    modules[current_module].append("".join(current_tool))
                    current_tool = []
                current_tool = [line]
            elif line.strip() == "" and current_tool:
                current_tool.append(line)
                if current_module:
                    modules[current_module].append("".join(current_tool))
                current_tool = []
            elif current_tool:
                current_tool.append(line)

        if current_tool and current_module:
            modules[current_module].append("".join(current_tool))

    return modules


def save_readme(cfg, modules):
    """Grava o README organizado por módulo e em ordem alfabética."""
    tools_dir = cfg["tools_dir"]
    os.makedirs(tools_dir, exist_ok=True)
    path = readme_path(cfg)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {cfg.get('repo_name') or 'Tools'}\n\n")
        f.write("Arsenal de ferramentas gerenciado pelo [AvocTools](https://github.com/).\n\n")
        for module in sorted(modules.keys()):
            f.write(f"## {module}\n\n")
            for tool in sorted(modules[module], key=lambda x: x.splitlines()[0].lower()):
                f.write(tool.strip() + "\n\n")


def git_update(cfg, msg):
    """git add + commit + push, com tratamento de upstream e rejeições."""
    if not cfg.get("github_sync"):
        print("ℹ️ Sincronização desativada. Alterações salvas apenas localmente.")
        return

    tools_dir = cfg["tools_dir"]
    branch = cfg.get("branch", "main")
    url = remote_url(cfg)

    try:
        # Garantir o remoto correto
        has_origin = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=tools_dir, capture_output=True,
        )
        if has_origin.returncode != 0:
            run_git(["remote", "add", "origin", url], tools_dir)
        else:
            run_git(["remote", "set-url", "origin", url], tools_dir)

        run_git(["add", "."], tools_dir)
        commit = subprocess.run(
            ["git", "commit", "-m", msg], cwd=tools_dir, capture_output=True, text=True,
        )
        if commit.returncode != 0:
            saida = (commit.stdout + commit.stderr).lower()
            if "nothing to commit" in saida:
                print("ℹ️ Nada novo para commitar.")
            else:
                print("⚠️ Commit falhou:\n", commit.stderr)

        # Descobrir a branch atual
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=tools_dir,
            ).decode().strip() or branch
        except subprocess.CalledProcessError:
            pass

        push = subprocess.run(
            ["git", "push"], cwd=tools_dir, capture_output=True, text=True,
        )
        if push.returncode != 0:
            stderr = (push.stderr or "").lower()
            if any(s in stderr for s in ("set-upstream", "no upstream", "the current branch")):
                push = subprocess.run(
                    ["git", "push", "--set-upstream", "origin", branch],
                    cwd=tools_dir, capture_output=True, text=True,
                )
                if push.returncode != 0:
                    print("⚠️ Erro ao dar push:\n", push.stderr)
                    return
            elif "fetch first" in stderr or "rejected" in stderr:
                print("🔄 O remoto tem commits novos, fazendo pull antes de enviar...")
                pull = subprocess.run(
                    ["git", "pull", "origin", branch, "--no-rebase"],
                    cwd=tools_dir, capture_output=True, text=True,
                )
                if pull.returncode != 0:
                    print("⚠️ Falha no pull:\n", pull.stderr)
                    return
                push = subprocess.run(
                    ["git", "push"], cwd=tools_dir, capture_output=True, text=True,
                )
                if push.returncode != 0:
                    print("⚠️ Erro ao dar push após pull:\n", push.stderr)
                    return
            else:
                print("⚠️ Erro ao dar push:\n", push.stderr)
                return

        print("✅ Atualização enviada ao repositório com sucesso!")
    except (subprocess.CalledProcessError, OSError) as e:
        print("⚠️ Erro ao atualizar o repositório Git. Detalhes:", e)


# ---------------------------------------------------------------------------
# Listagem / busca
# ---------------------------------------------------------------------------

def listar_grupos(cfg):
    modules = load_readme(cfg)
    if not modules:
        print("⚠️ Nenhum grupo encontrado (README vazio).")
        return []
    print("\nGrupos existentes:")
    for i, module in enumerate(sorted(modules.keys()), start=1):
        print(f"{i}. {module}")
    return sorted(modules.keys())


def listar_ferramentas(cfg):
    modules = load_readme(cfg)
    if not modules:
        print("⚠️ Nenhuma ferramenta cadastrada.")
        return
    print("\n== Ferramentas cadastradas ==")
    for module in sorted(modules.keys()):
        print(f"\n## {module}")
        for tool in modules[module]:
            lines = tool.strip().splitlines()
            name = lines[0].replace("### ", "").strip()
            print(f"\n  {name}")
            for line in lines[1:]:
                if line.strip():
                    print(f"  {line.strip()}")


def buscar_ferramenta(cfg):
    query = input("Termo de busca: ").strip().lower()
    if not query:
        print("❌ Termo vazio.")
        return

    modules = load_readme(cfg)
    resultados = []
    for module, tools in modules.items():
        for tool in tools:
            lines = tool.strip().splitlines()
            name = lines[0].replace("### ", "").strip()
            desc = " ".join(lines[1:])
            if query in name.lower() or query in module.lower() or query in desc.lower():
                resultados.append((name, module, lines[1:]))

    if not resultados:
        print(f"\n🔍 Nenhum resultado para '{query}'.")
        return

    print(f"\n🔍 {len(resultados)} resultado(s) para '{query}':")
    for nome, modulo, detalhes in resultados:
        print(f"\n  [{modulo}] {nome}")
        for linha in detalhes:
            if linha.strip():
                print(f"    {linha.strip()}")


# ---------------------------------------------------------------------------
# Sincronização
# ---------------------------------------------------------------------------

def atualizar_diretorio(cfg):
    """Puxa mudanças do remoto para o diretório local (nova máquina / outra VM)."""
    if not cfg.get("github_sync"):
        print("ℹ️ Sincronização desativada.")
        return
    tools_dir = cfg["tools_dir"]
    branch = cfg.get("branch", "main")
    try:
        print("🔄 Atualizando a partir do remoto...")
        run_git(["config", "pull.rebase", "false"], tools_dir)
        pull = subprocess.run(
            ["git", "pull", "origin", branch, "--allow-unrelated-histories", "--no-rebase"],
            cwd=tools_dir, capture_output=True, text=True,
        )
        if pull.returncode != 0:
            print("⚠️ Falha no git pull:\n", pull.stderr)
            return
        print("✅ Diretório atualizado a partir do remoto.")
    except OSError as e:
        print("⚠️ Erro ao atualizar diretório:", e)


def enviar_alteracoes_locais(cfg):
    """Detecta ferramentas adicionadas manualmente e sincroniza com o remoto."""
    tools_dir = cfg["tools_dir"]
    modules = load_readme(cfg)

    documentadas = set()
    for tools in modules.values():
        for tool in tools:
            nome = tool.splitlines()[0].replace("### ", "").strip()
            documentadas.add(nome)

    try:
        entradas = [
            d for d in os.listdir(tools_dir)
            if os.path.isdir(os.path.join(tools_dir, d)) and not d.startswith(".")
        ]
    except FileNotFoundError:
        print("⚠️ Diretório de ferramentas não encontrado.")
        return

    nao_documentadas = [d for d in entradas if d not in documentadas]

    if not nao_documentadas:
        print("✅ Nenhuma ferramenta local sem documentação encontrada.")
        print("   Verificando arquivos modificados para enviar...")
        git_update(cfg, "Sincronização manual")
        return

    print(f"\n🔍 {len(nao_documentadas)} ferramenta(s) sem documentação:")
    for d in nao_documentadas:
        print(f"  - {d}")

    print()
    grupos = listar_grupos(cfg)

    for tool_name in nao_documentadas:
        print(f"\n--- {tool_name} ---")
        if not ask_yes_no("Documentar esta ferramenta?", default=True):
            continue

        if grupos:
            print("Digite o número de um grupo existente ou um novo nome:")
            choice = input("Grupo: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(grupos):
                module_name = grupos[int(choice) - 1]
            else:
                module_name = choice
        else:
            module_name = input("Módulo: ").strip()

        if not module_name:
            print("⚠️ Módulo vazio, pulando.")
            continue

        function_desc = input("Descrição/Função: ").strip()
        destino = os.path.join(tools_dir, tool_name)
        entry = (
            f"### {tool_name}\n"
            f"- **Função:** {function_desc}\n"
            f"- **Local:** `{tool_name}`\n"  # caminho relativo, sem expor paths pessoais
        )
        modules[module_name].append(entry)
        print(f"✅ '{tool_name}' documentada em '{module_name}'.")

    save_readme(cfg, modules)
    print("\n=== Enviando para o repositório ===")
    git_update(cfg, "Sincronização de ferramentas adicionadas manualmente")


def sincronizar_menu(cfg):
    print("\n=== Sincronizar Repositório ===")
    print("1 - Puxar do remoto         (nova máquina / atualizar local)")
    print("2 - Enviar alterações locais (adicionou ferramenta manualmente)")
    print("0 - Voltar")
    escolha = input("Escolha: ").strip()
    if escolha == "1":
        atualizar_diretorio(cfg)
    elif escolha == "2":
        enviar_alteracoes_locais(cfg)
    elif escolha != "0":
        print("❌ Opção inválida.")


# ---------------------------------------------------------------------------
# Operações principais
# ---------------------------------------------------------------------------

def adicionar_ferramenta(cfg):
    tools_dir = cfg["tools_dir"]
    print("=== Adicionar Ferramenta ===")
    print("1 - Adicionar via wget")
    print("2 - Adicionar via git clone")
    escolha = input("Escolha uma opção (1 ou 2): ").strip()
    if escolha not in ("1", "2"):
        print("❌ Opção inválida.")
        return

    url = input("Digite a URL: ").strip()
    if not url:
        print("❌ URL vazia.")
        return
    tool_name = input("Nome da ferramenta: ").strip()
    if not tool_name:
        print("❌ Nome vazio.")
        return

    existing = listar_grupos(cfg)
    if existing:
        print("\nDigite o número de um grupo existente ou digite um novo nome:")
        choice = input("Grupo (número ou nome): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(existing):
            module_name = existing[int(choice) - 1]
        else:
            module_name = choice
    else:
        module_name = input("Módulo a que pertence: ").strip()

    if not module_name:
        print("❌ Módulo vazio.")
        return

    function_desc = input("Descrição/Função da ferramenta: ").strip()

    destino = os.path.join(tools_dir, tool_name)
    os.makedirs(destino, exist_ok=True)

    if escolha == "1":
        print(f"📥 Baixando arquivo com wget para {tool_name}/...")
        subprocess.run(["wget", "-P", destino, url], check=False)
    else:
        print(f"📥 Clonando repositório com git clone para {tool_name}/...")
        subprocess.run(["git", "clone", "--depth", "1", url, destino], check=False)
        # remover .git interno para evitar submódulos
        shutil.rmtree(os.path.join(destino, ".git"), ignore_errors=True)

    entry = (
        f"### {tool_name}\n"
        f"- **Função:** {function_desc}\n"
        f"- **Local:** `{tool_name}`\n"
        f"- **Origem:** {url}\n"
    )

    modules = load_readme(cfg)
    modules[module_name].append(entry)
    save_readme(cfg, modules)

    print(f"\n✅ Ferramenta '{tool_name}' adicionada e documentada em '{module_name}'!")
    print("\n=== Atualizando repositório Git ===")
    git_update(cfg, f"Adicionada ferramenta {tool_name}")


def remover_ferramenta(cfg):
    tools_dir = cfg["tools_dir"]
    print("=== Remover Ferramenta ===")

    modules = load_readme(cfg)
    todas_ferramentas = []
    for module, tools in modules.items():
        for tool in tools:
            nome = tool.splitlines()[0].replace("### ", "").strip()
            todas_ferramentas.append((nome, module))

    if not todas_ferramentas:
        print("⚠️ Nenhuma ferramenta encontrada para remover.")
        return

    print("\nFerramentas disponíveis:")
    for i, (nome, modulo) in enumerate(todas_ferramentas, start=1):
        print(f"{i}. {nome}  ({modulo})")

    try:
        escolha = int(input("\nDigite o número da ferramenta que deseja remover: ").strip())
        if escolha < 1 or escolha > len(todas_ferramentas):
            print("❌ Opção inválida.")
            return
    except ValueError:
        print("❌ Entrada inválida.")
        return

    tool_name, module_name = todas_ferramentas[escolha - 1]

    # ---------- CHECK TRIPLO ----------
    if not ask_yes_no(f"Tem certeza que deseja remover '{tool_name}'?", default=False):
        print("❌ Operação cancelada.")
        return

    a, b = random.randint(1, 9), random.randint(1, 9)
    try:
        resposta = int(input(f"Para confirmar, resolva: {a} + {b} = ").strip())
        if resposta != a + b:
            print("❌ Resposta incorreta. Cancelando operação.")
            return
    except ValueError:
        print("❌ Entrada inválida. Cancelando operação.")
        return

    confirm_name = input("Digite exatamente o nome da ferramenta para confirmar: ").strip()
    if confirm_name != tool_name:
        print("❌ Nome incorreto. Cancelando operação.")
        return

    # Remover do README
    modules[module_name] = [
        tool for tool in modules[module_name]
        if not tool.startswith(f"### {tool_name}")
    ]
    save_readme(cfg, modules)

    destino = os.path.join(tools_dir, tool_name)
    if os.path.exists(destino):
        shutil.rmtree(destino)
        print(f"🗑️ Diretório '{tool_name}/' removido.")
    else:
        print("⚠️ Diretório da ferramenta não encontrado (pode ter outro nome).")

    print(f"\n✅ Ferramenta '{tool_name}' removida com sucesso!")
    print("\n=== Atualizando repositório Git ===")
    git_update(cfg, f"Removida ferramenta {tool_name}")


# ---------------------------------------------------------------------------
# Menu de configuração
# ---------------------------------------------------------------------------

def menu_configuracao(cfg):
    while True:
        print("\n=== Configuração ===")
        print(f"1 - Diretório de ferramentas : {cfg['tools_dir']}")
        print(f"2 - Sincronizar com GitHub   : {'sim' if cfg['github_sync'] else 'não'}")
        print(f"3 - Método de autenticação   : {cfg['auth_method']}")
        print(f"4 - Usuário/repo             : {cfg['github_user']}/{cfg['repo_name']}")
        print(f"5 - Branch                   : {cfg['branch']}")
        print("6 - Reconfigurar tudo (setup inicial)")
        print("0 - Voltar")
        escolha = input("Escolha: ").strip()

        if escolha == "1":
            novo = ask("Novo diretório de ferramentas", cfg["tools_dir"])
            cfg["tools_dir"] = str(Path(novo).expanduser().resolve())
            Path(cfg["tools_dir"]).mkdir(parents=True, exist_ok=True)
            save_config(cfg)
        elif escolha == "2":
            cfg["github_sync"] = ask_yes_no("Sincronizar com o GitHub?", default=cfg["github_sync"])
            if cfg["github_sync"] and not cfg["github_user"]:
                cfg["github_user"] = ask("Usuário/organização do GitHub")
                cfg["repo_name"] = ask("Nome do repositório", "Tools")
                setup_git_repo(cfg, repo_exists=ask_yes_no("O repositório já existe?", default=True))
            save_config(cfg)
        elif escolha == "3":
            m = ask("Método (ssh/https)", cfg["auth_method"])
            cfg["auth_method"] = "https" if m.lower().startswith("h") else "ssh"
            if (Path(cfg["tools_dir"]) / ".git").exists():
                run_git(["remote", "set-url", "origin", remote_url(cfg)], cfg["tools_dir"])
            save_config(cfg)
        elif escolha == "4":
            cfg["github_user"] = ask("Usuário/organização", cfg["github_user"])
            cfg["repo_name"] = ask("Repositório", cfg["repo_name"])
            if (Path(cfg["tools_dir"]) / ".git").exists():
                run_git(["remote", "set-url", "origin", remote_url(cfg)], cfg["tools_dir"])
            save_config(cfg)
        elif escolha == "5":
            cfg["branch"] = ask("Branch principal", cfg["branch"])
            save_config(cfg)
        elif escolha == "6":
            return first_run_setup()
        elif escolha == "0":
            return cfg
        else:
            print("❌ Opção inválida.")


# ---------------------------------------------------------------------------
# Menu principal
# ---------------------------------------------------------------------------

def main():
    cfg = load_config()
    if cfg is None or not cfg.get("tools_dir"):
        cfg = first_run_setup()

    while True:
        print("\n=== AvocTools - Gerenciador de Ferramentas ===")
        print("1 - Adicionar nova ferramenta")
        print("2 - Remover ferramenta existente")
        print("3 - Listar ferramentas")
        print("4 - Buscar ferramenta")
        print("5 - Sincronizar repositório")
        print("6 - Configuração")
        print("0 - Sair")
        escolha = input("Escolha uma opção: ").strip()

        if escolha == "1":
            clear(); adicionar_ferramenta(cfg)
        elif escolha == "2":
            clear(); remover_ferramenta(cfg)
        elif escolha == "3":
            clear(); listar_ferramentas(cfg)
        elif escolha == "4":
            clear(); buscar_ferramenta(cfg)
        elif escolha == "5":
            clear(); sincronizar_menu(cfg)
        elif escolha == "6":
            clear(); cfg = menu_configuracao(cfg)
        elif escolha == "0":
            print("Saindo...")
            break
        else:
            print("❌ Opção inválida.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrompido. Até logo!")
        sys.exit(130)
