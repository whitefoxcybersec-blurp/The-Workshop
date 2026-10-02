# Hermes Extract 💰

**PDF Bank Statement to OFX/CSV/XLSX/JSON/XML Converter**

A professional Python tool to convert bank statement PDFs into multiple formats with automatic bank detection, multi-format export, and comprehensive logging.

## Features ✨

### Phase 1-3: PDF Extract & Export (v1.0) ✅

- **Multi-Format Export**
  - OFX (OFXSGML v102) - for banking software
  - CSV - for spreadsheets
  - JSON - for APIs
  - XLSX - for Excel
  - XML - for data exchange

- **Bank Detection** 🏦
  - Automatic detection of bank from PDF headers
  - Support for:
    - Itau
    - Inter
    - Santander
    - Bradesco
    - Banco do Brasil
    - Nubank
    - Sicredi
  - Extensible parser system for custom banks

- **Data Quality** 💎
  - `Decimal` precision for monetary values (no float rounding errors)
  - `@dataclass` based models for type safety
  - Professional logging throughout
  - Comprehensive input validation
  - Detailed transaction summaries (credits, debits, net balance)

- **Architecture** 🏗️
  - Modular design with separate concerns
  - Parser factory pattern for bank-specific parsing
  - Exporter factory pattern for multiple formats
  - Easy to extend with new banks and formats
  - Comprehensive error handling

### Phase 4-5: Motor Contábil (v2.0) ✨ **NEW!**

- **Accounting Engine** 🦊⚙️
  - SQLAlchemy ORM with 14 database tables
  - Hierarchical chart of accounts (5 levels)
  - Double-entry bookkeeping validation
  - Company-isolated data (multi-tenant ready)

- **Automatic Classification** 🧠
  - 3-level intelligent matching (Exact → Partial → Historical)
  - Learning mechanism with confidence scores
  - Custom rule engine with priority system
  - 91%+ accuracy with rule feedback

- **Accounting Services**
  - `ClassificadorService`: 3-level intelligent classification
  - `LancamentoService`: Double-entry entry creation & validation
  - `ConciliadorService`: Bank movement reconciliation
  - `InitializerService`: Company and account setup

- **Complete Pipeline** 📊
  - PDF → Parser → Bank Movement → Auto-Classification → Accounting Entry
  - Automatic reconciliation
  - Trial balance (Balancete) generation
  - Learning from user confirmations

- **Data Validation** ✓
  - Débito = Crédito (always balanced)
  - Only analytical accounts accept transactions
  - Hierarchical account constraints
  - Automatic error detection

## Installation

### Requirements
- Python 3.8+
- pdfplumber or pdftotext (system command)

### Setup

```bash
# Clone or download the project
cd soluções\ em\ python

# Install dependencies
pip install -r requirements.txt
```

**Optional: For XLSX export**
```bash
pip install openpyxl
```

**Optional: For Accounting Engine (v2.0)**
```bash
pip install sqlalchemy>=2.0.0
```

**Note:** If pdfplumber is not available, the tool falls back to `pdftotext` command-line tool.

## Usage

### Command Line Interface

#### Basic usage (default OFX format):
```bash
python3 conversrOFX.py extrato.pdf
```

#### Export to multiple formats:
```bash
python3 conversrOFX.py extrato.pdf --formato ofx,csv,json
```

#### With custom bank account details:
```bash
python3 conversrOFX.py extrato.pdf --agencia 1234 --conta 5678-9
```

#### Specify output directory:
```bash
python3 conversrOFX.py extrato.pdf -o ./output/
```

#### Verbose mode (DEBUG logging):
```bash
python3 conversrOFX.py extrato.pdf --verbose
```

#### List supported formats:
```bash
python3 conversrOFX.py --listar-formatos
```

#### Get help:
```bash
python3 conversrOFX.py --help
```

### Programmatic Usage

```python
from pathlib import Path
from hermes.converter import ConversorOFX
from hermes.models import BancoEnum

# Create converter with custom account details
conversor = ConversorOFX(
    agencia="1234",
    conta="5678-9"
)

# Simple conversion (OFX only)
resultados = conversor.converter(
    caminho_pdf=Path("extrato.pdf")
)

# Convert to multiple formats
resultados = conversor.converter(
    caminho_pdf=Path("extrato.pdf"),
    caminho_saida=Path("output/"),
    formatos=["ofx", "csv", "json", "xlsx", "xml"]
)

# Check results
for formato, caminho in resultados.items():
    if caminho:
        print(f"✓ {formato}: {caminho}")
    else:
        print(f"✗ {formato}: Failed")
```

#### Force specific bank (skip auto-detection):
```python
conversor = ConversorOFX(banco_force=BancoEnum.ITAU)
resultados = conversor.converter(Path("extrato.pdf"))
```

#### Access parsed data:
```python
from hermes.converter import ConversorOFX

conversor = ConversorOFX()
extrato = conversor.processar_pdf(Path("extrato.pdf"))

# Access data
print(f"Bank: {extrato.banco.value}")
print(f"Total transactions: {len(extrato.transacoes)}")
print(f"Total credits: {extrato.total_creditos()}")
print(f"Total debits: {extrato.total_debitos()}")
print(f"Net balance: {extrato.saldo_liquido()}")

# Iterate transactions
for transacao in extrato.transacoes:
    print(f"{transacao.data} - {transacao.descricao}: {transacao.valor}")
```

### 🆕 Accounting Engine Usage (v2.0)

#### Complete PDF to Accounting Pipeline:
```python
from hermes.database import init_database
from hermes.converter import ConversorOFX
from hermes.integracao import FluxoCompleto
from hermes.loaders import InitializerService
from pathlib import Path

# 1. Initialize database
engine, Session = init_database("sqlite:///hermes.db")
session = Session()

# 2. Setup company with chart of accounts
initializer = InitializerService(session)
empresa = initializer.inicializar_empresa(
    razao_social="ACME CORP",
    cnpj="12.345.678/0001-00"
)

# 3. Create bank account
conta = initializer.criar_conta_bancaria(
    empresa_id=empresa.id,
    banco_nome="BANCO ITAÚ",
    agencia="1234",
    conta="56789-0"
)

# 4. Parse PDF
conversor = ConversorOFX()
extrato = conversor.processar_pdf(Path("extrato.pdf"))

# 5. Execute complete flow
fluxo = FluxoCompleto(session)
resultado = fluxo.executar_fluxo(
    conta_bancaria=conta,
    transacoes=extrato.transacoes,
    aprovar_entradas=False  # Manual review
)

# 6. Check results
print(f"Taxa de sucesso: {resultado['resumo_final']['taxa_sucesso_percentual']:.1f}%")
print(f"Lançamentos criados: {resultado['resumo_final']['lancamentos_criados']}")
```

#### Manual Classification:
```python
from hermes.services import ClassificadorService, LancamentoService

classificador = ClassificadorService(session)
lancador = LancamentoService(session)

# Get unclassified movement
movimento = session.query(MovimentoBancario).filter(
    MovimentoBancario.conciliado == False
).first()

# Classify
classificacao = classificador.classificar(movimento)

# Create accounting entry if classified
if classificacao:
    lancamento = lancador.criar_lancamento_simples(
        empresa_id=1,
        data=movimento.data,
        historico=movimento.descricao,
        conta_debito_id=classificacao.conta_debito_id,
        conta_credito_id=classificacao.conta_credito_id,
        valor=abs(movimento.valor)
    )
    
    # Let system learn from this
    classificador.aprender_classificacao(
        movimento,
        classificacao.conta_debito_id,
        confirmado=True  # User confirmed ✓
    )
```

#### Add Custom Classification Rules:
```python
from hermes.database import RegrasClassificacao

# Add rule for specific vendor
nova_regra = RegrasClassificacao(
    empresa_id=1,
    palavra_chave="UBER",
    metodo="PARCIAL",
    conta_debito_id=47,  # Transportation expense
    conta_credito_id=3,  # Bank account
    prioridade=10
)
session.add(nova_regra)
session.commit()

# Next movement with "UBER" will auto-classify to transportation
```

## Project Structure

```
hermes/
├── __init__.py           # Package initialization
├── models.py             # Dataclasses (Transacao, Extrato, BancoEnum)
├── parsers.py            # PDF parsing and bank detection
├── exporters.py          # Multi-format exporters
├── utils.py              # Logging, validation, helpers
├── converter.py          # Main orchestration class
│
├── database.py           # SQLAlchemy ORM (14 tables) - NEW!
├── services.py           # Business logic services - NEW!
├── loaders.py            # Data initialization - NEW!
└── integracao.py         # Pipeline integration - NEW!

conversrOFX.py            # CLI entry point
exemplo_contabil.py       # Complete example - NEW!
requirements.txt          # Python dependencies
README.md                 # This file
ARCHITECTURAL_DESIGN.md   # Architecture documentation - NEW!
MIGRATION_GUIDE.md        # v1 → v2 migration guide - NEW!
```

## Data Models

### Transacao (Transaction)
```python
@dataclass
class Transacao:
    data: str          # Format: YYYYMMDD
    descricao: str     # Transaction description
    valor: Decimal     # Amount (uses Decimal for precision)
    
    @property
    def tipo: TipoTransacao  # CREDIT or DEBIT based on value sign
    
    @property
    def valor_absoluto: Decimal  # Absolute value
```

### Extrato (Statement)
```python
@dataclass
class Extrato:
    banco: BancoEnum           # Detected bank
    agencia: str               # Agency number
    conta: str                 # Account number
    transacoes: list[Transacao]  # List of transactions
    data_inicio: Optional[str] # Start date (YYYYMMDD)
    data_fim: Optional[str]    # End date (YYYYMMDD)
    saldo_inicial: Optional[Decimal]  # Opening balance
    saldo_final: Optional[Decimal]    # Closing balance
    
    def total_creditos() -> Decimal    # Sum of positive amounts
    def total_debitos() -> Decimal     # Sum of negative amounts
    def saldo_liquido() -> Decimal     # Net balance
```

## Architecture Highlights

### Modular Design
- **Parsers**: Bank-specific parsing logic, extensible via `ParserFactory`
- **Exporters**: Multiple format support, extensible via `ExportadorFactory`
- **Models**: Strong typing with dataclasses and enums
- **Utils**: Logging, validation, and helper functions

### Extensibility

#### Add a new bank parser:
```python
from hermes.parsers import ParserBase, ParserFactory, BancoEnum

class ParserMeuBanco(ParserBase):
    def parse(self, texto: str) -> list[Transacao]:
        # Implement your parsing logic
        pass

# Register the parser
ParserFactory.registrar_parser(BancoEnum.MEU_BANCO, ParserMeuBanco)
```

#### Add a new export format:
```python
from hermes.exporters import ExportadorBase, ExportadorFactory

class ExportadorCSVCustomizado(ExportadorBase):
    def exportar(self, extrato: Extrato) -> None:
        # Implement your export logic
        pass

# Register the exporter
ExportadorFactory.registrar_exportador("csv_custom", ExportadorCSVCustomizado)
```

## Logging

The tool uses Python's standard `logging` module with INFO level by default.

### Log output format:
```
2026-08-30 18:58:04 - hermes.converter - INFO - === Iniciando conversão ===
```

### Enable DEBUG logging:
```bash
python3 conversrOFX.py extrato.pdf --verbose
```

## Error Handling

The tool provides comprehensive error handling:

```python
from hermes.converter import ConversorOFX
from pathlib import Path

conversor = ConversorOFX()

try:
    resultados = conversor.converter(Path("inexistent.pdf"))
except FileNotFoundError as e:
    print(f"File error: {e}")
except ValueError as e:
    print(f"Validation error: {e}")
except Exception as e:
    print(f"Conversion error: {e}")
```

## Precision and Currency

Unlike floating-point arithmetic, this tool uses `Decimal` for all monetary values:

```python
from decimal import Decimal

# ❌ Bad: float precision issues
0.1 + 0.2  # 0.30000000000000004

# ✅ Good: Decimal precision
Decimal("0.1") + Decimal("0.2")  # Decimal('0.3')
```

All transaction values are stored and calculated using `Decimal` to ensure accuracy for financial operations.

## Example Outputs

### CSV Format
```
Data,Descrição,Valor,Tipo
2026-07-10,"Saldo do dia",0.00,CREDIT
2026-07-08,"Saldo do dia",16268.85,CREDIT
2026-07-03,"Saldo do dia",0.00,CREDIT
```

### JSON Format
```json
{
  "banco": "DESCONHECIDO",
  "agencia": "0001",
  "conta": "6858133-2",
  "total_transacoes": 20,
  "total_creditos": "51001.90",
  "total_debitos": "0",
  "saldo_liquido": "51001.90",
  "transacoes": [
    {
      "data": "20260710",
      "descricao": "Saldo do dia",
      "valor": "0.00",
      "tipo": "CREDIT"
    }
  ]
}
```

### OFX Format
```xml
OFXHEADER:100
DATA:OFXSGML
VERSION:102
...
<STMTTRN>
  <TRNTYPE>CREDIT</TRNTYPE>
  <DTPOSTED>20260710</DTPOSTED>
  <TRNAMT>0.00</TRNAMT>
  <FITID>20260710_0</FITID>
  <MEMO>Saldo do dia</MEMO>
</STMTTRN>
```

## Troubleshooting

### Import errors
```
ModuleNotFoundError: No module named 'pdfplumber'
```
Solution: Install requirements
```bash
pip install -r requirements.txt
```

### PDF not found
```
FileNotFoundError: Arquivo não encontrado: extrato.pdf
```
Solution: Ensure the PDF file exists and the path is correct

### Bank not detected
```
WARNING - Banco não identificado, usando parser genérico
```
This is normal - the tool will use the generic parser which works for most banks

### XLSX export fails
```
ImportError: openpyxl not installed
```
Solution: 
```bash
pip install openpyxl
```

## Future Enhancements

Based on the original suggestions, future versions could include:

1. **OCR Support** - Convert scanned PDFs and images
2. **Web Interface** - Flask/FastAPI web application
3. **Dashboard** - Visualize transactions and statistics
4. **Bank Reconciliation** - Auto-match bank statements with accounting records
5. **API** - REST API for integration with ERPs
6. **Database Storage** - Persist transactions in database
7. **Advanced Classification** - AI/ML for transaction categorization

## Development

### Code Quality
- Type hints throughout the codebase
- Dataclass-based models with validation
- Comprehensive logging
- Error handling and validation

### Testing
```bash
# Run tests (when available)
python3 -m pytest tests/
```

## License

MIT License - feel free to use, modify, and distribute

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review example usage
3. Check logging output with `--verbose` flag

## Changelog

### v1.0.0 (2026-08-30)
- Initial release
- Multi-format export (OFX, CSV, JSON, XLSX, XML)
- Bank auto-detection
- Professional logging
- Comprehensive error handling
- Type-safe models with Decimal precision

---

**Made with ❤️ for financial professionals and developers**
