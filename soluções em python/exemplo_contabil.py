"""
Complete example demonstrating the Hermes accounting engine.

This shows the full pipeline:
PDF → Parser → Movements → Classification → Accounting Entries → Reconciliation
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from hermes.database import init_database
from hermes.converter import ConversorOFX
from hermes.loaders import InitializerService
from hermes.integracao import FluxoCompleto
from hermes.utils import configurar_logging

logger = configurar_logging("exemplo_contabil", "INFO")


def exemplo_completo():
    """Complete example from PDF to accounting entries."""
    
    logger.info("=" * 70)
    logger.info("EXEMPLO COMPLETO: HERMES EXTRACT - MOTOR CONTÁBIL")
    logger.info("=" * 70)
    
    # ========================================================================
    # PASSO 1: INICIALIZAR BANCO DE DADOS
    # ========================================================================
    logger.info("\n[PASSO 1] Inicializando banco de dados...")
    engine, Session = init_database("sqlite:///hermes_exemplo.db")
    session = Session()
    
    logger.info("✓ Banco de dados criado")
    
    # ========================================================================
    # PASSO 2: SETUP DA EMPRESA
    # ========================================================================
    logger.info("\n[PASSO 2] Configurando empresa...")
    
    initializer = InitializerService(session)
    empresa = initializer.inicializar_empresa(
        razao_social="ACME CORP BRASIL LTDA",
        nome_fantasia="ACME",
        cnpj="12.345.678/0001-00"
    )
    
    logger.info(f"✓ Empresa criada: {empresa.razao_social} (ID: {empresa.id})")
    
    # ========================================================================
    # PASSO 3: CRIAR CONTA BANCÁRIA
    # ========================================================================
    logger.info("\n[PASSO 3] Criando conta bancária...")
    
    conta_banco = initializer.criar_conta_bancaria(
        empresa_id=empresa.id,
        banco_nome="BANCO ITAÚ",
        banco_codigo="033",
        agencia="1234",
        conta="56789",
        digito="0",
        titular="ACME CORP",
        cpf_cnpj="12.345.678/0001-00",
        conta_contabil_codigo="1.1.1.02.0003"  # Banco Itau
    )
    
    logger.info(f"✓ Conta bancária criada: {conta_banco.banco_nome} {conta_banco.agencia}/{conta_banco.conta}")
    
    # ========================================================================
    # PASSO 4: EXTRAIR PDF E FAZER PARSING
    # ========================================================================
    logger.info("\n[PASSO 4] Extraindo dados do PDF...")
    
    caminho_pdf = Path("/home/whitefox/Documentos/soluções em python/pdf/ead-solucoes-integradas-ltda_01022026_a_31072026_26d7e73f.pdf")
    
    if not caminho_pdf.exists():
        logger.error(f"PDF não encontrado: {caminho_pdf}")
        return
    
    # Use existing parser
    conversor = ConversorOFX()
    extrato = conversor.processar_pdf(caminho_pdf)
    
    logger.info(f"✓ PDF processado: {len(extrato.transacoes)} transações extraídas")
    logger.info(f"  - Créditos: {extrato.total_creditos()}")
    logger.info(f"  - Débitos: {extrato.total_debitos()}")
    logger.info(f"  - Saldo: {extrato.saldo_liquido()}")
    
    # ========================================================================
    # PASSO 5: EXECUTAR FLUXO COMPLETO
    # ========================================================================
    logger.info("\n[PASSO 5] Executando fluxo: Movimento → Classificação → Lançamento...")
    
    fluxo = FluxoCompleto(session)
    resultado_fluxo = fluxo.executar_fluxo(
        conta_bancaria=conta_banco,
        transacoes=extrato.transacoes,
        aprovar_entradas=False  # Deixar para revisão manual
    )
    
    # ========================================================================
    # PASSO 6: RELATÓRIOS
    # ========================================================================
    logger.info("\n[PASSO 6] Gerando relatórios...")
    
    # Movimentos não classificados
    nao_classificados = resultado_fluxo["fase_processamento"]["resultados"]
    sem_class = [r for r in nao_classificados if r["status"] == "nao_classificado"]
    
    if sem_class:
        logger.info(f"\n⚠ Movimentos SEM classificação ({len(sem_class)}):")
        for r in sem_class[:5]:  # Show first 5
            mov = session.query(MovimentoBancario).get(r["movimento_id"])
            if mov:
                logger.info(f"  - {mov.data}: {mov.descricao} (R$ {mov.valor})")
    
    # Lançamentos criados
    lancamentos_criados = [r for r in nao_classificados if r["status"] == "sucesso"]
    if lancamentos_criados:
        logger.info(f"\n✓ Lançamentos criados ({len(lancamentos_criados)}):")
        for r in lancamentos_criados[:3]:  # Show first 3
            lancamento_id = r["lancamento_id"]
            from hermes.database import LancamentoContabil
            lancamento = session.query(LancamentoContabil).get(lancamento_id)
            if lancamento:
                logger.info(f"  - #{lancamento_id}: {lancamento.historico} ({lancamento.status.value})")
                logger.info(f"    D: {lancamento.total_debitos()} / C: {lancamento.total_creditos()}")
    
    # ========================================================================
    # PASSO 7: EXEMPLOS DE CONSULTAS
    # ========================================================================
    logger.info("\n[PASSO 7] Exemplos de consultas ao banco de dados...")
    
    from hermes.database import PlanoContas, LancamentoContabil, MovimentoBancario
    
    # Contas analíticas (aceitam lançamentos)
    contas_analiticas = session.query(PlanoContas).filter(
        PlanoContas.empresa_id == empresa.id,
        PlanoContas.aceita_lancamento == True
    ).limit(5).all()
    
    logger.info(f"\nContas Analíticas da Empresa:")
    for conta in contas_analiticas:
        logger.info(f"  - {conta.codigo}: {conta.descricao}")
    
    # Movimentos conciliados
    movimentos_conciliados = session.query(MovimentoBancario).filter(
        MovimentoBancario.conta_bancaria_id == conta_banco.id,
        MovimentoBancario.conciliado == True
    ).count()
    
    logger.info(f"\nMovimentos Conciliados: {movimentos_conciliados}")
    
    # Lançamentos aprovados
    lancamentos_aprovados = session.query(LancamentoContabil).filter(
        LancamentoContabil.empresa_id == empresa.id
    ).all()
    
    logger.info(f"Total de Lançamentos: {len(lancamentos_aprovados)}")
    
    # ========================================================================
    # PASSO 8: BALANCETE (TRIAL BALANCE)
    # ========================================================================
    logger.info("\n[PASSO 8] Gerando balancete (Trial Balance)...")
    
    balancete_data = {}
    for lancamento in lancamentos_aprovados:
        for partida in lancamento.partidas:
            conta_id = partida.conta_id
            if conta_id not in balancete_data:
                balancete_data[conta_id] = {"debitos": Decimal("0"), "creditos": Decimal("0")}
            
            if partida.debito:
                balancete_data[conta_id]["debitos"] += partida.debito
            if partida.credito:
                balancete_data[conta_id]["creditos"] += partida.credito
    
    if balancete_data:
        logger.info("\nBALANCETE (Resumido):")
        logger.info(f"{'Código':<20} {'Descrição':<40} {'Débito':<15} {'Crédito':<15}")
        logger.info("-" * 90)
        
        total_debitos = Decimal("0")
        total_creditos = Decimal("0")
        
        for conta_id, saldos in list(balancete_data.items())[:10]:  # First 10
            conta = session.query(PlanoContas).get(conta_id)
            if conta:
                deb = saldos["debitos"]
                cred = saldos["creditos"]
                total_debitos += deb
                total_creditos += cred
                
                logger.info(f"{conta.codigo:<20} {conta.descricao:<40} {str(deb):<15} {str(cred):<15}")
        
        logger.info("-" * 90)
        logger.info(f"{'TOTAL':<20} {'':<40} {str(total_debitos):<15} {str(total_creditos):<15}")
    
    # ========================================================================
    # PASSO 9: EXEMPLO DE CLASSIFICAÇÃO MANUAL
    # ========================================================================
    logger.info("\n[PASSO 9] Exemplo: Classificando movimento manualmente...")
    
    # Find unclassified movement
    movimento_nao_classificado = session.query(MovimentoBancario).filter(
        MovimentoBancario.conta_bancaria_id == conta_banco.id,
        MovimentoBancario.conciliado == False
    ).first()
    
    if movimento_nao_classificado:
        logger.info(f"\nMovimento sem classificação:")
        logger.info(f"  Data: {movimento_nao_classificado.data}")
        logger.info(f"  Descrição: {movimento_nao_classificado.descricao}")
        logger.info(f"  Valor: {movimento_nao_classificado.valor}")
        
        logger.info(f"\nProcessando manualmente...")
        from hermes.integracao import ProcessadorMovimentos
        processador = ProcessadorMovimentos(session)
        resultado = processador.processar_movimento(movimento_nao_classificado.id)
        
        logger.info(f"Resultado: {resultado['status']}")
        if resultado['status'] == 'sucesso':
            logger.info(f"  Lançamento #{resultado['lancamento_id']} criado")
            logger.info(f"  Confiança: {resultado['classificacao']['confianca']:.1f}%")
            logger.info(f"  Método: {resultado['classificacao']['metodo']}")
    
    # ========================================================================
    # RESUMO FINAL
    # ========================================================================
    logger.info("\n" + "=" * 70)
    logger.info("RESUMO FINAL DO EXEMPLO")
    logger.info("=" * 70)
    
    logger.info(f"\nEmpresa: {empresa.razao_social}")
    logger.info(f"Banco: {conta_banco.banco_nome} ({conta_banco.agencia}/{conta_banco.conta})")
    logger.info(f"Transações importadas: {len(extrato.transacoes)}")
    logger.info(f"Lançamentos criados: {resultado_fluxo['resumo_final']['lancamentos_criados']}")
    logger.info(f"Taxa de sucesso: {resultado_fluxo['resumo_final']['taxa_sucesso_percentual']:.1f}%")
    
    logger.info(f"\nBanco de dados: hermes_exemplo.db")
    logger.info(f"Tabelas criadas: {list(engine.table_names())[:5]}... e mais")
    
    logger.info("\n✓ Exemplo concluído com sucesso!")
    logger.info("\nPróximos passos:")
    logger.info("  1. Revisar movimentos não classificados")
    logger.info("  2. Adicionar regras de classificação customizadas")
    logger.info("  3. Gerar balancete e DRE")
    logger.info("  4. Exportar para sistema contábil")
    
    session.close()


if __name__ == "__main__":
    try:
        exemplo_completo()
    except Exception as e:
        logger.error(f"Erro no exemplo: {e}")
        import traceback
        traceback.print_exc()
