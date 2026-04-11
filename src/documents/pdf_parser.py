"""
PDF Parser
Extract text and perform sentiment analysis on announcement PDFs
"""
import re
from pathlib import Path
from typing import Optional, Dict, List
import logging

try:
    import PyPDF2
    import pdfplumber
except ImportError:
    PyPDF2 = None
    pdfplumber = None

from textblob import TextBlob
from src.config.config import config

logger = logging.getLogger(__name__)


class PDFParser:
    """Parse PDF documents and extract insights"""

    def __init__(self):
        """Initialize PDF parser"""
        if PyPDF2 is None or pdfplumber is None:
            logger.warning("PDF parsing libraries not available")

    def extract_text_pypdf2(self, pdf_path: Path) -> str:
        """
        Extract text using PyPDF2

        Parameters
        ----------
        pdf_path : Path
            Path to PDF file

        Returns
        -------
        str
            Extracted text
        """
        text = ""
        try:
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            logger.error(f"PyPDF2 extraction failed: {e}")
        return text

    def extract_text_pdfplumber(self, pdf_path: Path) -> str:
        """
        Extract text using pdfplumber (better quality)

        Parameters
        ----------
        pdf_path : Path
            Path to PDF file

        Returns
        -------
        str
            Extracted text
        """
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
        return text

    def extract_text(self, pdf_path: Path) -> str:
        """
        Extract text from PDF using best available method

        Parameters
        ----------
        pdf_path : Path
            Path to PDF file

        Returns
        -------
        str
            Extracted text
        """
        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            return ""

        # Try pdfplumber first (better quality)
        text = self.extract_text_pdfplumber(pdf_path)

        # Fallback to PyPDF2
        if not text:
            text = self.extract_text_pypdf2(pdf_path)

        logger.info(f"Extracted {len(text)} characters from {pdf_path.name}")
        return text

    def extract_financial_metrics(self, text: str) -> Dict[str, Optional[float]]:
        """
        Extract financial metrics from text using regex

        Parameters
        ----------
        text : str
            PDF text content

        Returns
        -------
        dict
            Extracted financial metrics
        """
        metrics = {
            'revenue': None,
            'net_profit': None,
            'eps': None,
            'ebitda': None,
            'operating_margin': None,
            'net_margin': None,
        }

        # Clean text
        text = text.lower()

        # Regex patterns for common financial metrics
        patterns = {
            'revenue': r'revenue[:\s]+(?:rs\.?|inr)?\s*([\d,]+\.?\d*)\s*(cr|crore|million|billion)?',
            'net_profit': r'net profit[:\s]+(?:rs\.?|inr)?\s*([\d,]+\.?\d*)\s*(cr|crore|million|billion)?',
            'eps': r'eps[:\s]+(?:rs\.?|inr)?\s*([\d,]+\.?\d*)',
            'ebitda': r'ebitda[:\s]+(?:rs\.?|inr)?\s*([\d,]+\.?\d*)\s*(cr|crore|million|billion)?',
        }

        for metric, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                try:
                    value = float(match.group(1).replace(',', ''))
                    unit = match.group(2) if len(match.groups()) > 1 else None

                    # Convert to common unit (crores)
                    if unit and 'million' in unit:
                        value *= 0.1  # Convert millions to crores
                    elif unit and 'billion' in unit:
                        value *= 100  # Convert billions to crores

                    metrics[metric] = value
                except Exception as e:
                    logger.debug(f"Failed to parse {metric}: {e}")

        return metrics

    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """
        Perform sentiment analysis on text

        Parameters
        ----------
        text : str
            Text to analyze

        Returns
        -------
        dict
            Sentiment scores and keywords
        """
        if not text:
            return {
                'polarity': 0.0,
                'subjectivity': 0.0,
                'positive_keywords': 0,
                'negative_keywords': 0,
                'sentiment_score': 0.0
            }

        # TextBlob sentiment
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity  # -1 to 1
        subjectivity = blob.sentiment.subjectivity  # 0 to 1

        # Count keyword occurrences
        text_lower = text.lower()
        positive_count = sum(
            text_lower.count(word)
            for word in config.SENTIMENT_KEYWORDS_POSITIVE
        )
        negative_count = sum(
            text_lower.count(word)
            for word in config.SENTIMENT_KEYWORDS_NEGATIVE
        )

        # Composite sentiment score
        keyword_score = (positive_count - negative_count) / max(
            positive_count + negative_count, 1
        )
        sentiment_score = 0.6 * polarity + 0.4 * keyword_score

        return {
            'polarity': polarity,
            'subjectivity': subjectivity,
            'positive_keywords': positive_count,
            'negative_keywords': negative_count,
            'sentiment_score': sentiment_score
        }

    def parse_announcement(self, pdf_path: Path) -> Dict:
        """
        Complete parsing of announcement PDF

        Parameters
        ----------
        pdf_path : Path
            Path to PDF file

        Returns
        -------
        dict
            Parsed information including text, metrics, sentiment
        """
        logger.info(f"Parsing PDF: {pdf_path}")

        # Extract text
        text = self.extract_text(pdf_path)

        if not text:
            logger.warning(f"No text extracted from {pdf_path}")
            return {
                'text': '',
                'metrics': {},
                'sentiment': self.analyze_sentiment(''),
                'word_count': 0
            }

        # Extract metrics
        metrics = self.extract_financial_metrics(text)

        # Analyze sentiment
        sentiment = self.analyze_sentiment(text)

        result = {
            'text': text,
            'metrics': metrics,
            'sentiment': sentiment,
            'word_count': len(text.split())
        }

        logger.info(f"Parsed {result['word_count']} words, "
                   f"sentiment: {sentiment['sentiment_score']:.2f}")

        return result

    def extract_guidance(self, text: str) -> Dict[str, any]:
        """
        Extract forward guidance from announcement text

        Parameters
        ----------
        text : str
            Announcement text

        Returns
        -------
        dict
            Guidance indicators
        """
        guidance = {
            'has_guidance': False,
            'guidance_sentiment': 0.0,
            'mentions_growth': False,
            'mentions_expansion': False,
            'mentions_orders': False,
        }

        text_lower = text.lower()

        # Look for guidance keywords
        guidance_keywords = [
            'guidance', 'outlook', 'expect', 'forecast', 'project',
            'anticipate', 'target', 'goal'
        ]

        if any(keyword in text_lower for keyword in guidance_keywords):
            guidance['has_guidance'] = True

        # Check for specific positive signals
        if any(word in text_lower for word in ['growth', 'grow', 'increase']):
            guidance['mentions_growth'] = True

        if any(word in text_lower for word in ['expansion', 'expand', 'capex']):
            guidance['mentions_expansion'] = True

        if any(word in text_lower for word in ['order', 'booking', 'pipeline']):
            guidance['mentions_orders'] = True

        # Calculate guidance sentiment
        positive_signals = sum([
            guidance['mentions_growth'],
            guidance['mentions_expansion'],
            guidance['mentions_orders']
        ])

        if guidance['has_guidance']:
            guidance['guidance_sentiment'] = positive_signals / 3.0

        return guidance
