import datetime
from datetime import datetime, timedelta, timezone
import os
import random  # Importado para sorteio de páginas aleatórias
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests

# CONFIGURAÇÕES DE API, BDR E SMTP (CARREGADAS VIA VARIÁVEIS DE AMBIENTE)

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
JOEL_OWNER_ID = os.getenv("JOEL_OWNER_ID", "90392770")

# Configurações do E-mail do Joel (SMTP)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
JOEL_EMAIL_ADDRESS = os.getenv("JOEL_EMAIL_ADDRESS", "joel@startrh.io")
JOEL_EMAIL_PASSWORD = os.getenv("JOEL_EMAIL_PASSWORD")

# ACESSO AO HUBSPOT
HEADERS_HUBSPOT = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

HEADERS_APOLLO = {
    "Cache-Control": "no-cache",
    "Content-Type": "application/json",
    "x-api-key": APOLLO_API_KEY,
}


# TEMPLATE DO E-MAIL EM HTML + ASSINATURA

EMAIL_ASSUNTO = (
    "{empresa} + START RH - Parceria Estratégica em Recrutamento e Seleção"
)
EMAIL_CORPO_HTML = """
<p>Olá {nome}, tudo bem?</p>

<p>Sou o Joel, da Start RH. Aqui apoiamos empresas nos processos de recrutamento e seleção: temos times especializados em vagas operacionais, executivas, estágio e PCD (fechamos mais de 90 vagas inclusivas no último mês).</p>

<p>Quero ter uma conversa rápida com quem cuida desse setor na <strong>{empresa}</strong>.</p>

<p>É com você que eu falo? Se for, me passa um dia e horário para conversarmos. Em 15 minutos te apresento como podemos ajudar: <a href="https://meetings.hubspot.com/joel-oliveira?uuid=3dae6946-5a35-483c-a5ce-f14e4c42ae76" style="color: #F5A623; font-weight: bold;">(Minha Agenda)</a>.</p>

<p>Se não for, você consegue me passar o contato de quem cuida dessa parte?</p>

<p>Aguardo o retorno.<br>Att,</p>

<!-- INÍCIO ASSINATURA START RH -->
<table cellpadding="0" cellspacing="0" border="0" style="font-family: Arial, sans-serif; font-size: 13px; color: #333333; margin-top: 16px;">
  <tbody>
    <tr>
      <td style="padding-right: 16px; border-right: 2px solid #e0e0e0; vertical-align: middle; text-align: center;">
        <a href="https://startrh.io" target="_blank">
          <img src="https://startrh.io/wp-content/uploads/2025/04/startrh-logo.png" alt="Start RH" width="100" style="display: block; margin: 0 auto;">
        </a>
      </td>
      <td style="padding-left: 16px; vertical-align: middle;">
        <p style="margin: 0; font-weight: bold; font-size: 14px; color: #1a1a1a;">Joel Costa</p>
        <p style="margin: 2px 0 6px 0; font-weight: bold; color: #555555;">Comercial, Start RH</p>
        <p style="margin: 0 0 4px 0; color: #333333;">
          11 92552-5691 &nbsp;|&nbsp;
          <a href="https://startrh.io" target="_blank" style="color: #F5A623; text-decoration: none;">startrh.io</a>
          &nbsp;|&nbsp;
          <a href="mailto:joel@startrh.io" style="color: #F5A623; text-decoration: none;">joel@startrh.io</a>
        </p>
        <p style="margin: 0 0 8px 0; color: #333333;">Rua Niterói, 400</p>
        <table cellpadding="0" cellspacing="0" border="0">
          <tbody>
            <tr>
              <td style="padding-right: 6px;">
                <a href="https://www.instagram.com/startrh.recrutamento/" target="_blank">
                  <img src="https://cdn-icons-png.flaticon.com/32/2111/2111463.png" alt="Instagram" width="28" height="28" style="display: block; border-radius: 6px;">
                </a>
              </td>
              <td>
                <a href="https://www.linkedin.com/company/startrecrutamento/" target="_blank">
                  <img src="https://cdn-icons-png.flaticon.com/32/174/174857.png" alt="LinkedIn" width="28" height="28" style="display: block; border-radius: 6px;">
                </a>
              </td>
            </tr>
          </tbody>
        </table>
      </td>
    </tr>
    <tr>
      <td colspan="2" style="padding-top: 12px; border-top: 1px solid #e0e0e0; font-size: 10px; color: #999999;">
        IMPORTANT: The contents of this email and any attachments are confidential. They are intended for the named recipient(s) only and should not be distributed to anyone else. If you are not the intended recipient, please notify the sender immediately and destroy this email. Any views or opinions expressed are those of the author only.
      </td>
    </tr>
  </tbody>
</table>
"""


# 1. DISPARO DE E-MAIL (SMTP JOEL - ENVIO REAL ATIVO)
def disparar_email_joel(email_destino, nome_contato, nome_empresa):
    """Envia o e-mail diretamente da caixa de entrada do Joel via SMTP."""
    try:
        assunto = EMAIL_ASSUNTO.format(nome=nome_contato, empresa=nome_empresa)
        corpo = EMAIL_CORPO_HTML.format(nome=nome_contato, empresa=nome_empresa)

        msg = MIMEMultipart()
        msg["From"] = f"Joel <{JOEL_EMAIL_ADDRESS}>"
        msg["To"] = email_destino
        msg["Subject"] = assunto
        msg.attach(MIMEText(corpo, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(JOEL_EMAIL_ADDRESS, JOEL_EMAIL_PASSWORD)
            server.send_message(msg)

        print(f"E-mail enviado com sucesso para {email_destino}!")
        return True, assunto, corpo
    except Exception as e:
        print(f"Falha ao enviar e-mail para {email_destino}: {e}")
        return False, None, None


# 2. CRIAÇÃO DA CADÊNCIA DE TAREFAS NO HUBSPOT
def criar_cadencia_tarefas_hubspot(
    contact_id, bdr_id, bdr_name, nome_lead, empresa_lead
):
    """Cria uma lista de tarefas categorizadas por tipo e status no HubSpot utilizando hs_timestamp."""
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
            "status": "COMPLETED",
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


# 3. INTEGRAÇÃO HUBSPOT
def empresa_existe_no_hubspot(dominio):
    """Pula empresas que já existam no CRM (busca por domínio)."""
    if not dominio:
        return False

    url = "https://api.hubapi.com/crm/v3/objects/companies/search"
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {"propertyName": "domain", "operator": "EQ", "value": dominio}
                ]
            }
        ]
    }
    res = requests.post(url, headers=HEADERS_HUBSPOT, json=payload)
    if res.status_code == 200:
        return len(res.json().get("results", [])) > 0
    return False


def criar_empresa_hubspot(nome, dominio, num_funcionarios):
    """Cria a empresa atribuída ao Joel."""
    url = "https://api.hubapi.com/crm/v3/objects/companies"
    payload = {
        "properties": {
            "name": nome,
            "domain": dominio,
            "numberofemployees": str(num_funcionarios) if num_funcionarios else "",
            "hubspot_owner_id": JOEL_OWNER_ID,
            "lifecyclestage": "lead",
        }
    }
    res = requests.post(url, headers=HEADERS_HUBSPOT, json=payload)
    if res.status_code == 201:
        return res.json().get("id")
    print(f"Erro ao criar empresa no HubSpot: {res.status_code} - {res.text}")
    return None


def obter_ou_criar_contato_hubspot(
    email, nome="", sobrenome="", cargo="", linkedin=""
):
    """Busca o contato ou cria um novo mapeando o LinkedIn para ambas as propriedades do HubSpot."""
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


def registrar_email_enviado_no_hubspot(contact_id, assunto, corpo_html):
    """Registra o e-mail na linha do tempo do Contato no HubSpot."""
    url = "https://api.hubapi.com/crm/v3/objects/emails"
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    payload = {
        "properties": {
            "hs_email_subject": assunto,
            "hs_email_text": corpo_html,
            "hs_email_status": "SENT",
            "hs_timestamp": timestamp_ms,
            "hubspot_owner_id": JOEL_OWNER_ID,
        },
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": 198,
                    }
                ],
            }
        ],
    }
    requests.post(url, headers=HEADERS_HUBSPOT, json=payload)


# 4. INTEGRAÇÃO APOLLO.IO
def buscar_empresas_apollo(pagina=1):
    """Busca empresas com no mínimo 50 funcionários no Apollo."""
    url = "https://api.apollo.io/v1/organizations/search"
    payload = {
        "api_key": APOLLO_API_KEY,
        "page": pagina,
        "per_page": 25,
        "organization_num_employees_ranges": [
            "50,100",
            "100,200",
            "200,500",
            "500,1000",
            "1000,5000",
            "5000,10000",
            "10000,100000",
        ],
    }
    res = requests.post(url, headers=HEADERS_APOLLO, json=payload)
    if res.status_code == 200:
        return res.json().get("organizations", [])
    print(f"Erro ao buscar no Apollo: {res.status_code} - {res.text}")
    return []


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


def buscar_contatos_empresa_apollo(domain_empresa, limite=3):
    """Busca contatos de RH no Brasil e extrai o LinkedIn URL corretamente."""
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
        "person_locations": ["Brazil"],
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

                # Se e-mail ou dados do perfil estiverem incompletos, faz o enrich/reveal
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


# 5. ORQUESTRADOR PRINCIPAL
def executar_automacao_apollo(limite_lote=10):
    empresas_criadas = 0

    # Sorteia uma página inicial aleatória entre 1 e 100 a cada execução
    pagina_atual = random.randint(1, 100)

    print(
        f"Iniciando automação Apollo -> HubSpot (Página inicial sorteada: {pagina_atual} | Meta: {limite_lote} novas empresas para o Joel)...\n"
    )

    while empresas_criadas < limite_lote:
        empresas_apollo = buscar_empresas_apollo(pagina=pagina_atual)

        if not empresas_apollo:
            print(f"Nenhuma outra empresa encontrada na página {pagina_atual} do Apollo.")
            break

        for emp in empresas_apollo:
            if empresas_criadas >= limite_lote:
                break

            nome = emp.get("name")
            dominio = emp.get("primary_domain") or emp.get("website_url")
            num_func = emp.get("estimated_num_employees", 0)

            if dominio:
                dominio = (
                    dominio.replace("https://", "")
                    .replace("http://", "")
                    .replace("www.", "")
                    .split("/")[0]
                )

            if not dominio:
                continue

            print(f"Analisando: {nome} ({num_func} func.) - {dominio}")

            # REGRA 1: Pula empresas existentes no HubSpot
            if empresa_existe_no_hubspot(dominio):
                print(f"Pulado: '{nome}' já existe no HubSpot.")
                continue

            # REGRA 2: Puxa exatamente até 3 contatos de RH no Brasil
            contatos = buscar_contatos_empresa_apollo(dominio, limite=3)
            if not contatos:
                print(
                    f"Pulado: Nenhum contato de RH no Brasil com e-mail encontrado para '{nome}'."
                )
                continue

            # 1. Cria a empresa para o Joel
            company_id = criar_empresa_hubspot(nome, dominio, num_func)
            if not company_id:
                continue

            print(f"Empresa '{nome}' criada no HubSpot (ID: {company_id})")

            # 2. Processa os contatos, vincula, envia e-mail, registra no CRM e agenda a cadência
            for c in contatos:
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

                    enviou, assunto, corpo = disparar_email_joel(
                        c["email"], nome_contato, nome
                    )

                    if enviou:
                        registrar_email_enviado_no_hubspot(
                            contact_id, assunto, corpo
                        )
                        print(
                            f"Contato {c['email']} associado + E-mail disparado e gravado no HubSpot!"
                        )
                    else:
                        print(f"Contato {c['email']} associado!")

                    # Criação da cadência de tarefas para o contato
                    criar_cadencia_tarefas_hubspot(
                        contact_id=contact_id,
                        bdr_id=JOEL_OWNER_ID,
                        bdr_name="Joel",
                        nome_lead=nome_contato,
                        empresa_lead=nome,
                    )

            empresas_criadas += 1
            print(f"Lote: {empresas_criadas}/{limite_lote} concluídas.\n")

            time.sleep(0.5)

        pagina_atual += 1

    print(
        f"Finalizado! {empresas_criadas} novas empresas foram integradas para o Joel com contatos de RH e seus perfis de LinkedIn."
    )


# EXECUÇÃO
if __name__ == "__main__":
    executar_automacao_apollo(limite_lote=10)
