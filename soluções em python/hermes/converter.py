"""Main converter orchestrating the PDF to multiple formats conversion."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import BancoEnum, Extrato
from .parsers import extrair_texto_pdf, detectar_banco, ParserFactory
from .exporters import ExportadorFactory
from .utils import validar_arquivo_pdf, configurar_logging

logger = configurar_logging(__name__)


class ConversorOFX:
    """Main converter class orchestrating extraction and export."""
    
    def __init__(
        self,
        agencia: str = "0001",
        conta: str = "6858133-2",
        banco_force: Optional[BancoEnum] = None
    ):
        """Initialize converter.
        
        Args:
            agencia: Bank agency number
            conta: Account number
            banco_force: Force specific bank (skip auto-detection)
        """
        self.agencia = agencia
        self.conta = conta
        self.banco_force = banco_force
        self.logger = logger
    
    def processar_pdf(self, caminho_pdf: Path) -> Extrato:
        """Process PDF and extract transactions.
        
        Args:
            caminho_pdf: Path to PDF file
            
        Returns:
            Extrato object with parsed transactions
            
        Raises:
            FileNotFoundError: If PDF doesn't exist
            ValueError: If PDF is invalid
        """
        caminho_pdf = Path(caminho_pdf)
        self.logger.info(f"Processando PDF: {caminho_pdf}")
        
        # Validate file
        validar_arquivo_pdf(caminho_pdf)
        
        # Extract text
        texto = extrair_texto_pdf(caminho_pdf)
        
        # Detect or use forced bank
        if self.banco_force:
            banco = self.banco_force
            self.logger.info(f"Banco forçado: {banco.value}")
        else:
            banco = detectar_banco(texto)
        
        # Get appropriate parser
        parser = ParserFactory.criar_parser(banco)
        
        # Parse transactions
        transacoes = parser.parse(texto)
        self.logger.info(f"Total de transações extraídas: {len(transacoes)}")
        
        # Create Extrato object
        extrato = Extrato(
            banco=banco,
            agencia=self.agencia,
            conta=self.conta,
            transacoes=transacoes,
            data_inicio=None,
            data_fim=None,
        )
        
        return extrato
    
    def exportar(
        self,
        extrato: Extrato,
        caminho_saida: Path,
        formatos: Optional[list[str]] = None
    ) -> dict[str, Path]:
        """Export extrato to multiple formats.
        
        Args:
            extrato: Extrato object to export
            caminho_saida: Base output path
            formatos: List of formats to export (default: ['ofx'])
            
        Returns:
            Dictionary mapping format to output file path
        """
        if formatos is None:
            formatos = ['ofx']
        
        caminho_saida = Path(caminho_saida)
        resultados = {}
        
        for formato in formatos:
            try:
                # Create output path with format extension
                if caminho_saida.is_dir():
                    caminho_arquivo = caminho_saida / f"extrato.{formato}"
                else:
                    caminho_arquivo = caminho_saida.with_suffix(f".{formato}")
                
                exportador = ExportadorFactory.criar_exportador(formato, caminho_arquivo)
                exportador.exportar(extrato)
                
                resultados[formato] = caminho_arquivo
                self.logger.info(f"Exportado para {formato}: {caminho_arquivo}")
                
            except Exception as e:
                self.logger.error(f"Erro ao exportar para {formato}: {e}")
                resultados[formato] = None
        
        return resultados
    
    def converter(
        self,
        caminho_pdf: Path,
        caminho_saida: Optional[Path] = None,
        formatos: Optional[list[str]] = None
    ) -> dict[str, Path]:
        """Complete conversion pipeline from PDF to export formats.
        
        Args:
            caminho_pdf: Path to input PDF
            caminho_saida: Path to output files (default: same as PDF location)
            formatos: List of formats to export (default: ['ofx'])
            
        Returns:
            Dictionary mapping format to output file path
        """
        caminho_pdf = Path(caminho_pdf)
        
        if caminho_saida is None:
            caminho_saida = caminho_pdf.parent
        
        self.logger.info("=== Iniciando conversão ===")
        self.logger.info(f"Arquivo: {caminho_pdf}")
        self.logger.info(f"Formatos: {formatos or ['ofx']}")
        
        # Process PDF
        extrato = self.processar_pdf(caminho_pdf)
        
        # Print summary
        self.logger.info(f"Banco: {extrato.banco.value}")
        self.logger.info(f"Total de transações: {len(extrato.transacoes)}")
        self.logger.info(f"Total de créditos: {extrato.total_creditos()}")
        self.logger.info(f"Total de débitos: {extrato.total_debitos()}")
        self.logger.info(f"Saldo líquido: {extrato.saldo_liquido()}")
        
        # Export
        resultados = self.exportar(extrato, caminho_saida, formatos)
        
        # Print results
        self.logger.info("=== Conversão concluída ===")
        for formato, caminho in resultados.items():
            if caminho:
                self.logger.info(f"✓ {formato.upper()}: {caminho}")
            else:
                self.logger.error(f"✗ {formato.upper()}: Falha na conversão")
        
        return resultados
