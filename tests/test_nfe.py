"""Testes do leitor de NF-e e da geração de lançamentos (não precisam de banco).

    py -m unittest discover -s tests -v
"""
import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "samples" / "nfe"))

import gerar_amostras as amostras  # noqa: E402
from contability.services import nfe  # noqa: E402

HOJE = date(2026, 11, 18)


def parse(xml_str):
    return nfe.parse_nfe(xml_str.encode("utf-8"))


class TestDigitos(unittest.TestCase):

    def test_cnpj(self):
        self.assertTrue(nfe.cnpj_valido(amostras.DEMO_CNPJ))
        self.assertFalse(nfe.cnpj_valido("12345678000199"))
        self.assertFalse(nfe.cnpj_valido("11111111111111"))
        self.assertFalse(nfe.cnpj_valido("123"))

    def test_chave(self):
        ch = amostras.chave("52", "2611", amostras.DEMO_CNPJ, 1, 318, 10203040)
        self.assertEqual(nfe.chave_dv(ch[:43]), int(ch[43]))


class TestLeitura(unittest.TestCase):

    def test_exemplo_do_usuario(self):
        p = nfe.parse_nfe((ROOT / "samples/nfe/exemplo_usuario_venda_sn.xml").read_bytes())
        h = p.header
        self.assertEqual((h["numero"], h["serie"], h["versao"]), (123, 1, "4.00"))
        self.assertEqual(h["v_total"], Decimal("150.00"))
        self.assertEqual(p.items[0]["icms_cst"], "102")
        self.assertIsNone(h["protocolo"])
        self.assertEqual(len(p.avisos), 3)  # DV da chave, homologação, sem protocolo
        self.assertEqual(nfe.classify(p, "12345678000199"), "saida")

    def test_compra_autorizada_com_parcelas(self):
        p = parse(amostras.compra_farinha(HOJE))
        h = p.header
        self.assertEqual(h["protocolo"], "152260000123456")
        self.assertEqual(p.avisos, [])
        self.assertEqual(len(p.items), 2)
        self.assertEqual(len(p.duplicatas), 3)
        self.assertEqual(sum(d["valor"] for d in p.duplicatas), h["v_total"])
        self.assertEqual(p.items[0]["icms_cst"], "00")
        self.assertGreater(h["v_icms"], 0)
        self.assertGreater(h["v_pis"], 0)
        self.assertEqual(nfe.classify(p, amostras.DEMO_CNPJ), "entrada")

    def test_reforma_tributaria_e_variantes_de_icms(self):
        p = parse(amostras.compra_embalagens_reforma(HOJE))
        h = p.header
        self.assertEqual([i["icms_cst"] for i in p.items], ["10", "40"])
        self.assertGreater(h["v_st"], 0)
        self.assertEqual(h["v_frete"], Decimal("35.00"))
        self.assertEqual(h["v_ibs"], Decimal("0.79"))
        self.assertEqual(h["v_cbs"], Decimal("7.11"))
        # IBS/CBS por item vêm do primeiro vIBS/vCBS do grupo (sem contar em dobro)
        self.assertEqual(p.items[0]["ibs_valor"], Decimal("0.64"))
        self.assertEqual(p.items[0]["cbs_valor"], Decimal("5.76"))

    def test_venda_simples_nacional(self):
        p = parse(amostras.venda_cafeteria(HOJE))
        self.assertEqual([i["icms_cst"] for i in p.items], ["101", "102", "102"])
        self.assertEqual(p.duplicatas, [])
        self.assertEqual(nfe.classify(p, amostras.DEMO_CNPJ), "saida")


class TestRecusa(unittest.TestCase):

    def base(self):
        return amostras.venda_cafeteria(HOJE)

    def assertRecusa(self, xml, trecho):
        with self.assertRaises(nfe.NFeError) as ctx:
            parse(xml)
        self.assertIn(trecho, str(ctx.exception))

    def test_modelo_65(self):
        self.assertRecusa(amostras.INVALIDOS["invalida_modelo65.xml"](self.base()), "Modelo 65")

    def test_versao_antiga(self):
        self.assertRecusa(amostras.INVALIDOS["invalida_versao310.xml"](self.base()), "3.10")

    def test_xxe_bloqueado(self):
        self.assertRecusa(amostras.INVALIDOS["invalida_xxe.xml"](self.base()), "não permitidas")

    def test_bomba_de_entidades(self):
        xml = ('<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa">'
               '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]><NFe>&b;</NFe>')
        self.assertRecusa(xml, "não permitidas")

    def test_nao_e_xml(self):
        self.assertRecusa("isto não é xml", "não é um XML válido")

    def test_outro_documento(self):
        self.assertRecusa('<pedido><n>1</n></pedido>', "namespace")

    def test_sem_itens(self):
        xml = self.base()
        inicio, fim = xml.index("<det "), xml.rindex("</det>") + len("</det>")
        self.assertRecusa(xml[:inicio] + xml[fim:], "não possui itens")

    def test_tamanho(self):
        with self.assertRaises(nfe.NFeError):
            nfe.parse_nfe(b" " * (nfe.MAX_XML_BYTES + 1))

    def test_nota_de_terceiros(self):
        p = parse(self.base())
        with self.assertRaises(nfe.NFeError):
            nfe.classify(p, "11222333000181")


class TestLancamentos(unittest.TestCase):

    def setUp(self):
        from contability.routes import notas  # importa Flask; só aqui para os outros testes rodarem sem ele
        self.build = notas.build_launches

    def test_compra_em_parcelas(self):
        p = parse(amostras.compra_farinha(HOJE))
        p.header["direcao"] = "entrada"
        ls = self.build(p.header, p.duplicatas, today=HOJE)
        self.assertEqual(len(ls), 3)
        self.assertTrue(all(l["type"] == "expense" and l["category"] == "Operacional" for l in ls))
        self.assertTrue(all(l["status"] == "pending" for l in ls))  # vencimentos futuros
        self.assertEqual(sum(l["amount"] for l in ls), p.header["v_total"])
        self.assertTrue(ls[0]["description"].endswith("(1/3)"))
        self.assertIn("MOINHO CERRADO", ls[0]["description"])

    def test_venda_a_vista(self):
        p = parse(amostras.venda_cafeteria(HOJE))
        p.header["direcao"] = "saida"
        ls = self.build(p.header, p.duplicatas, today=HOJE)
        self.assertEqual(len(ls), 1)
        self.assertEqual((ls[0]["type"], ls[0]["category"], ls[0]["status"]), ("income", "Vendas", "done"))
        self.assertEqual(ls[0]["date"], HOJE - timedelta(days=2))
        self.assertIn("CAFETERIA", ls[0]["description"])


if __name__ == "__main__":
    unittest.main()
