from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from urllib.parse import urlsplit


SECURITY_HEADERS = {
    "access-control-allow-origin",
    "access-control-allow-credentials",
    "strict-transport-security",
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
    "set-cookie",
}


def sha256_hex(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def classify_header(name: str, value: str) -> tuple[str, str]:
    normalized_name = name.lower()
    if normalized_name == "set-cookie":
        flags = [
            flag
            for flag in ("Secure", "HttpOnly", "SameSite")
            if re.search(rf"(?:^|;)\s*{flag}(?:=|;|$)", value, re.IGNORECASE)
        ]
        rendered = ", ".join(flags) if flags else "sem Secure, HttpOnly ou SameSite observados"
        bearing = "supports" if "samesite" not in [item.lower() for item in flags] else "neutral"
        return f"Set-Cookie flags: {rendered}", bearing
    if normalized_name == "access-control-allow-origin" and value.strip() == "*":
        return f"{name}: {value.strip()}", "supports"
    if normalized_name in {"strict-transport-security", "x-content-type-options"}:
        return f"{name}: {value.strip()}", "contradicts"
    return f"{name}: {value.strip()}", "neutral"


def _normalized_item(
    *, kind: str, observation: str, source: str, detail: str, bearing: str, artifact_hash: str
) -> dict[str, object]:
    safe_kind = kind.upper() if kind.upper() in {"HTTP", "TLS", "JWT", "CRYPTO"} else "OTHER"
    safe_bearing = bearing if bearing in {"supports", "neutral", "contradicts"} else "neutral"
    return {
        "source": source,
        "kind": safe_kind,
        "observation": observation[:500],
        "bearing": safe_bearing,
        "confidence": 0.9,
        "artifact_hash": artifact_hash,
        "detail": detail[:1000],
    }


def parse_json_artifact(content: str, source: str) -> list[dict[str, object]]:
    parsed = json.loads(content)
    records = parsed.get("evidence", []) if isinstance(parsed, dict) and "evidence" in parsed else parsed
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        raise ValueError("JSON must contain an evidence object or an array")
    digest = sha256_hex(content)
    result = []
    for item in records:
        if not isinstance(item, dict):
            continue
        observation = item.get("observation") or item.get("title")
        if not isinstance(observation, str) or not observation.strip():
            continue
        result.append(
            _normalized_item(
                kind=str(item.get("kind", "OTHER")),
                observation=observation,
                source=str(item.get("source") or source),
                detail=str(item.get("detail") or "Importado de JSON"),
                bearing=str(item.get("bearing", "neutral")),
                artifact_hash=digest,
            )
        )
    return result


def _cookie_flags(value: str) -> str:
    flags = [
        flag
        for flag in ("Secure", "HttpOnly", "SameSite")
        if re.search(rf"(?:^|;)\s*{flag}(?:=|;|$)", value, re.IGNORECASE)
    ]
    return ", ".join(flags) if flags else "sem Secure, HttpOnly ou SameSite observados"


def _header_records(
    headers: Iterable[tuple[str, str]], source: str, detail: str, digest: str
) -> list[dict[str, object]]:
    result = []
    for name, value in headers:
        normalized_name = name.strip().lower()
        if normalized_name not in SECURITY_HEADERS:
            continue
        observation, bearing = classify_header(name.strip(), value)
        result.append(
            _normalized_item(
                kind="HTTP",
                observation=observation,
                source=source,
                detail=detail,
                bearing=bearing,
                artifact_hash=digest,
            )
        )
    return result


def parse_headers_artifact(content: str, source: str) -> list[dict[str, object]]:
    headers: list[tuple[str, str]] = []
    for line in content.splitlines():
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers.append((name.strip(), value.strip()))
    return _header_records(headers, source, "Headers importados · valores de cookies removidos", sha256_hex(content))


def parse_har_artifact(content: str, source: str) -> list[dict[str, object]]:
    parsed = json.loads(content)
    entries = parsed.get("log", {}).get("entries", []) if isinstance(parsed, dict) else []
    if not isinstance(entries, list):
        raise ValueError("HAR log.entries must be an array")
    digest = sha256_hex(content)
    result = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        response = entry.get("response", {})
        request = entry.get("request", {})
        url = request.get("url", "") if isinstance(request, dict) else ""
        parts = urlsplit(url if isinstance(url, str) else "")
        safe_path = parts.path or "/"
        host_label = parts.hostname or "unknown host"
        status = response.get("status", "?") if isinstance(response, dict) else "?"
        response_headers = response.get("headers", []) if isinstance(response, dict) else []
        headers = [
            (str(header.get("name", "")), str(header.get("value", "")))
            for header in response_headers
            if isinstance(header, dict)
        ] if isinstance(response_headers, list) else []
        result.extend(
            _header_records(
                headers,
                source,
                f"HAR response {status} · {host_label}{safe_path} · cookie values removed",
                digest,
            )
        )
    return result


def parse_artifact(file_format: str, content: str, source: str) -> list[dict[str, object]]:
    if file_format == "json":
        return parse_json_artifact(content, source)
    if file_format == "har":
        return parse_har_artifact(content, source)
    if file_format == "headers":
        return parse_headers_artifact(content, source)
    raise ValueError("Unsupported artifact format")