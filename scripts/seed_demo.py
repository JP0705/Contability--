"""Cria (ou recria) um cliente de demonstração com dados da empresa dele.

Uso (na raiz do projeto):
    py scripts/seed_demo.py

Empresa fictícia: Doce Sabor Confeitaria (Simples Nacional), com 6 meses de
receitas e despesas até hoje. Rodar de novo apaga o cliente demo e recria tudo
do zero (os demais usuários não são tocados).

Credenciais de teste (apenas para ambiente local): DEMO_EMAIL e DEMO_PASSWORD abaixo.
"""
import random
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "samples" / "nfe"))

from contability import db  # noqa: E402
from contability.services import nfe  # noqa: E402
import gerar_amostras as amostras  # noqa: E402

DEMO_NAME = "Mariana Costa"
DEMO_EMAIL = "demo@docesabor.test"
DEMO_PASSWORD = "DoceSabor2026"

# contador afiliado com login (para testar o lado do contador: menu Atendimentos)
DEMO_ACC_EMAIL = "contador@contability.test"
DEMO_ACC_PASSWORD = "Contador2026"

COMPANY = "Doce Sabor Confeitaria"
COMPANY_RAZAO = "DOCE SABOR CONFEITARIA LTDA"
COMPANY_CNPJ = amostras.DEMO_CNPJ  # fictício, com DV válido
MONTHS = 6

# (descrição, categoria, dia, valor base, variação ±%, status no mês corrente)
INCOME = [
    ("Vendas no balcão — 1ª quinzena", "Vendas", 15, 9800, 12),
    ("Vendas no balcão — 2ª quinzena", "Vendas", 28, 10400, 12),
    ("Encomendas de bolos e festas", "Serviços prestados", 22, 4200, 30),
    ("Vendas pelo aplicativo de delivery", "Vendas", 10, 3100, 20),
]

EXPENSES = [
    ("Salários da equipe (3 funcionários)", "Pessoal", 5, 6300, 0),
    ("FGTS e encargos", "Pessoal", 7, 780, 0),
    ("Pró-labore da sócia", "Pessoal", 5, 2500, 0),
    ("Aluguel da loja", "Operacional", 10, 3200, 0),
    ("Energia elétrica", "Operacional", 12, 690, 15),
    ("Água", "Operacional", 12, 180, 10),
    ("Insumos (farinha, açúcar, ovos, laticínios)", "Operacional", 3, 4800, 15),
    ("Embalagens", "Operacional", 18, 650, 20),
    ("Combustível das entregas", "Logística", 20, 420, 20),
    ("Taxa do aplicativo de delivery", "Logística", 25, 0, 0),  # calculada: 23% das vendas no app
    ("Honorários do contador", "Serviços", 8, 650, 0),
    ("Internet e telefone", "Serviços", 15, 160, 0),
    ("Sistema de PDV (mensalidade)", "Serviços", 15, 129, 0),
    ("DAS — Simples Nacional", "Impostos", 20, 0, 0),         # calculado: ~6% da receita do mês anterior
    ("Manutenção de equipamentos", "Outros", 17, 350, 60),
]


def _add_months(d, n):
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _vary(rng, base, pct):
    if not pct:
        return Decimal(base)
    factor = 1 + rng.uniform(-pct, pct) / 100
    return (Decimal(base) * Decimal(str(round(factor, 4)))).quantize(Decimal("1.00"))


def build_transactions(today):
    rng = random.Random(2026)  # determinístico: mesmos números a cada execução
    current = today.replace(day=1)
    rows = []
    prev_income = Decimal("26000")

    for i in range(MONTHS - 1, -1, -1):
        month = _add_months(current, -i)
        is_current = month == current
        income_total = Decimal(0)
        app_sales = Decimal(0)

        for desc, cat, day, base, pct in INCOME:
            d = month.replace(day=day)
            amount = _vary(rng, base, pct)
            if is_current and d > today:
                continue  # receita futura ainda não aconteceu
            income_total += amount
            if "aplicativo" in desc:
                app_sales = amount
            rows.append(("income", desc, cat, amount, d, "done"))

        for desc, cat, day, base, pct in EXPENSES:
            d = month.replace(day=day)
            if "Taxa do aplicativo" in desc:
                amount = (app_sales * Decimal("0.23")).quantize(Decimal("1.00"))
            elif "DAS" in desc:
                amount = (prev_income * Decimal("0.061")).quantize(Decimal("1.00"))
            else:
                amount = _vary(rng, base, pct)
            if amount <= 0:
                continue
            # no mês corrente, o que vence depois de hoje fica pendente
            status = "pending" if is_current and d > today else "done"
            rows.append(("expense", desc, cat, amount, d, status))

        # um gasto pontual em alguns meses
        if month.month == 8:
            rows.append(("expense", "Forno turbo novo (parcela única)", "Outros",
                         Decimal("3890.00"), month.replace(day=14), "done"))
        if month.month == 10:
            rows.append(("income", "Encomenda corporativa — coffee break", "Serviços prestados",
                         Decimal("2750.00"), month.replace(day=9), "done"))

        prev_income = income_total

    return rows


CHAT = [
    ("user", "Oi! Tenho uma confeitaria no Simples Nacional. Como sei se estou pagando o DAS certo?"),
    ("assistant",
     "## Conferindo o DAS no Simples Nacional\n\n"
     "O valor do DAS depende de **três coisas**:\n\n"
     "1. **Anexo** da sua atividade — confeitaria com venda ao consumidor costuma ficar no **Anexo I (Comércio)**;\n"
     "2. **Receita bruta dos últimos 12 meses (RBT12)**, que define a faixa e a alíquota nominal;\n"
     "3. **Receita do mês** que está sendo apurado.\n\n"
     "| Etapa | O que fazer |\n|---|---|\n"
     "| 1 | Some o faturamento dos últimos 12 meses |\n"
     "| 2 | Encontre a faixa no Anexo I e calcule a alíquota efetiva |\n"
     "| 3 | Aplique a alíquota efetiva sobre a receita do mês |\n\n"
     "> Dica: confira com seu contador se encomendas para festas estão sendo tratadas como venda de mercadoria."),
]

# segunda conversa (contexto separado da primeira)
CHAT_2 = [
    ("user", "Qual a diferença entre pró-labore e distribuição de lucros para uma sócia de empresa do Simples?"),
    ("assistant",
     "## Pró-labore x distribuição de lucros\n\n"
     "| | Pró-labore | Distribuição de lucros |\n|---|---|---|\n"
     "| O que é | Remuneração pelo trabalho da sócia | Parte do lucro apurado |\n"
     "| INSS | Sim (11% retido) | Não |\n"
     "| IRRF | Conforme a tabela progressiva | Isento (com escrituração) |\n\n"
     "Na prática, é comum definir um **pró-labore mínimo** e retirar o restante como lucro, "
     "desde que a contabilidade comprove o resultado."),
]

# (título, mensagens) — a lista mostra a mais recente primeiro
CONVERSAS = [
    ("DAS no Simples Nacional", CHAT),
    ("Pró-labore x distribuição de lucros", CHAT_2),
]


# contadores afiliados fictícios: (nome, CRC, cidade, UF, especialidades, bio, anos, nota, disponível)
ACCOUNTANTS = [
    ("Ana Beatriz Rocha", "GO-018234/O", "Goiânia", "GO",
     ["Simples Nacional", "MEI", "Abertura de empresa"],
     "Atende pequenos negócios de comércio e alimentação há mais de uma década. "
     "Especialista em enquadramento no Simples e planejamento do DAS.", 12, 4.9, True),
    ("Carlos Eduardo Lima", "SP-301452/O", "São Paulo", "SP",
     ["Lucro Presumido", "Planejamento tributário", "Reforma Tributária"],
     "Consultor tributário focado em empresas em crescimento e na transição para IBS e CBS.", 18, 4.8, True),
    ("Fernanda Okamoto", "PR-067719/O", "Curitiba", "PR",
     ["Folha de pagamento", "eSocial", "Trabalhista"],
     "Ajuda empresas a organizar a folha, encargos, férias e rescisões sem surpresas.", 9, 4.7, True),
    ("Rafael Monteiro", "MG-112093/O", "Belo Horizonte", "MG",
     ["NF-e e documentos fiscais", "ICMS", "Substituição tributária"],
     "Especialista em ICMS e ST para indústria e comércio, com foco em notas fiscais de entrada e saída.", 15, 4.6, True),
    ("Juliana Prado", "RJ-145876/O", "Rio de Janeiro", "RJ",
     ["Imposto de Renda", "Pessoa física", "Investimentos"],
     "Declarações de IR de sócios e profissionais liberais, ganho de capital e investimentos.", 7, 4.8, False),
    ("Marcos Vinícius Alves", "DF-021567/O", "Brasília", "DF",
     ["Abertura de empresa", "Terceiro setor", "Regularização fiscal"],
     "Abertura, alteração e regularização de empresas e entidades sem fins lucrativos.", 11, 4.5, True),
]

DEMO_CONSULTA = [
    ("cliente", "Oi, Ana! Tenho uma confeitaria no Simples Nacional e queria entender se compensa "
                "separar as encomendas para festas como serviço."),
    ("contador", "Olá, Mariana! Boa pergunta. Na maioria dos casos, bolo e doces vendidos prontos "
                 "continuam sendo venda de mercadoria (Anexo I), mesmo sob encomenda."),
    ("contador", "Para eu confirmar no seu caso: você também cobra decoração ou montagem no local "
                 "do evento? Isso pode mudar o enquadramento de parte da receita."),
]


def seed_accountants():
    """Recria os contadores demo (e o login do contador). Conversas deles são apagadas junto."""
    with db.cursor() as cur:
        cur.execute("DELETE FROM accountants WHERE crc = ANY(%s)", ([a[1] for a in ACCOUNTANTS],))
        cur.execute("DELETE FROM users WHERE email = %s", (DEMO_ACC_EMAIL,))

    acc_user = db.create_user(ACCOUNTANTS[0][0], DEMO_ACC_EMAIL, generate_password_hash(DEMO_ACC_PASSWORD))
    ids = []
    with db.cursor() as cur:
        for i, (name, crc, city, uf, specs, bio, years, rating, available) in enumerate(ACCOUNTANTS):
            cur.execute(
                """INSERT INTO accountants (user_id, name, crc, city, uf, specialties, bio,
                                            years_experience, rating, available)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (acc_user["id"] if i == 0 else None, name, crc, city, uf, specs, bio, years, rating, available),
            )
            ids.append(cur.fetchone()["id"])
    return ids


def seed():
    db.init_db()
    today = date.today()

    with db.cursor() as cur:
        cur.execute("DELETE FROM users WHERE email = %s", (DEMO_EMAIL,))

    user = db.create_user(f"{DEMO_NAME}", DEMO_EMAIL, generate_password_hash(DEMO_PASSWORD))
    rows = build_transactions(today)

    with db.cursor() as cur:
        cur.executemany(
            """INSERT INTO transactions (user_id, type, description, category, amount, date, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [(user["id"], *r) for r in rows],
        )

    # conversas com a IA, cada uma com seu próprio contexto
    for title, msgs in CONVERSAS:
        conv = db.create_conversation(user["id"], title)
        for role, content in msgs:
            db.save_message(user["id"], conv["id"], role, content)

    # empresa + NF-e de exemplo (sem lançamentos: teste o botão "Gerar lançamentos")
    db.save_company(user["id"], COMPANY_CNPJ, COMPANY_RAZAO)
    notas = [amostras.compra_farinha(today), amostras.venda_cafeteria(today),
             amostras.compra_embalagens_reforma(today)]
    for xml in notas:
        parsed = nfe.parse_nfe(xml.encode("utf-8"))
        parsed.header["direcao"] = nfe.classify(parsed, COMPANY_CNPJ)
        db.insert_nfe(user["id"], parsed.header, parsed.items, parsed.duplicatas)

    # contadores afiliados + conversa da cliente demo com a contadora que tem login
    acc_ids = seed_accountants()
    cid = db.get_or_create_consultation(user["id"], acc_ids[0])
    for sender, content in DEMO_CONSULTA:
        db.add_consultation_message(cid, sender, content)

    income = sum(r[3] for r in rows if r[0] == "income")
    expense = sum(r[3] for r in rows if r[0] == "expense")
    print(f"Cliente demo criado: {DEMO_NAME} ({COMPANY})")
    print(f"  {len(rows)} transações em {MONTHS} meses | receitas R$ {income:,.2f} | despesas R$ {expense:,.2f}")
    print(f"  Empresa: {COMPANY_RAZAO} | CNPJ {COMPANY_CNPJ} | {len(notas)} NF-e importadas")
    print(f"  {len(acc_ids)} contadores afiliados | conversa demo com {ACCOUNTANTS[0][0]}")
    print("  Logins: cliente em DEMO_EMAIL/DEMO_PASSWORD e contador em DEMO_ACC_EMAIL/DEMO_ACC_PASSWORD (topo de scripts/seed_demo.py)")


if __name__ == "__main__":
    seed()
