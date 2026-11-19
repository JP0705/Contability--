"""Testes de integração: consultoria (permissões, mensagens) e páginas "Em breve".

Usam o banco real com usuários temporários (apagados ao final).
São pulados se o PostgreSQL não estiver acessível.

    py -m unittest discover -s tests -v
"""
import re
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contability import db  # noqa: E402

try:
    db.init_db()
    DB_OK = True
except Exception:  # banco fora do ar
    DB_OK = False


@unittest.skipUnless(DB_OK, "PostgreSQL indisponível")
class TestConsultoria(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import app as flask_app
        cls.app = flask_app.app
        tag = uuid.uuid4().hex[:8]
        cls.emails = [f"cli-{tag}@t.test", f"outro-{tag}@t.test", f"acc-{tag}@t.test"]
        cls.client_a = cls._signup("Cliente A", cls.emails[0])
        cls.client_b = cls._signup("Cliente B", cls.emails[1])
        cls.acc_client = cls._signup("Contador Teste", cls.emails[2])
        acc_user = db.get_user_by_email(cls.emails[2])
        with db.cursor() as cur:
            cur.execute(
                """INSERT INTO accountants (user_id, name, crc, specialties, available)
                   VALUES (%s, 'Contador Teste', %s, ARRAY['Teste'], TRUE) RETURNING id""",
                (acc_user["id"], f"TT-{tag}"),
            )
            cls.acc_id = cur.fetchone()["id"]

    @classmethod
    def tearDownClass(cls):
        with db.cursor() as cur:
            cur.execute("DELETE FROM accountants WHERE id = %s", (cls.acc_id,))
            cur.execute("DELETE FROM users WHERE email = ANY(%s)", (cls.emails,))

    @classmethod
    def _signup(cls, name, email):
        c = cls.app.test_client()
        r = c.post("/cadastro", data={"name": name, "email": email,
                                      "password": "senhaTeste123", "confirm": "senhaTeste123"})
        assert r.status_code == 302, r.status_code
        return c

    def _thread(self):
        r = self.client_a.get(f"/especialistas/{self.acc_id}/conversar")
        self.assertEqual(r.status_code, 302)
        return int(re.search(r"/conversas/(\d+)", r.headers["Location"]).group(1))

    def test_diretorio(self):
        with db.cursor() as cur:
            cur.execute("UPDATE accountants SET rating = 4.5 WHERE id = %s", (self.acc_id,))
        r = self.client_a.get("/especialistas/")
        self.assertEqual(r.status_code, 200)
        html = r.get_data(as_text=True)
        self.assertIn("Contador Teste", html)
        self.assertIn("4,5", html)
        self.assertIn(f"/especialistas/{self.acc_id}/conversar", html)

    def test_fluxo_completo(self):
        cid = self._thread()
        self.assertEqual(self._thread(), cid)  # mesma conversa ao clicar de novo

        r = self.client_a.post(f"/conversas/{cid}/mensagens", json={"content": "Olá, contador!"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json["message"]["sender"], "cliente")

        # contador vê na caixa (não lida) e responde
        inbox = self.acc_client.get("/atendimentos/").get_data(as_text=True)
        self.assertIn("Cliente A", inbox)
        self.assertIn("unread-badge", inbox)
        r = self.acc_client.post(f"/conversas/{cid}/mensagens", json={"content": "Olá! Como posso ajudar?"})
        self.assertEqual(r.json["message"]["sender"], "contador")

        # cliente recebe pelo polling só o que é novo
        first_id = r.json["message"]["id"] - 1
        news = self.client_a.get(f"/conversas/{cid}/mensagens?depois={first_id}").json["messages"]
        self.assertEqual([m["content"] for m in news], ["Olá! Como posso ajudar?"])

    def test_permissoes(self):
        cid = self._thread()
        # outro cliente não acessa a conversa nem a caixa de atendimentos
        self.assertEqual(self.client_b.get(f"/conversas/{cid}").status_code, 404)
        self.assertEqual(self.client_b.get(f"/conversas/{cid}/mensagens").status_code, 404)
        self.assertEqual(self.client_b.post(f"/conversas/{cid}/mensagens", json={"content": "x"}).status_code, 404)
        self.assertEqual(self.client_b.get("/atendimentos/").status_code, 404)
        # sem login: API responde 401 em JSON (não redireciona)
        anon = self.app.test_client()
        r = anon.get(f"/conversas/{cid}/mensagens")
        self.assertEqual(r.status_code, 401)
        self.assertIn("error", r.json)

    def test_validacao_mensagem(self):
        cid = self._thread()
        self.assertEqual(self.client_a.post(f"/conversas/{cid}/mensagens", json={"content": "  "}).status_code, 400)
        self.assertEqual(self.client_a.post(f"/conversas/{cid}/mensagens", json={"content": "x" * 2001}).status_code, 400)

    def test_html_na_mensagem_vira_texto(self):
        cid = self._thread()
        evil = '<img src=x onerror="alert(1)">'
        self.client_a.post(f"/conversas/{cid}/mensagens", json={"content": evil})
        page = self.client_a.get(f"/conversas/{cid}").get_data(as_text=True)
        # vai para a página só dentro do JSON escapado (e o JS usa textContent)
        self.assertNotIn(evil, page)
        self.assertIn("\\u003cimg", page)

    def test_contador_nao_conversa_consigo(self):
        r = self.acc_client.get(f"/especialistas/{self.acc_id}/conversar")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/especialistas/", r.headers["Location"])

    def test_menu_e_paginas_em_breve(self):
        home = self.client_a.get("/").get_data(as_text=True)
        menu = home[home.index('<nav class="menu">'):home.index("</nav>")]
        self.assertNotIn('href="#"', menu)  # nenhum item do menu leva a "#"
        self.assertNotIn("Atendimentos", menu)  # só contador vê
        self.assertIn("Atendimentos", self.acc_client.get("/").get_data(as_text=True))

        from contability.routes import wip
        for slug in wip.MODULES:
            r = self.client_a.get(f"/em-breve/{slug}")
            self.assertEqual(r.status_code, 200, slug)
            self.assertIn("Em construção", r.get_data(as_text=True))
        self.assertEqual(self.client_a.get("/em-breve/nao-existe").status_code, 404)


if __name__ == "__main__":
    unittest.main()
