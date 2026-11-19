"""Gera XMLs de NF-e de exemplo (fictícios) para testes manuais e automáticos.

    py samples/nfe/gerar_amostras.py

Empresa do cliente demo (seed_demo.py): DOCE SABOR CONFEITARIA — CNPJ em DEMO_CNPJ.
Os CNPJs, chaves e protocolos são fictícios, mas com dígitos verificadores válidos.
Nenhum XML é assinado (o MVP não verifica assinatura).
"""
import re
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent


def cnpj_dv(base12):
    def dv(base, pesos):
        resto = sum(int(a) * b for a, b in zip(base, pesos)) % 11
        return 0 if resto < 2 else 11 - resto
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = dv(base12, p1)
    return base12 + str(d1) + str(dv(base12 + str(d1), [6] + p1))


def chave(cuf, aamm, cnpj, serie, numero, cnf):
    c43 = f"{cuf}{aamm}{cnpj}55{serie:03d}{numero:09d}1{cnf:08d}"
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    resto = sum(int(d) * pesos[i % 8] for i, d in enumerate(reversed(c43))) % 11
    return c43 + str(0 if resto < 2 else 11 - resto)


DEMO_CNPJ = cnpj_dv("457231740001")        # Doce Sabor Confeitaria (cliente demo)
MOINHO_CNPJ = cnpj_dv("118765430001")      # fornecedor de farinha
EMBALA_CNPJ = cnpj_dv("230984560001")      # fornecedor de embalagens
CAFE_CNPJ = cnpj_dv("334455660001")        # cliente PJ (cafeteria)


def item(n, cprod, xprod, ncm, cfop, un, q, vun, icms_xml, extra_imp=""):
    vprod = round(q * vun, 2)
    return f"""
    <det nItem="{n}">
      <prod>
        <cProd>{cprod}</cProd><cEAN>SEM GTIN</cEAN><xProd>{xprod}</xProd>
        <NCM>{ncm}</NCM><CFOP>{cfop}</CFOP><uCom>{un}</uCom>
        <qCom>{q:.4f}</qCom><vUnCom>{vun:.10f}</vUnCom><vProd>{vprod:.2f}</vProd>
        <cEANTrib>SEM GTIN</cEANTrib><uTrib>{un}</uTrib><qTrib>{q:.4f}</qTrib>
        <vUnTrib>{vun:.10f}</vUnTrib><indTot>1</indTot>
      </prod>
      <imposto>
        <ICMS>{icms_xml}</ICMS>{extra_imp}
      </imposto>
    </det>""", vprod


def nfe_xml(ch, numero, dh, tpnf, natop, emit, dest, itens, totais, cobr="", protocolo=None, tpamb=1, extra_total=""):
    infnfe = f"""<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe Id="NFe{ch}" versao="4.00">
    <ide>
      <cUF>{ch[:2]}</cUF><cNF>{ch[35:43]}</cNF><natOp>{natop}</natOp><mod>55</mod>
      <serie>{int(ch[22:25])}</serie><nNF>{numero}</nNF><dhEmi>{dh}</dhEmi><tpNF>{tpnf}</tpNF>
      <idDest>1</idDest><cMunFG>5208707</cMunFG><tpImp>1</tpImp><tpEmis>1</tpEmis>
      <cDV>{ch[-1]}</cDV><tpAmb>{tpamb}</tpAmb><finNFe>1</finNFe><indFinal>0</indFinal>
      <indPres>9</indPres><procEmi>0</procEmi><verProc>1.0.0</verProc>
    </ide>
    {emit}
    {dest}
    {''.join(itens)}
    <total>
      <ICMSTot>{totais}</ICMSTot>{extra_total}
    </total>
    <transp><modFrete>0</modFrete></transp>
    {cobr}
    <pag><detPag><tPag>15</tPag><vPag>{totais.split('<vNF>')[1].split('<')[0]}</vPag></detPag></pag>
  </infNFe>
</NFe>"""
    if protocolo is None:
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + infnfe
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
{infnfe}
<protNFe versao="4.00">
  <infProt>
    <tpAmb>{tpamb}</tpAmb><verAplic>SVRS202611</verAplic><chNFe>{ch}</chNFe>
    <dhRecbto>{dh}</dhRecbto><nProt>{protocolo}</nProt><cStat>100</cStat>
    <xMotivo>Autorizado o uso da NF-e</xMotivo>
  </infProt>
</protNFe>
</nfeProc>"""


def party(tag, doc, nome, uf="GO", ie="ISENTO", crt=None):
    doc_tag = "CNPJ" if len(doc) == 14 else "CPF"
    ender = "enderEmit" if tag == "emit" else "enderDest"
    crt_xml = f"<CRT>{crt}</CRT>" if crt else ""
    ie_xml = f"<IE>{ie}</IE>" if tag == "emit" else ("<indIEDest>9</indIEDest>" if ie == "ISENTO" else f"<indIEDest>1</indIEDest><IE>{ie}</IE>")
    return f"""<{tag}>
      <{doc_tag}>{doc}</{doc_tag}><xNome>{nome}</xNome>
      <{ender}><xLgr>RUA EXEMPLO</xLgr><nro>10</nro><xBairro>CENTRO</xBairro>
        <cMun>5208707</cMun><xMun>GOIANIA</xMun><UF>{uf}</UF><CEP>74000000</CEP></{ender}>
      {ie_xml}{crt_xml}
    </{tag}>"""


def totais(vprod, vbc=0, vicms=0, vst=0, vbcst=0, vipi=0, vpis=0, vcofins=0, vfrete=0, vdesc=0):
    vnf = vprod + vst + vipi + vfrete - vdesc
    return (f"<vBC>{vbc:.2f}</vBC><vICMS>{vicms:.2f}</vICMS><vICMSDeson>0.00</vICMSDeson><vFCP>0.00</vFCP>"
            f"<vBCST>{vbcst:.2f}</vBCST><vST>{vst:.2f}</vST><vFCPST>0.00</vFCPST><vFCPSTRet>0.00</vFCPSTRet>"
            f"<vProd>{vprod:.2f}</vProd><vFrete>{vfrete:.2f}</vFrete><vSeg>0.00</vSeg><vDesc>{vdesc:.2f}</vDesc>"
            f"<vII>0.00</vII><vIPI>{vipi:.2f}</vIPI><vIPIDevol>0.00</vIPIDevol><vPIS>{vpis:.2f}</vPIS>"
            f"<vCOFINS>{vcofins:.2f}</vCOFINS><vOutro>0.00</vOutro><vNF>{vnf:.2f}</vNF>"), round(vnf, 2)


def compra_farinha(hoje):
    """Compra de insumos, regime normal (ICMS00 + IPI + PIS/COFINS), autorizada, 3 parcelas."""
    dh = (hoje - timedelta(days=4)).strftime("%Y-%m-%dT09:15:00-03:00")
    ch = chave("52", hoje.strftime("%y%m"), MOINHO_CNPJ, 1, 45871, 70412233)
    icms = lambda vbc: f"<ICMS00><orig>0</orig><CST>00</CST><modBC>3</modBC><vBC>{vbc:.2f}</vBC><pICMS>12.00</pICMS><vICMS>{vbc*0.12:.2f}</vICMS></ICMS00>"
    def pis_cofins(v):
        return (f"<IPI><cEnq>999</cEnq><IPITrib><CST>50</CST><vBC>{v:.2f}</vBC><pIPI>0.00</pIPI><vIPI>0.00</vIPI></IPITrib></IPI>"
                f"<PIS><PISAliq><CST>01</CST><vBC>{v:.2f}</vBC><pPIS>1.65</pPIS><vPIS>{v*0.0165:.2f}</vPIS></PISAliq></PIS>"
                f"<COFINS><COFINSAliq><CST>01</CST><vBC>{v:.2f}</vBC><pCOFINS>7.60</pCOFINS><vCOFINS>{v*0.076:.2f}</vCOFINS></COFINSAliq></COFINS>")
    i1, v1 = item(1, "FT-25", "FARINHA DE TRIGO TIPO 1 25KG", "11010010", "5101", "SC", 40, 89.90, icms(40 * 89.90), pis_cofins(40 * 89.90))
    i2, v2 = item(2, "AC-50", "ACUCAR REFINADO 50KG", "17019900", "5101", "SC", 12, 215.00, icms(12 * 215.00), pis_cofins(12 * 215.00))
    vprod = v1 + v2
    tot, vnf = totais(vprod, vbc=vprod, vicms=round(v1 * .12, 2) + round(v2 * .12, 2),
                      vpis=round(v1 * .0165, 2) + round(v2 * .0165, 2), vcofins=round(v1 * .076, 2) + round(v2 * .076, 2))
    p = round(vnf / 3, 2)
    parcelas = [p, p, round(vnf - 2 * p, 2)]
    dups = "".join(f"<dup><nDup>{i:03d}</nDup><dVenc>{(hoje + timedelta(days=30 * (i - 1) + 10)).isoformat()}</dVenc><vDup>{v:.2f}</vDup></dup>"
                   for i, v in enumerate(parcelas, 1))
    cobr = f"<cobr><fat><nFat>45871</nFat><vOrig>{vnf:.2f}</vOrig><vDesc>0.00</vDesc><vLiq>{vnf:.2f}</vLiq></fat>{dups}</cobr>"
    return nfe_xml(ch, 45871, dh, 1, "VENDA DE PRODUCAO DO ESTABELECIMENTO",
                   party("emit", MOINHO_CNPJ, "MOINHO CERRADO ALIMENTOS LTDA", ie="104455667", crt=3),
                   party("dest", DEMO_CNPJ, "DOCE SABOR CONFEITARIA LTDA", ie="109988776"),
                   [i1, i2], tot, cobr=cobr, protocolo="152260000123456")


def venda_cafeteria(hoje):
    """Venda da Doce Sabor (Simples Nacional, CSOSN 101/102) para cliente PJ, autorizada, à vista."""
    dh = (hoje - timedelta(days=2)).strftime("%Y-%m-%dT15:40:00-03:00")
    ch = chave("52", hoje.strftime("%y%m"), DEMO_CNPJ, 1, 318, 10203040)
    sn101 = lambda v: f"<ICMSSN101><orig>0</orig><CSOSN>101</CSOSN><pCredSN>1.25</pCredSN><vCredICMSSN>{v*0.0125:.2f}</vCredICMSSN></ICMSSN101>"
    sn102 = "<ICMSSN102><orig>0</orig><CSOSN>102</CSOSN></ICMSSN102>"
    i1, v1 = item(1, "BOLO-CH", "BOLO DE CHOCOLATE 2KG", "19059090", "5101", "UN", 6, 120.00, sn101(720))
    i2, v2 = item(2, "SALG-100", "KIT 100 SALGADOS SORTIDOS", "19059090", "5101", "KIT", 4, 95.00, sn102)
    i3, v3 = item(3, "DOCE-50", "BANDEJA 50 DOCES FINOS", "17049020", "5101", "UN", 3, 140.00, sn102)
    tot, _ = totais(v1 + v2 + v3)
    return nfe_xml(ch, 318, dh, 1, "VENDA DE PRODUCAO DO ESTABELECIMENTO",
                   party("emit", DEMO_CNPJ, "DOCE SABOR CONFEITARIA LTDA", ie="109988776", crt=1),
                   party("dest", CAFE_CNPJ, "CAFETERIA GRAO DOURADO LTDA", ie="108877665"),
                   [i1, i2, i3], tot, protocolo="152260000654321")


def compra_embalagens_reforma(hoje):
    """Compra com ICMS-ST (ICMS10), isento (ICMS40) e grupos IBS/CBS da Reforma Tributária."""
    dh = (hoje - timedelta(days=1)).strftime("%Y-%m-%dT11:05:00-03:00")
    ch = chave("35", hoje.strftime("%y%m"), EMBALA_CNPJ, 2, 9902, 55667788)
    st = (lambda v: f"<ICMS10><orig>0</orig><CST>10</CST><modBC>3</modBC><vBC>{v:.2f}</vBC><pICMS>18.00</pICMS>"
                    f"<vICMS>{v*.18:.2f}</vICMS><modBCST>4</modBCST><pMVAST>40.00</pMVAST><vBCST>{v*1.4:.2f}</vBCST>"
                    f"<pICMSST>18.00</pICMSST><vICMSST>{v*1.4*.18 - v*.18:.2f}</vICMSST></ICMS10>")
    isento = "<ICMS40><orig>0</orig><CST>40</CST></ICMS40>"
    def ibscbs(v):
        return (f"<IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib><gIBSCBS><vBC>{v:.2f}</vBC>"
                f"<gIBSUF><pIBSUF>0.1000</pIBSUF><vIBSUF>{v*.001:.2f}</vIBSUF></gIBSUF>"
                f"<gIBSMun><pIBSMun>0.0000</pIBSMun><vIBSMun>0.00</vIBSMun></gIBSMun><vIBS>{v*.001:.2f}</vIBS>"
                f"<gCBS><pCBS>0.9000</pCBS><vCBS>{v*.009:.2f}</vCBS></gCBS></gIBSCBS></IBSCBS>")
    i1, v1 = item(1, "CX-BOLO", "CAIXA PARA BOLO 30X30 (PCT 50)", "48191000", "6401", "PCT", 10, 64.00, st(640), ibscbs(640))
    i2, v2 = item(2, "FITA-CET", "FITA DE CETIM DECORATIVA (ROLO)", "58063200", "6102", "UN", 20, 7.50, isento, ibscbs(150))
    vprod = v1 + v2
    vst = round(640 * 1.4 * .18 - 640 * .18, 2)
    tot, vnf = totais(vprod, vbc=640, vicms=round(640 * .18, 2), vbcst=round(640 * 1.4, 2), vst=vst, vfrete=35.00)
    vibs, vcbs = round(vprod * .001, 2), round(vprod * .009, 2)
    ibstot = (f"<IBSCBSTot><vBCIBSCBS>{vprod:.2f}</vBCIBSCBS><gIBS><gIBSUF><vDif>0.00</vDif><vDevTrib>0.00</vDevTrib>"
              f"<vIBSUF>{vibs:.2f}</vIBSUF></gIBSUF><gIBSMun><vDif>0.00</vDif><vDevTrib>0.00</vDevTrib><vIBSMun>0.00</vIBSMun></gIBSMun>"
              f"<vIBS>{vibs:.2f}</vIBS><vCredPres>0.00</vCredPres><vCredPresCondSus>0.00</vCredPresCondSus></gIBS>"
              f"<gCBS><vDif>0.00</vDif><vDevTrib>0.00</vDevTrib><vCBS>{vcbs:.2f}</vCBS><vCredPres>0.00</vCredPres>"
              f"<vCredPresCondSus>0.00</vCredPresCondSus></gCBS></IBSCBSTot>")
    dup = f"<cobr><dup><nDup>001</nDup><dVenc>{(hoje + timedelta(days=21)).isoformat()}</dVenc><vDup>{vnf:.2f}</vDup></dup></cobr>"
    return nfe_xml(ch, 9902, dh, 1, "VENDA DE MERCADORIA",
                   party("emit", EMBALA_CNPJ, "EMBALA FACIL INDUSTRIA DE EMBALAGENS LTDA", uf="SP", ie="112233445566", crt=3),
                   party("dest", DEMO_CNPJ, "DOCE SABOR CONFEITARIA LTDA", ie="109988776"),
                   [i1, i2], tot, cobr=dup, protocolo="135260000999888", extra_total=ibstot)


INVALIDOS = {
    # modelo 65 (NFC-e) não é aceito
    "invalida_modelo65.xml": lambda x: x.replace("<mod>55</mod>", "<mod>65</mod>"),
    # leiaute antigo
    "invalida_versao310.xml": lambda x: re.sub(r'(<infNFe [^>]*)versao="4.00"', r'\1versao="3.10"', x),
    # tentativa de XXE (entidade externa) — deve ser bloqueada pelo defusedxml
    "invalida_xxe.xml": lambda x: x.replace('<?xml version="1.0" encoding="UTF-8"?>',
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE NFe [<!ENTITY xxe SYSTEM "file:///c:/windows/win.ini">]>')
        .replace("<natOp>VENDA DE PRODUCAO DO ESTABELECIMENTO</natOp>", "<natOp>&xxe;</natOp>"),
}


def main():
    hoje = date.today()
    amostras = {
        "compra_insumos_autorizada.xml": compra_farinha(hoje),
        "venda_cliente_pj_simples.xml": venda_cafeteria(hoje),
        "compra_embalagens_ibs_cbs.xml": compra_embalagens_reforma(hoje),
    }
    for nome, fn in INVALIDOS.items():
        amostras[nome] = fn(amostras["venda_cliente_pj_simples.xml"])
    amostras["invalida_nao_e_nfe.xml"] = '<?xml version="1.0"?>\n<pedido><numero>1</numero></pedido>'

    for nome, conteudo in amostras.items():
        (HERE / nome).write_text(conteudo, encoding="utf-8")
        print("gerado", nome)
    print("CNPJ da empresa demo:", DEMO_CNPJ)


if __name__ == "__main__":
    main()
