"""
ai/guardrail_adapter.py
Ghost Operator — Forge Guardrail Adaptörü

Ollama'nın döndürdüğü ham mesaj formatını Forge'un tip sistemine (ToolCall /
TextResponse) çevirir; Forge'un ürettiği ValidationResult'u da Ghost'un
LangGraph döngüsünün anlayacağı Ollama formatına (tool_calls / content) geri
çevirir.

Bağımsız, saf Python modülü — LangGraph veya ChatLLM'e bağımlılığı yok.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("ghost.guardrail")

# ── Forge tip importları ─────────────────────────────────────────────────────
from forge.core.workflow import TextResponse, ToolCall
from forge.guardrails import ResponseValidator

MAX_RETRY_ATTEMPTS = 3  # bir mesaj başına maksimum kurtarma denemesi

# ── Türkçe nudge şablonları ─────────────────────────────────────────────────
# Forge'un orijinal nudge'ları İngilizce. Ghost'un sistem promptu ve araç
# isimleri Türkçe olduğundan, yerel modeller Türkçe uyarıya daha tutarlı
# tepki veriyor. Forge'un nudge.kind değerine göre doğru şablon seçilir.

def _turkish_nudge(kind: str, content: str, tool_names: list[str]) -> str:
    """
    Forge nudge'ını Türkçe karşılığına çevirir.
    Bilinmeyen kind için orijinal İngilizce içeriği kullanır.
    """
    if kind == "retry":
        return (
            "Bir önceki cevabın geçerli bir araç çağrısı değildi. "
            "Düz metin döndürdün; bunun yerine mutlaka bir araç çağırmalısın. "
            "Lütfen geçerli bir araç çağrısı ile tekrar dene."
        )
    if kind == "unknown_tool":
        # İngilizce içerikten tool adını çıkarmaya çalış ("Tool 'X' does not exist")
        m = re.search(r"Tool '(.+?)' does not exist", content)
        bad_tool = m.group(1) if m else "?"
        available = ", ".join(tool_names)
        return (
            f"'{bad_tool}' adında bir araç mevcut değil. "
            f"Kullanabileceğin araçlar: {available}. "
            "Lütfen listeden birini seç ve tekrar çağır."
        )
    if kind == "tool_arg_validation":
        return (
            "Araç çağrısının argümanları hatalı formatta (dict olmalı). "
            "Lütfen argümanları JSON objesi olarak düzelt ve tekrar dene."
        )
    # Bilinmeyen kind → orijinal İngilizce
    return content


def build_validator(tool_schemas: list[dict[str, Any]]) -> ResponseValidator:
    """
    Ghost'un tool_registry.get_schemas() çıktısından ResponseValidator oluşturur.

    tool_schemas: [{"type": "function", "function": {"name": ..., ...}}, ...]
    """
    tool_names = [s["function"]["name"] for s in tool_schemas]
    validator = ResponseValidator(tool_names=tool_names, rescue_enabled=True)
    logger.debug("[Forge] Validator hazır — %d araç: %s", len(tool_names), tool_names)
    return validator


def ollama_msg_to_forge(msg: dict[str, Any]) -> TextResponse | list[ToolCall]:
    """
    Ollama API'sinden dönen ham `message` objesini Forge tiplerine çevirir.

    Ollama native tool_calls formatı:
        {
          "role": "assistant",
          "tool_calls": [
            {"function": {"name": "arama", "arguments": {"sorgu": "..."}}},
            ...
          ]
        }

    Düz metin cevap (format drift durumu):
        {"role": "assistant", "content": "Hava durumu ...", "tool_calls": None}
    """
    raw_tool_calls = msg.get("tool_calls") or []

    if raw_tool_calls:
        forge_calls = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            # args bazen JSON string gelebilir (bazı Ollama sürümlerinde)
            if isinstance(args, str):
                import json as _json
                try:
                    args = _json.loads(args)
                except Exception:
                    args = {}
            # Forge'un beklediği dict formatını garanti altına al
            if not isinstance(args, dict):
                args = {}
            forge_calls.append(ToolCall(tool=name, args=args))
        return forge_calls

    # tool_calls boş → metin cevap (format drift adayı)
    content = msg.get("content") or ""
    return TextResponse(content=content)


def forge_toolcalls_to_ollama(tool_calls: list[ToolCall], call_ids: list[str | None] | None = None) -> list[dict]:
    """
    Forge'un kurtardığı ToolCall listesini Ollama/OpenAI standardındaki
    tool_calls listesine çevirir.

    Opsiyonel call_ids, orijinal mesajdaki id'leri korumak için kullanılır.
    Eğer verilmezse veya eşleşme olmazsa id "rescued_<i>" olarak üretilir.
    """
    result = []
    for i, tc in enumerate(tool_calls):
        call_id = None
        if call_ids and i < len(call_ids):
            call_id = call_ids[i]
        call_id = call_id or f"rescued_{i}"
        result.append({
            "id": call_id,
            "type": "function",
            "function": {
                "name": tc.tool,
                "arguments": tc.args,
            }
        })
    return result


def validate_and_rescue(
    msg: dict[str, Any],
    validator: ResponseValidator,
    raw_call_fn,
    messages_so_far: list[dict],
    tools: list[dict],
) -> dict[str, Any]:
    """
    Ollama'dan gelen tek bir `msg`'yi Forge guardrail'ından geçirir.
    Format drift veya bilinmeyen araç durumunda kendi içinde en fazla
    MAX_RETRY_ATTEMPTS kez modele düzeltme nudge'ı gönderir.

    Args:
        msg              : Ollama'nın döndürdüğü ham message dict'i
        validator        : build_validator() ile oluşturulmuş ResponseValidator
        raw_call_fn      : (messages, tools) -> msg  —  ChatLLM._raw_call imzası
        messages_so_far  : Ollama'ya gönderilecek mevcut mesaj geçmişi
        tools            : Ollama payload'ında kullanılan tool şemaları

    Returns:
        Orijinal msg ya da kurtarılmış / düzeltilmiş yeni msg.
        Kurtarma başarısızsa orijinal msg olduğu gibi döner (Ghost kendi
        fallback'ini yönetir).
    """
    attempt = 0
    current_msg = msg
    working_messages = list(messages_so_far)
    tool_names = validator.tool_names  # Türkçe nudge için

    while attempt < MAX_RETRY_ATTEMPTS:
        forge_response = ollama_msg_to_forge(current_msg)
        result = validator.validate(forge_response)

        if not result.needs_retry:
            # ── Başarılı: kurtarıldıysa Ollama formatına geri çevir ──────────
            if result.tool_calls and not (current_msg.get("tool_calls")):
                # Metin içindeydi, rescue etti → Ollama formatına dönüştür
                rescued_ollama_calls = forge_toolcalls_to_ollama(result.tool_calls)
                rescued_msg = dict(current_msg)
                rescued_msg["tool_calls"] = rescued_ollama_calls
                rescued_msg["content"] = ""  # content'i temizle
                logger.info(
                    "[Forge] 🛟 Rescue başarılı — %d araç kurtarıldı: %s (deneme %d)",
                    len(result.tool_calls),
                    [tc.tool for tc in result.tool_calls],
                    attempt + 1,
                )
                return rescued_msg
            # Normal geçerli tool_call(s) — değiştirmeden döndür
            return current_msg

        # ── Retry gerekiyor: nudge'ı geçici mesaj olarak ekle ────────────────
        nudge = result.nudge
        logger.warning(
            "[Forge] ⚠️  Deneme %d/%d — %s nudge",
            attempt + 1, MAX_RETRY_ATTEMPTS,
            nudge.kind if nudge else "?",
        )

        working_messages = working_messages + [current_msg]
        if nudge:
            # ── BUG FIX #1: role="tool" → role="user" ────────────────────────
            # ── BUG FIX #2: İngilizce → Türkçe nudge ────────────────────────
            turkish_content = _turkish_nudge(nudge.kind, nudge.content, tool_names)
            working_messages = working_messages + [{
                "role": "user",
                "content": turkish_content,
            }]

        attempt += 1
        if attempt >= MAX_RETRY_ATTEMPTS:
            logger.error(
                "[Forge] ❌ %d denemeden sonra kurtarma başarısız — orijinal msg döndürülüyor.",
                MAX_RETRY_ATTEMPTS,
            )
            return current_msg

        # Modeli nudge ile tekrar çağır
        try:
            current_msg = raw_call_fn(messages=working_messages, tools=tools)
        except Exception as e:
            logger.error("[Forge] Retry sırasında model çağrısı başarısız: %s", e)
            return current_msg

    return current_msg
