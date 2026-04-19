"""
Visualization utilities for PEAD analysis
"""
import matplotlib

# Headless backend: FastAPI and other worker threads cannot use the macOS GUI backend.
matplotlib.use("Agg")

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class Visualizer:
    """Visualization utilities for PEAD analysis"""

    def __init__(self, style: str = 'seaborn-v0_8-darkgrid'):
        """
        Initialize visualizer

        Parameters
        ----------
        style : str
            Matplotlib style
        """
        try:
            plt.style.use(style)
        except:
            logger.warning(f"Style {style} not available, using default")
        sns.set_palette("husl")

    def plot_price_and_announcement(
        self,
        stock_data: pd.DataFrame,
        announcement_date: pd.Timestamp,
        save_path: Optional[str] = None
    ):
        """
        Plot stock price with announcement marker

        Parameters
        ----------
        stock_data : pd.DataFrame
            Stock OHLCV data
        announcement_date : pd.Timestamp
            Announcement date
        save_path : str, optional
            Path to save plot
        """
        fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

        # Price plot
        ax1 = axes[0]
        ax1.plot(stock_data.index, stock_data['Close'], linewidth=1.5, label='Close Price')
        ax1.axvline(announcement_date, color='red', linestyle='--', linewidth=2,
                   label='Announcement', alpha=0.7)
        ax1.set_ylabel('Price', fontsize=12)
        ax1.set_title('Stock Price Around Earnings Announcement', fontsize=14, fontweight='bold')
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)

        # Volume plot
        ax2 = axes[1]
        colors = ['green' if x >= 0 else 'red' for x in stock_data['Return'].fillna(0)]
        ax2.bar(stock_data.index, stock_data['Volume'], color=colors, alpha=0.6)
        ax2.axvline(announcement_date, color='red', linestyle='--', linewidth=2, alpha=0.7)
        ax2.set_ylabel('Volume', fontsize=12)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.set_title('Volume', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Plot saved to {save_path}")
        else:
            plt.show()

        plt.close()

    def plot_score_components(
        self,
        score_data: Dict,
        save_path: Optional[str] = None
    ):
        """
        Plot scoring components breakdown

        Parameters
        ----------
        score_data : dict
            Score data from composite scorer
        save_path : str, optional
            Path to save plot
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        # Bar chart of normalized components
        ax1 = axes[0]
        components = score_data['normalized_components']
        comp_names = [c.replace('_', ' ').title() for c in components.keys()]
        comp_values = list(components.values())

        colors = ['green' if v > 50 else 'orange' if v > 30 else 'red' for v in comp_values]
        ax1.barh(comp_names, comp_values, color=colors, alpha=0.7)
        ax1.axvline(50, color='gray', linestyle='--', alpha=0.5, label='Neutral (50)')
        ax1.set_xlabel('Normalized Score (0-100)', fontsize=12)
        ax1.set_title('Component Scores', fontsize=14, fontweight='bold')
        ax1.legend()
        ax1.grid(True, alpha=0.3, axis='x')

        # Pie chart of weighted contribution
        ax2 = axes[1]
        weights = score_data['weights']
        weighted_contrib = {
            k: components[k] * weights[k]
            for k in components.keys()
        }
        contrib_names = [c.replace('_', ' ').title() for c in weighted_contrib.keys()]
        contrib_values = [max(0, v) for v in weighted_contrib.values()]  # Only positive for pie

        ax2.pie(contrib_values, labels=contrib_names, autopct='%1.1f%%', startangle=90)
        ax2.set_title('Weighted Contribution to Final Score', fontsize=14, fontweight='bold')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Plot saved to {save_path}")
        else:
            plt.show()

        plt.close()

    def plot_comparison_dashboard(
        self,
        results_df: pd.DataFrame,
        save_path: Optional[str] = None
    ):
        """
        Plot comparison dashboard for multiple stocks

        Parameters
        ----------
        results_df : pd.DataFrame
            DataFrame with results for multiple stocks
        save_path : str, optional
            Path to save plot
        """
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))

        # 1. Composite scores ranking
        ax1 = axes[0, 0]
        sorted_df = results_df.sort_values('Composite_Score', ascending=True)
        colors = ['green' if x > 60 else 'orange' if x > 40 else 'red'
                 for x in sorted_df['Composite_Score']]

        ax1.barh(sorted_df['Symbol'], sorted_df['Composite_Score'], color=colors, alpha=0.7)
        ax1.set_xlabel('Composite Score', fontsize=12)
        ax1.set_title('PEAD Score Ranking', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='x')

        # 2. Confidence vs Score scatter
        ax2 = axes[0, 1]
        scatter = ax2.scatter(
            results_df['Composite_Score'],
            results_df['Confidence'],
            s=100,
            alpha=0.6,
            c=results_df['Composite_Score'],
            cmap='RdYlGn'
        )
        for idx, row in results_df.iterrows():
            ax2.annotate(row['Symbol'], (row['Composite_Score'], row['Confidence']),
                        fontsize=8, alpha=0.7)
        ax2.set_xlabel('Composite Score', fontsize=12)
        ax2.set_ylabel('Confidence', fontsize=12)
        ax2.set_title('Score vs Confidence', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        plt.colorbar(scatter, ax=ax2, label='Score')

        # 3. Component comparison heatmap
        ax3 = axes[1, 0]
        component_cols = [c for c in results_df.columns if '_normalized' in c]
        if component_cols:
            component_data = results_df[['Symbol'] + component_cols].set_index('Symbol')
            component_data.columns = [c.replace('_normalized', '').replace('_', ' ').title()
                                     for c in component_data.columns]

            sns.heatmap(component_data, annot=True, fmt='.1f', cmap='RdYlGn',
                       center=50, ax=ax3, cbar_kws={'label': 'Score'})
            ax3.set_title('Component Score Heatmap', fontsize=14, fontweight='bold')

        # 4. Rating distribution
        ax4 = axes[1, 1]
        rating_counts = results_df['Rating'].value_counts()
        ax4.pie(rating_counts.values, labels=rating_counts.index, autopct='%1.0f%%',
               startangle=90)
        ax4.set_title('Rating Distribution', fontsize=14, fontweight='bold')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Plot saved to {save_path}")
        else:
            plt.show()

        plt.close()

    def plot_fundamental_pillars(
        self,
        fundamental_data: Dict,
        save_path: Optional[str] = None,
    ):
        """
        Bar chart of fundamental screening pillars (0–25 each, total 0–100).
        """
        scores = fundamental_data.get("scores") or {}
        keys = ["valuation", "quality", "balance_sheet", "growth"]
        labels = ["Valuation", "Quality", "Balance sheet", "Growth"]
        vals = [float(scores.get(k, 0) or 0) for k in keys]
        total = float(scores.get("fundamental_score", sum(vals)) or 0)

        fig, ax = plt.subplots(figsize=(10, 5))
        colors = ["#2ecc71" if v >= 15 else "#f39c12" if v >= 10 else "#e74c3c" for v in vals]
        ax.bar(labels, vals, color=colors, alpha=0.85, edgecolor="black", linewidth=0.5)
        ax.set_ylim(0, 27)
        ax.axhline(12.5, color="gray", linestyle="--", alpha=0.5, label="Mid (12.5/25)")
        ax.set_ylabel("Pillar score (0–25)", fontsize=12)
        sym = fundamental_data.get("yahoo_symbol") or fundamental_data.get("symbol", "")
        ax.set_title(
            f"Fundamental screening — {sym}  (total {total:.1f} / 100)",
            fontsize=14,
            fontweight="bold",
        )
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3, axis="y")

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            logger.info(f"Fundamental chart saved to {save_path}")
        else:
            plt.show()
        plt.close()
