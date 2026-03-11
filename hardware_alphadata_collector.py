"""
Data collection module for Hardware Alpha.
Collects market data from multiple sources with robust error handling.
"""

import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import time
import json

# Internal imports
from hardware_alpha.config import config
from hardware_alpha.firebase_client import FirebaseClient

logger = logging.getLogger(__name__)

class DataCollector:
    """Orchestrates data collection from multiple sources"""
    
    def __init__(self, firebase_client: Optional[FirebaseClient] = None):
        self.firebase_client = firebase_client
        self.session = None
        self.collection_stats = {
            'successful_sources': 0,
            'failed_sources': 0,
            'total_items_collected': 0,
            'last_collection_time': None
        }
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'HardwareAlpha/1.0 (+https://github.com/evolution-ecosystem)'}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            
    async def collect_all_sources(self) -> Dict[str, List[Dict]]:
        """
        Collect data from all configured sources asynchronously
        
        Returns:
            Dictionary with source names as keys and lists of items as values
        """
        logger.info("Starting data collection from all sources")
        
        # Define collection tasks
        collection_tasks = [
            self._collect_apple_refurbished(),
            self._collect_ebay_listings(),
            self._collect_sec_filings(),
            # Note: Reddit collection requires OAuth2 - will implement if credentials provided
        ]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*collection_tasks, return_exceptions=True)
        
        # Process results
        collected_data = {}
        for i, result in enumerate(results):
            task_name = collection_tasks[i].__name__.replace('_collect_', '')
            
            if isinstance(result, Exception):
                logger.error(f"Failed to collect from {task_name}: {str(result)}")
                self.collection_stats['failed_sources'] += 1
                collected_data[task_name] = []
            else:
                logger.info(f"Collected {len(result)} items from {task_name}")
                self.collection_stats['successful_sources'] += 1
                self.collection_stats['total_items_collected'] += len(result)
                collected_data[task_name] = result
        
        self.collection_stats['last_collection_time'] = datetime.utcnow()
        
        # Store collection stats in Firebase
        if self.firebase_client:
            try:
                await self.firebase_client.store_collection_stats(self.collection_stats)
            except Exception as e:
                logger.error(f"Failed to store collection stats: {str(e)}")
        
        return collected_data
    
    async def _collect_apple_refurbished(self) -> List[Dict]:
        """Collect refurbished Mac listings from Apple's RSS feed"""
        items = []
        
        try:
            async with self.session.get(config.api.apple_refurbished_rss) as response:
                if response.status == 200:
                    xml_content = await response.text()
                    
                    # Parse XML
                    root = ET.fromstring(xml_content)
                    
                    # Namespace handling
                    ns = {'atom': 'http://www.w3.org/2005/Atom'}
                    
                    for entry in root.findall('atom:entry', ns):
                        try:
                            title = entry.find('atom:title', ns).text
                            link = entry.find('atom:link', ns).attrib.get('href', '')
                            price_elem = entry.find('.//s:price', {'s': 'http://www.w3.org/2005/Atom'})
                            price = float(price_elem.text) if price_elem is not None else 0.0
                            
                            # Check if it's a Mac Studio M2 Ultra
                            if any(model in title for model in config.target.target_models):
                                item = {
                                    'source': 'apple_refurbished',
                                    'title': title,
                                    'price': price,
                                    'url': link,
                                    'condition': 'refurbished',
                                    'seller': 'Apple',
                                    'timestamp': datetime.utcnow().isoformat(),
                                    'confidence_score': 0.95  # Apple refurbished is highly reliable
                                }
                                items.append(item)
                                
                        except (AttributeError, ValueError) as e:
                            logger.debug(f"Failed to parse Apple RSS item: {str(e)}")
                            continue
                            
                else:
                    logger.warning(f"Apple RSS returned status {response.status}")
                    
        except (aiohttp.ClientError, asyncio.TimeoutError, ET.ParseError) as e:
            logger.error(f"Failed to fetch Apple refurbished data: {str(e)}")
            raise
        
        return items
    
    async def _collect_ebay_listings(self) -> List[Dict]:
        """Collect listings from eBay API (requires credentials)"""
        items = []
        
        # Check if eBay API credentials are available
        if not all([config.api.ebay_app_id, config.api.ebay_cert_id, config.api.ebay_dev_id]):
            logger.warning("eBay API credentials not configured - skipping eBay collection")
            
            # Request eBay API access if this is critical
            if config.firebase:
                request_data = {
                    'service': 'eBay API',
                    'reason': 'Critical for marketplace price discovery and liquidity assessment',
                    'alternatives_attempted': ['Apple Refurbished RSS', 'Manual monitoring'],
                    'generated_account': {
                        'email': f'hardware-alpha-{int(time.time())}@evolution.ecosystem',
                        'password': f'HaRdWaRe{int(time.time() % 10000)}!'
                    },
                    'timestamp': datetime.utcnow().isoformat(),
                    'priority': 'HIGH'
                }
                
                # Log the access request
                logger.info("eBay API access required for complete market coverage")
                # Note: In production, this would trigger a Telegram alert to human operator
                
            return items
        
        try:
            # TODO: Implement eBay API OAuth2 authentication and search
            # This is a placeholder for the actual eBay API implementation
            logger.info("eBay API credentials available but not yet implemented")
            
        except Exception as e:
            logger.error(f"eBay API collection failed: {str(e)}")
            raise
        
        return items
    
    async def _collect_sec_filings(self) -> List[Dict]:
        """Collect relevant SEC filings for Apple Inc. (ticker: AAPL)"""
        items = []
        
        try:
            # Apple's CIK number is 320193
            cik = '0000320193'
            
            # Get recent filings
            filings_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            
            async with self.session.get(filings_url, headers={
                'User-Agent': 'HardwareAlpha/1.0 contact@evolution.ecosystem',
                'Accept': 'application/json'
            }) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract recent 10-Q and 10-K filings
                    recent_filings = data.get('filings', {}).get('recent', {})
                    
                    if recent_filings:
                        # Get the indices for form type, filing date, and primary document
                        forms = recent_filings.get('form', [])
                        filing_dates = recent_filings.get('filingDate', [])
                        primary_docs = recent_filings.get('primaryDocument', [])
                        accession_numbers = recent_filings.get('accessionNumber', [])
                        
                        for i, form in enumerate(forms):
                            if form in ['10-Q', '10-K', '8-K'] and i < len(filing_dates):
                                # Check if filing is recent (last 90 days)
                                filing_date = datetime.strptime(filing_dates[i], '%Y-%m-%d')
                                if datetime.utcnow() - filing_date < timedelta(days=90):
                                    item = {
                                        'source': 'sec_edgar',
                                        'form_type': form,
                                        'filing_date': filing_date.isoformat(),
                                        'accession_number': accession_numbers[i] if i < len(accession_numbers) else '',
                                        'primary_document': primary_docs[i] if i < len(primary_docs) else '',
                                        'relevance_score': self._calculate_sec_relevance(form),
                                        'timestamp': datetime.utcnow().isoformat()
                                    }
                                    items