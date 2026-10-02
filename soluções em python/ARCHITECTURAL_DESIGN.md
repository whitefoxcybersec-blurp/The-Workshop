# HERMES EXTRACT - MOTOR CONTÁBIL 🏛️

## A Evolução: De Conversor PDF para Plataforma Contábil

Este documento descreve a transformação arquitetural do Hermes Extract de um simples conversor de extrato bancário (PDF → OFX) para um **motor contábil profissional**.

---

## 📋 Índice

1. [Arquitetura Geral](#arquitetura-geral)
2. [Modelo de Dados](#modelo-de-dados)
3. [Componentes Principais](#componentes-principais)
4. [Fluxo de Processamento](#fluxo-de-processamento)
5. [Classificação Automática](#classificação-automática)
6. [Validação Contábil](#validação-contábil)
7. [Exemplos de Uso](#exemplos-de-uso)
8. [Próximas Fases](#próximas-fases)

---

## 🏗️ Arquitetura Geral

### Estrutura de Módulos

```
hermes/
├── database.py          ← Modelos SQLAlchemy (14 tabelas)
├── services.py          ← Lógica de negócio contábil
├── loaders.py           ← Carregamento de dados
├── integracao.py        ← Conexão parser ↔ contabilidade
│
├── parsers.py           ← Parser PDF/OFX (já existente)
├── exporters.py         ← Exportadores (já existente)
├── converter.py         ← Orquestração (já existente)
│
└── models.py            ← Modelos de domínio
    utils.py            ← Utilities
    __init__.py         ← Package init

exemplo_contabil.py      ← Exemplo completo
```

### Arquitetura em Camadas

```
┌─────────────────────────────────────────┐
│         APRESENTAÇÃO (CLI/Web)          │ ← conversrOFX.py + Flask/FastAPI
├─────────────────────────────────────────┤
│      ORQUESTRAÇÃO & FLUXOS               │ ← integracao.py (FluxoCompleto)
├─────────────────────────────────────────┤
│      SERVIÇOS DE NEGÓCIO                 │ ← services.py
│  - Classificador (IA de regras)          │
│  - Lançador (Double-entry)               │
│  - Conciliador (Reconciliação)           │
├─────────────────────────────────────────┤
│      IMPORTADORES & LOADERS              │ ← loaders.py, integracao.py
│  - PDF/OFX Parser → MovimentoBancario    │
│  - CSV de Plano de Contas                │
│  - Regras de Classificação               │
├─────────────────────────────────────────┤
│      MODELOS & PERSISTÊNCIA              │ ← database.py
│  - SQLAlchemy ORM                        │
│  - SQLite/PostgreSQL                     │
└─────────────────────────────────────────┘
```

---

## 📊 Modelo de Dados

### 14 Tabelas Principais

#### 1. **empresas** - Organizações

```python
Empresa
├── id
├── razao_social          # ACME CORP BRASIL
├── nome_fantasia         # ACME
├── cnpj                  # 12.345.678/0001-00
├── moeda                 # BRL
└── ativo
```

#### 2. **plano_contas** - Chart of Accounts

```python
PlanoContas
├── id
├── empresa_id            # Link to company
├── codigo                # "1.1.1.02.0003" (hierárquico)
├── descricao             # "BANCO ITAÚ"
├── tipo                  # SINTETICA ou ANALITICA
├── natureza              # DEVEDORA ou CREDORA
├── nivel                 # 1-5 (hierarchy)
├── aceita_lancamento     # True apenas para ANALITICA
└── conta_pai_id          # Referência hierárquica
```

**Hierarquia de Exemplo:**
```
1                                    (ATIVO - Nível 1)
└─ 1.1                              (ATIVO CIRCULANTE - Nível 2)
   └─ 1.1.1                         (DISPONIBILIDADES - Nível 3)
      └─ 1.1.1.02                   (BANCOS - Nível 4)
         └─ 1.1.1.02.0003           (BANCO ITAÚ - Nível 5) ✓ Aceita lançamento
```

#### 3. **contas_bancarias** - Bank Accounts

```python
ContaBancaria
├── id
├── empresa_id
├── banco_nome            # "BANCO ITAÚ"
├── banco_codigo          # "033"
├── agencia               # "1234"
├── conta                 # "56789-0"
├── conta_contabil_id     # Link a PlanoContas
├── saldo_inicial
├── saldo_atual
└── ativo
```

#### 4. **movimentos_bancarios** - Bank Movements

```python
MovimentoBancario
├── id
├── conta_bancaria_id     # Qual banco
├── data                  # 2026-08-30
├── descricao             # "UBER *TRIP"
├── valor                 # -45.90 (pode ser negativo)
├── saldo                 # Saldo corrente
├── conciliado            # True/False (reconciled?)
└── lancamento_id         # Link para lançamento contábil
```

#### 5. **lancamentos_contabeis** - Accounting Entries

```python
LancamentoContabil
├── id
├── empresa_id
├── data                  # 2026-08-30
├── historico             # "PAGAMENTO DE UBER"
├── origem                # EXTRATO_BANCARIO, NFSE, MANUAL, etc
├── status                # RASCUNHO, PENDENTE, APROVADO
├── conciliado            # True/False
└── partidas              # Relationship → N partidas
```

**Regra de Ouro:** 
```
Σ(débitos) = Σ(créditos)
```

#### 6. **partidas** - Line Items

```python
Partida
├── id
├── lancamento_id         # Qual lançamento
├── conta_id              # Qual conta
├── debito                # 2000.00 ou NULL
├── credito               # NULL ou 2000.00
├── centro_custo_id       # Opcional: cost center
└── projeto_id            # Opcional: project
```

**Exemplo de Lançamento Duplo:**
```
Lançamento #123: Pagamento de aluguel
├─ Partida 1: Débito em Despesa de Aluguel (4.2.1.01.0001) = 2000.00
└─ Partida 2: Crédito em Banco Itaú (1.1.1.02.0003) = 2000.00
   ✓ Balanceado: 2000 = 2000
```

**Exemplo de Lançamento Múltiplo:**
```
Lançamento #124: Compra com imposto
├─ Partida 1: Débito em Despesa (5.x) = 1000.00
├─ Partida 2: Débito em Imposto Recuperável = 180.00
└─ Partida 3: Crédito em Fornecedor = 1180.00
   ✓ Balanceado: 1180 = 1180
```

#### 7. **regras_classificacao** - Classification Rules

```python
RegrasClassificacao
├── id
├── empresa_id
├── palavra_chave         # "UBER"
├── metodo                # EXATA, PARCIAL, REGEX
├── conta_debito_id       # Débito em qual conta
├── conta_credito_id      # Crédito em qual conta
├── prioridade            # 0-100 (ordem de busca)
├── usos                  # Vezes usada
├── acertos               # Vezes confirmada
└── ativo
```

**Learning Metrics:**
```
Taxa de Acerto = acertos / usos * 100%

Ex: UBER
├─ Usos: 12
├─ Acertos: 11
└─ Taxa: 91.7% (confiável!)
```

---

## 🔄 Componentes Principais

### 1. ClassificadorService - Inteligência

**3 Níveis de Busca:**

```
Nível 1: EXATA
  "UBER *TRIP" == "UBER *TRIP" ?
  → Confiança: 100%

Nível 2: PARCIAL
  "UBER" in "UBER PAGTO VIA APP" ?
  → Confiança: 60-90% (baseado em prioridade)

Nível 3: HISTÓRICO
  Outros "UBER" foram classificados em qual conta?
  → Confiança: 45%
```

**Aprendizado:**
```python
classificador.aprender_classificacao(
    movimento,           # UBER *TRIP
    conta_debito_id,     # 5.2.1.01.0046 (Transporte)
    confirmado=True      # Usuário confirmou ✓
)
# Regra será atualizada com maior confiança na próxima vez
```

### 2. LancamentoService - Contabilidade

**Validações Automáticas:**
- ✓ Contas existem?
- ✓ Contas analíticas? (aceitam lançamentos)
- ✓ Débito = Crédito?
- ✓ Valor correto?

**Criação de Lançamento Simples:**
```python
lancador.criar_lancamento_simples(
    empresa_id=1,
    data=date(2026, 8, 30),
    historico="PAGAMENTO UBER",
    conta_debito_id=47,         # Despesa com Transporte
    conta_credito_id=3,         # Banco Itaú
    valor=Decimal("45.90")
)
```

### 3. ConciliadorService - Reconciliação

Automatiza o matching entre:
- Movimentos bancários
- Lançamentos contábeis

```python
conciliador.conciliar_movimento(
    movimento_id=123,
    lancamento_id=456
)
# Movimento agora está linked/reconciliado
```

### 4. InitializerService - Setup

```python
initializer = InitializerService(session)

# Setup completo de uma empresa
empresa = initializer.inicializar_empresa(
    razao_social="ACME CORP",
    cnpj="12.345.678/0001-00"
)
# Automaticamente:
# ✓ Cria empresa
# ✓ Carrega plano de contas
# ✓ Cria regras de classificação
# ✓ Setup padrão
```

---

## 🔀 Fluxo de Processamento

### Pipeline Completo: PDF → Contabilidade

```
┌─────────────────────────────────────────────────┐
│ 1. ARQUIVO PDF                                  │
│    ead-solucoes-2026-08-09.pdf                  │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 2. PARSING (Já existente)                       │
│    ConversorOFX().processar_pdf()               │
│    → Extrato com 20 Transacao objects           │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 3. IMPORTAÇÃO                                   │
│    ImportadorMovimentos.importar_lote()         │
│    → 20 MovimentoBancario objects no DB         │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 4. CLASSIFICAÇÃO (NEW!)                         │
│    ClassificadorService.classificar()           │
│    Nível 1: Exata    → Confiança 100%          │
│    Nível 2: Parcial  → Confiança 60%           │
│    Nível 3: Histórico → Confiança 45%          │
│                                                 │
│    Para cada movimento:                         │
│    UBER *TRIP → Classe: 5.2.1.01.0046         │
│    AWS → Classe: 5.2.1.01.0055                │
│    TARIFA → Classe: 5.2.2.01.0003             │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 5. CONTABILIZAÇÃO (NEW!)                        │
│    LancamentoService.criar_lancamento_simples() │
│                                                 │
│    Para cada movimento classificado:             │
│                                                 │
│    Movimento: UBER -45.90                      │
│    ↓                                            │
│    Lançamento #101:                             │
│    ├─ D: 5.2.1.01.0046 (Transporte) = 45.90   │
│    └─ C: 1.1.1.02.0003 (Banco Itaú) = 45.90   │
│       ✓ Balanceado                             │
│                                                 │
│    Status: RASCUNHO → (manual review)          │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 6. APRENDIZADO (NEW!)                           │
│    ClassificadorService.aprender_classificacao()│
│                                                 │
│    Usuário confirmou:                           │
│    "UBER → Transporte" ✓                       │
│                                                 │
│    Regra atualizada:                            │
│    taxa_acerto: 11/12 = 91.7%                 │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 7. APROVAÇÃO (Manual ou Automática)             │
│    LancamentoService.aprovar_lancamento()       │
│                                                 │
│    Status: RASCUNHO → APROVADO                 │
│                                                 │
│    Lançamento agora é válido para:             │
│    ✓ Balancete (Trial Balance)                 │
│    ✓ DRE (Income Statement)                    │
│    ✓ Exportação para ERP                       │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 8. RECONCILIAÇÃO                                │
│    ConciliadorService.conciliar_movimento()     │
│                                                 │
│    Movimento #50 (UBER) ←→ Lançamento #101    │
│    Status: CONCILIADO                          │
│                                                 │
│    Relatório:                                   │
│    ├─ Total de movimentos: 20                  │
│    ├─ Conciliados: 18                          │
│    └─ Pendentes: 2                             │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│ 9. RELATÓRIOS                                   │
│    - Balancete (Trial Balance)                  │
│    - DRE (Income Statement)                     │
│    - Reconciliação Bancária                     │
│    - Exportação (OFX, CSV, JSON)               │
└─────────────────────────────────────────────────┘
```

---

## 🧠 Classificação Automática

### Camadas de Inteligência

```python
def classificar(movimento: MovimentoBancario):
    
    # Camada 1: Regra Exata (Alta confiança)
    if "UBER *TRIP" == movimento.descricao:
        return ClassificacaoSugerida(
            conta_debito=5.2.1.01.0046,
            confianca=100.0,
            metodo="EXATA"
        )
    
    # Camada 2: Palavra-chave Parcial (Média confiança)
    if "UBER" in movimento.descricao:
        return ClassificacaoSugerida(
            conta_debito=5.2.1.01.0046,
            confianca=75.0,
            metodo="PARCIAL"
        )
    
    # Camada 3: Histórico Semelhante (Baixa confiança)
    if existe_movimento_similar("UBER"):
        return ClassificacaoSugerida(
            conta_debito=5.2.1.01.0046,
            confianca=45.0,
            metodo="HISTORICO"
        )
    
    # Sem classificação
    return None
```

### Exemplo Real

```
Movimento 1: "UBER PAGTO VIA APP" -45.90
├─ Nível 1 (EXATA): Não encontrado
├─ Nível 2 (PARCIAL): "UBER" encontrado ✓
│  └─ Prioridade: 10
│     Confiança: 60% + (10 * 1) = 70%
│     Conta: 5.2.1.01.0046 (Transporte)
│
├─ Usuário confirma ✓
│
└─ Regra atualizada:
   Usos: 1 → 2
   Acertos: 1 → 2
   Taxa: 100% (muito confiável!)

Movimento 2: "UBER" -32.50 (dias depois)
├─ Nível 1 (EXATA): Não encontrado
├─ Nível 2 (PARCIAL): "UBER" encontrado ✓
│  └─ Prioridade: 10
│     Confiança: 60% + (10 * 1) = 70%
│     Conta: 5.2.1.01.0046 (Transporte)
│     Taxa histórica: 100% (muito confiável!)
│     Confiança ajustada: 85%
│
└─ Sistema aprova automaticamente ✓
```

---

## ✓ Validação Contábil

### Princípio Fundamental: Débito = Crédito

Toda criação de lançamento valida:

```python
def criar_lancamento_simples(...):
    lancamento.partidas.append(Partida(..., debito=2000, credito=0))
    lancamento.partidas.append(Partida(..., debito=0, credito=2000))
    
    # Validação automática
    assert lancamento.total_debitos() == lancamento.total_creditos()
    # 2000 == 2000 ✓
```

**Se não passar:**
```
ValueError: Lançamento não balanceado (débito ≠ crédito)
```

### Validações de Contas

```python
def criar_lancamento_simples(..., conta_debito_id, conta_credito_id):
    conta_deb = PlanoContas.get(conta_debito_id)
    conta_cred = PlanoContas.get(conta_credito_id)
    
    # Validação 1: Contas existem?
    assert conta_deb is not None
    
    # Validação 2: Contas são analíticas?
    assert conta_deb.aceita_lancamento == True  # ANALITICA
    assert conta_cred.aceita_lancamento == True
    
    # Validação 3: Tipo de conta?
    # (SINTETICA: não aceita / ANALITICA: aceita)
```

---

## 📖 Exemplos de Uso

### Exemplo 1: Setup Básico

```python
from hermes.database import init_database
from hermes.loaders import InitializerService

# 1. Criar banco de dados
engine, Session = init_database("hermes.db")
session = Session()

# 2. Inicializar empresa completa
initializer = InitializerService(session)
empresa = initializer.inicializar_empresa(
    razao_social="ACME CORP",
    cnpj="12.345.678/0001-00"
)

# 3. Criar conta bancária
conta = initializer.criar_conta_bancaria(
    empresa_id=empresa.id,
    banco_nome="BANCO ITAÚ",
    agencia="1234",
    conta="56789-0"
)

# ✓ Setup completo em 3 passos!
```

### Exemplo 2: Fluxo Completo PDF → Contabilidade

```python
from hermes.converter import ConversorOFX
from hermes.integracao import FluxoCompleto

# 1. Extrair PDF
conversor = ConversorOFX()
extrato = conversor.processar_pdf(Path("extrato.pdf"))

# 2. Executar fluxo completo
fluxo = FluxoCompleto(session)
resultado = fluxo.executar_fluxo(
    conta_bancaria=conta,
    transacoes=extrato.transacoes,
    aprovar_entradas=False  # Revisão manual
)

# Resultado:
# {
#     "fase_importacao": {"movimentos_importados": 20},
#     "fase_processamento": {
#         "total": 20,
#         "sucesso": 18,
#         "nao_classificados": 1,
#         "erros": 1
#     },
#     "resumo_final": {
#         "taxa_sucesso_percentual": 90.0
#     }
# }
```

### Exemplo 3: Classificação Manual

```python
from hermes.services import ClassificadorService, LancamentoService

classificador = ClassificadorService(session)
lancador = LancamentoService(session)

# 1. Classificar movimento
movimento = session.query(MovimentoBancario).first()
classificacao = classificador.classificar(movimento)

if classificacao:
    # 2. Criar lançamento
    lancamento = lancador.criar_lancamento_simples(
        empresa_id=1,
        data=movimento.data,
        historico=movimento.descricao,
        conta_debito_id=classificacao.conta_debito_id,
        conta_credito_id=classificacao.conta_credito_id,
        valor=abs(movimento.valor)
    )
    
    # 3. Aprender desta classificação
    classificador.aprender_classificacao(
        movimento,
        classificacao.conta_debito_id,
        confirmado=True
    )
    
    print(f"Lançamento #{lancamento.id} criado e aprendizado atualizado!")
```

---

## 🚀 Próximas Fases

### Phase 5: Fiscal (NF-e / NFS-e)

```
Documento Fiscal
    ↓
Parser XML
    ↓
Movimento Fiscal (ItemNFe)
    ↓
Contabilização Automática
    ├─ Débito: Despesa/Ativo
    └─ Crédito: Fornecedor/Caixa
```

### Phase 6: Relatórios Contábeis

```
Balancete (Trial Balance)
    ├─ Contas: Código, Descrição
    └─ Saldos: Débito, Crédito

DRE (Income Statement)
    ├─ Receitas
    ├─ Despesas
    └─ Resultado

Fluxo de Caixa
    ├─ Entradas
    ├─ Saídas
    └─ Saldo
```

### Phase 7: Integração ERP

```
Hermes Extract
    ↓
API REST
    ↓
┌─ Domínio
├─ Alterdata
├─ Conta Azul
└─ Omie
```

### Phase 8: IA/ML Avançado

```
LLM para Classificação
├─ Treino em histórico
├─ Reconhecimento de padrões
└─ Sugestões inteligentes

Análise de Anomalias
├─ Valores incomuns
├─ Padrões suspeitos
└─ Alertas de fraude
```

---

## 📈 Evolução Completa

### De Simples...

```
conversrOFX.py (170 linhas)
├─ extrair_texto_pdf()
├─ parse_transacoes()
└─ gerar_ofx()
```

### Para Complexo e Profissional

```
hermes/ (6000+ linhas)
├── database.py         (14 tabelas SQL)
├── services.py         (3 services: Classificador, Lançador, Conciliador)
├── loaders.py          (Setup automático)
├── integracao.py       (Pipeline completo)
├── parsers.py          (Multi-banco)
└── exporters.py        (5 formatos)
```

### Funcionalidades

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Formatos | OFX | OFX + CSV + JSON + XLSX + XML |
| Bancos | 1 genérico | 8 + extensível |
| Contabilidade | ❌ | ✓ Double-entry |
| Classificação | ❌ | ✓ 3 níveis + aprendizado |
| Reconciliação | ❌ | ✓ Automática |
| Validação | Nenhuma | Completa |
| Banco de Dados | ❌ | ✓ 14 tabelas |

---

## 🔗 Conexões Importantes

1. **Parser → MovimentoBancario**
   - Transacao (do PDF) → MovimentoBancario (no DB)

2. **MovimentoBancario → LancamentoContabil**
   - Através de ClassificadorService
   - Via RegrasClassificacao
   - Com aprendizado contínuo

3. **LancamentoContabil → Relatórios**
   - Balancete
   - DRE
   - Reconciliação

4. **Empresa** é o ponto de integração
   - Uma empresa tem: Plano de Contas + Contas Bancárias + Regras
   - Tudo isolado e seguro por empresa_id

---

## 📚 Arquivos Relacionados

- `database.py` - Esquema completo
- `services.py` - Lógica contábil
- `loaders.py` - Inicialização
- `integracao.py` - Pipeline
- `exemplo_contabil.py` - Demonstração completa
- `ARCHITECTURAL_DESIGN.md` - Este arquivo

---

**Versão**: 2.0.0
**Data**: 2026-08-30
**Status**: ✅ Arquitetura Pronta para Implementação

Este é o caminho completo para transformar um conversor simples em uma plataforma contábil profissional. 🦊⚙️
