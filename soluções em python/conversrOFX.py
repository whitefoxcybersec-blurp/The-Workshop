"""
Hermes Extract - PDF Bank Statement to OFX/CSV/XLSX/JSON/XML Converter

This module provides a CLI for converting bank statement PDFs to multiple formats.

Usage:
    python conversrOFX.py <pdf_file> [--formato FORMAT] [--agencia AGENCIA] [--conta CONTA]

Examples:
    python conversrOFX.py extrato.pdf
    python conversrOFX.py extrato.pdf --formato ofx,csv,json
    python conversrOFX.py extrato.pdf --formato xlsx --agencia 1234 --conta 5678
"""

import argparse
import sys
from pathlib import Path

from hermes.converter import ConversorOFX
from hermes.exporters import ExportadorFactory
from hermes.utils import configurar_logging

logger = configurar_logging(__name__, "INFO")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Converte extratos bancários PDF para múltiplos formatos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python conversrOFX.py extrato.pdf
  python conversrOFX.py extrato.pdf --formato ofx,csv,json
  python conversrOFX.py extrato.pdf --formato xlsx --agencia 1234 --conta 5678
  
Formatos suportados: ofx, csv, json, xlsx, xml
        """,
    )
    
    parser.add_argument(
        "pdf",
        nargs="?",
        help="Caminho para o arquivo PDF"
    )
    
    parser.add_argument(
        "--formato",
        "-f",
        default="ofx",
        help="Formatos de saída (separados por vírgula). Padrão: ofx"
    )
    
    parser.add_argument(
        "--agencia",
        "-a",
        default="0001",
        help="Número da agência (padrão: 0001)"
    )
    
    parser.add_argument(
        "--conta",
        "-c",
        default="6858133-2",
        help="Número da conta (padrão: 6858133-2)"
    )
    
    parser.add_argument(
        "--saida",
        "-o",
        help="Diretório ou arquivo de saída (padrão: mesma pasta do PDF)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Modo verboso (DEBUG)"
    )
    
    parser.add_argument(
        "--listar-formatos",
        action="store_true",
        help="Lista os formatos suportados"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logger.setLevel("DEBUG")
    
    # List supported formats if requested
    if args.listar_formatos:
        print("Formatos suportados:")
        for fmt in ExportadorFactory.formatos_suportados():
            print(f"  - {fmt}")
        return 0
    
    # Use default PDF if no argument provided
    if not args.pdf:
        pasta_codigo = Path(__file__).resolve().parent
        pdf_default = pasta_codigo / 'pdf' / 'ead-solucoes-integradas-ltda_01022026_a_31072026_26d7e73f.pdf'
        
        if pdf_default.exists():
            args.pdf = pdf_default
            logger.info(f"Usando PDF padrão: {args.pdf}")
        else:
            logger.error("Nenhum arquivo PDF fornecido e arquivo padrão não encontrado")
            parser.print_help()
            return 1
    
    caminho_pdf = Path(args.pdf).resolve()
    
    # Determine output path
    caminho_saida = Path(args.saida) if args.saida else caminho_pdf.parent
    
    # Parse formats
    formatos = [f.strip() for f in args.formato.split(',')]
    
    try:
        # Create converter
        conversor = ConversorOFX(
            agencia=args.agencia,
            conta=args.conta
        )
        
        # Convert
        resultados = conversor.converter(
            caminho_pdf,
            caminho_saida,
            formatos
        )
        
        # Check for errors
        erros = [f for f, p in resultados.items() if p is None]
        if erros:
            logger.error(f"Falha em alguns formatos: {', '.join(erros)}")
            return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Erro durante conversão: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())