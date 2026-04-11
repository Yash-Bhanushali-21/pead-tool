"""
PDF Downloader
Download corporate announcement documents from NSE
"""
import os
import requests
from pathlib import Path
from typing import Optional
import logging
from datetime import datetime

from src.config.config import config

logger = logging.getLogger(__name__)


class PDFDownloader:
    """Download PDF documents from corporate announcements"""

    def __init__(self, download_dir: Optional[str] = None):
        """
        Initialize PDF downloader

        Parameters
        ----------
        download_dir : str, optional
            Directory to save PDFs
        """
        self.download_dir = Path(download_dir or config.PDF_DOWNLOAD_DIR)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"PDF download directory: {self.download_dir}")

    def download_pdf(
        self,
        url: str,
        symbol: str,
        announcement_date: datetime,
        filename: Optional[str] = None
    ) -> Optional[Path]:
        """
        Download PDF from URL

        Parameters
        ----------
        url : str
            PDF URL
        symbol : str
            Stock symbol
        announcement_date : datetime
            Announcement date
        filename : str, optional
            Custom filename

        Returns
        -------
        Path or None
            Path to downloaded file
        """
        try:
            if not url:
                logger.warning("No URL provided")
                return None

            # Generate filename if not provided
            if filename is None:
                date_str = announcement_date.strftime('%Y%m%d')
                filename = f"{symbol}_{date_str}.pdf"

            filepath = self.download_dir / filename

            # Skip if already downloaded
            if filepath.exists():
                logger.info(f"PDF already exists: {filepath}")
                return filepath

            # Download with timeout
            logger.info(f"Downloading PDF from {url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # Save PDF
            with open(filepath, 'wb') as f:
                f.write(response.content)

            logger.info(f"Downloaded PDF: {filepath}")
            return filepath

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download PDF from {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error saving PDF: {e}")
            return None

    def download_announcement_pdfs(
        self,
        announcements_df
    ) -> dict:
        """
        Download all PDFs from announcements DataFrame

        Parameters
        ----------
        announcements_df : pd.DataFrame
            DataFrame with announcement URLs

        Returns
        -------
        dict
            Mapping of symbol+date to filepath
        """
        downloaded = {}

        for idx, row in announcements_df.iterrows():
            try:
                symbol = row.get('SYMBOL', '')
                url = row.get('ATTACHMENT_URL', '')
                announcement_date = row.get('ANNOUNCEMENT_DATE', datetime.now())

                if not url or pd.isna(url):
                    continue

                # Ensure URL is complete
                if not url.startswith('http'):
                    # NSE URLs might be relative
                    url = f"https://www.nseindia.com{url}"

                filepath = self.download_pdf(url, symbol, announcement_date)

                if filepath:
                    key = f"{symbol}_{announcement_date.strftime('%Y%m%d')}"
                    downloaded[key] = filepath

            except Exception as e:
                logger.error(f"Error processing announcement {idx}: {e}")
                continue

        logger.info(f"Downloaded {len(downloaded)} PDFs")
        return downloaded

    def get_pdf_path(
        self,
        symbol: str,
        announcement_date: datetime
    ) -> Optional[Path]:
        """
        Get path to existing PDF

        Parameters
        ----------
        symbol : str
            Stock symbol
        announcement_date : datetime
            Announcement date

        Returns
        -------
        Path or None
            Path to PDF if exists
        """
        date_str = announcement_date.strftime('%Y%m%d')
        filename = f"{symbol}_{date_str}.pdf"
        filepath = self.download_dir / filename

        if filepath.exists():
            return filepath

        return None

    def cleanup_old_pdfs(self, days: int = 90) -> None:
        """
        Remove PDFs older than specified days

        Parameters
        ----------
        days : int
            Remove PDFs older than this many days
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days)
        removed = 0

        for pdf_file in self.download_dir.glob("*.pdf"):
            mtime = datetime.fromtimestamp(pdf_file.stat().st_mtime)
            if mtime < cutoff_date:
                pdf_file.unlink()
                removed += 1

        logger.info(f"Removed {removed} old PDFs")
