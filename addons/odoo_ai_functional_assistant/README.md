# Odoo AI Functional Assistant

This add-on is the foundation for an Odoo 19 functional consultant assistant.
It stores documentation chunks in Odoo, adds a `pgvector` embedding column, retrieves
the most relevant chunks for a question, and sends the retrieved context to an LLM.

## Install

1. Install PostgreSQL `pgvector` on the database server.
2. Enable the extension in the Odoo database:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

3. Add this repository path to `addons_path`.
4. Update the app list and install `Odoo AI Functional Assistant`.
5. Configure the provider and API key from Settings > Odoo AI Assistant.

For Gemini, use:

- Provider: `Gemini`
- Gemini API Key: your Google AI Studio key
- Embedding Model: `gemini-embedding-001`
- Chat Model: `gemini-2.5-flash`

For OpenAI, use:

- Provider: `OpenAI`
- OpenAI API Key: your OpenAI API key
- Embedding Model: `text-embedding-3-small`
- Chat Model: `gpt-4.1-mini`

## Add Knowledge

Clone the Odoo documentation outside the module:

```bash
git clone --depth 1 --branch 19.0 https://github.com/odoo/documentation.git
```

Create records in `AI Assistant > Knowledge Chunks`, or use Odoo shell:

```python
text = open("/path/to/documentation/content/applications/inventory_and_mrp/inventory.rst").read()
chunks = env["odoo.ai.knowledge.chunk"].create_chunks_from_text(
    text,
    "content/applications/inventory_and_mrp/inventory.rst",
    module_name="inventory",
)
chunks.action_generate_embedding()
```

If you switch providers, regenerate embeddings. OpenAI and Gemini embeddings are
different vector spaces and should not be mixed for similarity search.

## Ask Questions

Open `AI Assistant > Ask Assistant`, create a question, and click `Ask Assistant`.
The answer is generated only from the retrieved knowledge chunks. If the chunks do
not contain the setup step, the assistant should explain that it is a documentation
or customization gap.

## Similarity Search SQL

The module uses this pgvector pattern internally:

```sql
SELECT id, 1 - (embedding <=> '[...]'::vector) AS similarity
FROM odoo_ai_knowledge_chunk
WHERE active = true
  AND embedding IS NOT NULL
  AND embedding_provider = 'gemini'
ORDER BY embedding <=> '[...]'::vector
LIMIT 5;
```
