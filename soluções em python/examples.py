"""
Example usage patterns for Hermes Extract library

This file demonstrates different ways to use the library:
1. Basic CLI usage
2. Programmatic usage
3. Custom configuration
4. Multi-format export
5. Error handling
6. Logging configuration
7. Extending with custom parsers
"""

from pathlib import Path
from decimal import Decimal

from hermes.converter import ConversorOFX
from hermes.models import BancoEnum, Transacao, Extrato
from hermes.parsers import ParserBase, ParserFactory, extrair_texto_pdf
from hermes.exporters import ExportadorFactory
from hermes.utils import configurar_logging


def exemplo_1_uso_basico():
    """Example 1: Basic usage - convert PDF to OFX"""
    print("\n=== Exemplo 1: Uso Básico ===")
    
    caminho_pdf = Path("pdf/extrato.pdf")
    conversor = ConversorOFX()
    
    # Convert to OFX (default)
    resultados = conversor.converter(caminho_pdf)
    
    for formato, caminho in resultados.items():
        if caminho:
            print(f"✓ {formato.upper()}: {caminho}")
        else:
            print(f"✗ {formato.upper()}: Falha")


def exemplo_2_multiplos_formatos():
    """Example 2: Export to multiple formats simultaneously"""
    print("\n=== Exemplo 2: Múltiplos Formatos ===")
    
    caminho_pdf = Path("pdf/extrato.pdf")
    caminho_saida = Path("output/")
    
    conversor = ConversorOFX(
        agencia="1234",
        conta="5678-9"
    )
    
    # Export to OFX, CSV, JSON, and XLSX
    resultados = conversor.converter(
        caminho_pdf,
        caminho_saida,
        formatos=["ofx", "csv", "json", "xlsx"]
    )
    
    print(f"Arquivos gerados:")
    for formato, caminho in resultados.items():
        if caminho:
            print(f"  - {caminho}")


def exemplo_3_acesso_aos_dados():
    """Example 3: Access parsed transaction data programmatically"""
    print("\n=== Exemplo 3: Acesso aos Dados ===")
    
    caminho_pdf = Path("pdf/extrato.pdf")
    conversor = ConversorOFX()
    
    # Process PDF and get Extrato object
    extrato = conversor.processar_pdf(caminho_pdf)
    
    # Access statement information
    print(f"Banco: {extrato.banco.value}")
    print(f"Agência: {extrato.agencia}")
    print(f"Conta: {extrato.conta}")
    print(f"Total de Transações: {len(extrato.transacoes)}")
    print(f"\nResumo Financeiro:")
    print(f"  Créditos: {extrato.total_creditos()}")
    print(f"  Débitos: {extrato.total_debitos()}")
    print(f"  Saldo Líquido: {extrato.saldo_liquido()}")
    
    # Show first 5 transactions
    print(f"\nPrimeiras 5 Transações:")
    for i, tx in enumerate(extrato.transacoes[:5]):
        print(f"  {tx.data} - {tx.descricao}: {tx.valor} ({tx.tipo.value})")


def exemplo_4_banco_forcado():
    """Example 4: Force specific bank (skip auto-detection)"""
    print("\n=== Exemplo 4: Banco Forçado ===")
    
    caminho_pdf = Path("pdf/extrato.pdf")
    
    # Force Itau parser
    conversor = ConversorOFX(banco_force=BancoEnum.ITAU)
    
    extrato = conversor.processar_pdf(caminho_pdf)
    print(f"Banco forçado para: {extrato.banco.value}")


def exemplo_5_logging_customizado():
    """Example 5: Custom logging configuration"""
    print("\n=== Exemplo 5: Logging Customizado ===")
    
    # Configure DEBUG logging
    logger = configurar_logging("meuapp", "DEBUG")
    logger.debug("Teste de DEBUG")
    logger.info("Teste de INFO")
    logger.warning("Teste de WARNING")
    
    # Now run conversion with verbose logging
    caminho_pdf = Path("pdf/extrato.pdf")
    conversor = ConversorOFX()
    extrato = conversor.processar_pdf(caminho_pdf)


def exemplo_6_tratamento_erros():
    """Example 6: Error handling"""
    print("\n=== Exemplo 6: Tratamento de Erros ===")
    
    try:
        # Try to process non-existent file
        conversor = ConversorOFX()
        extrato = conversor.processar_pdf(Path("inexistente.pdf"))
        
    except FileNotFoundError as e:
        print(f"Erro de arquivo: {e}")
    except ValueError as e:
        print(f"Erro de validação: {e}")
    except Exception as e:
        print(f"Erro geral: {e}")


def exemplo_7_parser_customizado():
    """Example 7: Create and register custom parser for new bank"""
    print("\n=== Exemplo 7: Parser Customizado ===")
    
    # Define custom parser for "Meu Banco"
    class ParserMeuBanco(ParserBase):
        def parse(self, texto: str) -> list[Transacao]:
            """Parse Meu Banco statement format"""
            self.logger.info("Usando parser customizado: Meu Banco")
            
            # Implement your custom parsing logic here
            # For now, just return empty list as example
            return []
    
    # Register the custom parser
    banco_meu = BancoEnum.DESCONHECIDO  # Use as placeholder
    ParserFactory.registrar_parser(banco_meu, ParserMeuBanco)
    
    print("✓ Parser customizado registrado")


def exemplo_8_validacao_transacoes():
    """Example 8: Validate and filter transactions"""
    print("\n=== Exemplo 8: Validação e Filtro ===")
    
    caminho_pdf = Path("pdf/extrato.pdf")
    conversor = ConversorOFX()
    extrato = conversor.processar_pdf(caminho_pdf)
    
    # Filter only debit transactions
    debitos = [t for t in extrato.transacoes if t.valor < 0]
    print(f"Total de débitos: {len(debitos)}")
    
    # Filter only credit transactions
    creditos = [t for t in extrato.transacoes if t.valor > 0]
    print(f"Total de créditos: {len(creditos)}")
    
    # Filter by description (e.g., search for "PAGAMENTO")
    pagamentos = [
        t for t in extrato.transacoes 
        if "PAGAMENTO" in t.descricao.upper()
    ]
    print(f"Total de pagamentos: {len(pagamentos)}")
    
    # Sum all transactions with value > 1000
    grandes_valores = [t for t in extrato.transacoes if abs(t.valor) > 1000]
    total_grandes = sum(abs(t.valor) for t in grandes_valores)
    print(f"Total de transações > R$ 1000: {len(grandes_valores)} (Total: {total_grandes})")


def exemplo_9_exportacao_seletiva():
    """Example 9: Export specific format to custom path"""
    print("\n=== Exemplo 9: Exportação Seletiva ===")
    
    caminho_pdf = Path("pdf/extrato.pdf")
    conversor = ConversorOFX()
    extrato = conversor.processar_pdf(caminho_pdf)
    
    # Export only JSON to custom location
    exportador = ExportadorFactory.criar_exportador(
        "json",
        Path("relatorios/meu_extrato_2026_08.json")
    )
    exportador.exportar(extrato)
    print("✓ JSON exportado para relatorios/")
    
    # Export only CSV
    exportador_csv = ExportadorFactory.criar_exportador(
        "csv",
        Path("dados/extrato.csv")
    )
    exportador_csv.exportar(extrato)
    print("✓ CSV exportado para dados/")


def exemplo_10_pipeline_completo():
    """Example 10: Complete pipeline with all features"""
    print("\n=== Exemplo 10: Pipeline Completo ===")
    
    # Configuration
    caminho_pdf = Path("pdf/extrato.pdf")
    caminho_saida = Path("output/completo/")
    formatos = ["ofx", "csv", "json", "xlsx", "xml"]
    
    # Setup logging
    logger = configurar_logging("pipeline", "INFO")
    logger.info("Iniciando pipeline completo...")
    
    try:
        # Create converter
        conversor = ConversorOFX(
            agencia="1234",
            conta="9876-5"
        )
        
        logger.info("Processando PDF...")
        extrato = conversor.processar_pdf(caminho_pdf)
        
        # Print statistics
        logger.info(f"Banco: {extrato.banco.value}")
        logger.info(f"Transações: {len(extrato.transacoes)}")
        logger.info(f"Saldo: {extrato.saldo_liquido()}")
        
        # Export all formats
        logger.info("Exportando para todos os formatos...")
        resultados = conversor.exportar(extrato, caminho_saida, formatos)
        
        # Report results
        logger.info("Resultados:")
        for formato, caminho in resultados.items():
            if caminho:
                logger.info(f"  ✓ {formato.upper()}: {caminho}")
            else:
                logger.error(f"  ✗ {formato.upper()}: Falha")
        
        logger.info("Pipeline concluído com sucesso!")
        
    except Exception as e:
        logger.error(f"Erro no pipeline: {e}")
        import traceback
        traceback.print_exc()


def exemplo_11_precisao_decimal():
    """Example 11: Demonstrate Decimal precision advantage"""
    print("\n=== Exemplo 11: Precisão Decimal ===")
    
    from decimal import Decimal
    
    # ❌ Float precision issues
    resultado_float = 0.1 + 0.2
    print(f"Float (0.1 + 0.2): {resultado_float}")  # 0.30000000000000004
    print(f"Float == 0.3: {resultado_float == 0.3}")  # False ❌
    
    # ✅ Decimal precision
    resultado_decimal = Decimal("0.1") + Decimal("0.2")
    print(f"\nDecimal (0.1 + 0.2): {resultado_decimal}")  # 0.3
    print(f"Decimal == 0.3: {resultado_decimal == Decimal('0.3')}")  # True ✅
    
    # Financial example
    print("\nExemplo Financeiro:")
    valor1 = Decimal("10.50")
    valor2 = Decimal("20.30")
    valor3 = Decimal("30.20")
    total = valor1 + valor2 + valor3
    print(f"{valor1} + {valor2} + {valor3} = {total}")
    print(f"Com precisão: {total == Decimal('61.00')}")  # True ✅


if __name__ == "__main__":
    print("=" * 60)
    print("HERMES EXTRACT - EXEMPLOS DE USO")
    print("=" * 60)
    
    # Run all examples
    # (Uncomment the ones you want to test)
    
    # Basic examples
    # exemplo_1_uso_basico()
    # exemplo_2_multiplos_formatos()
    # exemplo_3_acesso_aos_dados()
    # exemplo_4_banco_forcado()
    # exemplo_5_logging_customizado()
    
    # Advanced examples
    # exemplo_6_tratamento_erros()
    # exemplo_7_parser_customizado()
    # exemplo_8_validacao_transacoes()
    # exemplo_9_exportacao_seletiva()
    # exemplo_10_pipeline_completo()
    
    # Educational example
    exemplo_11_precisao_decimal()
    
    print("\n" + "=" * 60)
    print("Para usar estes exemplos:")
    print("1. Descomente a função desejada no final do arquivo")
    print("2. Execute: python3 examples.py")
    print("=" * 60)
