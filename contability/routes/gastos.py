"""Tela de Gastos: resumo do mês, gráfico, categorias e CRUD de transações."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import psycopg2
from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, url_for,
)

from .. import db

bp = Blueprint("gastos", __name__, url_prefix="/gastos")

MONTHS_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
             "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

# categoria -> ícone (Bootstrap Icons)
CATEGORIES = {
    "expense": {
        "Pessoal": "bi-person-badge",
        "Operacional": "bi-building",
        "Logística": "bi-truck",
        "Serviços": "bi-lightning",
        "Impostos": "bi-bank",
        "Outros": "bi-three-dots",
    },
    "income": {
        "Vendas": "bi-cart",
        "Serviços prestados": "bi-briefcase",
        "Outros": "bi-three-dots",
    },
}

STATUS_LABELS = {
    "expense": {"done": "Pago", "pending": "Pendente"},
    "income": {"done": "Recebido", "pending": "A receber"},
}

CHART_MONTHS = 5
MAX_AMOUNT = Decimal("9999999999.99")  # NUMERIC(12,2)


def init_app(app):
    app.register_blueprint(bp)

    @app.template_filter("brl")
    def brl(value):
        """1234.5 -> 'R$ 1.234,50'; -1234.5 -> '-R$ 1.234,50'"""
        value = Decimal(value or 0)
        txt = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{'-' if value < 0 else ''}R$ {txt}"

    @app.template_filter("pct")
    def pct(value):
        return f"{value:.1f}".replace(".", ",") + "%"


# =========================
# DATAS
# =========================

def _add_months(d, n):
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _parse_month(value):
    """'2026-09' -> date(2026, 9, 1); inválido/ausente -> mês atual."""
    try:
        return datetime.strptime(value or "", "%Y-%m").date().replace(day=1)
    except ValueError:
        return date.today().replace(day=1)


def _month_label(d):
    return f"{MONTHS_PT[d.month - 1]} {d.year}"


# =========================
# CÁLCULOS
# =========================

def _variation(current, previous):
    """Variação percentual vs. mês anterior (None se não há base de comparação)."""
    if not previous:
        return None
    return float((current - previous) / abs(previous) * 100)


def _nice_ceiling(value):
    """Topo do eixo do gráfico: arredonda para 1, 2, 2.5 ou 5 x 10^n."""
    if value <= 0:
        return Decimal(1000)
    exp = len(str(int(value))) - 1
    base = Decimal(10) ** exp
    for step in (1, 2, Decimal("2.5"), 5, 10):
        if value <= step * base:
            return step * base
    return 10 * base


def build_dashboard(user_id, month):
    next_month = _add_months(month, 1)
    prev_month = _add_months(month, -1)
    chart_start = _add_months(month, -(CHART_MONTHS - 1))

    transactions = db.list_transactions(user_id, month, next_month)
    totals = db.monthly_totals(user_id, chart_start, next_month)

    income = sum((t["amount"] for t in transactions if t["type"] == "income"), Decimal(0))
    expense = sum((t["amount"] for t in transactions if t["type"] == "expense"), Decimal(0))
    pending = [t for t in transactions if t["type"] == "expense" and t["status"] == "pending"]

    prev = totals.get(prev_month.strftime("%Y-%m"), {"income": Decimal(0), "expense": Decimal(0)})
    prev_balance = prev["income"] - prev["expense"]

    # gastos por categoria (maior primeiro)
    by_cat = {}
    for t in transactions:
        if t["type"] != "expense":
            continue
        c = by_cat.setdefault(t["category"], {"name": t["category"], "total": Decimal(0), "count": 0})
        c["total"] += t["amount"]
        c["count"] += 1
    categories = sorted(by_cat.values(), key=lambda c: c["total"], reverse=True)
    for c in categories:
        c["pct"] = float(c["total"] / expense * 100) if expense else 0
        c["icon"] = CATEGORIES["expense"].get(c["name"], "bi-tag")

    # gráfico dos últimos meses
    months = [_add_months(chart_start, i) for i in range(CHART_MONTHS)]
    series = []
    for m in months:
        row = totals.get(m.strftime("%Y-%m"), {"income": Decimal(0), "expense": Decimal(0)})
        series.append({"label": MONTHS_PT[m.month - 1][:3], "income": row["income"], "expense": row["expense"]})
    top = _nice_ceiling(max([max(s["income"], s["expense"]) for s in series] + [Decimal(0)]))
    for s in series:
        s["income_h"] = float(s["income"] / top * 100)
        s["expense_h"] = float(s["expense"] / top * 100)
    axis = [top * Decimal(k) / 4 for k in (4, 3, 2, 1, 0)]

    return {
        "income": income,
        "expense": expense,
        "balance": income - expense,
        "income_var": _variation(income, prev["income"]),
        "expense_var": _variation(expense, prev["expense"]),
        "balance_var": _variation(income - expense, prev_balance),
        "pending_total": sum((t["amount"] for t in pending), Decimal(0)),
        "pending_count": len(pending),
        "categories": categories,
        "series": series,
        "axis": axis,
        "transactions": transactions,
    }


def month_summary(user_id, month=None):
    """Resumo do mês para o painel da home (mesmos cálculos da tela de Gastos)."""
    month = month or date.today().replace(day=1)
    dash = build_dashboard(user_id, month)
    top = dash["categories"][0] if dash["categories"] else None
    return {
        "month_label": _month_label(month),
        "month_value": month.strftime("%Y-%m"),
        "income": dash["income"],
        "expense": dash["expense"],
        "balance": dash["balance"],
        "balance_var": dash["balance_var"],
        "pending_total": dash["pending_total"],
        "pending_count": dash["pending_count"],
        "top_category": top,
        "count": len(dash["transactions"]),
    }


def _axis_label(value):
    value = int(value)
    if value >= 1000:
        k = value / 1000
        return (f"{k:.1f}".rstrip("0").rstrip(".") + "k").replace(".", ",")
    return str(value)


# =========================
# FORMULÁRIO
# =========================

def _parse_form(form):
    """Valida o formulário de transação. Retorna (dados, erros)."""
    errors = []
    tx_type = form.get("type")
    if tx_type not in CATEGORIES:
        errors.append("Tipo inválido.")
        tx_type = "expense"

    description = form.get("description", "").strip()
    if not description:
        errors.append("Informe a descrição.")
    elif len(description) > 200:
        errors.append("Descrição muito longa (máx. 200 caracteres).")

    category = form.get("category", "")
    if category not in CATEGORIES[tx_type]:
        errors.append("Categoria inválida para o tipo escolhido.")

    raw_amount = form.get("amount", "").strip()
    # aceita "1.234,56", "1234,56" e "1234.56"
    if "," in raw_amount:
        raw_amount = raw_amount.replace(".", "").replace(",", ".")
    try:
        amount = Decimal(raw_amount).quantize(Decimal("0.01"))
        if amount <= 0 or amount > MAX_AMOUNT:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errors.append("Informe um valor maior que zero.")
        amount = None

    try:
        tx_date = datetime.strptime(form.get("date", ""), "%Y-%m-%d").date()
    except ValueError:
        errors.append("Informe uma data válida.")
        tx_date = None

    status = form.get("status")
    if status not in ("done", "pending"):
        errors.append("Status inválido.")

    data = {"type": tx_type, "description": description, "category": category,
            "amount": amount, "date": tx_date, "status": status}
    return data, errors


def _redirect_to_month(d=None):
    mes = (d.strftime("%Y-%m") if d else request.form.get("mes")) or None
    return redirect(url_for("gastos.index", mes=mes))


# =========================
# ROTAS
# =========================

@bp.route("/")
def index():
    month = _parse_month(request.args.get("mes"))
    try:
        dash = build_dashboard(g.user["id"], month)
    except psycopg2.Error:
        flash("Banco de dados indisponível. Tente novamente em instantes.", "danger")
        dash = None

    return render_template(
        "gastos/index.html",
        dash=dash,
        month=month,
        month_value=month.strftime("%Y-%m"),
        month_label=_month_label(month),
        prev_month=_add_months(month, -1).strftime("%Y-%m"),
        next_month=_add_months(month, 1).strftime("%Y-%m"),
        categories={k: list(v) for k, v in CATEGORIES.items()},
        status_labels=STATUS_LABELS,
        axis_label=_axis_label,
        today=date.today().isoformat(),
    )


@bp.route("/transacoes", methods=["POST"])
def create():
    data, errors = _parse_form(request.form)
    if errors:
        for e in errors:
            flash(e, "danger")
        return _redirect_to_month()
    db.create_transaction(g.user["id"], data)
    flash("Transação cadastrada.", "success")
    return _redirect_to_month(data["date"])


@bp.route("/transacoes/<int:tx_id>/editar", methods=["POST"])
def update(tx_id):
    data, errors = _parse_form(request.form)
    if errors:
        for e in errors:
            flash(e, "danger")
        return _redirect_to_month()
    if not db.update_transaction(g.user["id"], tx_id, data):
        abort(404)
    flash("Transação atualizada.", "success")
    return _redirect_to_month(data["date"])


@bp.route("/transacoes/<int:tx_id>/excluir", methods=["POST"])
def delete(tx_id):
    if not db.delete_transaction(g.user["id"], tx_id):
        abort(404)
    flash("Transação excluída.", "success")
    return _redirect_to_month()
