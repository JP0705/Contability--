"""Menu lateral e páginas "Em breve" dos módulos ainda não construídos."""
import math

from flask import Blueprint, abort, g, render_template, request, url_for

bp = Blueprint("wip", __name__, url_prefix="/em-breve")

# módulos em construção: o que vão fazer, progresso e perguntas para o assistente
MODULES = {
    "impostos": {
        "title": "Impostos",
        "icon": "bi-shield-check",
        "summary": "Cálculo e acompanhamento dos tributos da sua empresa, com alertas de vencimento.",
        "progress": 35,
        "features": [
            ("Resumo dos impostos destacados nas NF-e importadas", "done"),
            ("Calendário de vencimentos (DAS, DARF, GPS, ICMS)", "doing"),
            ("Simulação de alíquota efetiva do Simples Nacional", "todo"),
            ("Alertas de impostos a vencer", "todo"),
        ],
        "questions": [
            "Como calcular a alíquota efetiva do Simples Nacional?",
            "Quais impostos uma empresa do Simples paga no DAS?",
            "O que muda com o IBS e a CBS da Reforma Tributária?",
        ],
    },
    "fluxo-de-caixa": {
        "title": "Fluxo de Caixa",
        "icon": "bi-check2-square",
        "summary": "Projeção de entradas e saídas para você enxergar o caixa dos próximos meses.",
        "progress": 45,
        "features": [
            ("Lançamentos de receitas e gastos (aba Gastos)", "done"),
            ("Contas a pagar e a receber a partir das NF-e", "done"),
            ("Projeção de saldo diário para 90 dias", "doing"),
            ("Cenários: otimista, realista e pessimista", "todo"),
        ],
        "questions": [
            "Como montar um fluxo de caixa para uma pequena empresa?",
            "Qual a diferença entre fluxo de caixa e DRE?",
            "Como melhorar o capital de giro do meu negócio?",
        ],
    },
    "folha-de-pagamento": {
        "title": "Folha de Pagamento",
        "icon": "bi-file-earmark-text",
        "summary": "Cadastro de funcionários, cálculo de salários, encargos, férias e 13º.",
        "progress": 15,
        "features": [
            ("Cadastro de funcionários e pró-labore", "doing"),
            ("Cálculo de INSS, FGTS e IRRF", "todo"),
            ("Férias, 13º salário e rescisões", "todo"),
            ("Integração com o eSocial", "todo"),
        ],
        "questions": [
            "Quanto custa contratar um funcionário CLT?",
            "Como calcular férias e o terço constitucional?",
            "Qual a diferença entre pró-labore e distribuição de lucros?",
        ],
    },
    "mei-simples": {
        "title": "MEI & Simples",
        "icon": "bi-building",
        "summary": "Ferramentas para MEI e Simples Nacional: limites, DAS e enquadramento.",
        "progress": 25,
        "features": [
            ("Acompanhamento do limite de faturamento anual", "doing"),
            ("Geração e controle do DAS", "todo"),
            ("Simulador de desenquadramento do MEI", "todo"),
            ("Declaração anual (DASN-SIMEI / DEFIS)", "todo"),
        ],
        "questions": [
            "Qual o limite de faturamento do MEI?",
            "O que acontece se o MEI ultrapassar o limite de faturamento?",
            "Quando vale a pena sair do MEI para o Simples Nacional?",
        ],
    },
    "receita-federal": {
        "title": "Receita Federal",
        "icon": "bi-globe",
        "summary": "Consultas de CNPJ, situação cadastral e certidões em um só lugar.",
        "progress": 10,
        "features": [
            ("Consulta de CNPJ e situação cadastral", "doing"),
            ("Emissão de certidão negativa de débitos (CND)", "todo"),
            ("Acompanhamento de pendências e malha fiscal", "todo"),
        ],
        "questions": [
            "Como emitir a certidão negativa de débitos federais?",
            "O que significa CNPJ com situação inapta?",
            "Como regularizar pendências na Receita Federal?",
        ],
    },
    "obrigacoes-fiscais": {
        "title": "Obrigações Fiscais",
        "icon": "bi-journal-text",
        "summary": "Agenda das obrigações acessórias da empresa, com lembretes antes do prazo.",
        "progress": 20,
        "features": [
            ("Agenda mensal de obrigações por regime tributário", "doing"),
            ("Lembretes de prazos (SPED, DCTFWeb, EFD-Reinf)", "todo"),
            ("Checklist de entrega por competência", "todo"),
        ],
        "questions": [
            "Quais obrigações acessórias uma empresa do Simples precisa entregar?",
            "O que é a DCTFWeb e quem é obrigado a entregar?",
            "Qual a multa por atraso na entrega de obrigações acessórias?",
        ],
    },
    "relatorios-financeiros": {
        "title": "Relatórios Financeiros",
        "icon": "bi-currency-dollar",
        "summary": "DRE, balancete e relatórios gerenciais gerados a partir dos seus lançamentos.",
        "progress": 30,
        "features": [
            ("Resumo mensal de receitas, gastos e categorias", "done"),
            ("DRE gerencial simplificada", "doing"),
            ("Exportação em PDF e Excel", "todo"),
            ("Comparativo entre períodos", "todo"),
        ],
        "questions": [
            "Como montar uma DRE simplificada?",
            "Quais indicadores financeiros acompanhar todo mês?",
            "Como calcular a margem de lucro do meu negócio?",
        ],
    },
}

# menu lateral: (rótulo, ícone, endpoint, kwargs)
MENU = [
    ("Início", "bi-house", "home", {}),
    ("Gastos", "bi-bar-chart", "gastos.index", {}),
    ("Notas Fiscais", "bi-receipt", "notas.index", {}),
    ("Impostos", "bi-shield-check", "wip.page", {"slug": "impostos"}),
    ("Fluxo de Caixa", "bi-check2-square", "wip.page", {"slug": "fluxo-de-caixa"}),
    ("Folha de Pagamento", "bi-file-earmark-text", "wip.page", {"slug": "folha-de-pagamento"}),
    ("MEI & Simples", "bi-building", "wip.page", {"slug": "mei-simples"}),
    ("Receita Federal", "bi-globe", "wip.page", {"slug": "receita-federal"}),
    ("Obrigações Fiscais", "bi-journal-text", "wip.page", {"slug": "obrigacoes-fiscais"}),
    ("Relatórios Financeiros", "bi-currency-dollar", "wip.page", {"slug": "relatorios-financeiros"}),
    ("Especialistas", "bi-people", "consultoria.directory", {}),
]

# páginas que acendem um item do menu mesmo tendo outro endpoint
ACTIVE_ALIASES = {
    "notas.detail": "notas.index",
    "consultoria.start": "consultoria.directory",
    "consultoria.thread": "consultoria.directory",
}


def gear_path(cx, cy, outer, inner, teeth):
    """Caminho SVG de uma engrenagem (dentes trapezoidais) centrada em (cx, cy)."""
    step = 2 * math.pi / teeth
    pts = []
    for i in range(teeth):
        a = i * step
        # base do dente (raio interno) -> topo (raio externo) -> base
        for ang, r in ((a, inner), (a + step * .18, outer), (a + step * .45, outer), (a + step * .63, inner)):
            pts.append(f"{cx + r * math.cos(ang):.1f},{cy + r * math.sin(ang):.1f}")
    return "M" + " L".join(pts) + " Z"


def init_app(app):
    app.register_blueprint(bp)
    app.jinja_env.globals["gear_path"] = gear_path

    @app.context_processor
    def menu_context():
        endpoint = ACTIVE_ALIASES.get(request.endpoint, request.endpoint)
        view_args = request.view_args or {}
        items = []
        for label, icon, ep, kwargs in MENU:
            active = endpoint == ep and all(view_args.get(k) == v for k, v in kwargs.items())
            items.append({"label": label, "icon": icon, "url": url_for(ep, **kwargs),
                          "active": active, "wip": ep == "wip.page"})
        return {"menu_items": items}


@bp.route("/<slug>")
def page(slug):
    module = MODULES.get(slug)
    if not module:
        abort(404)
    others = [(s, m) for s, m in MODULES.items() if s != slug]
    done = sum(1 for _, status in module["features"] if status == "done")
    return render_template("wip.html", slug=slug, module=module, others=others, done=done)
