"""PDF parsing logic for different banks."""

import re
import subprocess
from abc import ABC, abstractmethod
from decimal import Decimal
from pathlib import Path
from typing import Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

from .models import BancoEnum, Transacao
from .utils import configurar_logging

logger = configurar_logging(__name__)


def extrair_texto_pdf(caminho_pdf: Path) -> str:
    """Extract text from PDF file.
    
    Tries pdfplumber first, falls back to pdftotext command-line tool.
    
    Args:
        caminho_pdf: Path to PDF file
        
    Returns:
        Extracted text from all pages
    """
    logger.info(f"Extraindo texto do PDF: {caminho_pdf}")
    
    if pdfplumber is not None:
        logger.debug("Usando pdfplumber para extração")
        texto_completo = ""
        with pdfplumber.open(caminho_pdf) as pdf:
            for i, pagina in enumerate(pdf.pages):
                texto = pagina.extract_text()
                if texto:
                    texto_completo += texto + "\n"
                    logger.debug(f"Página {i+1} extraída ({len(texto)} caracteres)")
        return texto_completo
    else:
        logger.debug("Usando pdftotext para extração")
        resultado = subprocess.run(
            ['pdftotext', '-layout', str(caminho_pdf), '-'],
            check=True,
            capture_output=True,
            text=True,
        )
        return resultado.stdout


def detectar_banco(texto: str) -> BancoEnum:
    """Auto-detect bank from PDF header text.
    
    Args:
        texto: Extracted PDF text
        
    Returns:
        Detected bank or DESCONHECIDO if not matched
    """
    texto_upper = texto.upper()
    
    # Define bank keywords
    deteccoes = {
        BancoEnum.ITAU: [r'\bitau\b', r'banco itau'],
        BancoEnum.INTER: [r'\binter\b', r'banco inter'],
        BancoEnum.SANTANDER: [r'\bsantander\b'],
        BancoEnum.BRADESCO: [r'\bbradesco\b', r'banco bradesco'],
        BancoEnum.BANCO_DO_BRASIL: [r'\bbb\b', r'banco do brasil'],
        BancoEnum.NUBANK: [r'\bnubank\b'],
        BancoEnum.SICREDI: [r'\bsicredi\b'],
    }
    
    # Check first 1000 characters (usually header)
    texto_header = texto_upper[:1000]
    
    for banco, palavras in deteccoes.items():
        for palavra in palavras:
            if re.search(palavra, texto_header, re.IGNORECASE):
                logger.info(f"Banco detectado: {banco.value}")
                return banco
    
    logger.warning("Banco não identificado, usando parser genérico")
    return BancoEnum.DESCONHECIDO


class ParserBase(ABC):
    """Abstract base class for bank-specific parsers."""
    
    def __init__(self):
        self.logger = logger
    
    @abstractmethod
    def parse(self, texto: str) -> list[Transacao]:
        """Parse transactions from text.
        
        Args:
            texto: Extracted PDF text
            
        Returns:
            List of Transacao objects
        """
        pass


class ParserGenerico(ParserBase):
    """Generic parser for unknown banks."""
    
    def parse(self, texto: str) -> list[Transacao]:
        """Parse generic bank statement format."""
        transacoes = []
        linhas = texto.splitlines()

        padrao_data = re.compile(r'^\s*(\d{2}/\d{2}/\d{4})\b')
        padrao_valor = re.compile(
            r'(?:(?P<signal_before>[+-])\s*)?R\$\s*(?:(?P<signal_after>[+-])\s*)?(?P<valor>[\d.]+,\d{2})'
        )

        i = 0
        while i < len(linhas):
            linha = linhas[i].strip()
            if not linha:
                i += 1
                continue

            correspondencia_data = padrao_data.match(linha)
            if not correspondencia_data:
                i += 1
                continue

            data = correspondencia_data.group(1)
            from datetime import datetime
            data_iso = datetime.strptime(data, '%d/%m/%Y').strftime('%Y%m%d')
            restante = linha[correspondencia_data.end():].strip()

            if not restante:
                i += 1
                continue

            correspondencia_valor = padrao_valor.search(restante)
            if correspondencia_valor:
                texto_descricao = restante[:correspondencia_valor.start()].strip()
                if not texto_descricao or not re.search(r'[A-Za-zÀ-ÿ]', texto_descricao):
                    i += 1
                    continue

                sinal_antes = correspondencia_valor.group('signal_before') or ''
                sinal_depois = correspondencia_valor.group('signal_after') or ''
                valor_str = correspondencia_valor.group('valor').replace('.', '').replace(',', '.')
                sinal = '-' if sinal_antes == '-' or sinal_depois == '-' else ''
                valor_limpo = f'{sinal}{valor_str}'

                descricao_itens = [texto_descricao]
                j = i + 1
                while j < len(linhas):
                    proxima = linhas[j].strip()
                    if not proxima:
                        j += 1
                        continue
                    if padrao_data.match(proxima):
                        break
                    if re.search(r'\bR\$\b|[+-]?\s*\d{1,3}(?:[\.\s]\d{3})*,\d{2}', proxima):
                        break
                    descricao_itens.append(proxima)
                    j += 1

                descricao = ' '.join(part for part in descricao_itens if part).strip()
                descricao = re.sub(r'\s+', ' ', descricao)
                
                try:
                    transacao = Transacao(
                        data=data_iso,
                        descricao=descricao,
                        valor=Decimal(valor_limpo)
                    )
                    transacoes.append(transacao)
                    self.logger.debug(f"Transação parseada: {transacao.descricao} - {transacao.valor}")
                except Exception as e:
                    self.logger.error(f"Erro ao parsear transação: {e}")
                
                i = j
                continue

            descricao_itens = [restante]
            j = i + 1
            while j < len(linhas):
                proxima = linhas[j].strip()
                if not proxima:
                    j += 1
                    continue
                if padrao_data.match(proxima):
                    break
                if re.search(r'\bR\$\b|[+-]?\s*\d{1,3}(?:[\.\s]\d{3})*,\d{2}', proxima):
                    break
                descricao_itens.append(proxima)
                j += 1

            if any(part for part in descricao_itens if part):
                descricao = ' '.join(part for part in descricao_itens if part).strip()
                descricao = re.sub(r'\s+', ' ', descricao)
                
                try:
                    transacao = Transacao(
                        data=data_iso,
                        descricao=descricao,
                        valor=Decimal('0.00')
                    )
                    transacoes.append(transacao)
                except Exception as e:
                    self.logger.error(f"Erro ao parsear transação: {e}")
            
            i = j

        return transacoes


class ParserItau(ParserBase):
    """Itau-specific parser."""
    
    def parse(self, texto: str) -> list[Transacao]:
        """Parse Itau statement format."""
        self.logger.info("Usando parser específico: Itau")
        # For now, use generic parser; can be enhanced with Itau-specific patterns
        return ParserGenerico().parse(texto)


class ParserInter(ParserBase):
    """Inter-specific parser."""
    
    def parse(self, texto: str) -> list[Transacao]:
        """Parse Inter statement format."""
        self.logger.info("Usando parser específico: Inter")
        return ParserGenerico().parse(texto)


class ParserFactory:
    """Factory to create appropriate parser based on bank."""
    
    _parsers = {
        BancoEnum.ITAU: ParserItau,
        BancoEnum.INTER: ParserInter,
        BancoEnum.SANTANDER: ParserGenerico,
        BancoEnum.BRADESCO: ParserGenerico,
        BancoEnum.BANCO_DO_BRASIL: ParserGenerico,
        BancoEnum.NUBANK: ParserGenerico,
        BancoEnum.SICREDI: ParserGenerico,
        BancoEnum.DESCONHECIDO: ParserGenerico,
    }
    
    @classmethod
    def criar_parser(cls, banco: BancoEnum) -> ParserBase:
        """Create parser for specified bank.
        
        Args:
            banco: Bank to create parser for
            
        Returns:
            Parser instance
        """
        parser_class = cls._parsers.get(banco, ParserGenerico)
        return parser_class()
    
    @classmethod
    def registrar_parser(cls, banco: BancoEnum, parser_class):
        """Register custom parser for bank.
        
        Args:
            banco: Bank identifier
            parser_class: Parser class
        """
        cls._parsers[banco] = parser_class
        logger.info(f"Parser registrado para {banco.value}")
