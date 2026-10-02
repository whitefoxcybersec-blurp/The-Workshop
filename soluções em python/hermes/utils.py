"""Utility functions and logging configuration."""

import logging
from pathlib import Path


def configurar_logging(nome: str = "hermes", nivel: str = "INFO") -> logging.Logger:
    """Configure and return a logger instance.
    
    Args:
        nome: Logger name
        nivel: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(nome)
    
    # Avoid adding multiple handlers
    if logger.hasHandlers():
        return logger
    
    logger.setLevel(getattr(logging, nivel))
    
    # Console handler with formatting
    handler = logging.StreamHandler()
    handler.setLevel(getattr(logging, nivel))
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger


def validar_arquivo_pdf(caminho: Path) -> None:
    """Validate if PDF file exists and is readable.
    
    Args:
        caminho: Path to PDF file
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not a PDF
        PermissionError: If file is not readable
    """
    caminho = Path(caminho)
    
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    
    if caminho.suffix.lower() != '.pdf':
        raise ValueError(f"Arquivo não é um PDF: {caminho}")
    
    if not caminho.is_file():
        raise ValueError(f"Caminho não é um arquivo: {caminho}")
    
    # Check read permissions by trying to open
    try:
        with open(caminho, 'rb') as f:
            # Read first few bytes to verify PDF signature
            header = f.read(4)
            if header != b'%PDF':
                raise ValueError(f"Arquivo não é um PDF válido: {caminho}")
    except PermissionError as e:
        raise PermissionError(f"Sem permissão para ler: {caminho}") from e


def limpar_descricao(descricao: str) -> str:
    """Clean and normalize transaction description.
    
    Args:
        descricao: Raw description text
        
    Returns:
        Cleaned description
    """
    import re
    
    # Remove extra whitespace
    descricao = re.sub(r'\s+', ' ', descricao).strip()
    
    # Remove common prefixes/suffixes
    descricao = re.sub(r'^(HISTÓRICO|MEMO|DESC)[\s:]*', '', descricao, flags=re.IGNORECASE)
    
    return descricao
