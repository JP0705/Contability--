"""Cadastro mínimo da empresa do usuário (CNPJ e razão social)."""
import re

import psycopg2
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .. import db
from ..services.nfe import cnpj_valido

bp = Blueprint("empresa", __name__, url_prefix="/empresa")


def init_app(app):
    app.register_blueprint(bp)

    @app.template_filter("cnpj")
    def format_cnpj(value):
        v = re.sub(r"\D", "", value or "")
        if len(v) == 14:
            return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}"
        if len(v) == 11:  # CPF
            return f"{v[:3]}.{v[3:6]}.{v[6:9]}-{v[9:]}"
        return value or ""


@bp.route("/", methods=["GET", "POST"])
def index():
    company = db.get_company(g.user["id"])
    next_url = request.args.get("next")

    if request.method == "POST":
        cnpj = re.sub(r"\D", "", request.form.get("cnpj", ""))
        razao = request.form.get("razao_social", "").strip()

        errors = []
        if len(cnpj) != 14:
            errors.append("O CNPJ deve ter 14 dígitos.")
        if not razao:
            errors.append("Informe a razão social.")
        elif len(razao) > 200:
            errors.append("Razão social muito longa (máx. 200 caracteres).")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("empresa/index.html", company={"cnpj": cnpj, "razao_social": razao}), 400

        try:
            db.save_company(g.user["id"], cnpj, razao)
        except psycopg2.Error:
            flash("Banco de dados indisponível. Tente novamente em instantes.", "danger")
            return render_template("empresa/index.html", company={"cnpj": cnpj, "razao_social": razao}), 503

        if cnpj_valido(cnpj):
            flash("Dados da empresa salvos.", "success")
        else:
            # aceito para permitir testes com XMLs de exemplo, mas avisa
            flash("Dados salvos, mas o dígito verificador do CNPJ não confere. Confira o número.", "danger")

        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
        return redirect(url_for("empresa.index"))

    return render_template("empresa/index.html", company=company)
