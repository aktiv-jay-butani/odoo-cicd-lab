# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    odoo_ai_provider = fields.Selection(
        [
            ("openai", "OpenAI"),
            ("gemini", "Gemini"),
        ],
        string="AI Provider",
        default="gemini",
        config_parameter="odoo_ai_functional_assistant.provider",
    )
    odoo_ai_openai_api_key = fields.Char(
        string="OpenAI API Key",
        config_parameter="odoo_ai_functional_assistant.openai_api_key",
    )
    odoo_ai_gemini_api_key = fields.Char(
        string="Gemini API Key",
        config_parameter="odoo_ai_functional_assistant.gemini_api_key",
    )
    odoo_ai_embedding_model = fields.Char(
        string="Embedding Model",
        default="gemini-embedding-001",
        config_parameter="odoo_ai_functional_assistant.embedding_model",
    )
    odoo_ai_chat_model = fields.Char(
        string="Chat Model",
        default="gemini-2.5-flash",
        config_parameter="odoo_ai_functional_assistant.chat_model",
    )
