import datetime
from datetime import datetime, timedelta, timezone
import os
import re
import time
import requests

# CONFIGURAÇÕES DE API E BDR (CARREGADAS VIA VARIÁVEIS DE AMBIENTE)

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
JOEL_OWNER_ID = os.getenv("JOEL_OWNER_ID", "90392770")

# HEADERS DE AUTENTICAÇÃO
HEADERS_HUBSPOT = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

HEADERS_APOLLO = {
    "Cache-Control": "no-cache",
    "Content-Type": "application/json",
    "x-api-key": APOLLO_API_KEY,
}


# 1. CRIAÇÃO DA CADÊNCIA DE TAREFAS NO HUBSPOT
def criar_cadencia_tarefas_hubspot(
    contact_id, bdr_id, bdr_name, nome_lead, empresa_lead
):
    """Cria uma lista de 8 tarefas categorizadas por tipo no HubSpot utilizando hs_timestamp."""
    url = "https://api.hubapi.com/crm/v3/objects/tasks"

    tarefas = [
        {
            "titulo": "Conexão - LinkedIn",
            "dias_prazo": 1,
            "tipo": "TODO",
            "status": "NOT_STARTED",
        },
        {
            "titulo": "Primeiro E-mail (Problema)",
            "dias_prazo": 1,
            "tipo": "EMAIL",
            "status": "NOT_STARTED",  # Status NOT_STARTED para envio manual
        },
        {
            "titulo": "Primeira Ligação - Referencia o E-mail",
            "dias_prazo": 3,
            "tipo": "CALL",
            "status": "NOT_STARTED",
        },
        {
            "titulo": "Segundo E-mail - Prova Social ou Dado de Mercado",
            "dias_prazo": 5,
            "tipo": "EMAIL",
            "status": "NOT_STARTED",
        },
        {
            "titulo": (
                "Linkedin - Comentário ou Mensagem - Nunca Pitch Direto"
            ),
            "dias_prazo": 8,
            "tipo": "TODO",
            "status": "NOT_STARTED",
        },
        {
            "titulo": "Segunda Ligação - Ângulo Diferente",
            "dias_prazo": 11,
            "tipo": "CALL",
            "status": "NOT_STARTED",
        },
        {
            "titulo": "WhatsApp - Só com Sinal Prévio",
            "dias_prazo": 15,
            "tipo": "TODO",
            "status": "NOT_STARTED",
        },
        {
            "titulo": "Break Up E-mail - O Mais Poderoso da Cadência",
            "dias_prazo": 19,
            "tipo": "EMAIL",
            "status": "NOT_STARTED",
        },
    ]

    agora_utc = datetime.now(timezone.utc)

    for t in tarefas:
        data_vencimento = agora_utc + timedelta(days=t["dias_prazo"])
        vencimento_iso = data_vencimento.strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "properties": {
                "hs_task_subject": f"{t['titulo']} | {nome_lead} ({empresa_lead})",
                "hs_task_status": t.get("status", "NOT_STARTED"),
                "hs_task_type": t["tipo"],
                "hubspot_owner_id": str(bdr_id),
                "hs_timestamp": vencimento_iso,
            },
            "associations": [
                {
                    "to": {"id": str(contact_id)},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 204,
                        }
                    ],
                }
            ],
        }

        try:
            res = requests.post(url, headers=HEADERS_HUBSPOT, json=payload)
            if res.status_code == 201:
                print(
                    f"Tarefa '{t['titulo']}' [{t['tipo']}] [{t['status']}]"
                    f" criada com sucesso para {bdr_name}!"
                )
            else:
                print(
                    f"Erro ao criar tarefa '{t['titulo']}' [{res.status_code}]:"
                    f" {res.text}"
                )
        except Exception as e:
            print(f"Falha na conexão com a API de Tarefas: {e}")


# 2. INTEGRAÇÃO HUBSPOT
def buscar_empresas_buyer_intent_hubspot(limite=20):
    """Busca no HubSpot apenas empresas marcadas com Buyer Intent criadas no dia de hoje."""
    url = "https://api.hubapi.com/crm/v3/objects/companies/search"

    # Calcula o timestamp referente a 00:00:00 de HOJE em UTC
    inicio_hoje_utc = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    timestamp_inicio_hoje_ms = str(int(inicio_hoje_utc.timestamp() * 1000))

    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "lifecyclestage",
                        "operator": "EQ",
                        "value": "lead",
                    },
                    {
                        "propertyName": "createdate",  # Altere para "hs_lastmodifieddate" se preferir empresas modificadas hoje
                        "operator": "GTE",
                        "value": timestamp_inicio_hoje_ms,
                    },
                ]
            }
        ],
        "properties": ["name", "domain", "numberofemployees"],
        "limit": limite,
    }
    try:
        res = requests.post(url, headers=HEADERS_HUBSPOT, json=payload)
        if res.status_code == 200:
            return res.json().get("results", [])
        print(
            f"Erro ao buscar empresas no HubSpot [{res.status_code}]: {res.text}"
        )
    except Exception as e:
        print(f"Falha na requisição de Buyer Intent no HubSpot: {e}")
    return []


def contar_contatos_associados_empresa(company_id):
    """Verifica a quantidade de contatos já vinculados à empresa no HubSpot."""
    url = f"https://api.hubapi.com/crm/v3/objects/companies/{company_id}/associations/contacts"
    try:
        res = requests.get(url, headers=HEADERS_HUBSPOT)
        if res.status_code == 200:
            results = res.json().get("results", [])
            return len(results)
    except Exception as e:
        print(f"Erro ao verificar contatos associados da empresa {company_id}: {e}")
    return 0


def obter_ou_criar_contato_hubspot(
    email, nome="", sobrenome="", cargo="", linkedin=""
):
    """Busca o contato ou cria um novo mapeando o LinkedIn para ambas as propriedades do CRM."""
    url_search = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    payload_search = {
        "filterGroups": [
            {
                "filters": [
                    {"propertyName": "email", "operator": "EQ", "value": email}
                ]
            }
        ]
    }
    res = requests.post(
        url_search, headers=HEADERS_HUBSPOT, json=payload_search
    )
    if res.status_code == 200 and res.json().get("results"):
        return res.json()["results"][0]["id"]

    url_create = "https://api.hubapi.com/crm/v3/objects/contacts"
    url_linkedin = str(linkedin) if linkedin else ""

    payload_create = {
        "properties": {
            "email": str(email),
            "firstname": str(nome),
            "lastname": str(sobrenome),
            "jobtitle": str(cargo),
            "hs_linkedin_url": url_linkedin,
            "linkedinbio": url_linkedin,
            "hubspot_owner_id": JOEL_OWNER_ID,
        }
    }
    res_c = requests.post(
        url_create, headers=HEADERS_HUBSPOT, json=payload_create
    )
    if res_c.status_code == 201:
        return res_c.json().get("id")
    return None


def associar_contato_empresa(contact_id, company_id):
    """Associa o Contato à Empresa no CRM."""
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}/associations/companies/{company_id}/contact_to_company"
    res = requests.put(url, headers=HEADERS_HUBSPOT)
    return res.status_code in [200, 201]


# 3. INTEGRAÇÃO APOLLO.IO (GLOBAL - SEM RESTRIÇÃO DE PAÍS)
def revelar_email_apollo(person_id):
    """Revela e-mail e traz dados completos do perfil no Apollo."""
    url = "https://api.apollo.io/v1/people/match"
    payload = {
        "api_key": APOLLO_API_KEY,
        "id": person_id,
        "reveal_personal_emails": False,
    }
    try:
        res = requests.post(url, headers=HEADERS_APOLLO, json=payload)
        if res.status_code == 200:
            return res.json().get("person") or {}
    except Exception as e:
        print(f"Erro ao tentar revelar e-mail no Apollo: {e}")
    return {}


def buscar_contatos_rh_global_apollo(domain_empresa, limite=3):
    """Busca até 3 contatos de RH globalmente para o domínio especificado."""
    url = "https://api.apollo.io/v1/mixed_people/api_search"
    payload = {
        "api_key": APOLLO_API_KEY,
        "q_organization_domains": domain_empresa,
        "person_titles": [
            "RH",
            "HR",
            "Recrutamento",
            "Recruiter",
            "Talent Acquisition",
            "Recursos Humanos",
            "Gente e Gestão",
            "Gente e Gestao",
            "Head de RH",
            "Diretor de RH",
            "Gerente de RH",
            "HRBP",
            "VP of People",
            "Head of People",
            "Chief People Officer",
        ],
        "page": 1,
        "per_page": 50,
    }
    contatos_validos = []

    try:
        res = requests.post(url, headers=HEADERS_APOLLO, json=payload)
        if res.status_code == 200:
            dados = res.json()
            pessoas = dados.get("people") or []

            for p in pessoas:
                if not p:
                    continue

                email = p.get("email")
                linkedin = p.get("linkedin_url")

                if (not email or not linkedin) and p.get("id"):
                    detalhes = revelar_email_apollo(p.get("id"))
                    if detalhes:
                        email = email or detalhes.get("email")
                        linkedin = linkedin or detalhes.get("linkedin_url")

                if email and "@" in email:
                    contatos_validos.append(
                        {
                            "email": email,
                            "nome": p.get("first_name", ""),
                            "sobrenome": p.get("last_name", ""),
                            "cargo": p.get("title", ""),
                            "linkedin": linkedin or "",
                        }
                    )
                if len(contatos_validos) >= limite:
                    break
        else:
            print(
                f"Erro na resposta do Apollo para {domain_empresa} [{res.status_code}]: {res.text}"
            )
    except Exception as e:
        print(f"Falha na requisição ao Apollo para {domain_empresa}: {e}")

    return contatos_validos


# 4. ORQUESTRADOR PRINCIPAL (BUYER INTENT WORKFLOW)
def processar_buyer_intent_workflow():
    print("Iniciando processamento de empresas Buyer Intent do dia...\n")

    # 1. Busca empresas no HubSpot que apresentaram Buyer Intent hoje
    empresas_buyer_intent = buscar_empresas_buyer_intent_hubspot(limite=20)

    if not empresas_buyer_intent:
        print("Nenhuma empresa de Buyer Intent criada hoje encontrada no HubSpot.")
        return

    processadas = 0

    for emp in empresas_buyer_intent:
        company_id = emp.get("id")
        props = emp.get("properties", {})
        nome_empresa = props.get("name") or "Empresa"
        dominio = props.get("domain")

        if dominio:
            dominio = (
                dominio.replace("https://", "")
                .replace("http://", "")
                .replace("www.", "")
                .split("/")[0]
            )

        if not dominio:
            print(f"Empresa '{nome_empresa}' (ID: {company_id}) ignorada por falta de domínio.")
            continue

        print(f"Analisando Buyer Intent de hoje: {nome_empresa} - Domínio: {dominio}")

        # REGRA DE VERIFICAÇÃO: Se já possuir 3 ou mais contatos vinculados, pula a empresa
        qtd_existente = contar_contatos_associados_empresa(company_id)
        if qtd_existente >= 3:
            print(f"Pulado: '{nome_empresa}' já possui {qtd_existente} contatos associados no HubSpot.\n")
            continue

        # 2. Busca contatos de RH necessários para completar até 3 no Apollo
        limite_busca = 3 - qtd_existente
        contatos_rh = buscar_contatos_rh_global_apollo(dominio, limite=limite_busca)

        if not contatos_rh:
            print(f"Nenhum contato de RH encontrado no Apollo para '{nome_empresa}'.\n")
            continue

        # 3. Processa cada contato encontrado, associa ao CRM e cria a cadência de tarefas
        for c in contatos_rh:
            nome_contato = c["nome"] or "Olá"

            contact_id = obter_ou_criar_contato_hubspot(
                email=c["email"],
                nome=c["nome"],
                sobrenome=c["sobrenome"],
                cargo=c["cargo"],
                linkedin=c["linkedin"],
            )

            if contact_id:
                associar_contato_empresa(contact_id, company_id)
                print(f"Contato {c['email']} criado/encontrado e associado no HubSpot!")

                # Cria a cadência de 8 tarefas para o contato no HubSpot
                criar_cadencia_tarefas_hubspot(
                    contact_id=contact_id,
                    bdr_id=JOEL_OWNER_ID,
                    bdr_name="Joel",
                    nome_lead=nome_contato,
                    empresa_lead=nome_empresa,
                )

        processadas += 1
        print(f"Empresa '{nome_empresa}' concluída com sucesso.\n")
        time.sleep(0.5)

    print(f"Finalizado! {processadas} empresas de Buyer Intent de hoje foram processadas com sucesso.")


# EXECUÇÃO
if __name__ == "__main__":
    processar_buyer_intent_workflow()