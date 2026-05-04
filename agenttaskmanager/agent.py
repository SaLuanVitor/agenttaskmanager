from google.adk.agents.llm_agent import Agent
from trello import TrelloClient
from dotenv import load_dotenv
from datetime import datetime
from typing import Any, Callable
import os
import re
import logging
import requests

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# Configurações
# =========================

TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_API_SECRET = os.getenv("TRELLO_API_SECRET")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")

BOARD_NAME = "Minhas Atividades"
DEFAULT_LIST_NAME = "A FAZER"
REQUEST_TIMEOUT_SECONDS = 15
MAX_TEXT_LENGTH = 500
MAX_TASKS_RETURNED = 50

STATUS_LISTS = {
    "a fazer": "A FAZER",
    "fazer": "A FAZER",
    "pendente": "A FAZER",
    "pendentes": "A FAZER",

    "em andamento": "EM ANDAMENTO",
    "andamento": "EM ANDAMENTO",
    "fazendo": "EM ANDAMENTO",

    "concluída": "CONCLUÍDAS",
    "concluídas": "CONCLUÍDAS",
    "concluida": "CONCLUÍDAS",
    "concluidas": "CONCLUÍDAS",
    "concluído": "CONCLUÍDAS",
    "concluido": "CONCLUÍDAS",
    "finalizada": "CONCLUÍDAS",
    "finalizado": "CONCLUÍDAS",
}


# =========================
# Respostas padronizadas
# =========================

def success_response(message: str, **data):
    return {
        "success": True,
        "message": message,
        **data
    }


def error_response(message: str, **data):
    return {
        "success": False,
        "message": message,
        **data
    }


def run_safely(action: Callable[[], dict], fallback_message: str):
    """
    Centraliza tratamento de exceções das tools.

    Evita que erros internos quebrem o agente e também evita expor stack trace,
    credenciais ou detalhes sensíveis ao usuário.
    """

    try:
        return action()
    except requests.Timeout:
        logger.exception("Timeout ao acessar Trello.")
        return error_response("O Trello demorou para responder. Tente novamente em instantes.")
    except requests.RequestException:
        logger.exception("Erro de comunicação com Trello.")
        return error_response("Não consegui me comunicar com o Trello agora.")
    except ValueError as exc:
        return error_response(str(exc))
    except Exception:
        logger.exception("Erro inesperado na ferramenta.")
        return error_response(fallback_message)


# =========================
# Validações e sanitização
# =========================

def normalize_text(value: str) -> str:
    return value.strip().lower() if value else ""


def sanitize_text(value: str, field_name: str, required: bool = True, max_length: int = MAX_TEXT_LENGTH) -> str:
    """
    Sanitiza textos vindos do usuário.

    Não existe SQL injection aqui porque não há SQL, mas isso ajuda contra:
    - entradas vazias;
    - textos gigantes;
    - caracteres de controle;
    - payloads maliciosos enviados para API externa.
    """

    if value is None:
        value = ""

    value = str(value).strip()

    # Remove caracteres de controle invisíveis
    value = re.sub(r"[\x00-\x1f\x7f]", "", value)

    if required and not value:
        raise ValueError(f"O campo '{field_name}' é obrigatório.")

    if len(value) > max_length:
        raise ValueError(f"O campo '{field_name}' excedeu o limite de {max_length} caracteres.")

    return value


def normalize_due_date(due_date: str) -> str:
    """
    Valida e normaliza data para formato ISO aceito pelo Trello.

    Aceita:
    - 2026-05-03
    - 2026-05-03T23:59:00
    - 2026-05-03 00:00:00+00:00
    """

    due_date = sanitize_text(due_date, "due_date", required=True, max_length=40)

    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", due_date):
            parsed = datetime.fromisoformat(f"{due_date}T23:59:00")
        else:
            parsed = datetime.fromisoformat(due_date.replace("Z", "+00:00"))

        return parsed.isoformat()
    except ValueError:
        raise ValueError(
            "Data de vencimento inválida. Use formato ISO, exemplo: 2026-05-03T23:59:00."
        )


def get_status_list_name(status: str):
    status = sanitize_text(status, "status", required=True, max_length=50)
    return STATUS_LISTS.get(normalize_text(status))


def validate_credentials():
    if not TRELLO_API_KEY or not TRELLO_TOKEN:
        raise ValueError("Credenciais do Trello não configuradas no .env.")


# =========================
# Cliente Trello
# =========================

def get_trello_client():
    validate_credentials()

    return TrelloClient(
        api_key=TRELLO_API_KEY,
        api_secret=TRELLO_API_SECRET,
        token=TRELLO_TOKEN
    )


def trello_api_request(method: str, endpoint: str, payload: dict | None = None):
    """
    Centraliza chamadas diretas à API REST do Trello.

    Usa params para que o requests faça o encoding correto dos dados,
    evitando concatenação manual de entrada do usuário na URL.
    """

    validate_credentials()

    url = f"https://api.trello.com/1/{endpoint.lstrip('/')}"
    params = {
        "key": TRELLO_API_KEY,
        "token": TRELLO_TOKEN
    }

    if payload:
        params.update(payload)

    response = requests.request(
        method=method.upper(),
        url=url,
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS
    )

    if response.status_code not in (200, 201):
        logger.warning(
            "Erro Trello API. Status=%s Endpoint=%s Body=%s",
            response.status_code,
            endpoint,
            response.text[:300]
        )

        return error_response(
            "O Trello recusou a operação. Verifique permissões, token e acesso ao quadro.",
            status_code=response.status_code
        )

    if response.text:
        return success_response("Operação realizada com sucesso.", data=response.json())

    return success_response("Operação realizada com sucesso.")


# =========================
# Helpers de board/list/card
# =========================

def get_main_board():
    client = get_trello_client()
    boards = client.list_boards()

    board = next(
        (item for item in boards if item.name == BOARD_NAME),
        None
    )

    if not board:
        raise ValueError(f"Board '{BOARD_NAME}' não encontrado.")

    return board


def get_board_lists(board):
    return board.list_lists()


def get_list_by_name(board, list_name: str):
    list_name = sanitize_text(list_name, "list_name", required=True, max_length=80)
    lists = get_board_lists(board)

    return next(
        (
            trello_list
            for trello_list in lists
            if trello_list.name.upper() == list_name.upper()
        ),
        None
    )


def get_required_list(board, list_name: str):
    trello_list = get_list_by_name(board, list_name)

    if not trello_list:
        raise ValueError(f"Lista '{list_name}' não encontrada no Trello.")

    return trello_list


def card_to_dict(card, status: str):
    """
    Retorna apenas os campos necessários para reduzir consumo de tokens.
    """

    return {
        "name": card.name,
        "description": card.description,
        "status": status,
        "due_date": str(card.due_date) if card.due_date else None,
        "url": card.url
    }


def find_card_by_name(task_name: str):
    """
    Busca um card por nome exato dentro do board configurado.

    Usa busca exata para evitar mover, alterar ou remover tarefa errada.
    """

    task_name = sanitize_text(task_name, "task_name", required=True, max_length=120)

    board = get_main_board()
    task_name_normalized = normalize_text(task_name)
    matches = []

    for trello_list in get_board_lists(board):
        for card in trello_list.list_cards():
            if normalize_text(card.name) == task_name_normalized:
                matches.append({
                    "board": board,
                    "list": trello_list,
                    "card": card
                })

    if not matches:
        raise ValueError(f"Tarefa '{task_name}' não encontrada.")

    if len(matches) > 1:
        raise ValueError(
            f"Existe mais de uma tarefa chamada '{task_name}'. Informe um nome mais específico."
        )

    return matches[0]


# =========================
# Tools do agente
# =========================

def get_temporal_context():
    """
    Retorna data e hora atual para o agente usar em tarefas com vencimento.
    """

    def action():
        now = datetime.now()

        return success_response(
            "Contexto temporal obtido com sucesso.",
            current_datetime=now.strftime("%Y-%m-%d %H:%M:%S"),
            current_date=now.strftime("%Y-%m-%d"),
            current_date_br=now.strftime("%d/%m/%Y"),
            current_time=now.strftime("%H:%M:%S")
        )

    return run_safely(action, "Não consegui obter a data e hora atual.")


def add_task_to_trello(task_name: str, task_description: str, due_date: str):
    """
    Cria uma tarefa no Trello na lista 'A FAZER'.
    """

    def action():
        safe_name = sanitize_text(task_name, "task_name", required=True, max_length=120)
        safe_description = sanitize_text(task_description, "task_description", required=False, max_length=500)
        safe_due_date = normalize_due_date(due_date)

        board = get_main_board()
        trello_list = get_required_list(board, DEFAULT_LIST_NAME)

        card = trello_list.add_card(
            name=safe_name,
            desc=safe_description,
            due=safe_due_date
        )

        return success_response(
            "Tarefa criada com sucesso.",
            task=card_to_dict(card, trello_list.name)
        )

    return run_safely(action, "Não consegui criar a tarefa no Trello.")


def list_tasks(status: str = "todas", max_items: int = MAX_TASKS_RETURNED):
    """
    Lista tarefas do Trello.

    Parâmetros:
    - status: todas, a fazer, em andamento ou concluídas.
    - max_items: limite máximo de tarefas retornadas.
    """

    def action():
        safe_status = sanitize_text(status, "status", required=True, max_length=50)
        max_items_safe = max(1, min(int(max_items), MAX_TASKS_RETURNED))

        board = get_main_board()
        lists = get_board_lists(board)

        if normalize_text(safe_status) == "todas":
            selected_lists = lists
        else:
            list_name = get_status_list_name(safe_status)

            if not list_name:
                raise ValueError("Status inválido. Use: todas, a fazer, em andamento ou concluídas.")

            selected_lists = [get_required_list(board, list_name)]

        tasks = []

        for trello_list in selected_lists:
            for card in trello_list.list_cards():
                tasks.append(card_to_dict(card, trello_list.name))

                if len(tasks) >= max_items_safe:
                    return success_response(
                        "Tarefas listadas com sucesso.",
                        total_returned=len(tasks),
                        truncated=True,
                        data=tasks
                    )

        return success_response(
            "Tarefas listadas com sucesso.",
            total_returned=len(tasks),
            truncated=False,
            data=tasks
        )

    return run_safely(action, "Não consegui listar as tarefas.")


def move_task(task_name: str, target_status: str):
    """
    Move uma tarefa para outra lista/status.

    Status aceitos:
    - a fazer
    - em andamento
    - concluídas
    """

    def action():
        target_list_name = get_status_list_name(target_status)

        if not target_list_name:
            raise ValueError("Status inválido. Use: a fazer, em andamento ou concluídas.")

        result = find_card_by_name(task_name)

        board = result["board"]
        current_list = result["list"]
        card = result["card"]
        target_list = get_required_list(board, target_list_name)

        if current_list.id == target_list.id:
            return success_response(
                f"A tarefa '{card.name}' já está em '{target_list.name}'.",
                task_name=card.name,
                status=target_list.name
            )

        update_result = trello_api_request(
            method="PUT",
            endpoint=f"cards/{card.id}",
            payload={
                "idList": target_list.id
            }
        )

        if not update_result["success"]:
            return update_result

        return success_response(
            f"Tarefa movida de '{current_list.name}' para '{target_list.name}'.",
            task_name=card.name,
            from_status=current_list.name,
            to_status=target_list.name
        )

    return run_safely(action, "Não consegui mover a tarefa.")


def complete_task(task_name: str):
    """
    Marca uma tarefa como concluída.
    """

    return move_task(task_name, "concluídas")


def remove_task(task_name: str):
    """
    Remove uma tarefa do Trello pelo nome exato.
    """

    def action():
        result = find_card_by_name(task_name)
        card = result["card"]

        delete_result = trello_api_request(
            method="DELETE",
            endpoint=f"cards/{card.id}"
        )

        if not delete_result["success"]:
            return delete_result

        return success_response(
            f"Tarefa '{card.name}' removida com sucesso.",
            task_name=card.name
        )

    return run_safely(action, "Não consegui remover a tarefa.")


def update_task(
    task_name: str,
    new_task_name: str = "",
    new_description: str = "",
    new_due_date: str = ""
):
    """
    Altera nome, descrição ou vencimento de uma tarefa.
    """

    def action():
        result = find_card_by_name(task_name)
        card = result["card"]

        payload = {}

        if new_task_name and new_task_name.strip():
            payload["name"] = sanitize_text(new_task_name, "new_task_name", required=True, max_length=120)

        if new_description and new_description.strip():
            payload["desc"] = sanitize_text(new_description, "new_description", required=False, max_length=500)

        if new_due_date and new_due_date.strip():
            payload["due"] = normalize_due_date(new_due_date)

        if not payload:
            raise ValueError("Nenhuma alteração foi informada.")

        update_result = trello_api_request(
            method="PUT",
            endpoint=f"cards/{card.id}",
            payload=payload
        )

        if not update_result["success"]:
            return update_result

        return success_response(
            "Tarefa atualizada com sucesso.",
            old_task_name=task_name,
            new_task_name=payload.get("name", card.name),
            changed_fields=list(payload.keys())
        )

    return run_safely(action, "Não consegui atualizar a tarefa.")


# =========================
# Agente
# =========================

root_agent = Agent(
    model="gemini-2.5-flash",
    name="root_agent",
    description="Agente de organização de tarefas integrado ao Trello.",
    instruction="""
Você é um assistente pessoal de organização de tarefas integrado ao Trello.

Use linguagem natural, objetiva e amigável.
Não exponha JSON, IDs, tokens, stack traces ou detalhes técnicos ao usuário.

Ferramentas:
- get_temporal_context: obter data/hora atual.
- add_task_to_trello: criar tarefa.
- list_tasks: listar tarefas.
- move_task: mover tarefa entre status.
- complete_task: concluir tarefa.
- remove_task: remover tarefa.
- update_task: alterar nome, descrição ou vencimento.

Regras:
- Ao iniciar, use get_temporal_context e pergunte as tarefas do dia.
- Para criar tarefa, colete nome, descrição e vencimento.
- Para datas relativas como hoje/amanhã, converta para ISO antes de chamar a ferramenta.
- Ao listar tarefas, formate em texto amigável e agrupe por status quando fizer sentido.
- Ao mover, aceite: a fazer, em andamento e concluídas.
- Ao concluir, use complete_task.
- Ao alterar, use update_task.
- Ao remover, use remove_task somente quando o nome da tarefa estiver claro.
- Se a ferramenta retornar erro, explique em linguagem simples.
- Se o horário do vencimento for 00:00:00, mostre apenas a data no formato DD/MM/AAAA.
""",
    tools=[
        get_temporal_context,
        add_task_to_trello,
        list_tasks,
        move_task,
        complete_task,
        remove_task,
        update_task
    ]
)