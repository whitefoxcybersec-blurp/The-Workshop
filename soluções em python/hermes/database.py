"""
Database models and schema for Hermes accounting system.

This module defines the core data structures using SQLAlchemy ORM.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List

try:
    from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, Date, DateTime, ForeignKey, Text, Enum as SQLEnum, DECIMAL
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import relationship, sessionmaker
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

if HAS_SQLALCHEMY:
    Base = declarative_base()
else:
    Base = object


class TipoContaEnum(str, Enum):
    """Account type classification."""
    SINTETICA = "SINTETICA"      # Summary account (no transactions)
    ANALITICA = "ANALITICA"      # Analytical account (accepts transactions)


class NaturezaContaEnum(str, Enum):
    """Account nature (debit/credit side)."""
    DEVEDORA = "DEVEDORA"        # Debit balance (assets, expenses)
    CREDORA = "CREDORA"          # Credit balance (liabilities, income)


class OrigemLancamentoEnum(str, Enum):
    """Origin of accounting entry."""
    EXTRATO_BANCARIO = "EXTRATO_BANCARIO"
    NFSE = "NFSE"
    NFE = "NFE"
    MANUAL = "MANUAL"
    SISTEMA = "SISTEMA"


class StatusLancamentoEnum(str, Enum):
    """Accounting entry status."""
    RASCUNHO = "RASCUNHO"
    PENDENTE = "PENDENTE"
    APROVADO = "APROVADO"
    CANCELADO = "CANCELADO"


class Empresa(Base):
    """Company/Organization."""
    __tablename__ = 'empresas'
    
    id = Column(Integer, primary_key=True)
    razao_social = Column(String(255), nullable=False, unique=True)
    nome_fantasia = Column(String(255))
    cnpj = Column(String(20), unique=True)
    
    moeda = Column(String(3), default="BRL")
    pais = Column(String(100), default="BR")
    
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    plano_contas = relationship("PlanoContas", back_populates="empresa", cascade="all, delete-orphan")
    contas_bancarias = relationship("ContaBancaria", back_populates="empresa", cascade="all, delete-orphan")
    regras = relationship("RegrasClassificacao", back_populates="empresa", cascade="all, delete-orphan")
    lancamentos = relationship("LancamentoContabil", back_populates="empresa", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Empresa {self.razao_social}>"


class PlanoContas(Base):
    """Chart of Accounts (Plano de Contas)."""
    __tablename__ = 'plano_contas'
    
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey('empresas.id'), nullable=False)
    
    codigo = Column(String(30), nullable=False)
    codigo_reduzido = Column(Integer)
    descricao = Column(String(255), nullable=False)
    descricao_padronizada = Column(String(255))  # Normalized version
    
    tipo = Column(SQLEnum(TipoContaEnum), nullable=False)  # SINTETICA or ANALITICA
    natureza = Column(SQLEnum(NaturezaContaEnum))  # DEVEDORA or CREDORA
    
    conta_pai_id = Column(Integer, ForeignKey('plano_contas.id'))
    nivel = Column(Integer, nullable=False)  # 1-5 hierarchy level
    
    aceita_lancamento = Column(Boolean, default=False)  # Only analytical accounts accept entries
    ativo = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    empresa = relationship("Empresa", back_populates="plano_contas")
    conta_pai = relationship("PlanoContas", remote_side=[id], backref="subcontas")
    partidas = relationship("Partida", back_populates="conta")
    
    __table_args__ = (
        # Unique constraint on company + codigo
        ('empresa_id', 'codigo'),
    )
    
    def __repr__(self):
        return f"<Conta {self.codigo} - {self.descricao}>"


class ContaBancaria(Base):
    """Bank account associated with a company."""
    __tablename__ = 'contas_bancarias'
    
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey('empresas.id'), nullable=False)
    
    banco_codigo = Column(String(10))  # Bank code (001=BB, 033=Santander, etc)
    banco_nome = Column(String(100), nullable=False)
    agencia = Column(String(20), nullable=False)
    conta = Column(String(30), nullable=False)
    digito = Column(String(2))
    
    titular = Column(String(255))
    cpf_cnpj = Column(String(20))
    
    conta_contabil_id = Column(Integer, ForeignKey('plano_contas.id'))
    
    saldo_inicial = Column(DECIMAL(15, 2))
    saldo_atual = Column(DECIMAL(15, 2), default=0)
    
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    empresa = relationship("Empresa", back_populates="contas_bancarias")
    conta_contabil = relationship("PlanoContas")
    movimentos = relationship("MovimentoBancario", back_populates="conta_bancaria")
    
    def __repr__(self):
        return f"<ContaBancaria {self.banco_nome} {self.agencia}/{self.conta}>"


class MovimentoBancario(Base):
    """Bank statement movement/transaction."""
    __tablename__ = 'movimentos_bancarios'
    
    id = Column(Integer, primary_key=True)
    conta_bancaria_id = Column(Integer, ForeignKey('contas_bancarias.id'), nullable=False)
    
    data = Column(Date, nullable=False)
    descricao = Column(String(255), nullable=False)
    
    valor = Column(DECIMAL(15, 2), nullable=False)  # Can be positive (credit) or negative (debit)
    saldo = Column(DECIMAL(15, 2))  # Running balance
    
    documento = Column(String(100))
    tipo = Column(String(20))  # CREDIT, DEBIT, etc
    
    conciliado = Column(Boolean, default=False)
    lancamento_id = Column(Integer, ForeignKey('lancamentos_contabeis.id'))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    conta_bancaria = relationship("ContaBancaria", back_populates="movimentos")
    lancamento = relationship("LancamentoContabil", back_populates="movimentos_bancarios")
    
    def __repr__(self):
        return f"<Movimento {self.data} - {self.descricao}: {self.valor}>"


class LancamentoContabil(Base):
    """Accounting entry (can have multiple line items)."""
    __tablename__ = 'lancamentos_contabeis'
    
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey('empresas.id'), nullable=False)
    
    data = Column(Date, nullable=False)
    historico = Column(Text, nullable=False)
    
    documento = Column(String(100))
    origem = Column(SQLEnum(OrigemLancamentoEnum), default=OrigemLancamentoEnum.MANUAL)
    
    status = Column(SQLEnum(StatusLancamentoEnum), default=StatusLancamentoEnum.RASCUNHO)
    
    conciliado = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    empresa = relationship("Empresa", back_populates="lancamentos")
    partidas = relationship("Partida", back_populates="lancamento", cascade="all, delete-orphan")
    movimentos_bancarios = relationship("MovimentoBancario", back_populates="lancamento")
    
    def total_debitos(self) -> Decimal:
        """Calculate total debits."""
        return sum(
            (p.debito or Decimal('0')) for p in self.partidas
        )
    
    def total_creditos(self) -> Decimal:
        """Calculate total credits."""
        return sum(
            (p.credito or Decimal('0')) for p in self.partidas
        )
    
    def esta_balanceado(self) -> bool:
        """Verify double-entry principle: sum(debits) == sum(credits)."""
        return self.total_debitos() == self.total_creditos()
    
    def __repr__(self):
        return f"<Lançamento {self.data} - {self.historico[:50]}>"


class Partida(Base):
    """Line item in an accounting entry."""
    __tablename__ = 'partidas'
    
    id = Column(Integer, primary_key=True)
    lancamento_id = Column(Integer, ForeignKey('lancamentos_contabeis.id'), nullable=False)
    conta_id = Column(Integer, ForeignKey('plano_contas.id'), nullable=False)
    
    debito = Column(DECIMAL(15, 2), default=0)
    credito = Column(DECIMAL(15, 2), default=0)
    
    centro_custo_id = Column(Integer)  # Future: link to cost center
    projeto_id = Column(Integer)       # Future: link to project
    
    descricao = Column(String(255))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    lancamento = relationship("LancamentoContabil", back_populates="partidas")
    conta = relationship("PlanoContas", back_populates="partidas")
    
    def valor(self) -> Decimal:
        """Get the value (debit if positive, credit if negative)."""
        if self.debito:
            return self.debito
        elif self.credito:
            return -self.credito
        return Decimal('0')
    
    def __repr__(self):
        return f"<Partida {self.conta.codigo} D:{self.debito} C:{self.credito}>"


class RegrasClassificacao(Base):
    """Classification rules for automatic bank movement categorization."""
    __tablename__ = 'regras_classificacao'
    
    id = Column(Integer, primary_key=True)
    empresa_id = Column(Integer, ForeignKey('empresas.id'), nullable=False)
    
    palavra_chave = Column(String(255), nullable=False)
    metodo = Column(String(50), default="EXATA")  # EXATA, PARCIAL, REGEX
    
    conta_debito_id = Column(Integer, ForeignKey('plano_contas.id'))
    conta_credito_id = Column(Integer, ForeignKey('plano_contas.id'))
    
    centro_custo_id = Column(Integer)
    
    prioridade = Column(Integer, default=0)  # Higher = better match
    
    usos = Column(Integer, default=0)  # Times used for learning
    acertos = Column(Integer, default=0)  # Times confirmed correct
    
    ativo = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    empresa = relationship("Empresa", back_populates="regras")
    conta_debito = relationship("PlanoContas", foreign_keys=[conta_debito_id])
    conta_credito = relationship("PlanoContas", foreign_keys=[conta_credito_id])
    
    def taxa_acerto(self) -> float:
        """Get accuracy rate (learning metric)."""
        if self.usos == 0:
            return 0.0
        return (self.acertos / self.usos) * 100
    
    def __repr__(self):
        return f"<Regra '{self.palavra_chave}' P:{self.prioridade}>"


def init_database(db_url: str = "sqlite:///hermes.db"):
    """Initialize database and create all tables.
    
    Args:
        db_url: SQLAlchemy database URL
        
    Returns:
        Tuple of (engine, Session)
    """
    if not HAS_SQLALCHEMY:
        raise ImportError("SQLAlchemy is required. Install with: pip install sqlalchemy")
    
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    return engine, Session


if __name__ == "__main__":
    # Test database initialization
    engine, Session = init_database()
    print("✓ Database initialized successfully")
    print(f"Database: hermes.db")
    print(f"Tables: {Base.metadata.tables.keys()}")
