# -*- coding: utf-8 -*-

import json
import logging
import urllib.error
import urllib.request

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OdooAiKnowledgeChunk(models.Model):
    _name = "odoo.ai.knowledge.chunk"
    _description = "Odoo AI Knowledge Chunk"
    _order = "id desc"

    name = fields.Char(required=True)
    content = fields.Text(required=True)
    source_path = fields.Char(required=True)
    source_type = fields.Selection(
        [
            ("documentation", "Documentation"),
            ("source_code", "Source Code"),
            ("manual", "Manual"),
        ],
        default="documentation",
        required=True,
    )
    module_name = fields.Char()
    version = fields.Char(default="19.0")
    embedding_provider = fields.Selection(
        [
            ("openai", "OpenAI"),
            ("gemini", "Gemini"),
        ],
        readonly=True,
    )
    embedding_model = fields.Char(default="text-embedding-3-small")
    embedding_dimension = fields.Integer(default=1536)
    is_embedded = fields.Boolean(readonly=True)
    active = fields.Boolean(default=True)

    def init(self):
        """Add pgvector storage beside ORM-managed metadata."""
        if not self._is_pgvector_available():
            _logger.warning(
                "PostgreSQL pgvector is not installed on the server. "
                "The module can install, but embeddings and similarity search "
                "will not work until the pgvector server package is installed."
            )
            return

        with self.env.cr.savepoint():
            try:
                self.env.cr.execute("CREATE EXTENSION IF NOT EXISTS vector")
                self._create_embedding_column()
            except Exception as exc:
                _logger.warning("Could not initialize pgvector storage: %s", exc)

    def _is_pgvector_available(self):
        self.env.cr.execute(
            """
            SELECT 1
            FROM pg_available_extensions
            WHERE name = 'vector'
            LIMIT 1
            """
        )
        return bool(self.env.cr.fetchone())

    def _has_embedding_column(self):
        self.env.cr.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'odoo_ai_knowledge_chunk'
            AND column_name = 'embedding'
            LIMIT 1
            """
        )
        return bool(self.env.cr.fetchone())

    def _create_embedding_column(self):
        dimension = 1536
        self.env.cr.execute(
            """
            ALTER TABLE odoo_ai_knowledge_chunk
            ADD COLUMN IF NOT EXISTS embedding vector(%d)
            """ % dimension
        )
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS odoo_ai_knowledge_chunk_embedding_idx
            ON odoo_ai_knowledge_chunk
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
            """
        )

    def _ensure_pgvector_ready(self):
        if not self._is_pgvector_available():
            raise UserError(
                _(
                    "PostgreSQL pgvector is not installed on this server. "
                    "Install the pgvector package for PostgreSQL, restart PostgreSQL, "
                    "then upgrade this module."
                )
            )
        if not self._has_embedding_column():
            with self.env.cr.savepoint():
                self.env.cr.execute("CREATE EXTENSION IF NOT EXISTS vector")
                self._create_embedding_column()
        if not self._has_embedding_column():
            raise UserError(
                _(
                    "The embedding column is not ready yet. "
                    "Run CREATE EXTENSION IF NOT EXISTS vector; then upgrade this module."
                )
            )

    def action_generate_embedding(self):
        for chunk in self:
            chunk._write_embedding(chunk._create_embedding(chunk.content))
        return True

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

    def _get_embedding_model(self):
        provider = self._get_ai_provider()
        default_model = "gemini-embedding-001" if provider == "gemini" else "text-embedding-3-small"
        configured_model = self.env["ir.config_parameter"].sudo().get_param(
            "odoo_ai_functional_assistant.embedding_model"
        )
        if provider == "gemini" and configured_model and configured_model.startswith("gemini"):
            return configured_model
        if provider == "openai" and configured_model and configured_model.startswith("text-embedding"):
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
            with urllib.request.urlopen(request, timeout=90) as response:
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
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise UserError(_("Gemini request failed: %s") % body) from exc

    def _create_embedding(self, text):
        model = self._get_embedding_model()
        if self._get_ai_provider() == "gemini":
            response = self._gemini_post(
                "models/%s:embedContent" % model,
                {
                    "model": "models/%s" % model,
                    "content": {
                        "parts": [
                            {
                                "text": text,
                            }
                        ],
                    },
                    "task_type": "SEMANTIC_SIMILARITY",
                    "output_dimensionality": 1536,
                },
            )
            return response["embedding"]["values"]

        response = self._openai_post(
            "embeddings",
            {
                "model": model,
                "input": text,
            },
        )
        return response["data"][0]["embedding"]

    def _write_embedding(self, embedding):
        self.ensure_one()
        self._ensure_pgvector_ready()
        vector = "[%s]" % ",".join(str(value) for value in embedding)
        self.env.cr.execute(
            """
            UPDATE odoo_ai_knowledge_chunk
               SET embedding = %s,
                   is_embedded = true,
                   embedding_provider = %s,
                   embedding_model = %s,
                   embedding_dimension = %s
             WHERE id = %s
            """,
            (
                vector,
                self._get_ai_provider(),
                self._get_embedding_model(),
                len(embedding),
                self.id,
            ),
        )

    @api.model
    def similarity_search(self, question, limit=5):
        self._ensure_pgvector_ready()
        embedding = self._create_embedding(question)
        vector = "[%s]" % ",".join(str(value) for value in embedding)
        provider = self._get_ai_provider()
        self.env.cr.execute(
            """
            SELECT id, 1 - (embedding <=> %s::vector) AS similarity
              FROM odoo_ai_knowledge_chunk
             WHERE active = true
               AND embedding IS NOT NULL
               AND embedding_provider = %s
             ORDER BY embedding <=> %s::vector
             LIMIT %s
            """,
            (vector, provider, vector, limit),
        )
        rows = self.env.cr.fetchall()
        records = self.browse([row[0] for row in rows])
        score_by_id = {row[0]: row[1] for row in rows}
        return [(record, score_by_id.get(record.id, 0.0)) for record in records]

    @api.model
    def chunk_text(self, text, chunk_size=1000, overlap=120):
        chunks = []
        start = 0
        text = text or ""
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
        return chunks

    @api.model
    def create_chunks_from_text(self, text, source_path, source_type="documentation", module_name=False):
        records = self.env["odoo.ai.knowledge.chunk"]
        for index, chunk in enumerate(self.chunk_text(text), start=1):
            records |= self.create(
                {
                    "name": "%s #%s" % (source_path, index),
                    "content": chunk,
                    "source_path": source_path,
                    "source_type": source_type,
                    "module_name": module_name,
                }
            )
        return records
