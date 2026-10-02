"""
Integration layer connecting PDF/OFX import to accounting system.

This module bridges the existing parser with the new accounting engine,
showing the complete flow: PDF → Movement → Classification → Entry
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from hermes.models import Transacao
from hermes.database import (
    MovimentoBancario, ContaBancaria, OrigemLancamentoEnum
)
from hermes.services import ClassificadorService, LancamentoService
from hermes.utils import configurar_logging

logger = configurar_logging(__name__)


class ImportadorMovimentos:
    """Import bank movements from parser transactions into the system."""
    
    def __init__(self, session):
        self.session = session
    
    def importar_transacao(
        self,
        conta_bancaria: ContaBancaria,
        transacao: Transacao,
        documento: Optional[str] = None
    ) -> MovimentoBancario:
        """Import a parsed transaction as a bank movement.
        
        Args:
            conta_bancaria: Target bank account
            transacao: Parsed transaction from PDF/OFX
            documento: Optional document reference
            
        Returns:
            Created MovimentoBancario
        """
        logger.info(f"Importando transação: {transacao.descricao}")
        
        # Create movement
        movimento = MovimentoBancario(
            conta_bancaria_id=conta_bancaria.id,
            data=datetime.strptime(transacao.data, '%Y%m%d').date(),
            descricao=transacao.descricao,
            valor=transacao.valor,
            documento=documento,
            tipo=transacao.tipo.value
        )
        
        self.session.add(movimento)
        self.session.commit()
        
        logger.info(f"✓ Movimento importado (ID: {movimento.id})")
        
        return movimento
    
    def importar_lote(
        self,
        conta_bancaria: ContaBancaria,
        transacoes: List[Transacao],
        origem: str = "PDF"
    ) -> List[MovimentoBancario]:
        """Import multiple transactions.
        
        Args:
            conta_bancaria: Target bank account
            transacoes: List of parsed transactions
            origem: Import source
            
        Returns:
            List of created MovimentoBancario objects
        """
        logger.info(f"Importando lote de {len(transacoes)} transações...")
        
        movimentos = []
        for transacao in transacoes:
            movimento = self.importar_transacao(conta_bancaria, transacao)
            movimentos.append(movimento)
        
        logger.info(f"✓ Lote importado: {len(movimentos)} movimentos")
        
        return movimentos


class ProcessadorMovimentos:
    """Process movements through classification and accounting."""
    
    def __init__(self, session):
        self.session = session
        self.classificador = ClassificadorService(session)
        self.lancador = LancamentoService(session)
        self.logger = logger
    
    def processar_movimento(
        self,
        movimento_id: int,
        aprovar: bool = False
    ) -> Optional[dict]:
        """Process a single bank movement.
        
        Steps:
        1. Classify the movement
        2. Create accounting entry
        3. Optionally approve
        
        Args:
            movimento_id: Movement ID to process
            aprovar: Whether to approve immediately
            
        Returns:
            Result dict with classification and entry info
        """
        movimento = self.session.query(MovimentoBancario).get(movimento_id)
        if not movimento:
            raise ValueError(f"Movimento #{movimento_id} não encontrado")
        
        self.logger.info(f"Processando movimento: {movimento.descricao}")
        
        # Classify
        classificacao = self.classificador.classificar(movimento)
        
        if not classificacao:
            self.logger.warning(f"Sem classificação para: {movimento.descricao}")
            return {
                "movimento_id": movimento_id,
                "status": "nao_classificado",
                "classificacao": None,
                "lancamento_id": None
            }
        
        self.logger.info(f"Classificado com {classificacao.confianca:.1f}% de confiança")
        
        # Create accounting entry
        try:
            lancamento = self.lancador.criar_lancamento_simples(
                empresa_id=movimento.conta_bancaria.empresa_id,
                data=movimento.data,
                historico=movimento.descricao,
                conta_debito_id=classificacao.conta_debito_id,
                conta_credito_id=classificacao.conta_credito_id,
                valor=abs(movimento.valor),
                documento=movimento.documento,
                origem=OrigemLancamentoEnum.EXTRATO_BANCARIO,
                movimento_id=movimento_id
            )
            
            if aprovar:
                self.lancador.aprovar_lancamento(lancamento.id)
            
            # Learn from classification
            self.classificador.aprender_classificacao(
                movimento,
                classificacao.conta_debito_id,
                confirmado=True
            )
            
            return {
                "movimento_id": movimento_id,
                "status": "sucesso",
                "classificacao": {
                    "confianca": classificacao.confianca,
                    "metodo": classificacao.metodo,
                    "regra_id": classificacao.regra_id
                },
                "lancamento_id": lancamento.id,
                "lancamento_status": lancamento.status.value
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao criar lançamento: {e}")
            return {
                "movimento_id": movimento_id,
                "status": "erro",
                "erro": str(e),
                "classificacao": classificacao.__dict__ if classificacao else None
            }
    
    def processar_lote(
        self,
        movimento_ids: List[int],
        aprovar: bool = False,
        parar_em_erro: bool = False
    ) -> dict:
        """Process multiple movements.
        
        Args:
            movimento_ids: List of movement IDs
            aprovar: Approve all created entries
            parar_em_erro: Stop processing on first error
            
        Returns:
            Summary of processing results
        """
        self.logger.info(f"Processando lote de {len(movimento_ids)} movimentos...")
        
        resultados = []
        erros = 0
        nao_classificados = 0
        sucesso = 0
        
        for movimento_id in movimento_ids:
            try:
                resultado = self.processar_movimento(movimento_id, aprovar=aprovar)
                resultados.append(resultado)
                
                if resultado["status"] == "sucesso":
                    sucesso += 1
                elif resultado["status"] == "nao_classificado":
                    nao_classificados += 1
                else:
                    erros += 1
                    if parar_em_erro:
                        break
                        
            except Exception as e:
                self.logger.error(f"Erro ao processar movimento #{movimento_id}: {e}")
                erros += 1
                if parar_em_erro:
                    break
        
        resumo = {
            "total": len(movimento_ids),
            "sucesso": sucesso,
            "nao_classificados": nao_classificados,
            "erros": erros,
            "resultados": resultados
        }
        
        self.logger.info(f"✓ Lote processado: {sucesso} OK, {nao_classificados} sem classificação, {erros} erros")
        
        return resumo


class FluxoCompleto:
    """Complete flow from PDF to accounting entry."""
    
    def __init__(self, session):
        self.session = session
        self.importador = ImportadorMovimentos(session)
        self.processador = ProcessadorMovimentos(session)
        self.logger = logger
    
    def executar_fluxo(
        self,
        conta_bancaria: ContaBancaria,
        transacoes: List[Transacao],
        aprovar_entradas: bool = False
    ) -> dict:
        """Execute complete flow from transactions to accounting entries.
        
        Pipeline:
        1. Import transactions as movements
        2. Classify movements
        3. Create accounting entries
        4. Reconcile and optionally approve
        
        Args:
            conta_bancaria: Target bank account
            transacoes: Parsed transactions from PDF/OFX
            aprovar_entradas: Auto-approve entries
            
        Returns:
            Summary of entire flow
        """
        self.logger.info("=" * 60)
        self.logger.info("INICIANDO FLUXO COMPLETO: PDF → CONTABILIDADE")
        self.logger.info("=" * 60)
        
        # Step 1: Import
        self.logger.info("\n[PASSO 1] IMPORTAÇÃO")
        self.logger.info("-" * 60)
        movimentos = self.importador.importar_lote(conta_bancaria, transacoes)
        movimento_ids = [m.id for m in movimentos]
        
        # Step 2: Process
        self.logger.info("\n[PASSO 2] PROCESSAMENTO (Classificação + Contabilização)")
        self.logger.info("-" * 60)
        resumo_processamento = self.processador.processar_lote(
            movimento_ids,
            aprovar=aprovar_entradas
        )
        
        # Step 3: Summary
        self.logger.info("\n[PASSO 3] RESUMO FINAL")
        self.logger.info("-" * 60)
        
        total_movimentos = len(movimentos)
        lancamentos_criados = resumo_processamento["sucesso"]
        nao_classificados = resumo_processamento["nao_classificados"]
        erros = resumo_processamento["erros"]
        
        self.logger.info(f"Total de movimentos: {total_movimentos}")
        self.logger.info(f"Lançamentos criados: {lancamentos_criados}")
        self.logger.info(f"Não classificados: {nao_classificados}")
        self.logger.info(f"Erros: {erros}")
        
        taxa_sucesso = (lancamentos_criados / total_movimentos * 100) if total_movimentos > 0 else 0
        self.logger.info(f"\nTaxa de sucesso: {taxa_sucesso:.1f}%")
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info("FLUXO CONCLUÍDO")
        self.logger.info("=" * 60)
        
        return {
            "fase_importacao": {
                "movimentos_importados": total_movimentos
            },
            "fase_processamento": resumo_processamento,
            "resumo_final": {
                "total": total_movimentos,
                "lancamentos_criados": lancamentos_criados,
                "nao_classificados": nao_classificados,
                "erros": erros,
                "taxa_sucesso_percentual": taxa_sucesso
            }
        }
