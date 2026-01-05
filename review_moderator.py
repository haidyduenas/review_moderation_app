from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

import pandas as pd

DEFAULT_POLICY = {
    "min_words_for_approve": 5,
    "min_chars_for_approve": 20,
    "caps_ratio_human": 0.70,
    "excessive_exclamations_human": 5,
    "excessive_question_human": 5,
    "max_repeated_char_run": 6,
    "max_repeated_word_ratio": 0.35,
    "deny_if_contains_url": True,
    "deny_if_contains_email": True,
    "deny_if_contains_phone": True,
    "deny_if_duplicate": True,
}

PROFANITY = {
    "mierda", "puta", "puto", "pendejo", "pendeja", "imbecil", "idiota",
    "estupido", "estúpido", "malparido", "hijueputa", "hpta",
    "fuck", "shit", "bitch", "asshole",
}

SPAM_PROMO_KEYWORDS = {
    "gratis", "promoción", "promocion", "descuento", "cupón", "cupon", "codigo", "código",
    "whatsapp", "telegram", "contáctame", "contactame", "dm", "inbox",
    "sígueme", "sigueme", "follow", "link", "mi tienda", "mi negocio",
}

POSITIVE_WORDS = {"bueno", "excelente", "genial", "recomendado", "recomiendo", "perfecto", "me encanta", "satisfecho", "satisfecha"}
NEGATIVE_WORDS = {"malo", "pésimo", "pesimo", "horrible", "terrible", "defectuoso", "estafa", "no sirve", "decepcionado", "decepcionada"}
SARCASM_MARKERS = {"sí claro", "si claro", "ajá", "aja", "claro que sí", "claro que si", "irónico", "ironico", "sarcasmo"}

URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(\+?\d[\d\s().-]{7,}\d)\b")
WHITESPACE_RE = re.compile(r"\s+")
REPEATED_CHAR_RE = re.compile(r"(.)\1{6,}")

def normalize(text: str) -> str:
    text = ("" if text is None else str(text)).strip()
    text = WHITESPACE_RE.sub(" ", text)
    return text

def word_list(text: str) -> List[str]:
    return re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9']+", text.lower())

def caps_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    caps = sum(1 for c in letters if c.isupper())
    return caps / max(len(letters), 1)

def exclamation_count(text: str) -> int:
    return text.count("!")

def question_count(text: str) -> int:
    return text.count("?")

def contains_profanity(text: str) -> Optional[str]:
    wl = set(word_list(text))
    for bad in PROFANITY:
        if bad in wl:
            return bad
    return None

def contains_url(text: str) -> bool:
    return bool(URL_RE.search(text))

def contains_email(text: str) -> bool:
    return bool(EMAIL_RE.search(text))

def contains_phone(text: str) -> bool:
    return bool(PHONE_RE.search(text))

def repeated_char_run(text: str) -> bool:
    return bool(REPEATED_CHAR_RE.search(text))

def repeated_word_ratio(text: str) -> float:
    words = word_list(text)
    if len(words) < 6:
        return 0.0
    from collections import Counter
    c = Counter(words)
    return c.most_common(1)[0][1] / len(words)

def looks_like_spam_promo(text: str) -> Optional[str]:
    t = text.lower()
    for k in SPAM_PROMO_KEYWORDS:
        if k in t:
            return k
    return None

def is_gibberish(text: str) -> bool:
    if not text:
        return True
    alpha = sum(1 for c in text if c.isalpha())
    if alpha == 0:
        return True
    symbol = sum(1 for c in text if not c.isalnum() and not c.isspace())
    ratio_symbols = symbol / max(len(text), 1)
    ratio_alpha = alpha / max(len(text), 1)
    return ratio_alpha < 0.35 or ratio_symbols > 0.35

def has_mixed_sentiment(text: str) -> bool:
    t = text.lower()
    pos = any(w in t for w in POSITIVE_WORDS)
    neg = any(w in t for w in NEGATIVE_WORDS)
    return pos and neg

def has_sarcasm_marker(text: str) -> Optional[str]:
    t = text.lower()
    for s in SARCASM_MARKERS:
        if s in t:
            return s
    return None

def short_or_low_info(text: str, min_words: int, min_chars: int) -> bool:
    words = word_list(text)
    return len(words) < min_words or len(text) < min_chars

def guess_review_column(df: pd.DataFrame) -> Optional[str]:
    preferred = {"review", "reseña", "resena", "comentario", "texto", "opinion", "opinión", "comment", "feedback"}
    for c in df.columns:
        if str(c).strip().lower() in preferred:
            return c
    text_cols = []
    for c in df.columns:
        s = df[c].dropna().astype(str).head(20)
        if not s.empty and s.map(len).mean() >= 10:
            text_cols.append(c)
    return text_cols[0] if len(text_cols) == 1 else None

@dataclass
class Decision:
    classification: str
    explanation: str
    human_factor: str = ""

def classify_review(text: str, *, policy: Dict[str, Any], is_duplicate: bool) -> Decision:
    t = normalize(text)
    if not t:
        return Decision("Denegar", "La reseña está vacía.", "")

    bad = contains_profanity(t)
    if bad:
        return Decision("Denegar", f"Contiene lenguaje ofensivo/prohibido (término detectado: '{bad}').", "")

    if policy.get("deny_if_contains_url", True) and contains_url(t):
        return Decision("Denegar", "Incluye un enlace/URL, lo cual suele considerarse promoción externa o spam.", "")

    if policy.get("deny_if_contains_email", True) and contains_email(t):
        return Decision("Denegar", "Incluye un correo electrónico, lo cual no se permite en reseñas públicas.", "")

    if policy.get("deny_if_contains_phone", True) and contains_phone(t):
        return Decision("Denegar", "Incluye un número de teléfono, lo cual no se permite en reseñas públicas.", "")

    promo_kw = looks_like_spam_promo(t)
    if promo_kw:
        if any(x in promo_kw for x in {"whatsapp", "telegram", "dm", "inbox"}):
            return Decision("Denegar", f"Se detectó posible promoción/spam (señal: '{promo_kw}').", "")
        return Decision("Revisión humana requerida", "La reseña tiene señales de promoción o manipulación.", f"Posible contenido promocional (señal: '{promo_kw}').")

    if policy.get("deny_if_duplicate", True) and is_duplicate:
        return Decision("Denegar", "La reseña es un duplicado exacto dentro del archivo cargado.", "")

    if caps_ratio(t) >= float(policy.get("caps_ratio_human", 0.70)) and len(t) >= 15:
        return Decision("Revisión humana requerida", "La reseña está escrita mayormente en mayúsculas, lo cual afecta legibilidad y tono.", "Texto mayormente en MAYÚSCULAS.")

    if exclamation_count(t) >= int(policy.get("excessive_exclamations_human", 5)):
        return Decision("Revisión humana requerida", "Tiene un exceso de signos de exclamación, lo cual puede percibirse como spam o tono agresivo.", "Exceso de signos de exclamación.")

    if question_count(t) >= int(policy.get("excessive_question_human", 5)):
        return Decision("Revisión humana requerida", "Tiene muchas preguntas; podría no ser una reseña útil sino una consulta.", "Exceso de signos de interrogación.")

    if repeated_char_run(t):
        return Decision("Revisión humana requerida", "Se detectaron repeticiones exageradas de caracteres, lo cual reduce calidad y legibilidad.", "Repetición exagerada de caracteres.")

    if repeated_word_ratio(t) >= float(policy.get("max_repeated_word_ratio", 0.35)):
        return Decision("Revisión humana requerida", "La reseña repite excesivamente una palabra; puede ser spam o baja calidad.", "Repetición excesiva de palabras.")

    sarcasm = has_sarcasm_marker(t)
    if sarcasm:
        return Decision("Revisión humana requerida", "Podría contener sarcasmo o ambigüedad semántica; conviene validar manualmente.", f"Posible sarcasmo/ambigüedad (señal: '{sarcasm}').")

    if has_mixed_sentiment(t):
        return Decision("Revisión humana requerida", "Combina señales positivas y negativas; puede ser ambigua.", "Sentimiento mixto (positivo y negativo).")

    if is_gibberish(t):
        return Decision("Revisión humana requerida", "El texto parece poco legible o con exceso de símbolos; requiere verificación manual.", "Baja legibilidad / texto confuso.")

    if short_or_low_info(t, int(policy.get("min_words_for_approve", 5)), int(policy.get("min_chars_for_approve", 20))):
        return Decision("Revisión humana requerida", "La reseña es muy corta o aporta poca información útil para otros usuarios.", "Contenido muy corto / baja utilidad.")

    return Decision("Aprobar", "Cumple criterios de legibilidad y comportamiento aceptable (sin señales de spam/ofensivo).", "")

def classify_dataframe(df: pd.DataFrame, *, review_col: str, policy: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    policy = policy or DEFAULT_POLICY
    out = df.copy()
    norm = out[review_col].fillna("").astype(str).map(normalize).str.lower()
    dup_mask = norm.duplicated(keep="first")

    cl, ex, hf = [], [], []
    for i, txt in enumerate(out[review_col].tolist()):
        d = classify_review(txt, policy=policy, is_duplicate=bool(dup_mask.iloc[i]))
        cl.append(d.classification); ex.append(d.explanation); hf.append(d.human_factor)

    out["clasificacion"] = cl
    out["explicacion"] = ex
    out["factor_revision_humana"] = hf
    return out
