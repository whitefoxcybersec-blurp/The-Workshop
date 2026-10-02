# GUIA DE TRANSIÇÃO: Hermes Extract v1 → v2 (Motor Contábil)

## 📋 O Que Mudou?

Sua ferramenta evoluiu de um **conversor de PDF para OFX** para um **motor contábil completo**.

### Compatibilidade Retroativa ✅

**A boa notícia:** Todo o código v1 continua funcionando!

```bash
# Isto continua funcionando exatamente como antes
python3 conversrOFX.py extrato.pdf --formato ofx,csv,json

# Saída:
# ✓ OFX: pdf/extrato.ofx
# ✓ CSV: pdf/extrato.csv
# ✓ JSON: pdf/extrato.json
```

### O Que É Novo

Agora você também tem:
- ✓ Banco de dados SQL com plano de contas
- ✓ Classificação automática de movimentos
- ✓ Criação de lançamentos contábeis (double-entry)
- ✓ Aprendizado de padrões de classificação
- ✓ Reconciliação automática
- ✓ Relatórios contábeis (Balancete, DRE)

---

## 🔄 Como Usar v2

### Opção 1: Modo Simples (Como Antes)

Se você apenas quer extrair e exportar:

```bash
python3 conversrOFX.py extrato.pdf --formato ofx,csv,json,xlsx
# Funciona exatamente como v1
```

### Opção 2: Modo Contábil (Novo!)

Para usar a contabilidade:

```bash
# 1. Execute o exemplo
python3 exemplo_contabil.py

# Isto irá:
# - Criar banco de dados (hermes_exemplo.db)
# - Registrar empresa
# - Setup plano de contas
# - Importar PDF
# - Classificar automaticamente
# - Gerar lançamentos
# - Produzir balancete
```

---

## 📊 Estrutura de Dados

### v1: Simples

```python
{
    'data': '20260830',
    'descricao': 'PAGAMENTO UBER',
    'valor': '-45.90'
}
```

### v2: Estruturado

```
MovimentoBancario (do banco)
    ├─ data: 2026-08-30
    ├─ descricao: "PAGAMENTO UBER"
    ├─ valor: -45.90
    └─ conciliado: False
         ↓
    LancamentoContabil (criado automaticamente)
        ├─ historico: "PAGAMENTO UBER"
        └─ partidas:
            ├─ Débito: 5.2.1.01.0046 (Transporte) = 45.90
            └─ Crédito: 1.1.1.02.0003 (Banco Itaú) = 45.90
                ✓ Balanceado!
```

---

## 🔀 Fluxo de Trabalho

### v1: Linear

```
PDF → Parser → OFX/CSV/JSON → Done
```

### v2: Completo

```
PDF
  ↓
Parser → MovimentoBancario
  ↓
ClassificadorService → Sugestão de Conta
  ↓
LancamentoService → Cria Lançamento
  ↓
ConciliadorService → Reconcilia
  ↓
Relatórios (Balancete, DRE)
```

---

## 💾 Instalação

### Dependências Novas

```bash
pip install sqlalchemy>=2.0.0
```

Ou use o requirements.txt atualizado:

```bash
pip install -r requirements.txt
```

### Banco de Dados

Escolha uma opção:

**SQLite** (padrão, recomendado para DEV):
```python
engine, Session = init_database("sqlite:///hermes.db")
```

**PostgreSQL** (produção):
```python
engine, Session = init_database(
    "postgresql://user:pass@localhost/hermes"
)
```

---

## 🚀 Primeiros Passos

### Passo 1: Setup Básico

```python
from hermes.database import init_database
from hermes.loaders import InitializerService

# Criar DB
engine, Session = init_database()
session = Session()

# Setup empresa
initializer = InitializerService(session)
empresa = initializer.inicializar_empresa(
    razao_social="SUA EMPRESA",
    cnpj="12.345.678/0001-00"
)
```

### Passo 2: Importar PDF

```python
from hermes.converter import ConversorOFX

conversor = ConversorOFX()
extrato = conversor.processar_pdf(Path("extrato.pdf"))
```

### Passo 3: Executar Pipeline

```python
from hermes.integracao import FluxoCompleto

fluxo = FluxoCompleto(session)
resultado = fluxo.executar_fluxo(
    conta_bancaria=conta,
    transacoes=extrato.transacoes
)

# Resultado com estatísticas de sucesso/erro
print(f"Taxa de sucesso: {resultado['resumo_final']['taxa_sucesso_percentual']:.1f}%")
```

---

## 🎓 Exemplos por Caso de Uso

### Caso 1: Apenas Exportar (v1 compatível)

```bash
python3 conversrOFX.py extrato.pdf --formato ofx,csv,json
# Sem banco de dados, sem contabilidade
```

### Caso 2: Contabilidade Simples

```python
# Importar e classificar automaticamente
from exemplo_contabil import exemplo_completo
exemplo_completo()
```

### Caso 3: Contabilidade Customizada

```python
from hermes.database import init_database
from hermes.services import ClassificadorService, LancamentoService

session = Session()
classificador = ClassificadorService(session)
lancador = LancamentoService(session)

# Sua lógica customizada aqui
```

### Caso 4: Adicionar Novas Regras

```python
from hermes.database import RegrasClassificacao

# Regra manual
nova_regra = RegrasClassificacao(
    empresa_id=1,
    palavra_chave="AWS",
    metodo="PARCIAL",
    conta_debito_id=55,           # Hospedagem
    conta_credito_id=3,           # Banco Itaú
    prioridade=15
)
session.add(nova_regra)
session.commit()

# Próximo movimento "AWS" será classificado automaticamente
```

---

## 🔍 Checklist de Migração

- [ ] Instalar SQLAlchemy: `pip install sqlalchemy>=2.0.0`
- [ ] Testar v1 (garantir compatibilidade): `python3 conversrOFX.py`
- [ ] Criar banco de dados: `init_database()`
- [ ] Setup empresa: `InitializerService.inicializar_empresa()`
- [ ] Criar conta bancária: `InitializerService.criar_conta_bancaria()`
- [ ] Executar exemplo: `python3 exemplo_contabil.py`
- [ ] Revisar lançamentos criados
- [ ] Adicionar regras customizadas
- [ ] Ir para produção ✓

---

## ⚠️ Coisas Importantes

### 1. Plano de Contas

O sistema vem com um plano **básico**. Você deve:
- ✓ Revisar e ajustar conforme sua empresa
- ✓ Adicionar/remover contas analíticas
- ✓ Definir hierarquia correta

```python
# Exemplo: Adicionar conta
nova_conta = PlanoContas(
    empresa_id=1,
    codigo="5.3.1.01.0099",
    descricao="MINHA DESPESA CUSTOMIZADA",
    tipo=TipoContaEnum.ANALITICA,
    natureza=NaturezaContaEnum.CREDORA,
    nivel=5,
    aceita_lancamento=True
)
```

### 2. Regras de Classificação

As regras vêm com exemplos:
- UBER → Transporte
- AWS → Hospedagem
- TARIFA → Tarifa Bancária

Você deve:
- ✓ Revisar e validar
- ✓ Adicionar regras specificas da sua empresa
- ✓ Ajustar prioridades conforme necessário

### 3. Movimentos Não Classificados

Alguns movimentos podem não ser classificados. Isto é normal!

```python
# Revisar e classificar manualmente
movimento = session.query(MovimentoBancario).filter(
    MovimentoBancario.conciliado == False
).first()

if movimento:
    # Você classifica manualmente
    classificacao = ClassificacaoSugerida(
        conta_debito_id=47,
        conta_credito_id=3,
        confianca=100.0
    )
    # E o sistema aprende!
```

### 4. Backup do Banco de Dados

```bash
# Backup SQLite
cp hermes.db hermes.db.backup

# Backup PostgreSQL
pg_dump hermes > hermes.sql
```

---

## 🚨 Troubleshooting

### Erro: "No module named 'sqlalchemy'"

```bash
pip install sqlalchemy>=2.0.0
```

### Erro: "Conta contábil não encontrada"

A conta precisa existir no plano de contas primeiro.

```python
# Verificar
contas = session.query(PlanoContas).filter(
    PlanoContas.empresa_id == empresa.id
).all()
for conta in contas:
    print(f"{conta.codigo}: {conta.descricao}")
```

### Movimento não é classificado

Isto pode ser:
1. Movimento com descrição muito genérica
2. Sem regras criadas
3. Confiança muito baixa

```python
# Debug: Ver resultado da classificação
classificacao = classificador.classificar(movimento)
if not classificacao:
    print(f"Sem classificação para: {movimento.descricao}")
    # Adicionar regra manualmente
```

### Taxa de sucesso baixa

Adicione mais regras:

```python
# Exemplo: Adicionar 10 regras customizadas
regras_empresa = [
    ("CLIENTE X", 4.1.0.01.0001, 3),  # Receita
    ("FORNECEDOR Y", 5.1.0.01.0001, 2),  # Despesa
    # etc...
]

for palavra, conta_deb, conta_cred in regras_empresa:
    nova_regra = RegrasClassificacao(
        empresa_id=1,
        palavra_chave=palavra,
        conta_debito_id=conta_deb,
        conta_credito_id=conta_cred
    )
    session.add(nova_regra)
session.commit()
```

---

## 📈 Próximos Passos

### Curto Prazo (Esta Semana)
- [ ] Revisar plano de contas
- [ ] Adicionar regras customizadas
- [ ] Testar com seus PDFs reais
- [ ] Revisar lançamentos criados

### Médio Prazo (Este Mês)
- [ ] Criar balancete
- [ ] Exportar para ERP
- [ ] Integrar com sistema fiscal

### Longo Prazo (Este Trimestre)
- [ ] Adicionar NF-e/NFS-e
- [ ] Criar dashboard
- [ ] Implementar IA para classificação

---

## 📚 Documentação

- `ARCHITECTURAL_DESIGN.md` - Design completo
- `README.md` - Documentação de uso
- `EVOLUTION.md` - Evolução do projeto
- `exemplo_contabil.py` - Exemplo completo
- `requirements.txt` - Dependências

---

## 🆘 Precisa de Ajuda?

Verifique:
1. `exemplo_contabil.py` - Execute e estude
2. `ARCHITECTURAL_DESIGN.md` - Entenda a arquitetura
3. `database.py` - Veja os modelos
4. `services.py` - Veja a lógica

Ou revise os 14 pontos da proposta original:

```
1. Transformar plano em estrutura hierárquica ✓
2. Separar conta de lançamento ✓
3. Criar tabela de lançamentos ✓
4. Validação double-entry ✓
5. Extrato como evento financeiro ✓
6. Motor de classificação ✓
7. Níveis de inteligência ✓
8. Aprendizado das classificações ✓
9. Empresas com planos diferentes ✓
10. Cadastro de bancos ✓
11. Parser isolado ✓
12. Motor contábil ✓
13. Limpar inconsistências ✓
14. Motor de parametrização ✓
```

**Tudo implementado!** 🎉

---

## ✅ Status

- ✓ Banco de dados com 14 tabelas
- ✓ 3 serviços principais (Classificador, Lançador, Conciliador)
- ✓ Pipeline completo PDF → Contabilidade
- ✓ Classificação com 3 níveis + aprendizado
- ✓ Validação contábil (double-entry)
- ✓ Exemplo funcionando
- ✓ Documentação completa

**Pronto para usar!** 🚀

---

**Versão**: 2.0.0
**Data**: 2026-08-30
**Status**: ✅ Produção
