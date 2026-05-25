"""Conservative course-consumption detection for Read IA summaries."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

CURSO_NAO_CONSUMIU = "Não consumiu"
CONTEXT_WINDOW_CHARS = 120

COURSE_NAMES = [
    "Scratch",
    "No Code",
    "Introdução à Web",
    "Linux",
    "Python I",
    "JavaScript",
    "Banco de Dados",
    "Programação Orientada a Objetos",
    "Python II",
    "Fundamentos de interface",
    "Desenvolvimento de websites com mentalidade ágil",
    "Desenvolvimento de Interfaces Web Frameworks Front-End",
    "React JS",
    "Programação Multiplataforma com React Native",
    "Programação Multiplataforma com Flutter",
    "Padrão de Projeto de Software",
    "Desenvolvimento de APIs RESTful",
    "Desenvolvimento Nativo para Android",
    "Framework Full Stack para Web",
    "Teste de Software para Web",
]

COURSE_SYNONYMS = {
    "Python intermediário": "Python II",
    "Python avançado": "Python II",
    "Python básico": "Python I",
    "interfaces": "Fundamentos de interface",
    "fundamentos de interface": "Fundamentos de interface",
    "banco": "Banco de Dados",
    "banco de dados": "Banco de Dados",
}

POSITIVE_EXPRESSIONS = [
    "consumiu",
    "assistiu",
    "viu",
    "fez",
    "concluiu",
    "avançou em",
    "estudou",
    "realizou",
    "trabalhou em",
    "iniciou",
    "finalizou",
]

FUTURE_EXPRESSIONS = [
    "meta",
    "metas",
    "próxima semana",
    "próximas semanas",
    "para depois",
    "ficou combinado",
    "foi orientado a",
    "deve assistir",
    "precisa assistir",
    "precisa consumir",
    "plano",
    "planejamento",
    "sugeri",
    "recomendei",
    "foi passado",
    "foi proposto",
    "tarefa para casa",
]


@dataclass(frozen=True)
class ConsumedCoursesDetection:
    courses: list[str]
    reason: str


@dataclass(frozen=True)
class _Phrase:
    text: str
    normalized: str
    start: int
    end: int


@dataclass(frozen=True)
class _CourseMention:
    course: str
    alias: str
    normalized_alias: str
    start: int
    end: int


@dataclass(frozen=True)
class _MentionDecision:
    mention: _CourseMention
    consumed: bool
    positive: _Phrase | None
    future: _Phrase | None
    reason: str


def detect_consumed_courses_from_text(text: str) -> list[str]:
    """Return safely detected consumed courses from a Read IA summary."""
    return describe_consumed_courses_from_text(text).courses


def describe_consumed_courses_from_text(text: Any) -> ConsumedCoursesDetection:
    normalized_text = _normalize_search_text(text)
    if not normalized_text:
        return ConsumedCoursesDetection(
            courses=[CURSO_NAO_CONSUMIU],
            reason="Sem texto para analisar.",
        )

    mentions = _find_course_mentions(normalized_text)
    if not mentions:
        return ConsumedCoursesDetection(
            courses=[CURSO_NAO_CONSUMIU],
            reason="Nenhum curso reconhecido no texto.",
        )

    decisions = [_decide_mention(normalized_text, mention) for mention in mentions]
    consumed_courses: list[str] = []
    consumed_reasons: list[str] = []
    for decision in decisions:
        if not decision.consumed:
            continue
        course = decision.mention.course
        if course in consumed_courses:
            continue
        consumed_courses.append(course)
        if decision.positive is not None:
            consumed_reasons.append(f"{course}: {decision.positive.text}")

    if consumed_courses:
        return ConsumedCoursesDetection(
            courses=consumed_courses,
            reason="Expressão positiva próxima sem contexto de meta: "
            + "; ".join(consumed_reasons),
        )

    if any(decision.future is not None for decision in decisions):
        return ConsumedCoursesDetection(
            courses=[CURSO_NAO_CONSUMIU],
            reason="Cursos citados apenas em contexto de meta/orientação futura.",
        )

    return ConsumedCoursesDetection(
        courses=[CURSO_NAO_CONSUMIU],
        reason="Cursos citados sem expressão positiva de consumo próxima.",
    )


def _find_course_mentions(normalized_text: str) -> list[_CourseMention]:
    mentions: list[_CourseMention] = []
    occupied_spans: list[tuple[int, int, str]] = []

    for alias, course in _course_aliases():
        normalized_alias = _normalize_search_text(alias)
        if not normalized_alias:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(normalized_alias)}(?!\w)")
        for match in pattern.finditer(normalized_text):
            start, end = match.span()
            if _overlaps_existing_mention(occupied_spans, start, end):
                continue
            mentions.append(
                _CourseMention(
                    course=course,
                    alias=alias,
                    normalized_alias=normalized_alias,
                    start=start,
                    end=end,
                )
            )
            occupied_spans.append((start, end, course))

    return sorted(mentions, key=lambda mention: (mention.start, mention.end))


def _decide_mention(normalized_text: str, mention: _CourseMention) -> _MentionDecision:
    context_start = max(0, mention.start - CONTEXT_WINDOW_CHARS)
    context_end = min(len(normalized_text), mention.end + CONTEXT_WINDOW_CHARS)
    positives = _find_phrases(
        normalized_text,
        POSITIVE_EXPRESSIONS,
        context_start=context_start,
        context_end=context_end,
    )
    futures = _find_phrases(
        normalized_text,
        FUTURE_EXPRESSIONS,
        context_start=context_start,
        context_end=context_end,
    )

    positive = _nearest_phrase(positives, mention)
    future = _nearest_relevant_future(normalized_text, futures, mention)

    if future is not None:
        return _MentionDecision(
            mention=mention,
            consumed=False,
            positive=positive,
            future=future,
            reason=f"contexto futuro/meta: {future.text}",
        )
    if positive is None:
        return _MentionDecision(
            mention=mention,
            consumed=False,
            positive=None,
            future=None,
            reason="sem expressão positiva próxima",
        )
    return _MentionDecision(
        mention=mention,
        consumed=True,
        positive=positive,
        future=None,
        reason=f"expressão positiva próxima: {positive.text}",
    )


def _course_aliases() -> list[tuple[str, str]]:
    aliases = [(course, course) for course in COURSE_NAMES]
    aliases.extend(COURSE_SYNONYMS.items())
    return sorted(
        aliases,
        key=lambda item: len(_normalize_search_text(item[0])),
        reverse=True,
    )


def _overlaps_existing_mention(
    spans: list[tuple[int, int, str]],
    start: int,
    end: int,
) -> bool:
    return any(
        start < existing_end and end > existing_start
        for existing_start, existing_end, _ in spans
    )


def _find_phrases(
    normalized_text: str,
    phrases: list[str],
    *,
    context_start: int,
    context_end: int,
) -> list[_Phrase]:
    found: list[_Phrase] = []
    for phrase in phrases:
        normalized_phrase = _normalize_search_text(phrase)
        pattern = re.compile(rf"(?<!\w){re.escape(normalized_phrase)}(?!\w)")
        for match in pattern.finditer(normalized_text, context_start, context_end):
            found.append(
                _Phrase(
                    text=phrase,
                    normalized=normalized_phrase,
                    start=match.start(),
                    end=match.end(),
                )
            )
    return found


def _nearest_phrase(
    phrases: list[_Phrase],
    mention: _CourseMention,
) -> _Phrase | None:
    if not phrases:
        return None
    return min(phrases, key=lambda phrase: _distance_to_mention(phrase, mention))


def _nearest_relevant_future(
    normalized_text: str,
    futures: list[_Phrase],
    mention: _CourseMention,
) -> _Phrase | None:
    relevant_futures = [
        future
        for future in futures
        if _future_applies_to_mention(normalized_text, future, mention)
    ]
    return _nearest_phrase(relevant_futures, mention)


def _future_applies_to_mention(
    normalized_text: str,
    future: _Phrase,
    mention: _CourseMention,
) -> bool:
    if future.start <= mention.start:
        return True

    gap = normalized_text[mention.end : future.start]
    if _gap_starts_new_future_scope(gap):
        return False
    if _find_course_mentions(gap):
        return False
    if _future_expression_starts_new_scope(future, gap):
        return False

    return True


def _gap_starts_new_future_scope(normalized_gap: str) -> bool:
    return re.search(
        r"(?<!\w)(e\s+)?(passei|sugeri|recomendei|orientei|propus|combinei)(?!\w)",
        normalized_gap,
    ) is not None


def _future_expression_starts_new_scope(future: _Phrase, normalized_gap: str) -> bool:
    future_starters = {
        _normalize_search_text("ficou combinado"),
        _normalize_search_text("foi orientado a"),
        _normalize_search_text("deve assistir"),
        _normalize_search_text("precisa assistir"),
        _normalize_search_text("precisa consumir"),
        _normalize_search_text("sugeri"),
        _normalize_search_text("recomendei"),
        _normalize_search_text("foi passado"),
        _normalize_search_text("foi proposto"),
        _normalize_search_text("tarefa para casa"),
    }
    return future.normalized in future_starters and normalized_gap.strip() == "e"


def _distance_to_mention(phrase: _Phrase, mention: _CourseMention) -> int:
    if phrase.end <= mention.start:
        return mention.start - phrase.end
    if phrase.start >= mention.end:
        return phrase.start - mention.end
    return 0


def _normalize_search_text(value: Any) -> str:
    normalized = str(value or "").strip().casefold()
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
