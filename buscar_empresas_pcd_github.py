import os
import smtplib
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from apify_client import ApifyClient


# CONFIGURAÇÕES E VARIÁVEIS DE AMBIENTE

HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
JOEL_OWNER_ID = os.getenv("JOEL_OWNER_ID", "90392771")

LIMITE_NOVAS_EMPRESAS = 10  # Trava máxima de empresas cadastradas por execução

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
JOEL_EMAIL_ADDRESS = os.getenv("JOEL_EMAIL_ADDRESS", "joel@startrh.io")
JOEL_EMAIL_PASSWORD = os.getenv("JOEL_EMAIL_PASSWORD")

HEADERS_HUBSPOT = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

HEADERS_APOLLO = {
    "Cache-Control": "no-cache",
    "Content-Type": "application/json",
    "x-api-key": APOLLO_API_KEY,
}

apify_client = ApifyClient(APIFY_TOKEN)

# TEMPLATE DE E-MAIL

EMAIL_ASSUNTO = "{empresa} + START RH - Parceria Estratégica em Recrutamento e Seleção"
EMAIL_CORPO_HTML = """
<p>Olá {nome}, tudo bem?</p>

<p>Construir um time realmente inclusivo, com profissionais PCD qualificados, e agora dar conta das exigências da NR-1 tem sido um desafio real para a maioria das empresas. A oferta é escassa e o processo costuma emperrar.</p>

<p>É exatamente isso que resolvemos. Temos um time especializado em recrutamento inclusivo e um amplo banco de talentos PCD em todo o território nacional.</p>

<p>Hoje conduzimos grandes projetos PCD para empresas como Cielo, Porto Seguro, Piracanjuba e Natura. Só no último bimestre, fechamos mais de 90 posições inclusivas.</p>

<p>Gostaria de te mostrar nosso projeto em apenas 15 minutos. Qual o melhor horário para você? Se preferir, é só agendar direto <a href="https://meetings.hubspot.com/joel-oliveira?uuid=3dae6946-5a35-483c-a5ce-f14e4c42ae76" style="color: #F5A623; font-weight: bold;">clicando na minha agenda</a>.</p>

<p>Abraços,</p>

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
      </td>
    </tr>
  </tbody>
</table>
"""

# FUNÇÕES AUXILIARES

def limpar_dominio(url: str) -> str:
    if not url:
        return ""
    d = url.lower().strip()
    d = d.replace("https://", "").replace("http://", "").replace("www.", "")
    return d.split("/")[0]

def disparar_email_joel(email_destino, nome_contato, nome_empresa):
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

def criar_cadencia_tarefas_hubspot(contact_id, bdr_id, bdr_name, nome_lead, empresa_lead):
    url = "https://api.hubapi.com/crm/v3/objects/tasks"
    tarefas = [
        {"titulo": "Conexão - LinkedIn", "dias_prazo": 1, "tipo": "TODO", "status": "NOT_STARTED"},
        {"titulo": "Primeiro E-mail (Problema)", "dias_prazo": 1, "tipo": "EMAIL", "status": "COMPLETED"},
        {"titulo": "Primeira Ligação - Referencia o E-mail", "dias_prazo": 3, "tipo": "CALL", "status": "NOT_STARTED"},
        {"titulo": "Segundo E-mail - Prova Social ou Dado de Mercado", "dias_prazo": 5, "tipo": "EMAIL", "status": "NOT_STARTED"},
        {"titulo": "Linkedin - Comentário ou Mensagem", "dias_prazo": 8, "tipo": "TODO", "status": "NOT_STARTED"},
        {"titulo": "Segunda Ligação - Ângulo Diferente", "dias_prazo": 11, "tipo": "CALL", "status": "NOT_STARTED"},
        {"titulo": "WhatsApp - Só com Sinal Prévio", "dias_prazo": 15, "tipo": "TODO", "status": "NOT_STARTED"},
        {"titulo": "Break Up E-mail", "dias_prazo": 19, "tipo": "EMAIL", "status": "NOT_STARTED"},
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
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 204}],
                }
            ],
        }
        try:
            requests.post(url, headers=HEADERS_HUBSPOT, json=payload)
        except Exception as e:
            print(f"Falha na conexão com a API de Tarefas: {e}")


# INTEGRACAO HUBSPOT (VERIFICAÇÃO E CRIAÇÃO)

def empresa_existe_no_hubspot(dominio):
    """Consulta rápida no CRM para evitar gastar qualquer outro crédito de API."""
    if not dominio:
        return False
    url = "https://api.hubapi.com/crm/v3/objects/companies/search"
    payload = {
        "filterGroups": [
            {"filters": [{"propertyName": "domain", "operator": "EQ", "value": dominio}]}
        ]
    }
    res = requests.post(url, headers=HEADERS_HUBSPOT, json=payload)
    if res.status_code == 200:
        return len(res.json().get("results", [])) > 0
    return False

def criar_empresa_hubspot(nome, dominio, num_vagas_pcd=0):
    url = "https://api.hubapi.com/crm/v3/objects/companies"
    payload = {
        "properties": {
            "name": nome,
            "domain": dominio,
            "description": f"Importado via Apify. Empresa com {num_vagas_pcd} vaga(s) PCD/Inclusiva(s) aberta(s).",
            "hubspot_owner_id": JOEL_OWNER_ID,
            "lifecyclestage": "lead",
        }
    }
    res = requests.post(url, headers=HEADERS_HUBSPOT, json=payload)
    if res.status_code == 201:
        return res.json().get("id")
    print(f"Erro ao criar empresa no HubSpot: {res.status_code} - {res.text}")
    return None

def criar_nota_empresa_hubspot(company_id, texto_nota):
    url = "https://api.hubapi.com/crm/v3/objects/notes"
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    payload = {
        "properties": {
            "hs_note_body": texto_nota,
            "hs_timestamp": timestamp_ms,
            "hubspot_owner_id": JOEL_OWNER_ID,
        },
        "associations": [
            {
                "to": {"id": str(company_id)},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 190}],
            }
        ],
    }
    res = requests.post(url, headers=HEADERS_HUBSPOT, json=payload)
    if res.status_code == 201:
        print("-> [Nota Criada] Observação de Vagas PCD vinculada à empresa no HubSpot!")

def obter_ou_criar_contato_hubspot(email, nome="", sobrenome="", cargo="", linkedin=""):
    url_search = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    payload_search = {
        "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}]
    }
    res = requests.post(url_search, headers=HEADERS_HUBSPOT, json=payload_search)
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
    res_c = requests.post(url_create, headers=HEADERS_HUBSPOT, json=payload_create)
    if res_c.status_code == 201:
        return res_c.json().get("id")
    return None

def associar_contato_empresa(contact_id, company_id):
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}/associations/companies/{company_id}/contact_to_company"
    res = requests.put(url, headers=HEADERS_HUBSPOT)
    return res.status_code in [200, 201]

def registrar_email_enviado_no_hubspot(contact_id, assunto, corpo_html):
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
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 198}],
            }
        ],
    }
    requests.post(url, headers=HEADERS_HUBSPOT, json=payload)


# INTEGRAÇÃO APOLLO.IO

def revelar_email_apollo(person_id):
    url = "https://api.apollo.io/v1/people/match"
    payload = {"api_key": APOLLO_API_KEY, "id": person_id, "reveal_personal_emails": False}
    try:
        res = requests.post(url, headers=HEADERS_APOLLO, json=payload)
        if res.status_code == 200:
            return res.json().get("person") or {}
    except Exception as e:
        print(f"Erro ao revelar e-mail no Apollo: {e}")
    return {}

def buscar_contatos_empresa_apollo(domain_empresa, limite=3):
    url = "https://api.apollo.io/v1/mixed_people/api_search"
    payload = {
        "api_key": APOLLO_API_KEY,
        "q_organization_domains": domain_empresa,
        "person_titles": [
            "RH", "HR", "Recrutamento", "Recruiter", "Talent Acquisition",
            "Recursos Humanos", "Gente e Gestão", "Gente e Gestao",
            "Head de RH", "Diretor de RH", "Gerente de RH", "HRBP",
            "VP of People", "Head of People", "Chief People Officer",
        ],
        "person_locations": ["Brazil"],
        "page": 1,
        "per_page": 50,
    }
    contatos_validos = []
    try:
        res = requests.post(url, headers=HEADERS_APOLLO, json=payload)
        if res.status_code == 200:
            pessoas = res.json().get("people") or []
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
                    contatos_validos.append({
                        "email": email,
                        "nome": p.get("first_name", ""),
                        "sobrenome": p.get("last_name", ""),
                        "cargo": p.get("title", ""),
                        "linkedin": linkedin or "",
                    })
                if len(contatos_validos) >= limite:
                    break
    except Exception as e:
        print(f"Falha na requisição ao Apollo para {domain_empresa}: {e}")

    return contatos_validos

# ORQUESTRADOR COM TRAVA DE CRÉDITOS E LIMITE DE 10 EMPRESAS

def executar_automacao_pcd():
    print("Iniciando raspagem de vagas PCD via Apify (Com limite para economizar créditos)...")

   # 1. Parâmetros ajustados para o Scraper do Curious Coder (PCD + Últimos 7 dias)
    run_input = {
        "title": 'PCD OR "Pessoa com Deficiencia" OR "Pessoa com Deficiência" OR Inclusiva OR "Ações Afirmativas"',
        "location": "Brazil",
        "publishedAt": "r604800",  # Vagas dos últimos 7 dias (604.800 segundos)
        "count": 60,                # Limite de vagas coletadas no lote
    }

    # 2. Execução chamando o Actor exato da imagem
    run = apify_client.actor("curious_coder/linkedin-jobs-scraper").call(run_input=run_input)
    # Forma corrigida (compatível com objeto e dicionário):
    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
    dataset_items = apify_client.dataset(dataset_id).list_items().items

    print(f"Total de vagas raspadas pelo Apify no lote: {len(dataset_items)}")

    # 2. Agrupar contagem de vagas e capturar domínio
    empresas_vagas = Counter()
    empresas_dominios = {}

    for item in dataset_items:
        nome_empresa = item.get("companyName")
        url_empresa = item.get("companyWebsite") or item.get("companyDomain") or item.get("companyUrl")

        if nome_empresa:
            empresas_vagas[nome_empresa] += 1
            dom = limpar_dominio(url_empresa)
            if dom and nome_empresa not in empresas_dominios:
                empresas_dominios[nome_empresa] = dom

    empresas_processadas = 0

    # 3. Iterar sobre empresas encontradas
    for nome_empresa, total_vagas_pcd in empresas_vagas.items():
        # TRAVA DE PARADA: Se já processou 10 novas empresas, encerra imediatamente
        if empresas_processadas >= LIMITE_NOVAS_EMPRESAS:
            print(f"\nLimite de {LIMITE_NOVAS_EMPRESAS} novas empresas atingido. Encerrando execução!")
            break

        dominio = empresas_dominios.get(nome_empresa, "")

        print(f"\n--- Analisando {nome_empresa} ({total_vagas_pcd} vaga(s) PCD) | Domínio: '{dominio}' ---")

        if not dominio:
            print(f"Pulado: Domínio não encontrado para '{nome_empresa}'.")
            continue

        # CHECAGEM ANTES DO APOLLO: Se já existe no HubSpot, ignora e NÃO consome créditos do Apollo
        if empresa_existe_no_hubspot(dominio):
            print(f"Pulado: Empresa '{nome_empresa}' ({dominio}) já existe no HubSpot. Créditos mantidos intactos.")
            continue

        # Só consulta o Apollo se a empresa passou no filtro de "NÃO EXISTE NO HUBSPOT"
        contatos = buscar_contatos_empresa_apollo(dominio, limite=3)
        if not contatos:
            print(f"Pulado: Nenhum contato de RH no Brasil encontrado via Apollo para '{nome_empresa}'.")
            continue

        # 4. Criação da Empresa no CRM
        company_id = criar_empresa_hubspot(nome_empresa, dominio, num_vagas_pcd=total_vagas_pcd)
        if not company_id:
            continue

        print(f"Empresa '{nome_empresa}' criada no HubSpot (ID: {company_id})")

        # 5. Adiciona Observação/Nota na Empresa
        texto_nota = (
            f"REGISTRO DE VAGAS PCD:\n"
            f"Esta empresa possui {total_vagas_pcd} vaga(s) PCD/Inclusiva(s) aberta(s) no LinkedIn "
            f"identificada(s) via Apify em {datetime.now().strftime('%d/%m/%Y')}."
        )
        criar_nota_empresa_hubspot(company_id, texto_nota)

        # 6. Processa os contatos, e-mail e tarefas
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

                enviou, assunto, corpo = disparar_email_joel(c["email"], nome_contato, nome_empresa)

                if enviou:
                    registrar_email_enviado_no_hubspot(contact_id, assunto, corpo)
                    print(f"-> Contato {c['email']} associado + E-mail enviado e registrado!")
                else:
                    print(f"-> Contato {c['email']} associado!")

                criar_cadencia_tarefas_hubspot(
                    contact_id=contact_id,
                    bdr_id=JOEL_OWNER_ID,
                    bdr_name="Joel",
                    nome_lead=nome_contato,
                    empresa_lead=nome_empresa,
                )

        # Incrementa o contador de novas empresas concluídas
        empresas_processadas += 1
        print(f"Progresso: {empresas_processadas}/{LIMITE_NOVAS_EMPRESAS} empresas adicionadas.")
        time.sleep(1)

    print(f"\nFinalizado! Total de {empresas_processadas} novas empresas integradas no HubSpot.")


if __name__ == "__main__":
    executar_automacao_pcd()