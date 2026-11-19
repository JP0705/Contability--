"""Aba Notas Fiscais: upload de XML de NF-e (modelo 55), lista, detalhe,
download do XML, exclusão e geração de lançamentos na aba Gastos."""
from datetime import date
from decimal import Decimal

import psycopg2
from flask import (
    Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for,
)

import db
import nfe
from gastos import _add_months, _month_label, _parse_month

bp = Blueprint("notas", __name__, url_prefix="/notas")

MAX_FILES = 50

# categoria usada nos lançamentos gerados (pode ser editada depois em Gastos)
LAUNCH_CATEGORY = {"entrada": ("expense", "Operacional"), "saida": ("income", "Vendas")}


def init_app(app):
    app.register_blueprint(bp)
    # limite do corpo da requisição (vários XMLs de até 2 MB)
    app.config.setdefault("MAX_CONTENT_LENGTH", 25 * 1024 * 1024)

    @app.errorhandler(413)
    def too_large(_e):
        flash("Envio grande demais (máx. 25 MB no total). Envie menos arquivos por vez.", "danger")
        return redirect(url_for("notas.index"))

    @app.template_filter("chave")
    def format_chave(value):
        """Chave de acesso em blocos de 4 dígitos."""
        return " ".join(value[i:i + 4] for i in range(0, len(value or ""), 4))


def _company_or_redirect():
    company = db.get_company(g.user["id"])
    if not company:
        flash("Cadastre o CNPJ da sua empresa para importar notas fiscais.", "danger")
        return None, redirect(url_for("empresa.index", next=url_for("notas.index")))
    return company, None


# =========================
# LANÇAMENTOS
# =========================

def build_launches(header, duplicatas, today=None):
    """Lançamentos a partir da nota: um por parcela ou um único no valor total."""
    today = today or date.today()
    tx_type, category = LAUNCH_CATEGORY[header["direcao"]]
    contraparte = header["dest_nome"] if header["direcao"] == "saida" else header["emit_nome"]
    base = f"NF-e {header['numero']} — {contraparte or 'sem nome'}"

    if duplicatas:
        n = len(duplicatas)
        parcelas = [(d["vencimento"], d["valor"], f" ({i}/{n})" if n > 1 else "")
                    for i, d in enumerate(duplicatas, 1)]
    else:
        parcelas = [(header["emissao"].date(), header["v_total"], "")]

    return [{
        "type": tx_type,
        "category": category,
        "description": (base + sufixo)[:200],
        "amount": Decimal(valor),
        "date": venc,
        "status": "pending" if venc > today else "done",
    } for venc, valor, sufixo in parcelas if Decimal(valor) > 0]


# =========================
# ROTAS
# =========================

@bp.route("/")
def index():
    company, redir = _company_or_redirect()
    if redir:
        return redir

    month = _parse_month(request.args.get("mes"))
    direcao = request.args.get("tipo") if request.args.get("tipo") in ("entrada", "saida") else None

    try:
        notas = db.list_nfe(g.user["id"], month, _add_months(month, 1), direcao)
    except psycopg2.Error:
        flash("Banco de dados indisponível. Tente novamente em instantes.", "danger")
        notas = []

    def soma(campo, dir_=None):
        return sum((n[campo] for n in notas if dir_ is None or n["direcao"] == dir_), Decimal(0))

    impostos = sum((soma(c) for c in ("v_icms", "v_st", "v_ipi", "v_pis", "v_cofins", "v_ibs", "v_cbs")), Decimal(0))

    return render_template(
        "notas.html",
        company=company,
        notas=notas,
        resumo={
            "entradas": soma("v_total", "entrada"),
            "saidas": soma("v_total", "saida"),
            "impostos": impostos,
            "qtd": len(notas),
            "qtd_entradas": sum(1 for n in notas if n["direcao"] == "entrada"),
            "qtd_saidas": sum(1 for n in notas if n["direcao"] == "saida"),
        },
        direcao=direcao,
        month_value=month.strftime("%Y-%m"),
        month_label=_month_label(month),
        prev_month=_add_months(month, -1).strftime("%Y-%m"),
        next_month=_add_months(month, 1).strftime("%Y-%m"),
    )


@bp.route("/importar", methods=["POST"])
def upload():
    company, redir = _company_or_redirect()
    if redir:
        return redir

    files = [f for f in request.files.getlist("xmls") if f and f.filename]
    gerar = request.form.get("gerar_lancamentos") == "1"

    if not files:
        flash("Selecione ao menos um arquivo XML.", "danger")
        return redirect(url_for("notas.index"))
    if len(files) > MAX_FILES:
        flash(f"Envie no máximo {MAX_FILES} arquivos por vez.", "danger")
        return redirect(url_for("notas.index"))

    importadas, ultima_emissao = 0, None
    for f in files:
        nome = f.filename
        if not nome.lower().endswith(".xml"):
            flash(f"{nome}: apenas arquivos .xml são aceitos.", "danger")
            continue
        try:
            parsed = nfe.parse_nfe(f.read(nfe.MAX_XML_BYTES + 1))
            parsed.header["direcao"] = nfe.classify(parsed, company["cnpj"])

            if db.nfe_exists(g.user["id"], parsed.header["chave"]):
                raise nfe.NFeError("esta nota já foi importada.")

            nfe_id = db.insert_nfe(g.user["id"], parsed.header, parsed.items, parsed.duplicatas)
            gerados = 0
            if gerar:
                gerados = db.create_nfe_launches(
                    g.user["id"], nfe_id, build_launches(parsed.header, parsed.duplicatas))
        except nfe.NFeError as e:
            flash(f"{nome}: {e}", "danger")
            continue
        except psycopg2.errors.UniqueViolation:
            flash(f"{nome}: esta nota já foi importada.", "danger")
            continue
        except psycopg2.Error:
            flash(f"{nome}: erro ao gravar no banco de dados.", "danger")
            continue

        importadas += 1
        ultima_emissao = parsed.header["emissao"]
        tipo = "venda" if parsed.header["direcao"] == "saida" else "compra"
        extra = f", {gerados} lançamento(s) gerado(s)" if gerados else ""
        aviso = f" — {len(parsed.avisos)} aviso(s)" if parsed.avisos else ""
        flash(f"NF-e {parsed.header['numero']} importada ({tipo}{extra}){aviso}.", "success")

    if importadas == 1:
        # uma nota só: abre direto o detalhe dela
        return redirect(url_for("notas.detail", nfe_id=nfe_id))
    mes = ultima_emissao.strftime("%Y-%m") if ultima_emissao else None
    return redirect(url_for("notas.index", mes=mes))


@bp.route("/<int:nfe_id>")
def detail(nfe_id):
    nota = db.get_nfe(g.user["id"], nfe_id)
    if not nota:
        abort(404)
    impostos = [
        ("ICMS", nota["v_icms"]), ("ICMS-ST", nota["v_st"]), ("IPI", nota["v_ipi"]),
        ("PIS", nota["v_pis"]), ("COFINS", nota["v_cofins"]),
        ("IBS", nota["v_ibs"]), ("CBS", nota["v_cbs"]),
    ]
    return render_template(
        "nota_detalhe.html",
        nota=nota,
        impostos=impostos,
        total_impostos=sum((v for _, v in impostos), Decimal(0)),
        previa=build_launches(nota, nota["duplicatas"]) if not nota["tem_lancamentos"] else [],
        ambientes=nfe.AMBIENTES,
    )


@bp.route("/<int:nfe_id>/xml")
def download(nfe_id):
    nota = db.get_nfe(g.user["id"], nfe_id)
    if not nota:
        abort(404)
    return Response(
        nota["xml"],
        mimetype="application/xml",
        headers={"Content-Disposition": f'attachment; filename="NFe{nota["chave"]}.xml"'},
    )


@bp.route("/<int:nfe_id>/lancamentos", methods=["POST"])
def launches(nfe_id):
    nota = db.get_nfe(g.user["id"], nfe_id)
    if not nota:
        abort(404)
    criados = db.create_nfe_launches(g.user["id"], nfe_id, build_launches(nota, nota["duplicatas"]))
    if criados:
        flash(f"{criados} lançamento(s) criado(s) na aba Gastos.", "success")
    else:
        flash("Esta nota já possui lançamentos.", "danger")
    return redirect(url_for("notas.detail", nfe_id=nfe_id))


@bp.route("/<int:nfe_id>/excluir", methods=["POST"])
def delete(nfe_id):
    nota = db.get_nfe(g.user["id"], nfe_id)
    if not nota or not db.delete_nfe(g.user["id"], nfe_id):
        abort(404)
    flash(f"NF-e {nota['numero']} excluída"
          f"{' junto com seus lançamentos' if nota['tem_lancamentos'] else ''}.", "success")
    return redirect(url_for("notas.index", mes=nota["emissao"].strftime("%Y-%m")))
