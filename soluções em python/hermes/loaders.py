"""
Data loaders and initialization for the accounting system.

Handles setup of companies, chart of accounts, bank accounts, and classification rules.
"""

from decimal import Decimal
from datetime import date
from typing import Dict, List, Optional

from hermes.database import (
    Empresa, PlanoContas, ContaBancaria, RegrasClassificacao,
    TipoContaEnum, NaturezaContaEnum
)
from hermes.utils import configurar_logging

logger = configurar_logging(__name__)


class PlanoContasLoader:
    """Load chart of accounts from data structures."""
    
    def __init__(self, session):
        self.session = session
    
    def criar_conta(
        self,
        empresa_id: int,
        codigo: str,
        descricao: str,
        tipo: TipoContaEnum,
        natureza: Optional[NaturezaContaEnum] = None,
        nivel: int = 1,
        conta_pai_codigo: Optional[str] = None,
        codigo_reduzido: Optional[int] = None,
        descricao_padronizada: Optional[str] = None
    ) -> PlanoContas:
        """Create or update a chart of accounts entry.
        
        Args:
            empresa_id: Company ID
            codigo: Account code (e.g., "1.1.1.02.0003")
            descricao: Account description
            tipo: SINTETICA or ANALITICA
            natureza: DEVEDORA or CREDORA (for analytical accounts)
            nivel: Hierarchy level (1-5)
            conta_pai_codigo: Parent account code
            codigo_reduzido: Reduced account code
            descricao_padronizada: Normalized description
            
        Returns:
            PlanoContas object
        """
        # Check if already exists
        existe = self.session.query(PlanoContas).filter(
            PlanoContas.empresa_id == empresa_id,
            PlanoContas.codigo == codigo
        ).first()
        
        if existe:
            self.logger.debug(f"Conta {codigo} já existe, atualizando...")
            return existe
        
        # Get parent account if specified
        conta_pai = None
        if conta_pai_codigo:
            conta_pai = self.session.query(PlanoContas).filter(
                PlanoContas.empresa_id == empresa_id,
                PlanoContas.codigo == conta_pai_codigo
            ).first()
        
        # Create account
        conta = PlanoContas(
            empresa_id=empresa_id,
            codigo=codigo,
            descricao=descricao,
            descricao_padronizada=descricao_padronizada or descricao,
            tipo=tipo,
            natureza=natureza,
            nivel=nivel,
            conta_pai=conta_pai,
            codigo_reduzido=codigo_reduzido,
            aceita_lancamento=(tipo == TipoContaEnum.ANALITICA)
        )
        
        self.session.add(conta)
        self.logger.debug(f"Conta criada: {codigo} - {descricao}")
        
        return conta
    
    def carregar_plano_de_contas_exemplo(self, empresa_id: int):
        """Load example chart of accounts (simplified version).
        
        This is a simplified version of the user's chart.
        In production, you would load from CSV, Excel, or database.
        """
        self.logger.info("Carregando plano de contas exemplo...")
        
        # Level 1: Synthetic accounts
        ativo = self.criar_conta(
            empresa_id, "1", "ATIVO", TipoContaEnum.SINTETICA, nivel=1
        )
        
        passivo = self.criar_conta(
            empresa_id, "2", "PASSIVO", TipoContaEnum.SINTETICA, nivel=1
        )
        
        patrimonio = self.criar_conta(
            empresa_id, "3", "PATRIMÔNIO LÍQUIDO", TipoContaEnum.SINTETICA, nivel=1
        )
        
        receitas = self.criar_conta(
            empresa_id, "4", "RECEITAS", TipoContaEnum.SINTETICA, nivel=1
        )
        
        despesas = self.criar_conta(
            empresa_id, "5", "DESPESAS", TipoContaEnum.SINTETICA, nivel=1
        )
        
        # Level 2: Subaccounts
        ativo_circulante = self.criar_conta(
            empresa_id, "1.1", "ATIVO CIRCULANTE", TipoContaEnum.SINTETICA,
            NaturezaContaEnum.DEVEDORA, nivel=2, conta_pai_codigo="1"
        )
        
        # Level 3: More specific
        disponibilidades = self.criar_conta(
            empresa_id, "1.1.1", "DISPONIBILIDADES", TipoContaEnum.SINTETICA,
            NaturezaContaEnum.DEVEDORA, nivel=3, conta_pai_codigo="1.1"
        )
        
        # Level 4: Very specific
        caixa_bancos = self.criar_conta(
            empresa_id, "1.1.1.02", "BANCOS", TipoContaEnum.SINTETICA,
            NaturezaContaEnum.DEVEDORA, nivel=4, conta_pai_codigo="1.1.1"
        )
        
        # Level 5: Analytical accounts (accept transactions)
        banco_bb = self.criar_conta(
            empresa_id, "1.1.1.02.0001", "BANCO DO BRASIL",
            TipoContaEnum.ANALITICA, NaturezaContaEnum.DEVEDORA,
            nivel=5, conta_pai_codigo="1.1.1.02"
        )
        
        banco_bradesco = self.criar_conta(
            empresa_id, "1.1.1.02.0002", "BANCO BRADESCO",
            TipoContaEnum.ANALITICA, NaturezaContaEnum.DEVEDORA,
            nivel=5, conta_pai_codigo="1.1.1.02"
        )
        
        banco_itau = self.criar_conta(
            empresa_id, "1.1.1.02.0003", "BANCO ITAÚ",
            TipoContaEnum.ANALITICA, NaturezaContaEnum.DEVEDORA,
            nivel=5, conta_pai_codigo="1.1.1.02"
        )
        
        # Expenses
        despesa_operacional = self.criar_conta(
            empresa_id, "5.1", "DESPESAS OPERACIONAIS", TipoContaEnum.SINTETICA,
            NaturezaContaEnum.CREDORA, nivel=2, conta_pai_codigo="5"
        )
        
        despesa_pessoal = self.criar_conta(
            empresa_id, "5.1.1", "DESPESAS COM PESSOAL", TipoContaEnum.SINTETICA,
            NaturezaContaEnum.CREDORA, nivel=3, conta_pai_codigo="5.1"
        )
        
        despesa_aluguel = self.criar_conta(
            empresa_id, "5.1.1.01.0001", "ALUGUEL",
            TipoContaEnum.ANALITICA, NaturezaContaEnum.CREDORA,
            nivel=5, conta_pai_codigo="5.1.1"
        )
        
        despesa_transporte = self.criar_conta(
            empresa_id, "5.2.1.01.0046", "DESPESA COM VIAGENS/TRANSPORTE",
            TipoContaEnum.ANALITICA, NaturezaContaEnum.CREDORA,
            nivel=5, conta_pai_codigo="5.2.1"
        )
        
        despesa_hospedagem = self.criar_conta(
            empresa_id, "5.2.1.01.0055", "DOMÍNIOS E HOSPEDAGEM",
            TipoContaEnum.ANALITICA, NaturezaContaEnum.CREDORA,
            nivel=5, conta_pai_codigo="5.2.1"
        )
        
        tarifa_bancaria = self.criar_conta(
            empresa_id, "5.2.2.01.0003", "TARIFA BANCÁRIA",
            TipoContaEnum.ANALITICA, NaturezaContaEnum.CREDORA,
            nivel=5, conta_pai_codigo="5.2.2"
        )
        
        self.session.commit()
        self.logger.info(f"✓ Plano de contas carregado com sucesso")


class ClassificacaoRulesLoader:
    """Load classification rules for automatic categorization."""
    
    def __init__(self, session):
        self.session = session
    
    def criar_regra(
        self,
        empresa_id: int,
        palavra_chave: str,
        conta_debito_id: int,
        conta_credito_id: int,
        metodo: str = "PARCIAL",
        prioridade: int = 0,
        centro_custo_id: Optional[int] = None
    ) -> RegrasClassificacao:
        """Create a classification rule.
        
        Args:
            empresa_id: Company ID
            palavra_chave: Keyword to match in description
            conta_debito_id: Default debit account
            conta_credito_id: Default credit account
            metodo: EXATA, PARCIAL, or REGEX
            prioridade: Rule priority (higher = better)
            centro_custo_id: Cost center ID
            
        Returns:
            RegrasClassificacao object
        """
        regra = RegrasClassificacao(
            empresa_id=empresa_id,
            palavra_chave=palavra_chave,
            metodo=metodo,
            conta_debito_id=conta_debito_id,
            conta_credito_id=conta_credito_id,
            prioridade=prioridade,
            centro_custo_id=centro_custo_id
        )
        
        self.session.add(regra)
        self.logger.debug(f"Regra criada: {palavra_chave}")
        
        return regra
    
    def carregar_regras_exemplo(self, empresa_id: int):
        """Load example classification rules.
        
        In production, these would come from user configuration.
        """
        self.logger.info("Carregando regras de classificação exemplo...")
        
        # Get account IDs (must exist first)
        banco_itau = self.session.query(PlanoContas).filter(
            PlanoContas.empresa_id == empresa_id,
            PlanoContas.codigo == "1.1.1.02.0003"
        ).first()
        
        despesa_transporte = self.session.query(PlanoContas).filter(
            PlanoContas.empresa_id == empresa_id,
            PlanoContas.codigo == "5.2.1.01.0046"
        ).first()
        
        despesa_hospedagem = self.session.query(PlanoContas).filter(
            PlanoContas.empresa_id == empresa_id,
            PlanoContas.codigo == "5.2.1.01.0055"
        ).first()
        
        tarifa_bancaria = self.session.query(PlanoContas).filter(
            PlanoContas.empresa_id == empresa_id,
            PlanoContas.codigo == "5.2.2.01.0003"
        ).first()
        
        if not (banco_itau and despesa_transporte and despesa_hospedagem and tarifa_bancaria):
            self.logger.error("Contas necessárias não encontradas")
            return
        
        # Create rules
        self.criar_regra(
            empresa_id, "UBER",
            conta_debito_id=despesa_transporte.id,
            conta_credito_id=banco_itau.id,
            metodo="PARCIAL",
            prioridade=10
        )
        
        self.criar_regra(
            empresa_id, "UBER *TRIP",
            conta_debito_id=despesa_transporte.id,
            conta_credito_id=banco_itau.id,
            metodo="EXATA",
            prioridade=20
        )
        
        self.criar_regra(
            empresa_id, "AWS",
            conta_debito_id=despesa_hospedagem.id,
            conta_credito_id=banco_itau.id,
            metodo="PARCIAL",
            prioridade=15
        )
        
        self.criar_regra(
            empresa_id, "TARIFA",
            conta_debito_id=tarifa_bancaria.id,
            conta_credito_id=banco_itau.id,
            metodo="PARCIAL",
            prioridade=5
        )
        
        self.session.commit()
        self.logger.info("✓ Regras de classificação carregadas")


class InitializerService:
    """Complete initialization service."""
    
    def __init__(self, session):
        self.session = session
    
    def inicializar_empresa(
        self,
        razao_social: str,
        nome_fantasia: Optional[str] = None,
        cnpj: Optional[str] = None
    ) -> Empresa:
        """Initialize a new company with default settings.
        
        Args:
            razao_social: Company legal name
            nome_fantasia: Company trade name
            cnpj: Company CNPJ
            
        Returns:
            Created Empresa object
        """
        logger.info(f"Inicializando empresa: {razao_social}")
        
        # Check if exists
        existe = self.session.query(Empresa).filter(
            Empresa.razao_social == razao_social
        ).first()
        
        if existe:
            logger.info(f"Empresa já existe: {razao_social}")
            return existe
        
        # Create company
        empresa = Empresa(
            razao_social=razao_social,
            nome_fantasia=nome_fantasia or razao_social,
            cnpj=cnpj
        )
        
        self.session.add(empresa)
        self.session.commit()
        
        logger.info(f"✓ Empresa criada (ID: {empresa.id})")
        
        # Load chart of accounts
        plano_loader = PlanoContasLoader(self.session)
        plano_loader.carregar_plano_de_contas_exemplo(empresa.id)
        
        # Load classification rules
        regras_loader = ClassificacaoRulesLoader(self.session)
        regras_loader.carregar_regras_exemplo(empresa.id)
        
        return empresa
    
    def criar_conta_bancaria(
        self,
        empresa_id: int,
        banco_nome: str,
        agencia: str,
        conta: str,
        banco_codigo: Optional[str] = None,
        titular: Optional[str] = None,
        cpf_cnpj: Optional[str] = None,
        conta_contabil_codigo: str = "1.1.1.02.0003"  # Default: Itau
    ) -> ContaBancaria:
        """Create a bank account for the company.
        
        Args:
            empresa_id: Company ID
            banco_nome: Bank name
            agencia: Agency number
            conta: Account number
            banco_codigo: Bank code (e.g., "033" for Santander)
            titular: Account holder name
            cpf_cnpj: Account holder CPF/CNPJ
            conta_contabil_codigo: Link to accounting account
            
        Returns:
            Created ContaBancaria object
        """
        logger.info(f"Criando conta bancária: {banco_nome} {agencia}/{conta}")
        
        # Get accounting account
        conta_contabil = self.session.query(PlanoContas).filter(
            PlanoContas.empresa_id == empresa_id,
            PlanoContas.codigo == conta_contabil_codigo
        ).first()
        
        if not conta_contabil:
            logger.error(f"Conta contábil não encontrada: {conta_contabil_codigo}")
            raise ValueError(f"Conta contábil não encontrada: {conta_contabil_codigo}")
        
        # Create bank account
        conta_banco = ContaBancaria(
            empresa_id=empresa_id,
            banco_nome=banco_nome,
            banco_codigo=banco_codigo,
            agencia=agencia,
            conta=conta,
            titular=titular,
            cpf_cnpj=cpf_cnpj,
            conta_contabil_id=conta_contabil.id,
            saldo_inicial=Decimal('0'),
            saldo_atual=Decimal('0')
        )
        
        self.session.add(conta_banco)
        self.session.commit()
        
        logger.info(f"✓ Conta bancária criada (ID: {conta_banco.id})")
        
        return conta_banco
