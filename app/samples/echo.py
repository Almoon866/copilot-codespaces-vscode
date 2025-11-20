"""مثال لبرنامج فرعي بسيط لاختبار التشغيل والمعاينة."""

from __future__ import annotations


def run(payload: dict) -> dict:
    """إرجاع ملخص عن الحمولة المستلمة مع عدّاد بسيط."""
    text = payload.get("text", "")
    count = int(payload.get("count", 1))
    return {
        "echo": text,
        "repeat": count,
        "message": f"Received '{text}' repeated {count} time(s)",
    }
