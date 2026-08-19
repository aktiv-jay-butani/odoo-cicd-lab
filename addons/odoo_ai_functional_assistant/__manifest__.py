# -*- coding: utf-8 -*-
{
    "name": "Odoo AI Functional Assistant",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": "AI assistant for Odoo functional consultants using Odoo documentation knowledge",
    "description": """
Build a functional consultant assistant backed by Odoo knowledge chunks,
OpenAI embeddings, and PostgreSQL pgvector similarity search.
    """,
    "author": "Custom",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/ai_knowledge_chunk_views.xml",
        "views/ai_assistant_session_views.xml",
        "views/res_config_settings_views.xml",
        "views/ai_assistant_menus.xml",
    ],
    "installable": True,
    "application": True,
}

