import smtplib
import requests
import itertools
from email.message import EmailMessage
from hubspot import HubSpot
from hubspot.crm.contacts import SimplePublicObjectInputForCreate as ContactInput
from hubspot.crm.companies import SimplePublicObjectInputForCreate as CompanyInput
from datetime import datetime, timedelta, timezone

# CHAVE PARA ACESSO AO HUBSPOT 
HUBSPOT_ACCESS_TOKEN = "hupspot_access_token"

# CHAVE DE ACESSO DO APOLLO
APOLLO_API_KEY = "apollo_api_key"

# Configurações de SMTP
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER_JOEL  = "userjoel"
SMTP_PASS_JOEL = "passjoel"
SMTP_USER_ANTONY = "userantony"
SMTP_PASS_ANTONY = "passantony"

VENDEDORES = [
    {"id": "0000000", "email": "userantony", "bdr_name": "Antony"},
    {"id": "0000001", "email": "userjoel", "bdr_name": "Joel"}
]

# Inicializa roleta e cliente HubSpot
roleta_vendedores = itertools.cycle(VENDEDORES)
hubspot_client = HubSpot(access_token=HUBSPOT_ACCESS_TOKEN)


def buscar_e_desbloquear_leads_apollo(quantidade=50):
    """Busca pessoas no Apollo, limita a 3 por empresa e revela os e-mails"""
    url_search = "https://api.apollo.io/v1/mixed_people/api_search"
    url_enrich = "https://api.apollo.io/v1/people/match"
    
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY  
    }

    payload_search = {
        "page": 110,
        "per_page": 12,
        "person_locations": ["Brazil"],
        "person_titles": ["HR Coordinator", "HRBP", "CEO", "HR Manager", "CHRO", "Director", "Gerente de RH", "Diretor de RH", "Coordenador de RH"]
    }

    try:
        res_search = requests.post(url_search, headers=headers, json=payload_search)
        if res_search.status_code != 200:
            print(f"Erro na busca do Apollo: {res_search.status_code} - {res_search.text}")
            return []
        
        pessoas_encontradas = res_search.json().get("people", [])
    except Exception as e:
        print(f"Falha ao conectar com o Apollo: {e}")
        return []

    leads_desbloqueados = []
    contatos_por_empresa = {}

    for pessoa in pessoas_encontradas:
        person_id = pessoa.get("id")
        nome = pessoa.get("first_name", "")
        cargo = pessoa.get("title", "").upper() if pessoa.get("title") else ""

        organizacao = pessoa.get("organization", {})
        company_name = organizacao.get("name", "")
        company_domain = organizacao.get("primary_domain", "")
        chave_empresa = company_domain if company_domain else company_name

        if not person_id or not chave_empresa:
            continue

        if contatos_por_empresa.get(chave_empresa, 0) >= 3:
            print(f"Limite de 3 contatos atingido no Apollo para '{company_name}'. Pulando {nome}...")
            continue

        print(f"Consumindo créditos para revelar e-mail de {nome} ({cargo})...")

        payload_enrich = {"id": person_id}
        res_enrich = requests.post(url_enrich, headers=headers, json=payload_enrich)

        if res_enrich.status_code == 200:
            dados_completos = res_enrich.json().get("person", {})
            linkedin_encontrado = dados_completos.get("linkedin_url") or pessoa.get("linkedin_url", "")
            if linkedin_encontrado:
                dados_completos["linkedin_url"] = linkedin_encontrado

            if dados_completos.get("email"):
                leads_desbloqueados.append(dados_completos)
                contatos_por_empresa[chave_empresa] = contatos_por_empresa.get(chave_empresa, 0) + 1
                print(f"E-mail revelado: {dados_completos.get('email')} ({contatos_por_empresa[chave_empresa]}/3 de {company_name})")
            else:
                print(f"Apollo não encontrou e-mail para {nome}.")
        else:
            print(f"Falha ao destravar {nome}: {res_enrich.status_code}")

    return leads_desbloqueados


def buscar_id_empresa_hubspot(nome_ou_dominio):
    """Consulta o HubSpot e retorna o ID da empresa se ela já existir."""
    if not nome_ou_dominio:
        return None
        
    url = "https://api.hubapi.com/crm/v3/objects/companies/search"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    propriedade = "domain" if "." in nome_ou_dominio else "name"
    
    payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": propriedade,
                "operator": "EQ",
                "value": nome_ou_dominio
            }]
        }]
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            resultados = res.json().get("results", [])
            if resultados:
                return resultados[0]["id"]
    except Exception:
        pass
        
    return None


def empresa_atingiu_limite_hubspot(empresa_id):
    """Verifica no HubSpot se a empresa já possui 3 ou mais contatos vinculados."""
    if not empresa_id:
        return False
        
    url = f"https://api.hubapi.com/crm/v3/objects/companies/{empresa_id}/associations/contacts"
    headers = {"Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}"}
    
    try:
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            total_contatos = len(res.json().get("results", []))
            return total_contatos >= 3
    except Exception:
        pass
        
    return False


def contato_existe_no_hubspot(email):
    """Verifica se o contato já está cadastrado usando o e-mail."""
    try:
        resultado = hubspot_client.crm.contacts.basic_api.get_by_id(
            contact_id=email,
            id_property="email"
        )
        return resultado.id if resultado else None
    except Exception:
        return None


def validar_email_disparo_teste(email_destino, name_lead, empresa_lead, bdr_name):
    """Envia o e-mail real de prospecção via SMTP mapeando o BDR dinamicamente."""
    credenciais = {
        "Joel": (SMTP_USER_JOEL, SMTP_PASS_JOEL),
        "Antony": (SMTP_USER_ANTONY, SMTP_PASS_ANTONY)
    }

    if bdr_name not in credenciais:
        print(f"BDR '{bdr_name}' não possui credenciais salvas. Pulando disparo.")
        return True

    user_smtp, pass_smtp = credenciais[bdr_name]

    try:
        msg = EmailMessage()
        msg['Subject'] = "Qual a principal dor do seu time hoje?"
        msg['From'] = user_smtp
        msg['To'] = email_destino

        corpo = (
            f"Olá, {name_lead}, tudo bem?\n\n"
            f"Me chamo {bdr_name}, da Start RH. Somos uma consultoria de recrutamento e seleção "
            f"que atua com alocação de profissionais, RPO e contratações pontuais, ajudando empresas "
            f"a reduzir o tempo de vaga aberta sem abrir mão da qualidade da contratação. "
            f"Também temos uma frente dedicada a executive search, para posições de liderança.\n\n"
            f"Identifiquei um possível fit com os desafios da empresa {empresa_lead}, e, nos próximos dias, "
            f"vou compartilhar mais detalhes de como temos apoiado times parecidos com o seu.\n\n"
            f"Faz sentido essa conversa por aí?"
        )
        msg.set_content(corpo)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(user_smtp, pass_smtp)
            server.send_message(msg)

        print(f"E-mail disparado com sucesso ({bdr_name}) para {email_destino}")
        return True
    except Exception as e:  
        print(f"Falha no disparo de e-mail ({bdr_name}) para {email_destino}: {e}")
        return False


def criar_cadencia_tarefas_hubspot(contact_id, bdr_id, bdr_name, nome_lead, empresa_lead):
    """Cria uma lista de tarefas categorizadas por tipo no HubSpot utilizando hs_timestamp."""
    url = "https://api.hubapi.com/crm/v3/objects/tasks"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    tarefas = [
        {"titulo": "Conexão - LinkedIn", "dias_prazo": 1, "tipo": "TODO"},
        {"titulo": "Primeiro E-mail (Problema)", "dias_prazo": 1, "tipo": "EMAIL"},
        {"titulo": "Primeira Ligação - Referencia o E-mail", "dias_prazo": 3, "tipo": "CALL"},
        {"titulo": "Segundo E-mail - Prova Social ou Dado de Mercado", "dias_prazo": 5, "tipo": "EMAIL"},
        {"titulo": "Linkedin - Comentário ou Mensagem - Nunca Pitch Direto", "dias_prazo": 8, "tipo": "TODO"},
        {"titulo": "Segunda Ligação - Ângulo Diferente", "dias_prazo": 11, "tipo": "CALL"},
        {"titulo": "WhatsApp - Só com Sinal Prévio", "dias_prazo": 15, "tipo": "TODO"},
        {"titulo": "Break Up E-mail - O Mais Poderoso da Cadência", "dias_prazo": 19, "tipo": "EMAIL"}
    ]

    agora_utc = datetime.now(timezone.utc)

    for t in tarefas:
        data_vencimento = agora_utc + timedelta(days=t["dias_prazo"])
        vencimento_iso = data_vencimento.strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "properties": {
                "hs_task_subject": t["titulo"],
                "hs_task_status": "NOT_STARTED",
                "hs_task_type": t["tipo"],  
                "hubspot_owner_id": str(bdr_id),
                "hs_timestamp": vencimento_iso
            },
            "associations": [
                {
                    "to": {"id": str(contact_id)},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED", 
                            "associationTypeId": 204
                        }
                    ]
                }
            ]
        }
        
        try:
            res = requests.post(url, headers=headers, json=payload)
            if res.status_code == 201:
                print(f"Tarefa '{t['titulo']}' [{t['tipo']}] criada com sucesso para o BDR ({bdr_name})!")
            else:
                print(f"Erro ao criar tarefa '{t['titulo']}' [{res.status_code}]: {res.text}")
        except Exception as e:
            print(f"Falha na conexão com a API de Tarefas: {e}")


def executar_pipeline_outbound():
    print("1. Buscando e destravando e-mails no Apollo.io...")
    leads = buscar_e_desbloquear_leads_apollo(quantidade=10)

    memoria_vendedores = {}

    for person in leads:
        email = person.get("email")
        first_name = person.get("first_name", "")
        last_name = person.get("last_name", "")
        company_name = person.get("organization", {}).get("name", "Empresa Desconhecida")
        company_domain = person.get("organization", {}).get("primary_domain", "")
        cargo = person.get("title", "membro do RH")
        
       
        linkedin_lead = person.get("linkedin_url", "")
        print(f"LinkedIn encontrado para {first_name}: '{linkedin_lead}'")
        if isinstance(linkedin_lead, tuple) or isinstance(linkedin_lead, list):
            linkedin_lead = linkedin_lead[0] if linkedin_lead else ""

        if not email:
            print(f"Skipping {first_name}: e-mail não disponível no Apollo.")
            continue

        # TRAVA ANTI-DUPLICIDADE DE CONTATO
        hubspot_contact_id = contato_existe_no_hubspot(email)
        if hubspot_contact_id:
            print(f"\nO contato {email} JÁ EXISTE no HubSpot (ID: {hubspot_contact_id}). Pulando disparo e cadastro!")
            continue

        print(f"\n--------------------------------------------------")
        print(f"Processando Lead NOVO: {first_name} {last_name} ({email}) - {company_name}")

        # LÓGICA DE EMPRESA
        chave_empresa = company_domain if company_domain else company_name
        empresa_id = buscar_id_empresa_hubspot(chave_empresa)
        
        if empresa_id:
            print(f"A empresa '{company_name}' já existe (ID: {empresa_id}). Vinculando novo contato nela...")
        else:
            print(f"Criando nova empresa no HubSpot: {company_name}...")
            empresa_input = CompanyInput(
                properties={
                    "name": company_name,
                    "domain": company_domain
                }
            )
            empresa_criada = hubspot_client.crm.companies.basic_api.create(
                simple_public_object_input_for_create=empresa_input
            )
            empresa_id = empresa_criada.id
            print(f"Nova empresa '{company_name}' criada com sucesso (ID: {empresa_id}).")

        # TRAVA DE 3 CONTATOS NO HUBSPOT
        if empresa_id and empresa_atingiu_limite_hubspot(empresa_id):
            print(f"A empresa '{company_name}' já possui 3 contatos no HubSpot. Pulando cadastro de {first_name}...")
            continue

        # DEFINIÇÃO DO VENDEDOR (BDR ROTATIVO)
        if chave_empresa not in memoria_vendedores:
            memoria_vendedores[chave_empresa] = next(roleta_vendedores)
        vendedor_da_vez = memoria_vendedores[chave_empresa]
        
        bdr_id = vendedor_da_vez["id"]
        bdr_name = vendedor_da_vez["bdr_name"]

        # ETAPA 1: Disparo de E-mail via SMTP
        email_valido = validar_email_disparo_teste(
            email_destino=email, 
            name_lead=first_name, 
            empresa_lead=company_name, 
            bdr_name=bdr_name
        )
        if not email_valido:
            print(f"Lead descartado: E-mail {email} inválido ou caixa cheia.")
            continue

        # ETAPA 2: Criar Contato no HubSpot
        print(f"Criando contato no HubSpot...")
        contato_input = ContactInput(
            properties={
                "email": str(email),
                "firstname": str(first_name),
                "lastname": str(last_name),
                "jobtitle": str(cargo),
                "hs_linkedin_url": str(linkedin_lead),  
                "hubspot_owner_id": str(bdr_id)
            },
            associations=[
                {
                    "to": {"id": empresa_id},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 1}]
                }
            ]
        )
        contato_criado = hubspot_client.crm.contacts.basic_api.create(
            simple_public_object_input_for_create=contato_input
        )
        novo_contact_id = contato_criado.id
        print(f"Contato {first_name} criado e associado à Empresa {empresa_id}.")

        # ETAPA 3: Criar Cadência de Tarefas para o BDR
        criar_cadencia_tarefas_hubspot(
            contact_id=novo_contact_id,
            bdr_id=bdr_id,
            bdr_name=bdr_name,
            nome_lead=f"{first_name} {last_name}",
            empresa_lead=company_name
        )


# BLOCO DE EXECUÇÃO PRINCIPAL
if __name__ == "__main__":
    executar_pipeline_outbound()