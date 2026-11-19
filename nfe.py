"""Leitura e validação de XML de NF-e (modelo 55).

Estratégia do MVP: o XML original é guardado inteiro e só os campos
essenciais são extraídos. Grupos opcionais ausentes (frete, IPI, PIS,
cobrança, IBS/CBS...) viram zero/vazio em vez de erro.

Aceita tanto o XML autorizado (<nfeProc> com <NFe> + <protNFe>) quanto o
<NFe> "puro" (sem protocolo); este último entra com aviso.

    resultado = parse_nfe(xml_bytes)          # levanta NFeError se inválido
    resultado.header / .items / .duplicatas / .avisos
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException
from xml.etree.ElementTree import ParseError

NS = "http://www.portalfiscal.inf.br/nfe"
N = {"n": NS}

# versões de leiaute aceitas (atributo versao de <infNFe>)
ACCEPTED_VERSIONS = {"4.00"}
MODELO = "55"
MAX_XML_BYTES = 2 * 1024 * 1024  # 2 MB por arquivo

AMBIENTES = {"1": "Produção", "2": "Homologação"}


class NFeError(ValueError):
    """XML recusado (mensagem pronta para mostrar ao usuário)."""


@dataclass
class ParsedNFe:
    header: dict
    items: list
    duplicatas: list
    avisos: list = field(default_factory=list)
    emit_doc: str = ""
    dest_doc: str = ""
    tp_nf: str = ""


# =========================
# AUXILIARES
# =========================

def _find(node, path):
    return node.find(path, N) if node is not None else None


def _text(node, path, default=None):
    el = _find(node, path)
    if el is None or el.text is None:
        return default
    return el.text.strip()


def _dec(node, path, default="0"):
    raw = _text(node, path)
    try:
        return Decimal(raw) if raw not in (None, "") else Decimal(default)
    except InvalidOperation:
        return Decimal(default)


def _doc(node):
    """CNPJ ou CPF (o que existir) de emit/dest."""
    return _text(node, "n:CNPJ") or _text(node, "n:CPF") or _text(node, "n:idEstrangeiro") or ""


def _first_child(node):
    """Primeiro filho de um grupo com variantes (ex.: <ICMS><ICMSSN102>...)."""
    if node is None:
        return None
    for child in node:
        return child
    return None


def _first_desc(node, local_name):
    """Valor do primeiro descendente com esse nome local, em qualquer profundidade.

    Usado nos grupos da Reforma Tributária (IBSCBS / IBSCBSTot), cuja estrutura
    interna ainda muda entre Notas Técnicas: pegamos o primeiro vIBS/vCBS
    encontrado em vez de somar todos (evita contar o mesmo valor duas vezes).
    """
    if node is None:
        return Decimal(0)
    for el in node.iter(f"{{{NS}}}{local_name}"):
        try:
            return Decimal((el.text or "0").strip())
        except InvalidOperation:
            return Decimal(0)
    return Decimal(0)


def chave_dv(chave43):
    """Dígito verificador da chave de acesso (módulo 11, pesos 2..9)."""
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = sum(int(d) * pesos[i % 8] for i, d in enumerate(reversed(chave43)))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def cnpj_valido(cnpj):
    if not re.fullmatch(r"\d{14}", cnpj or "") or len(set(cnpj)) == 1:
        return False

    def dv(base, pesos):
        resto = sum(int(a) * b for a, b in zip(base, pesos)) % 11
        return 0 if resto < 2 else 11 - resto

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = dv(cnpj[:12], p1)
    d2 = dv(cnpj[:12] + str(d1), [6] + p1)
    return cnpj[-2:] == f"{d1}{d2}"


def _parse_datetime(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _parse_date(raw):
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


# =========================
# LEITURA
# =========================

def _load(xml_bytes):
    if len(xml_bytes) > MAX_XML_BYTES:
        raise NFeError("Arquivo grande demais para uma NF-e (máx. 2 MB).")
    try:
        # defusedxml bloqueia DTD/entidades (XXE, "bomba de entidades")
        return SafeET.fromstring(xml_bytes, forbid_dtd=True)
    except (DefusedXmlException, ValueError):
        raise NFeError("O XML contém declarações não permitidas (DTD/entidades).")
    except ParseError:
        raise NFeError("O arquivo não é um XML válido.")


def _locate(root):
    """Retorna (<NFe>, <protNFe> ou None) a partir da raiz."""
    tag = root.tag
    if tag == f"{{{NS}}}nfeProc":
        return _find(root, "n:NFe"), _find(root, "n:protNFe")
    if tag == f"{{{NS}}}NFe":
        return root, None
    if not tag.startswith(f"{{{NS}}}"):
        raise NFeError("O XML não usa o namespace da NF-e (portalfiscal.inf.br/nfe).")
    local = tag.split("}")[-1]
    raise NFeError(f"Documento <{local}> não é uma NF-e (esperado <NFe> ou <nfeProc>).")


def parse_nfe(xml_bytes):
    root = _load(xml_bytes)
    nfe_el, prot = _locate(root)
    inf = _find(nfe_el, "n:infNFe")
    if inf is None:
        raise NFeError("Grupo <infNFe> não encontrado.")

    avisos = []

    # ---------- versão, modelo e chave ----------
    versao = inf.get("versao", "")
    if versao not in ACCEPTED_VERSIONS:
        raise NFeError(f"Versão de leiaute {versao or '(ausente)'} não suportada "
                       f"(aceitas: {', '.join(sorted(ACCEPTED_VERSIONS))}).")

    ide = _find(inf, "n:ide")
    modelo = _text(ide, "n:mod")
    if modelo != MODELO:
        raise NFeError(f"Modelo {modelo or '(ausente)'} não suportado — apenas NF-e modelo 55.")

    chave = (inf.get("Id") or "").removeprefix("NFe")
    if not re.fullmatch(r"\d{44}", chave):
        raise NFeError("Chave de acesso ausente ou inválida (atributo Id de <infNFe>).")
    if chave_dv(chave[:43]) != int(chave[43]):
        avisos.append("Dígito verificador da chave de acesso não confere.")

    numero = _text(ide, "n:nNF")
    serie = _text(ide, "n:serie")
    emissao = _parse_datetime(_text(ide, "n:dhEmi"))
    if not (numero and numero.isdigit()) or not (serie and serie.isdigit()) or emissao is None:
        raise NFeError("Número, série ou data de emissão ausentes/inválidos em <ide>.")

    ambiente = _text(ide, "n:tpAmb", "1")
    if ambiente == "2":
        avisos.append("Nota emitida em ambiente de homologação (teste), sem valor fiscal.")

    # ---------- emitente / destinatário ----------
    emit = _find(inf, "n:emit")
    dest = _find(inf, "n:dest")
    emit_doc = _doc(emit)
    if not emit_doc or not _text(emit, "n:xNome"):
        raise NFeError("Emitente sem CNPJ/CPF ou nome.")

    # ---------- protocolo de autorização ----------
    protocolo = status = None
    if prot is not None:
        inf_prot = _find(prot, "n:infProt")
        protocolo = _text(inf_prot, "n:nProt")
        status = _text(inf_prot, "n:cStat")
        if status not in ("100", "150"):
            motivo = _text(inf_prot, "n:xMotivo", "")
            avisos.append(f"Protocolo com situação {status} ({motivo}) — nota não autorizada.")
    else:
        avisos.append("XML sem protocolo de autorização da SEFAZ (<protNFe>).")

    # ---------- itens ----------
    items = []
    for det in inf.findall("n:det", N):
        prod = _find(det, "n:prod")
        imp = _find(det, "n:imposto")
        icms = _first_child(_find(imp, "n:ICMS"))
        ipi_trib = _find(imp, "n:IPI/n:IPITrib")
        items.append({
            "n_item": int(det.get("nItem", len(items) + 1)),
            "codigo": _text(prod, "n:cProd"),
            "descricao": (_text(prod, "n:xProd") or "(sem descrição)")[:200],
            "ncm": _text(prod, "n:NCM"),
            "cfop": _text(prod, "n:CFOP"),
            "unidade": (_text(prod, "n:uCom") or "")[:10] or None,
            "quantidade": _dec(prod, "n:qCom"),
            "valor_unitario": _dec(prod, "n:vUnCom"),
            "valor_total": _dec(prod, "n:vProd"),
            # ICMS vem em ~17 variantes; lemos os campos comuns de qualquer uma
            "icms_cst": _text(icms, "n:CST") or _text(icms, "n:CSOSN"),
            "icms_valor": _dec(icms, "n:vICMS"),
            "ipi_valor": _dec(ipi_trib, "n:vIPI"),
            "pis_valor": _dec(_first_child(_find(imp, "n:PIS")), "n:vPIS"),
            "cofins_valor": _dec(_first_child(_find(imp, "n:COFINS")), "n:vCOFINS"),
            # Reforma Tributária (grupo IBSCBS); ausente em notas antigas
            "ibs_valor": _first_desc(_find(imp, "n:IBSCBS"), "vIBS"),
            "cbs_valor": _first_desc(_find(imp, "n:IBSCBS"), "vCBS"),
        })
    if not items:
        raise NFeError("A nota não possui itens (<det>).")

    # ---------- totais ----------
    tot = _find(inf, "n:total/n:ICMSTot")
    if tot is None:
        raise NFeError("Totais da nota (<ICMSTot>) não encontrados.")
    ibscbs_tot = _find(inf, "n:total/n:IBSCBSTot")
    v_total = _dec(tot, "n:vNF")

    soma_itens = sum((i["valor_total"] for i in items), Decimal(0))
    if soma_itens != _dec(tot, "n:vProd"):
        avisos.append("Soma dos itens difere do total de produtos informado na nota.")

    # ---------- cobrança (parcelas) ----------
    duplicatas = []
    for dup in inf.findall("n:cobr/n:dup", N):
        venc = _parse_date(_text(dup, "n:dVenc"))
        valor = _dec(dup, "n:vDup")
        if venc and valor > 0:
            duplicatas.append({"numero": _text(dup, "n:nDup"), "vencimento": venc, "valor": valor})

    header = {
        "chave": chave,
        "versao": versao,
        "numero": int(numero),
        "serie": int(serie),
        "emissao": emissao,
        "natureza": (_text(ide, "n:natOp") or "")[:120] or None,
        "direcao": None,  # definida por classify() com o CNPJ do usuário
        "ambiente": int(ambiente) if ambiente.isdigit() else 1,
        "emit_doc": emit_doc,
        "emit_nome": _text(emit, "n:xNome")[:200],
        "emit_uf": _text(emit, "n:enderEmit/n:UF"),
        "dest_doc": _doc(dest) or None,
        "dest_nome": (_text(dest, "n:xNome") or "")[:200] or None,
        "dest_uf": _text(dest, "n:enderDest/n:UF"),
        "v_produtos": _dec(tot, "n:vProd"),
        "v_desconto": _dec(tot, "n:vDesc"),
        "v_frete": _dec(tot, "n:vFrete"),
        "v_icms": _dec(tot, "n:vICMS"),
        "v_st": _dec(tot, "n:vST"),
        "v_ipi": _dec(tot, "n:vIPI"),
        "v_pis": _dec(tot, "n:vPIS"),
        "v_cofins": _dec(tot, "n:vCOFINS"),
        "v_ibs": _first_desc(ibscbs_tot, "vIBS") if ibscbs_tot is not None else sum((i["ibs_valor"] for i in items), Decimal(0)),
        "v_cbs": _first_desc(ibscbs_tot, "vCBS") if ibscbs_tot is not None else sum((i["cbs_valor"] for i in items), Decimal(0)),
        "v_total": v_total,
        "protocolo": protocolo,
        "status_sefaz": status,
        "avisos": avisos,
        "xml": xml_bytes.decode("utf-8", errors="replace"),
    }
    return ParsedNFe(header=header, items=items, duplicatas=duplicatas, avisos=avisos,
                     emit_doc=emit_doc, dest_doc=_doc(dest), tp_nf=_text(ide, "n:tpNF", "1"))


def classify(parsed, company_cnpj):
    """Define entrada/saída comparando com o CNPJ da empresa do usuário.

    - empresa é a emitente: saída (tpNF=1) ou entrada própria (tpNF=0, ex.: devolução/importação)
    - empresa é a destinatária: entrada (compra)
    - nenhum dos dois: a nota não pertence à empresa -> recusada
    """
    if parsed.emit_doc == company_cnpj:
        return "saida" if parsed.tp_nf == "1" else "entrada"
    if parsed.dest_doc == company_cnpj:
        return "entrada"
    raise NFeError("A nota não pertence à sua empresa: o CNPJ cadastrado não é o emitente nem o destinatário.")
