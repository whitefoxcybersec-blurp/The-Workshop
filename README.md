
# Workshop

Este workspace reúne três projetos de estudo e prototipagem em segurança,
observabilidade e processamento de eventos:

- `ARES`: servidor HTTP/1.1 em C, construído sobre sockets POSIX.
- `ARGUS`: mecanismo defensivo local de threat hunting em Python.
- `RAVEN`: motor de regras temporais e DSL Ruby para detecção de eventos.

A ideia do repositório é demonstrar, em pequenas etapas, como construir uma
pilha completa de ingestão, normalização, correlação, alerta e regras.

## Estrutura do workspace

```text
.
├── Makefile
├── README.md
├── public/
├── src/
├── include/
├── tests/
├── build/
├── argus/
│   ├── README.md
│   ├── config.yaml
│   ├── requirements.txt
│   ├── samples/
│   ├── rules/
│   ├── storage/
│   ├── detection/
│   └── tests/
├── raven/
│   ├── README.md
│   ├── Gemfile
│   ├── bin/
│   ├── lib/
│   ├── rules/
│   └── samples/
└── README.md
```

## 1) ARES

ARES é um servidor HTTP/1.1 didático em C, sem framework, com parsing manual de
requisições e resposta de arquivos estáticos em `public/`.

### Compilar e executar

```sh
make
make test
make run
```

O servidor escuta em `127.0.0.1:8080`.

```sh
curl -i http://localhost:8080/
```

Para limpar os artefatos gerados:

```sh
make clean
```

### Comportamento atual

- Parsing da linha de requisição e dos headers, exigindo `Host` em HTTP/1.1.
- Limite do cabeçalho em 16 KiB.
- Rejeição de requisições malformadas.
- Suporte a `GET`; demais métodos retornam `405 Method Not Allowed`.
- Mapeamento de `/` para `public/index.html`.
- Inferência de tipos MIME comuns.
- Proteção contra `..`, symlinks e acesso fora de `public/`.
- Limite de 16 MiB por arquivo servido.

## 2) ARGUS

ARGUS é um mecanismo defensivo local de threat hunting em Python. Ele normaliza
logs, aplica regras determinísticas, correlaciona eventos por IP, calcula risco
acumulado e persiste eventos e alertas em SQLite.

### Configurar e executar

```sh
python -m pip install -r argus/requirements.txt
python -m argus.main analyze argus/samples/ssh_bruteforce.jsonl
python -m argus.main timeline --src-ip 192.168.1.50
python -m argus.main serve
```

A API fica restrita a `127.0.0.1:8765` por padrão.

- `GET /health`
- `GET /alerts?limit=100`
- `GET /timeline?src_ip=192.168.1.50&limit=500`

O banco `argus.db` é criado no diretório do projeto.

### Deteções iniciais

- Falha de autenticação isolada não gera alerta.
- 15 falhas do mesmo IP em 30 segundos geram brute force.
- Login bem-sucedido após o limiar aumenta o risco acumulado.
- Mesmo IP observado em outra fonte adiciona correlação.
- Regras em YAML podem identificar eventos específicos, como autenticação bem-sucedida para `root`.

### Testes

```sh
python -m unittest discover -s argus/tests -v
```

## 3) RAVEN

RAVEN é um Ruby DSL e motor temporal para detecção defensiva. As regras são
blocos Ruby em vez de predicados YAML; o parser avalia cada arquivo em um
contexto DSL pequeno, agrupa eventos e aplica janelas temporais.

### Setup

```sh
cd raven
bundle install
bundle exec rspec
```

### Executar regras sobre JSONL

```sh
bin/raven --rules rules --input samples/auth.jsonl
cat events.jsonl | bin/raven --rules rules
```

Cada alerta é emitido como um JSON em stdout. Linhas JSONL inválidas são
reportadas em stderr e ignoradas.

### Exemplo de DSL

```ruby
rule "SSH Bruteforce" do
  description "Repeated SSH authentication failures from one source IP"

  where event: "authentication", result: "failed"
  match do |event|
    event["service"] == "ssh" || event.fetch("message", "").match?(/\bsshd\b/i)
  end

  group_by :src_ip
  threshold 10
  within 60.seconds
  severity :high

  on_match do |context|
    alert context
  end
end
```

## Fluxo sugerido

1. Compile e rode o servidor `ARES` para entender a base HTTP.
2. Rode o pipeline de normalização e correlação em `ARGUS`.
3. Use `RAVEN` para aplicar regras temporais sobre eventos normalizados.
4. Combine os três elementos para uma visão completa de detecção e resposta.

## Próximos passos

- manter o servidor `ARES` com suporte a conexões persistentes;
- evoluir a camada de detecção em `ARGUS`;
- expandir a base de regras em `RAVEN`;
- adicionar benchmarking e testes de integração no conjunto do workshop.
