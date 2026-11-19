"""Testes do chat com IA em conversas separadas (contexto por conversa).

A chamada à Groq é substituída por uma IA falsa que registra o contexto recebido.
Usam o banco real com usuários temporários; são pulados se o PostgreSQL estiver fora.

    py -m unittest discover -s tests -v
"""
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contability import db  # noqa: E402

try:
    db.init_db()
    DB_OK = True
except Exception:
    DB_OK = False


class FakeLLM:
    """Responde 'eco: <última pergunta>' e guarda as mensagens de cada chamada."""

    def __init__(self):
        self.calls = []

    def create(self, model, messages):
        self.calls.append(messages)
        reply = "eco: " + messages[-1]["content"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])


@unittest.skipUnless(DB_OK, "PostgreSQL indisponível")
class TestChatConversas(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import app as flask_app
        from contability.routes import chat as chat_routes
        cls.module = flask_app
        cls.chat = chat_routes
        tag = uuid.uuid4().hex[:8]
        cls.emails = [f"chat-a-{tag}@t.test", f"chat-b-{tag}@t.test"]
        cls.a = cls._signup("Cliente A", cls.emails[0])
        cls.b = cls._signup("Cliente B", cls.emails[1])

    @classmethod
    def tearDownClass(cls):
        with db.cursor() as cur:
            cur.execute("DELETE FROM users WHERE email = ANY(%s)", (cls.emails,))

    @classmethod
    def _signup(cls, name, email):
        c = cls.module.app.test_client()
        c.post("/cadastro", data={"name": name, "email": email,
                                  "password": "senhaTeste123", "confirm": "senhaTeste123"})
        return c

    def setUp(self):
        self.llm = FakeLLM()
        patcher = mock.patch.object(self.chat.client.chat.completions, "create", self.llm.create)
        patcher.start()
        self.addCleanup(patcher.stop)

    def ask(self, client, message, conversation_id=None):
        r = client.post("/chat", json={"message": message, "conversation_id": conversation_id})
        return r

    def test_primeira_mensagem_cria_conversa_com_titulo(self):
        r = self.ask(self.a, "  Como   funciona o   DAS do MEI?  ")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json["created"])
        conv = r.json["conversation"]
        self.assertEqual(conv["title"], "Como funciona o DAS do MEI?")
        self.assertEqual(conv["url"], f"/c/{conv['id']}")
        # mensagem seguinte na mesma conversa não cria outra
        r2 = self.ask(self.a, "E o limite?", conv["id"])
        self.assertFalse(r2.json["created"])
        self.assertEqual(r2.json["conversation"]["id"], conv["id"])

    def test_titulo_longo_e_cortado(self):
        r = self.ask(self.a, "x" * 200)
        self.assertLessEqual(len(r.json["conversation"]["title"]), 60)
        self.assertTrue(r.json["conversation"]["title"].endswith("…"))

    def test_contexto_separado_por_conversa(self):
        c1 = self.ask(self.a, "Assunto ALFA").json["conversation"]["id"]
        c2 = self.ask(self.a, "Assunto BETA").json["conversation"]["id"]
        self.assertNotEqual(c1, c2)

        self.ask(self.a, "continua alfa", c1)
        contexto_c1 = " ".join(m["content"] for m in self.llm.calls[-1])
        self.assertIn("Assunto ALFA", contexto_c1)
        self.assertNotIn("Assunto BETA", contexto_c1)

        self.ask(self.a, "continua beta", c2)
        contexto_c2 = " ".join(m["content"] for m in self.llm.calls[-1])
        self.assertIn("Assunto BETA", contexto_c2)
        self.assertNotIn("Assunto ALFA", contexto_c2)

        # conversa nova não leva contexto nenhum (só system + pergunta)
        self.ask(self.a, "do zero")
        self.assertEqual(len(self.llm.calls[-1]), 2)

    def test_pagina_da_conversa_e_lista(self):
        conv = self.ask(self.a, "Pergunta da página").json["conversation"]
        html = self.a.get(conv["url"]).get_data(as_text=True)
        self.assertIn("Pergunta da página", html)              # histórico injetado
        self.assertIn(f'data-conversation-id="{conv["id"]}"', html)
        self.assertIn('class="conv-item active"', html)
        home = self.a.get("/").get_data(as_text=True)
        self.assertIn('data-conversation-id=""', home)          # home = conversa nova
        self.assertIn("Pergunta da página", home)               # aparece na lista lateral

    def test_renomear_e_excluir(self):
        cid = self.ask(self.a, "Para renomear").json["conversation"]["id"]
        r = self.a.post(f"/chat/{cid}/renomear", json={"title": "  Novo   nome  "})
        self.assertEqual(r.json["title"], "Novo nome")
        self.assertEqual(self.a.post(f"/chat/{cid}/renomear", json={"title": " "}).status_code, 400)

        self.assertEqual(self.a.post(f"/chat/{cid}/excluir").status_code, 200)
        self.assertEqual(self.a.get(f"/c/{cid}").status_code, 404)
        with db.cursor() as cur:
            cur.execute("SELECT count(*) n FROM messages WHERE conversation_id = %s", (cid,))
            self.assertEqual(cur.fetchone()["n"], 0)            # mensagens saíram junto

    def test_isolamento_entre_usuarios(self):
        cid = self.ask(self.a, "Segredo da A").json["conversation"]["id"]
        self.assertEqual(self.b.get(f"/c/{cid}").status_code, 404)
        self.assertEqual(self.ask(self.b, "invadir", cid).status_code, 404)
        self.assertEqual(self.b.post(f"/chat/{cid}/renomear", json={"title": "x"}).status_code, 404)
        self.assertEqual(self.b.post(f"/chat/{cid}/excluir").status_code, 404)
        self.assertNotIn("Segredo da A", self.b.get("/").get_data(as_text=True))

    def test_falha_da_ia_nao_cria_conversa_vazia(self):
        antes = len(db.list_conversations(db.get_user_by_email(self.emails[0])["id"]))
        with mock.patch.object(self.chat.client.chat.completions, "create", side_effect=RuntimeError("fora")):
            r = self.ask(self.a, "vai falhar")
        self.assertEqual(r.status_code, 502)
        depois = len(db.list_conversations(db.get_user_by_email(self.emails[0])["id"]))
        self.assertEqual(antes, depois)

    def test_conversation_id_invalido(self):
        self.assertEqual(self.ask(self.a, "oi", "abc").status_code, 404)
        self.assertEqual(self.ask(self.a, "oi", 999999999).status_code, 404)


if __name__ == "__main__":
    unittest.main()
