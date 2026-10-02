"""Data models for bank transactions."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class BancoEnum(Enum):
    """Supported banks."""
    ITAU = "ITAU"
    INTER = "INTER"
    SANTANDER = "SANTANDER"
    BRADESCO = "BRADESCO"
    BANCO_DO_BRASIL = "BB"
    NUBANK = "NUBANK"
    SICREDI = "SICREDI"
    DESCONHECIDO = "DESCONHECIDO"


class TipoTransacao(Enum):
    """Transaction types."""
    CREDITO = "CREDIT"
    DEBITO = "DEBIT"


@dataclass
class Transacao:
    """Represents a bank transaction."""
    data: str  # Format: YYYYMMDD
    descricao: str
    valor: Decimal
    
    def __post_init__(self):
        """Validate and convert valor to Decimal."""
        if isinstance(self.valor, str):
            self.valor = Decimal(self.valor.replace(',', '.'))
        elif isinstance(self.valor, float):
            # Convert float to Decimal via string to avoid precision loss
            self.valor = Decimal(str(self.valor))
        elif not isinstance(self.valor, Decimal):
            self.valor = Decimal(self.valor)
    
    @property
    def tipo(self) -> TipoTransacao:
        """Determine transaction type based on value sign."""
        return TipoTransacao.DEBITO if self.valor < 0 else TipoTransacao.CREDITO
    
    @property
    def valor_absoluto(self) -> Decimal:
        """Get absolute value."""
        return abs(self.valor)


@dataclass
class Extrato:
    """Represents a complete bank statement."""
    banco: BancoEnum
    agencia: str
    conta: str
    transacoes: list[Transacao]
    data_inicio: Optional[str] = None  # Format: YYYYMMDD
    data_fim: Optional[str] = None     # Format: YYYYMMDD
    saldo_inicial: Optional[Decimal] = None
    saldo_final: Optional[Decimal] = None
    
    def total_creditos(self) -> Decimal:
        """Calculate total credits."""
        return sum(
            t.valor for t in self.transacoes 
            if t.valor > 0
        )
    
    def total_debitos(self) -> Decimal:
        """Calculate total debits."""
        return sum(
            abs(t.valor) for t in self.transacoes 
            if t.valor < 0
        )
    
    def saldo_liquido(self) -> Decimal:
        """Calculate net balance."""
        return self.total_creditos() - self.total_debitos()
