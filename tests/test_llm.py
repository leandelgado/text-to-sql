from unittest.mock import MagicMock, patch

import pytest

from src.config import GROQ_MODEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_groq_response(content: str):
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


# ---------------------------------------------------------------------------
# _extract_sql
# ---------------------------------------------------------------------------

from src.llm import _extract_sql


class TestExtractSql:
    def test_plain_sql_returned_as_is(self):
        sql = "SELECT 1"
        assert _extract_sql(sql) == "SELECT 1"

    def test_strips_whitespace(self):
        assert _extract_sql("  SELECT 1  \n") == "SELECT 1"

    def test_extracts_from_sql_code_block(self):
        text = "```sql\nSELECT segment FROM t\n```"
        assert _extract_sql(text) == "SELECT segment FROM t"

    def test_extracts_from_generic_code_block(self):
        text = "```\nSELECT 1\n```"
        assert _extract_sql(text) == "SELECT 1"

    def test_multiline_sql_in_block(self):
        text = "```sql\nSELECT a, b\nFROM t\nWHERE x = 1\n```"
        assert _extract_sql(text) == "SELECT a, b\nFROM t\nWHERE x = 1"

    def test_trailing_text_outside_block_ignored(self):
        text = "Aquí el SQL:\n```sql\nSELECT 1\n```\nEspero que ayude."
        assert _extract_sql(text) == "SELECT 1"


# ---------------------------------------------------------------------------
# _build_user_message
# ---------------------------------------------------------------------------

from src.llm import _build_user_message


class TestBuildUserMessage:
    def test_normal_path_contains_question(self):
        msg = _build_user_message("¿Cuántos clientes?", None)
        assert "¿Cuántos clientes?" in msg

    def test_normal_path_no_correction_text(self):
        msg = _build_user_message("¿Cuántos clientes?", None)
        assert "corregí" not in msg.lower()
        assert "error" not in msg.lower()

    def test_correction_path_contains_question(self):
        ctx = "El siguiente SQL falló:\nSELECT x\n\nError: column not found"
        msg = _build_user_message("¿Cuántos clientes?", ctx)
        assert "¿Cuántos clientes?" in msg

    def test_correction_path_contains_error_context(self):
        ctx = "El siguiente SQL falló:\nSELECT x\n\nError: column not found"
        msg = _build_user_message("¿Cuántos clientes?", ctx)
        assert ctx in msg

    def test_correction_path_contains_instruction(self):
        ctx = "El siguiente SQL falló:\nSELECT x\n\nError: column not found"
        msg = _build_user_message("¿Cuántos clientes?", ctx)
        assert "corregí" in msg.lower()


# ---------------------------------------------------------------------------
# _build_system_prompt
# ---------------------------------------------------------------------------

from src.llm import _build_system_prompt


class TestBuildSystemPrompt:
    def test_contains_role_instruction(self):
        with patch("src.llm.format_schema_for_prompt", return_value="SCHEMA"):
            prompt = _build_system_prompt()
        assert "SQL" in prompt
        assert "concesionaria" in prompt.lower()

    def test_contains_output_instruction(self):
        with patch("src.llm.format_schema_for_prompt", return_value="SCHEMA"):
            prompt = _build_system_prompt()
        assert "únicamente" in prompt.lower() or "solo" in prompt.lower()

    def test_contains_injected_schema(self):
        with patch("src.llm.format_schema_for_prompt", return_value="FAKE_SCHEMA_XYZ"):
            prompt = _build_system_prompt()
        assert "FAKE_SCHEMA_XYZ" in prompt

    def test_contains_few_shot_examples(self):
        with patch("src.llm.format_schema_for_prompt", return_value="SCHEMA"):
            prompt = _build_system_prompt()
        assert "segmento" in prompt.lower()
        assert "facturación" in prompt.lower() or "facturacion" in prompt.lower()
        assert "VIP" in prompt


# ---------------------------------------------------------------------------
# generate_sql — camino normal
# ---------------------------------------------------------------------------

from src.llm import generate_sql


class TestGenerateSqlNormal:
    def test_returns_sql_string(self):
        response = _make_groq_response("SELECT segment FROM t")
        with patch("src.llm._client") as mock_client, \
             patch("src.llm.format_schema_for_prompt", return_value="SCHEMA"):
            mock_client.chat.completions.create.return_value = response
            result = generate_sql("¿Cuántos clientes hay por segmento?")
        assert result == "SELECT segment FROM t"

    def test_strips_markdown_code_block(self):
        response = _make_groq_response("```sql\nSELECT 1\n```")
        with patch("src.llm._client") as mock_client, \
             patch("src.llm.format_schema_for_prompt", return_value="SCHEMA"):
            mock_client.chat.completions.create.return_value = response
            result = generate_sql("Dame algo")
        assert result == "SELECT 1"

    def test_calls_groq_with_correct_model(self):
        response = _make_groq_response("SELECT 1")
        with patch("src.llm._client") as mock_client, \
             patch("src.llm.format_schema_for_prompt", return_value="SCHEMA"):
            mock_client.chat.completions.create.return_value = response
            generate_sql("pregunta")
        _, call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs["model"] == GROQ_MODEL

    def test_user_message_contains_question(self):
        response = _make_groq_response("SELECT 1")
        with patch("src.llm._client") as mock_client, \
             patch("src.llm.format_schema_for_prompt", return_value="SCHEMA"):
            mock_client.chat.completions.create.return_value = response
            generate_sql("¿Cuántos clientes VIP hay?")
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert "¿Cuántos clientes VIP hay?" in user_content


# ---------------------------------------------------------------------------
# generate_sql — self-correction y errores
# ---------------------------------------------------------------------------

class TestGenerateSqlCorrection:
    def test_error_context_included_in_user_message(self):
        response = _make_groq_response("SELECT 2")
        ctx = "El siguiente SQL falló:\nSELECT x\n\nError: column not found"
        with patch("src.llm._client") as mock_client, \
             patch("src.llm.format_schema_for_prompt", return_value="SCHEMA"):
            mock_client.chat.completions.create.return_value = response
            generate_sql("¿Cuántos clientes?", error_context=ctx)
        messages = mock_client.chat.completions.create.call_args.kwargs["messages"]
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert ctx in user_content
        assert "corregí" in user_content.lower()

    def test_correction_returns_new_sql(self):
        response = _make_groq_response("SELECT segment, COUNT(*) FROM t GROUP BY segment")
        ctx = "El siguiente SQL falló:\nSELECT x\n\nError: column not found"
        with patch("src.llm._client") as mock_client, \
             patch("src.llm.format_schema_for_prompt", return_value="SCHEMA"):
            mock_client.chat.completions.create.return_value = response
            result = generate_sql("¿Cuántos clientes?", error_context=ctx)
        assert result == "SELECT segment, COUNT(*) FROM t GROUP BY segment"


class TestGenerateSqlErrors:
    def test_raises_runtime_error_on_groq_failure(self):
        with patch("src.llm._client") as mock_client, \
             patch("src.llm.format_schema_for_prompt", return_value="SCHEMA"):
            mock_client.chat.completions.create.side_effect = Exception("connection timeout")
            with pytest.raises(RuntimeError, match="Error al llamar a Groq"):
                generate_sql("¿Cuántos clientes?")
