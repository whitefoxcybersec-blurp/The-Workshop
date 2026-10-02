
# The Workshop

Este workspace está sendo estruturado como um laboratório de engenharia de
segurança e observabilidade, com três camadas bem definidas e um contrato de
integração claro entre elas.

- ARES: infraestrutura, sockets, HTTP e baixo nível.
- ARGUS: ingestão, normalização, correlação e inteligência.
- RAVEN: regras declarativas, detecção temporal e alerta.
- CERBERUS: camada futura de integração, orquestração e resposta.

A ideia não é apenas “três projetos em linguagens diferentes”, mas um pipeline
funcional em que cada componente cumpre uma responsabilidade bem delimitada.

## Estrutura de referência do workshop

A organização abaixo representa o desenho desejado para o laboratório conforme o
projeto cresce. A estrutura atual pode evoluir naturalmente, mas a arquitetura
conceitual já está bem definida.

```text
The-Workshop/
├── README.md
├── Makefile
│
├── ares/
│   ├── README.md
│   ├── Makefile
│   ├── src/
│   ├── include/
│   ├── public/
│   ├── tests/
│   └── build/
│
├── argus/
│   ├── README.md
│   ├── config.yaml
│   ├── requirements.txt
│   ├── samples/
│   ├── rules/
│   ├── storage/
│   ├── detection/
│   └── tests/
│
├── raven/
│   ├── README.md
│   ├── Gemfile
│   ├── bin/
│   ├── lib/
│   ├── rules/
│   └── samples/
│
├── cerberus/
│   └── README.md
│
├── docs/
│   └── architecture/
│
└── tests/
    └── integration/
```

## Orquestração pelo Makefile raiz

O `Makefile` da raiz deve funcionar como orquestrador do workshop, reunindo todos
os runtimes em uma mesma rotina de verificação.

```make
ares:
	$(MAKE) -C ares

test-ares:
	$(MAKE) -C ares test

test-argus:
	python -m unittest discover -s argus/tests -v

test-raven:
	cd raven && bundle exec rspec

test: test-ares test-argus test-raven
```

A experiência desejada é simples:

```sh
make test
```

E aí o laboratório só é considerado saudável se C, Python e Ruby passarem juntos.

## Architecture

A arquitetura do workshop já deixa claro que o sistema não é apenas “três
programas independentes”. Ele é um pipeline de eventos com responsabilidades bem
separadas.

```text
                 THE WORKSHOP

                     EVENT
                       │
              ┌────────▼────────┐
              │      ARES       │
              │        C        │
              │ HTTP / Systems  │
              └────────┬────────┘
                       │
                    JSONL
                       │
              ┌────────▼────────┐
              │      ARGUS      │
              │     Python      │
              │ Correlation /   │
              │ Risk Analysis   │
              └────────┬────────┘
                       │
                Normalized Event
                       │
              ┌────────▼────────┐
              │      RAVEN      │
              │      Ruby       │
              │ Temporal Rules  │
              └────────┬────────┘
                       │
                     ALERT
                       │
                       ▼
              ┌─────────────────┐
              │    CERBERUS     │
              │  Integration    │
              └─────────────────┘
```

## Componentes

### ARES

ARES é a camada de infraestrutura e baixo nível. Ele produz eventos de sistema e
HTTP, valida entrada e limita o alcance da superfície de ataque.

Decisões que já dão substância ao componente:

- parsing de requisições HTTP/1.1;
- exigência de `Host` em HTTP/1.1;
- limite de cabeçalho em 16 KiB;
- rejeição de requisições malformadas;
- proteção contra traversal e symlinks;
- limitação de tamanho do arquivo servido;
- mapeamento de `/` para `public/index.html`.

### ARGUS

ARGUS é a camada de ingestão, correlação e inteligência. Ele entende eventos,
normaliza fontes heterogêneas e calcula risco conforme padrões de comportamento.

Decisões já incorporadas:

- persistência em SQLite;
- correlação por IP e janela temporal;
- agregação de risco e eventos por contexto;
- regras determinísticas e lógica de incident detection;
- arquitetura pronta para evoluir para um motor de anomalias e score mais rico.

### RAVEN

RAVEN é a camada declarativa. Ele traduz regra temporal em lógica legível,
utilizando janelas de tempo, agrupamento por chave e avaliação de eventos.

Decisões já incorporadas:

- `group_by` para separação de fluxos temporais;
- `threshold` e `within` para regras de detecção;
- avaliação por janela de tempo;
- DSL expressiva para detectar atividade repetitiva ou suspeita.

### CERBERUS

CERBERUS representa a etapa futura de integração e resposta. Ele será o ponto em
que alertas gerados pelo pipeline podem ser consumidos por mecanismos de
orquestração, enriquecimento, ação e observabilidade.

O nome funciona como o “coração do sistema” que conecta detecção à execução.

## Event Schema v1

A partir do momento em que o pipeline ganha um protocolo compartilhado, os três
runtimes deixam de ser apenas projetos independentes e passam a formar uma
arquitetura coerente.

O esquema abaixo é a base do contrato interno do workshop:

```json
{
  "schema": "workshop.event.v1",
  "timestamp": "2026-10-02T13:37:00Z",
  "source": "ares",
  "event": "http_request",
  "src_ip": "127.0.0.1",
  "attributes": {
    "method": "GET",
    "path": "/",
    "status": 200
  }
}
```

Esse contrato é importante porque:

- ARES produz eventos com estrutura estável;
- ARGUS entende, enriquece e normaliza esses dados;
- RAVEN avalia regras sobre esse mesmo payload;
- CERBERUS, no futuro, pode consumir esse mesmo formato para resposta e automação.

## Fluxo de valor do workshop

1. ARES observa e gera eventos de infraestrutura e HTTP.
2. ARGUS ingere e correlaciona esses eventos em contexto.
3. RAVEN avalia regras temporais sobre os eventos normalizados.
4. CERBERUS integra alertas e decisões em um plano maior de resposta.

Em outras palavras, o workshop deixa de ser um conjunto de mini projetos e se
transforma em um protocolo interno entre runtimes.

## Próximos passos

- reorganizar a estrutura física para separar `ares`, `argus` e `raven` em
  módulos independentes;
- consolidar o `Event Schema v1` como contrato compartilhado;
- manter `make test` como a verificação central do laboratório;
- evoluir `CERBERUS` como camada de integração e resposta;
- expandir testes de integração para garantir que C, Python e Ruby trabalhem
  contra o mesmo contrato de eventos.

## Estado atual

O laboratório já tem substância suficiente para ser tratado como projeto de
engenharia, e não apenas como coleção de experimentos isolados. O que está em
jogo agora é a maturidade do pipeline: padronizar a troca de eventos, dar
consistência à arquitetura e transformar cada runtime em peça de um sistema
coeso.

Esse é o ponto em que o workshop deixa de ser “três projetos simultâneos” e se
transforma em uma plataforma de detecção e resposta de eventos.
