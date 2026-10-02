"""
Classification and accounting services for automatic transaction processing.
"""

from decimal import Decimal
from datetime import date
from typing import Optional, List, Tuple
from dataclasses import dataclass

from hermes.database import (
    LancamentoContabil, Partida, PlanoContas, RegrasClassificacao,
    MovimentoBancario, StatusLancamentoEnum, OrigemLancamentoEnum
)
from hermes.utils import configurar_logging

logger = configurar_logging(__name__)


@dataclass
class ClassificacaoSugerida:
    """Suggested classification for a bank movement."""
    conta_debito_id: int
    conta_credito_id: int
    confianca: float  # 0-100
    metodo: str  # EXATA, PARCIAL, REGEX, HISTORICO
    regra_id: Optional[int] = None


class ClassificadorService:
    """Service for automatic classification of bank movements."""
    
    def __init__(self, session):
        self.session = session
        self.logger = logger
    
    def classificar(self, movimento: MovimentoBancario) -> Optional[ClassificacaoSugerida]:
        """Classify a bank movement.
        
        Args:
            movimento: MovimentoBancario to classify
            
        Returns:
            ClassificacaoSugerida or None if no match
        """
        self.logger.info(f"Classificando movimento: {movimento.descricao}")
        
        # Try exact match
        resultado = self._buscar_exata(movimento)
        if resultado:
            return resultado
        
        # Try partial match
        resultado = self._buscar_parcial(movimento)
        if resultado:
            return resultado
        
        # Try historical similarity
        resultado = self._buscar_historico(movimento)
        if resultado:
            return resultado
        
        self.logger.warning(f"Sem classificação encontrada para: {movimento.descricao}")
        return None
    
    def _buscar_exata(self, movimento: MovimentoBancario) -> Optional[ClassificacaoSugerida]:
        """Search for exact keyword match."""
        self.logger.debug("Buscando classificação exata...")
        
        descricao_upper = movimento.descricao.upper()
        empresa_id = movimento.conta_bancaria.empresa_id
        
        regras = self.session.query(RegrasClassificacao).filter(
            RegrasClassificacao.empresa_id == empresa_id,
            RegrasClassificacao.ativo == True,
            RegrasClassificacao.metodo == "EXATA"
        ).order_by(RegrasClassificacao.prioridade.desc()).all()
        
        for regra in regras:
            if regra.palavra_chave.upper() == descricao_upper:
                self.logger.info(f"✓ Classificação exata encontrada: {regra.palavra_chave}")
                
                regra.usos += 1
                self.session.commit()
                
                return ClassificacaoSugerida(
                    conta_debito_id=regra.conta_debito_id,
                    conta_credito_id=regra.conta_credito_id,
                    confianca=100.0,
                    metodo="EXATA",
                    regra_id=regra.id
                )
        
        return None
    
    def _buscar_parcial(self, movimento: MovimentoBancario) -> Optional[ClassificacaoSugerida]:
        """Search for partial keyword match."""
        self.logger.debug("Buscando classificação parcial...")
        
        descricao_upper = movimento.descricao.upper()
        empresa_id = movimento.conta_bancaria.empresa_id
        
        regras = self.session.query(RegrasClassificacao).filter(
            RegrasClassificacao.empresa_id == empresa_id,
            RegrasClassificacao.ativo == True,
            RegrasClassificacao.metodo == "PARCIAL"
        ).order_by(RegrasClassificacao.prioridade.desc()).all()
        
        melhor_regra = None
        melhor_confianca = 0.0
        
        for regra in regras:
            if regra.palavra_chave.upper() in descricao_upper:
                # Calculate confidence based on keyword position and length
                palavra_len = len(regra.palavra_chave)
                confianca = min(100.0, 60 + (regra.prioridade * 10))
                
                if confianca > melhor_confianca:
                    melhor_confianca = confianca
                    melhor_regra = regra
        
        if melhor_regra:
            self.logger.info(f"✓ Classificação parcial encontrada: {melhor_regra.palavra_chave} ({melhor_confianca:.1f}%)")
            
            melhor_regra.usos += 1
            self.session.commit()
            
            return ClassificacaoSugerida(
                conta_debito_id=melhor_regra.conta_debito_id,
                conta_credito_id=melhor_regra.conta_credito_id,
                confianca=melhor_confianca,
                metodo="PARCIAL",
                regra_id=melhor_regra.id
            )
        
        return None
    
    def _buscar_historico(self, movimento: MovimentoBancario) -> Optional[ClassificacaoSugerida]:
        """Search for similar historical movements."""
        self.logger.debug("Buscando similaridade histórica...")
        
        empresa_id = movimento.conta_bancaria.empresa_id
        
        # Find similar movements (same description prefix)
        descricao_prefix = movimento.descricao[:15].upper()
        
        similares = self.session.query(MovimentoBancario).filter(
            MovimentoBancario.lancamento_id.isnot(None),  # Already classified
            MovimentoBancario.descricao.ilike(f"{descricao_prefix}%")
        ).limit(5).all()
        
        if similares:
            # Get the most common classification from similar movements
            from sqlalchemy import func
            
            classificacoes = self.session.query(
                Partida.conta_id,
                func.count().label('freq')
            ).join(
                LancamentoContabil,
                Partida.lancamento_id == LancamentoContabil.id
            ).filter(
                LancamentoContabil.id.in_([m.lancamento_id for m in similares if m.lancamento_id])
            ).group_by(Partida.conta_id).order_by(func.count().desc()).all()
            
            if classificacoes:
                self.logger.info(f"✓ Classificação histórica encontrada (similaridade)")
                
                return ClassificacaoSugerida(
                    conta_debito_id=classificacoes[0].conta_id,
                    conta_credito_id=movimento.conta_bancaria.conta_contabil_id,
                    confianca=45.0,
                    metodo="HISTORICO"
                )
        
        return None
    
    def aprender_classificacao(self, movimento: MovimentoBancario, 
                               conta_debito_id: int, confirmado: bool = True):
        """Learn from user classification (reinforcement learning).
        
        Args:
            movimento: The classified movement
            conta_debito_id: The account that was classified
            confirmado: Whether user confirmed or corrected
        """
        palavra_chave = movimento.descricao[:30]
        empresa_id = movimento.conta_bancaria.empresa_id
        
        # Try to find existing rule
        regra = self.session.query(RegrasClassificacao).filter(
            RegrasClassificacao.empresa_id == empresa_id,
            RegrasClassificacao.palavra_chave.ilike(palavra_chave)
        ).first()
        
        if regra:
            regra.usos += 1
            if confirmado:
                regra.acertos += 1
            self.logger.info(f"Regra atualizada: {regra.palavra_chave} (taxa acerto: {regra.taxa_acerto():.1f}%)")
        else:
            # Create new rule
            regra = RegrasClassificacao(
                empresa_id=empresa_id,
                palavra_chave=palavra_chave,
                metodo="PARCIAL",
                conta_debito_id=conta_debito_id,
                conta_credito_id=movimento.conta_bancaria.conta_contabil_id,
                prioridade=1,
                usos=1,
                acertos=1 if confirmado else 0
            )
            self.session.add(regra)
            self.logger.info(f"Nova regra criada: {palavra_chave}")
        
        self.session.commit()


class LancamentoService:
    """Service for creating and validating accounting entries."""
    
    def __init__(self, session):
        self.session = session
        self.logger = logger
    
    def criar_lancamento_simples(
        self,
        empresa_id: int,
        data: date,
        historico: str,
        conta_debito_id: int,
        conta_credito_id: int,
        valor: Decimal,
        documento: Optional[str] = None,
        origem: OrigemLancamentoEnum = OrigemLancamentoEnum.MANUAL,
        movimento_id: Optional[int] = None
    ) -> LancamentoContabil:
        """Create a simple 2-sided accounting entry.
        
        Args:
            empresa_id: Company ID
            data: Entry date
            historico: Description/history
            conta_debito_id: Debit account ID
            conta_credito_id: Credit account ID
            valor: Amount
            documento: Reference document
            origem: Origin of entry
            movimento_id: Related bank movement ID
            
        Returns:
            Created LancamentoContabil
            
        Raises:
            ValueError: If accounts are invalid or not balanced
        """
        self.logger.info(f"Criando lançamento: {historico}")
        
        # Validate accounts
        conta_deb = self.session.query(PlanoContas).get(conta_debito_id)
        conta_cred = self.session.query(PlanoContas).get(conta_credito_id)
        
        if not conta_deb or not conta_cred:
            raise ValueError("Uma ou ambas as contas não existem")
        
        if not conta_deb.aceita_lancamento or not conta_cred.aceita_lancamento:
            raise ValueError("Uma ou ambas as contas não aceitam lançamentos (devem ser analíticas)")
        
        # Create entry
        lancamento = LancamentoContabil(
            empresa_id=empresa_id,
            data=data,
            historico=historico,
            documento=documento,
            origem=origem,
            status=StatusLancamentoEnum.RASCUNHO
        )
        
        # Create debit partida
        partida_deb = Partida(
            lancamento=lancamento,
            conta_id=conta_debito_id,
            debito=valor,
            credito=Decimal('0')
        )
        
        # Create credit partida
        partida_cred = Partida(
            lancamento=lancamento,
            conta_id=conta_credito_id,
            debito=Decimal('0'),
            credito=valor
        )
        
        lancamento.partidas.append(partida_deb)
        lancamento.partidas.append(partida_cred)
        
        # Validate
        if not lancamento.esta_balanceado():
            raise ValueError("Lançamento não balanceado (débito ≠ crédito)")
        
        self.session.add(lancamento)
        self.session.commit()
        
        self.logger.info(f"✓ Lançamento criado (ID: {lancamento.id})")
        
        # Link to bank movement if provided
        if movimento_id:
            movimento = self.session.query(MovimentoBancario).get(movimento_id)
            if movimento:
                movimento.lancamento_id = lancamento.id
                movimento.conciliado = True
                self.session.commit()
                self.logger.info(f"Movimento conciliado com lançamento #{lancamento.id}")
        
        return lancamento
    
    def criar_lancamento_multiplo(
        self,
        empresa_id: int,
        data: date,
        historico: str,
        partidas_debito: List[Tuple[int, Decimal]],  # [(conta_id, valor), ...]
        partidas_credito: List[Tuple[int, Decimal]],
        documento: Optional[str] = None,
        origem: OrigemLancamentoEnum = OrigemLancamentoEnum.MANUAL
    ) -> LancamentoContabil:
        """Create a multi-sided accounting entry (can have multiple debits/credits).
        
        Args:
            empresa_id: Company ID
            data: Entry date
            historico: Description
            partidas_debito: List of (account_id, amount) for debits
            partidas_credito: List of (account_id, amount) for credits
            documento: Reference document
            origem: Origin of entry
            
        Returns:
            Created LancamentoContabil
            
        Raises:
            ValueError: If not balanced
        """
        self.logger.info(f"Criando lançamento múltiplo: {historico}")
        
        lancamento = LancamentoContabil(
            empresa_id=empresa_id,
            data=data,
            historico=historico,
            documento=documento,
            origem=origem,
            status=StatusLancamentoEnum.RASCUNHO
        )
        
        # Add debit partidas
        for conta_id, valor in partidas_debito:
            partida = Partida(
                lancamento=lancamento,
                conta_id=conta_id,
                debito=valor,
                credito=Decimal('0')
            )
            lancamento.partidas.append(partida)
        
        # Add credit partidas
        for conta_id, valor in partidas_credito:
            partida = Partida(
                lancamento=lancamento,
                conta_id=conta_id,
                debito=Decimal('0'),
                credito=valor
            )
            lancamento.partidas.append(partida)
        
        # Validate double-entry
        if not lancamento.esta_balanceado():
            total_deb = lancamento.total_debitos()
            total_cred = lancamento.total_creditos()
            raise ValueError(f"Lançamento não balanceado: D={total_deb} ≠ C={total_cred}")
        
        self.session.add(lancamento)
        self.session.commit()
        
        self.logger.info(f"✓ Lançamento múltiplo criado (ID: {lancamento.id})")
        
        return lancamento
    
    def aprovar_lancamento(self, lancamento_id: int):
        """Approve an accounting entry.
        
        Args:
            lancamento_id: ID of entry to approve
        """
        lancamento = self.session.query(LancamentoContabil).get(lancamento_id)
        if not lancamento:
            raise ValueError(f"Lançamento #{lancamento_id} não encontrado")
        
        if not lancamento.esta_balanceado():
            raise ValueError("Lançamento não balanceado, não pode ser aprovado")
        
        lancamento.status = StatusLancamentoEnum.APROVADO
        self.session.commit()
        
        self.logger.info(f"Lançamento #{lancamento_id} aprovado")
    
    def cancelar_lancamento(self, lancamento_id: int):
        """Cancel an accounting entry.
        
        Args:
            lancamento_id: ID of entry to cancel
        """
        lancamento = self.session.query(LancamentoContabil).get(lancamento_id)
        if not lancamento:
            raise ValueError(f"Lançamento #{lancamento_id} não encontrado")
        
        lancamento.status = StatusLancamentoEnum.CANCELADO
        self.session.commit()
        
        self.logger.info(f"Lançamento #{lancamento_id} cancelado")


class ConciliadorService:
    """Service for bank reconciliation."""
    
    def __init__(self, session):
        self.session = session
        self.logger = logger
    
    def conciliar_movimento(self, movimento_id: int, lancamento_id: int):
        """Reconcile a bank movement with an accounting entry.
        
        Args:
            movimento_id: Bank movement ID
            lancamento_id: Accounting entry ID
        """
        movimento = self.session.query(MovimentoBancario).get(movimento_id)
        lancamento = self.session.query(LancamentoContabil).get(lancamento_id)
        
        if not movimento or not lancamento:
            raise ValueError("Movimento ou lançamento não encontrado")
        
        movimento.lancamento_id = lancamento_id
        movimento.conciliado = True
        
        self.session.commit()
        
        self.logger.info(f"Movimento #{movimento_id} conciliado com lançamento #{lancamento_id}")
    
    def gerar_relatorio_conciliacao(self, conta_bancaria_id: int, periodo_inicio: date, periodo_fim: date):
        """Generate bank reconciliation report.
        
        Args:
            conta_bancaria_id: Bank account ID
            periodo_inicio: Start date
            periodo_fim: End date
            
        Returns:
            Dict with reconciliation data
        """
        movimentos = self.session.query(MovimentoBancario).filter(
            MovimentoBancario.conta_bancaria_id == conta_bancaria_id,
            MovimentoBancario.data >= periodo_inicio,
            MovimentoBancario.data <= periodo_fim
        ).order_by(MovimentoBancario.data).all()
        
        conciliados = [m for m in movimentos if m.conciliado]
        nao_conciliados = [m for m in movimentos if not m.conciliado]
        
        return {
            "total_movimentos": len(movimentos),
            "conciliados": len(conciliados),
            "nao_conciliados": len(nao_conciliados),
            "valor_total": sum(m.valor for m in movimentos),
            "valor_nao_conciliado": sum(m.valor for m in nao_conciliados),
            "movimentos_nao_conciliados": nao_conciliados
        }
