import argparse
import json
import re
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


TIMEOUT = 10

SECURITY_HEADERS = {
    "Strict-Transport-Security": "HSTS",
    "Content-Security-Policy": "CSP",
    "X-Frame-Options": "Clickjacking Protection",
    "X-Content-Type-Options": "MIME Sniffing Protection",
    "Referrer-Policy": "Referrer Policy",
    "Permissions-Policy": "Permissions Policy",
}

COMMON_FILES = [
    "/robots.txt",
    "/sitemap.xml",
    "/security.txt",
    "/.well-known/security.txt",
]

SERVER_SIGNATURES = {
    "nginx": "Nginx",
    "apache": "Apache",
    "php": "PHP",
    "asp.net": "ASP.NET",
    "express": "Express",
    "django": "Django",
    "flask": "Flask",
    "wordpress": "WordPress",
    "laravel": "Laravel",
}


class PassiveScanner:

    def __init__(self, target):
        self.target = target.rstrip("/")

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PassiveSecurityAudit/1.0"
        })

        self.findings = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
            "info": [],
        }

        self.data = {
            "target": self.target,
            "final_url": None,
            "status": None,
            "server": None,
            "ip": None,
            "headers": {},
            "cookies": [],
            "technologies": [],
            "forms": [],
            "links": [],
            "common_files": {},
        }

    def add(self, severity, category, message):
        self.findings[severity].append({
            "category": category,
            "message": message
        })

    def request(self, url):
        try:
            return self.session.get(
                url,
                timeout=TIMEOUT,
                allow_redirects=True
            )
        except requests.RequestException as exc:
            self.add(
                "info",
                "HTTP",
                f"Falha ao acessar {url}: {exc}"
            )
            return None

    def analyze_http(self):

        response = self.request(self.target)

        if not response:
            return

        self.data["final_url"] = response.url
        self.data["status"] = response.status_code
        self.data["headers"] = dict(response.headers)
        self.data["server"] = response.headers.get("Server")

        parsed = urlparse(response.url)

        try:
            self.data["ip"] = socket.gethostbyname(parsed.hostname)
        except socket.gaierror:
            self.data["ip"] = None

        self.add(
            "info",
            "HTTP",
            f"HTTP {response.status_code} recebido"
        )

        if response.url != self.target:
            self.add(
                "info",
                "Redirect",
                f"Redirecionado para {response.url}"
            )

        if response.headers.get("Server"):
            self.add(
                "info",
                "Fingerprint",
                f"Servidor exposto: {response.headers['Server']}"
            )

        self.analyze_headers(response)
        self.analyze_cookies(response)
        self.analyze_html(response)

    def analyze_headers(self, response):

        for header, description in SECURITY_HEADERS.items():

            if header not in response.headers:

                self.add(
                    "medium",
                    "Security Header",
                    f"{description}: {header} ausente"
                )

            else:

                self.add(
                    "info",
                    "Security Header",
                    f"{header}: {response.headers[header]}"
                )

        # Headers que podem revelar tecnologia

        for header in [
            "X-Powered-By",
            "X-AspNet-Version",
            "X-AspNetMvc-Version"
        ]:

            if header in response.headers:

                self.add(
                    "low",
                    "Information Disclosure",
                    f"Header exposto: {header}: "
                    f"{response.headers[header]}"
                )

    def analyze_cookies(self, response):

        for cookie in response.cookies:

            info = {
                "name": cookie.name,
                "secure": cookie.secure,
                "httponly": None,
                "samesite": None,
            }

            self.data["cookies"].append(info)

            raw = str(cookie)

            if not cookie.secure:

                self.add(
                    "medium",
                    "Cookie",
                    f"Cookie '{cookie.name}' sem atributo Secure"
                )

            if "HttpOnly" not in raw:

                self.add(
                    "medium",
                    "Cookie",
                    f"Cookie '{cookie.name}' sem HttpOnly"
                )

            if "SameSite" not in raw:

                self.add(
                    "low",
                    "Cookie",
                    f"Cookie '{cookie.name}' sem SameSite"
                )

    def analyze_html(self, response):

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # --------------------------------------------------
        # Tecnologias
        # --------------------------------------------------

        html = response.text.lower()

        for signature, technology in SERVER_SIGNATURES.items():

            if signature in html:

                if technology not in self.data["technologies"]:

                    self.data["technologies"].append(
                        technology
                    )

                    self.add(
                        "info",
                        "Technology",
                        f"Tecnologia identificada: {technology}"
                    )

        # --------------------------------------------------
        # Forms
        # --------------------------------------------------

        forms = soup.find_all("form")

        for form in forms:

            method = form.get(
                "method",
                "GET"
            ).upper()

            action = form.get(
                "action",
                ""
            )

            inputs = []

            for field in form.find_all(
                ["input", "textarea", "select"]
            ):

                name = field.get("name")

                if name:
                    inputs.append(name)

            form_data = {
                "method": method,
                "action": urljoin(
                    response.url,
                    action
                ),
                "inputs": inputs,
            }

            self.data["forms"].append(form_data)

        if forms:

            self.add(
                "info",
                "Forms",
                f"{len(forms)} formulário(s) encontrado(s)"
            )

        # --------------------------------------------------
        # Links
        # --------------------------------------------------

        links = set()

        for link in soup.find_all("a", href=True):

            href = urljoin(
                response.url,
                link["href"]
            )

            links.add(href)

        self.data["links"] = sorted(links)

        self.add(
            "info",
            "Links",
            f"{len(links)} link(s) encontrado(s)"
        )

        # --------------------------------------------------
        # Comentários HTML
        # --------------------------------------------------

        comments = soup.find_all(
            string=lambda text:
            isinstance(text, str)
            and "<!--" in text
        )

        if comments:

            self.add(
                "low",
                "Information Disclosure",
                f"{len(comments)} comentário(s) HTML encontrado(s)"
            )

        # --------------------------------------------------
        # Meta generator
        # --------------------------------------------------

        generator = soup.find(
            "meta",
            attrs={"name": re.compile(
                "^generator$",
                re.I
            )}
        )

        if generator:

            content = generator.get(
                "content",
                "desconhecido"
            )

            self.add(
                "low",
                "Technology",
                f"Meta generator exposto: {content}"
            )

    def analyze_common_files(self):

        for path in COMMON_FILES:

            url = urljoin(
                self.target + "/",
                path.lstrip("/")
            )

            response = self.request(url)

            if not response:
                continue

            status = response.status_code

            self.data["common_files"][path] = status

            if status == 200:

                self.add(
                    "info",
                    "Public Resource",
                    f"Recurso público encontrado: {path}"
                )

            elif status in [401, 403]:

                self.add(
                    "info",
                    "Public Resource",
                    f"Recurso existente mas protegido: {path}"
                )

    def run(self):

        print("\n[+] Iniciando auditoria passiva...\n")

        self.analyze_http()
        self.analyze_common_files()

        return {
            "target": self.target,
            "data": self.data,
            "findings": self.findings
        }


def print_report(report):

    print("\n")
    print("=" * 70)
    print("           RELATÓRIO DE AUDITORIA PASSIVA")
    print("=" * 70)

    print(f"\nTarget : {report['target']}")
    print(f"Final  : {report['data']['final_url']}")
    print(f"Status : {report['data']['status']}")
    print(f"IP     : {report['data']['ip']}")
    print(f"Server : {report['data']['server']}")

    print("\n" + "-" * 70)
    print("ACHADOS")
    print("-" * 70)

    icons = {
        "critical": "[CRITICAL]",
        "high": "[HIGH]    ",
        "medium": "[MEDIUM]  ",
        "low": "[LOW]     ",
        "info": "[INFO]    ",
    }

    total = 0

    for severity in [
        "critical",
        "high",
        "medium",
        "low",
        "info"
    ]:

        findings = report["findings"][severity]

        if not findings:
            continue

        print(f"\n{icons[severity]}")

        for finding in findings:

            total += 1

            print(
                f"  [{finding['category']}] "
                f"{finding['message']}"
            )

    print("\n" + "-" * 70)
    print("RESUMO")
    print("-" * 70)

    for severity in [
        "critical",
        "high",
        "medium",
        "low",
        "info"
    ]:

        print(
            f"{severity.upper():10}: "
            f"{len(report['findings'][severity])}"
        )

    print(f"\nTotal de achados: {total}")

    print("\n" + "=" * 70)


def main():

    parser = argparse.ArgumentParser(
        description="Scanner passivo de segurança"
    )

    parser.add_argument(
        "url",
        help="URL do sistema autorizado para auditoria"
    )

    parser.add_argument(
        "--json",
        help="Salvar relatório JSON",
        metavar="ARQUIVO"
    )

    args = parser.parse_args()

    target = args.url

    if not target.startswith(("http://", "https://")):
        target = "https://" + target

    scanner = PassiveScanner(target)

    report = scanner.run()

    print_report(report)

    if args.json:

        with open(
            args.json,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                report,
                file,
                indent=2,
                ensure_ascii=False
            )

        print(
            f"\n[+] Relatório salvo em: {args.json}"
        )


if __name__ == "__main__":
    main()

