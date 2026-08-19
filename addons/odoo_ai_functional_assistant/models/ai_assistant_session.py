# -*- coding: utf-8 -*-

import json
import urllib.error
import urllib.request

from odoo import fields, models, _
from odoo.exceptions import UserError


class OdooAiAssistantSession(models.Model):
    _name = "odoo.ai.assistant.session"
    _description = "Odoo AI Assistant Session"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(default="Functional Question", required=True)
    question = fields.Text(required=True, tracking=True)
    answer = fields.Text(readonly=True, tracking=True)
    context_summary = fields.Text(readonly=True)
    model = fields.Char(default="gemini-2.5-flash")
    top_k = fields.Integer(default=5)

    def action_ask_assistant(self):
        for session in self:
            chunks = self.env["odoo.ai.knowledge.chunk"].similarity_search(
                session.question,
                limit=session.top_k or 5,
            )
            context = session._format_context(chunks)
            session.write(
                {
                    "answer": session._generate_answer(session.question, context),
                    "context_summary": context,
                }
            )
        return True

    def _format_context(self, chunks):
        blocks = []
        for chunk, score in chunks:
            blocks.append(
                "Source: %s\nSimilarity: %.4f\nContent:\n%s"
                % (chunk.source_path, score or 0.0, chunk.content)
            )
        return "\n\n---\n\n".join(blocks)

    def _get_openai_api_key(self):
        api_key = self.env["ir.config_parameter"].sudo().get_param(
            "odoo_ai_functional_assistant.openai_api_key"
        )
        if not api_key:
            raise UserError(_("Configure the OpenAI API key first."))
        return api_key

    def _get_gemini_api_key(self):
        api_key = self.env["ir.config_parameter"].sudo().get_param(
            "odoo_ai_functional_assistant.gemini_api_key"
        )
        if not api_key:
            raise UserError(_("Configure the Gemini API key first."))
        return api_key

    def _get_ai_provider(self):
        return (
            self.env["ir.config_parameter"].sudo().get_param(
                "odoo_ai_functional_assistant.provider"
            )
            or "gemini"
        )

    def _get_chat_model(self):
        provider = self._get_ai_provider()
        default_model = "gemini-2.5-flash" if provider == "gemini" else "gpt-4.1-mini"
        configured_model = self.env["ir.config_parameter"].sudo().get_param(
            "odoo_ai_functional_assistant.chat_model"
        )
        if provider == "gemini" and configured_model and configured_model.startswith("gemini"):
            return configured_model
        if provider == "openai" and configured_model and configured_model.startswith("gpt"):
            return configured_model
        return default_model

    def _openai_post(self, endpoint, payload):
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            "https://api.openai.com/v1/%s" % endpoint,
            data=data,
            headers={
                "Authorization": "Bearer %s" % self._get_openai_api_key(),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise UserError(_("OpenAI request failed: %s") % body) from exc

    def _gemini_post(self, endpoint, payload):
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/%s" % endpoint,
            data=data,
            headers={
                "x-goog-api-key": self._get_gemini_api_key(),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise UserError(_("Gemini request failed: %s") % body) from exc

    def _generate_answer(self, question, context):
        self.ensure_one()
        if not context:
            return _(
                "I could not find matching Odoo 19 knowledge."
                " Add or embed more documentation before answering this question."
            )

        system_prompt = (
            "You are an Odoo 19 functional consultant assistant. "
            "Answer only from the provided context. "
            "If a setup step is missing from the context, say it is a documentation gap "
            "or a likely customization gap. Give clear functional steps."
        )
        if self._get_ai_provider() == "gemini":
            model = self._get_chat_model()
            response = self._gemini_post(
                "models/%s:generateContent" % model,
                {
                    "systemInstruction": {
                        "parts": [
                            {
                                "text": system_prompt,
                            }
                        ]
                    },
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": "Context:\n%s\n\nQuestion:\n%s" % (context, question),
                                }
                            ],
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.2,
                    },
                },
            )
            parts = response["candidates"][0]["content"]["parts"]
            return "\n".join(part.get("text", "") for part in parts).strip()

        response = self._openai_post(
            "chat/completions",
            {
                "model": self._get_chat_model(),
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": "Context:\n%s\n\nQuestion:\n%s" % (context, question),
                    },
                ],
                "temperature": 0.2,
            },
        )
        return response["choices"][0]["message"]["content"]
