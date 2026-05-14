"""
Web scraping service with proxy rotation and rate limiting.

This service provides robust web scraping capabilities with proxy rotation,
user agent rotation, rate limiting, and compliance with robots.txt.
"""

import asyncio
import logging
import random
import time
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, robots
from urllib.robotparser import RobotFileParser
import json
import re

import httpx
import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from ..core.config import get_settings
from ..schemas.prospect_research import DataSource

logger = logging.getLogger(__name__)
settings = get_settings()


class ProxyRotator:
    """Manages proxy rotation for web scraping."""
    
    def __init__(self, proxy_list: List[str]):
        self.proxy_list = proxy_list
        self.current_index = 0
        self.failed_proxies = set()
        self.proxy_stats = {proxy: {"requests": 0, "failures": 0} for proxy in proxy_list}
    
    def get_next_proxy(self) -> Optional[str]:
        """Get the next available proxy."""
        if not self.proxy_list:
            return None
        
        # Filter out failed proxies
        available_proxies = [
            proxy for proxy in self.proxy_list 
            if proxy not in self.failed_proxies
        ]
        
        if not available_proxies:
            # Reset failed proxies if all are failed
            self.failed_proxies.clear()
            available_proxies = self.proxy_list
        
        # Round-robin selection
        proxy = available_proxies[self.current_index % len(available_proxies)]
        self.current_index += 1
        
        return proxy
    
    def mark_proxy_failed(self, proxy: str):
        """Mark a proxy as failed."""
        self.failed_proxies.add(proxy)
        self.proxy_stats[proxy]["failures"] += 1
        
        logger.warning(f"Marked proxy as failed: {proxy}")
    
    def record_success(self, proxy: str):
        """Record a successful request for a proxy."""
        self.proxy_stats[proxy]["requests"] += 1


class UserAgentRotator:
    """Manages user agent rotation for web scraping."""
    
    def __init__(self):
        self.user_agents = [
            # Chrome on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            
            # Chrome on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            
            # Firefox on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0",
            
            # Firefox on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0",
            
            # Safari on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            
            # Edge on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        ]
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent string."""
        return random.choice(self.user_agents)


class RobotsTxtChecker:
    """Checks robots.txt compliance for web scraping."""
    
    def __init__(self):
        self.robots_cache = {}
        self.cache_ttl = 3600  # 1 hour
    
    async def can_fetch(self, url: str, user_agent: str = "*") -> bool:
        """
        Check if URL can be fetched according to robots.txt.
        
        Args:
            url: URL to check
            user_agent: User agent string
            
        Returns:
            True if URL can be fetched, False otherwise
        """
        try:
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            robots_url = urljoin(base_url, "/robots.txt")
            
            # Check cache
            cache_key = base_url
            if cache_key in self.robots_cache:
                robots_data, timestamp = self.robots_cache[cache_key]
                if time.time() - timestamp < self.cache_ttl:
                    return robots_data.can_fetch(user_agent, url)
            
            # Fetch robots.txt
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(robots_url, timeout=10)
                    if response.status_code == 200:
                        rp = RobotFileParser()
                        rp.set_url(robots_url)
                        rp.read()
                        
                        # Cache the result
                        self.robots_cache[cache_key] = (rp, time.time())
                        
                        return rp.can_fetch(user_agent, url)
                    else:
                        # If robots.txt doesn't exist, assume allowed
                        return True
                except Exception:
                    # If we can't fetch robots.txt, assume allowed
                    return True
        
        except Exception as e:
            logger.warning(f"Error checking robots.txt for {url}: {e}")
            return True  # Default to allowed if check fails


class WebScrapingService:
    """
    Comprehensive web scraping service with proxy rotation and compliance.
    
    Provides both HTTP-based scraping and JavaScript-enabled scraping
    with Selenium for dynamic content.
    """
    
    def __init__(self):
        self.proxy_rotator = ProxyRotator(self._load_proxy_list())
        self.user_agent_rotator = UserAgentRotator()
        self.robots_checker = RobotsTxtChecker()
        
        # Rate limiting
        self.request_delays = {}
        self.min_delay = 1.0  # Minimum delay between requests to same domain
        self.max_concurrent = 3  # Maximum concurrent requests
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # Session management
        self.http_client = None
        self.selenium_driver = None
    
    async def scrape_url(self, 
                        url: str, 
                        method: str = "http",
                        respect_robots: bool = True,
                        custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Scrape a single URL with the specified method.
        
        Args:
            url: URL to scrape
            method: Scraping method ("http" or "selenium")
            respect_robots: Whether to respect robots.txt
            custom_headers: Custom headers to include
            
        Returns:
            Dictionary containing scraped data and metadata
        """
        start_time = time.time()
        
        try:
            # Check robots.txt compliance
            if respect_robots:
                user_agent = self.user_agent_rotator.get_random_user_agent()
                if not await self.robots_checker.can_fetch(url, user_agent):
                    return {
                        "url": url,
                        "success": False,
                        "error": "Blocked by robots.txt",
                        "data": None,
                        "metadata": {
                            "method": method,
                            "duration": time.time() - start_time,
                            "robots_blocked": True
                        }
                    }
            
            # Apply rate limiting
            await self._apply_rate_limit(url)
            
            # Use semaphore to limit concurrent requests
            async with self.semaphore:
                if method == "http":
                    result = await self._scrape_with_http(url, custom_headers)
                elif method == "selenium":
                    result = await self._scrape_with_selenium(url)
                else:
                    raise ValueError(f"Invalid scraping method: {method}")
            
            result["metadata"]["duration"] = time.time() - start_time
            return result
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {
                "url": url,
                "success": False,
                "error": str(e),
                "data": None,
                "metadata": {
                    "method": method,
                    "duration": time.time() - start_time,
                    "exception": type(e).__name__
                }
            }
    
    async def scrape_multiple_urls(self,
                                 urls: List[str],
                                 method: str = "http",
                                 max_concurrent: int = 3) -> List[Dict[str, Any]]:
        """
        Scrape multiple URLs concurrently.
        
        Args:
            urls: List of URLs to scrape
            method: Scraping method
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of scraping results
        """
        # Update semaphore limit
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Create scraping tasks
        tasks = [
            self.scrape_url(url, method=method)
            for url in urls
        ]
        
        # Execute tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "url": urls[i],
                    "success": False,
                    "error": str(result),
                    "data": None,
                    "metadata": {"exception": type(result).__name__}
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def extract_company_data(self, url: str) -> Dict[str, Any]:
        """
        Extract company-specific data from a website.
        
        Args:
            url: Company website URL
            
        Returns:
            Extracted company data
        """
        result = await self.scrape_url(url, method="http")
        
        if not result["success"]:
            return result
        
        soup = result["data"]["soup"]
        
        # Extract company information
        company_data = {
            "company_name": self._extract_company_name(soup, url),
            "description": self._extract_description(soup),
            "contact_info": self._extract_contact_info(soup),
            "social_media": self._extract_social_media(soup),
            "technology_stack": self._extract_technology_stack(result["data"]["html"]),
            "team_info": self._extract_team_info(soup),
            "news_updates": self._extract_news_updates(soup),
            "meta_data": self._extract_meta_data(soup)
        }
        
        result["data"]["company_data"] = company_data
        return result
    
    async def search_company_mentions(self, company_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for company mentions across various sources.
        
        Args:
            company_name: Name of the company to search for
            limit: Maximum number of results
            
        Returns:
            List of company mentions with metadata
        """
        search_sources = [
            f"https://www.google.com/search?q=\"{company_name}\" news",
            f"https://news.google.com/search?q={company_name}",
            f"https://www.crunchbase.com/search/organizations/{company_name}",
        ]
        
        mentions = []
        
        for source_url in search_sources:
            try:
                result = await self.scrape_url(source_url, method="http")
                if result["success"]:
                    # Extract mentions from search results
                    soup = result["data"]["soup"]
                    extracted_mentions = self._extract_search_results(soup, company_name)
                    mentions.extend(extracted_mentions)
                    
                    if len(mentions) >= limit:
                        break
                        
            except Exception as e:
                logger.warning(f"Error searching {source_url}: {e}")
                continue
        
        return mentions[:limit]
    
    async def _scrape_with_http(self, url: str, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Scrape URL using HTTP client."""
        if not self.http_client:
            await self._initialize_http_client()
        
        headers = {
            "User-Agent": self.user_agent_rotator.get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        if custom_headers:
            headers.update(custom_headers)
        
        # Get proxy
        proxy = self.proxy_rotator.get_next_proxy()
        proxies = {"http://": proxy, "https://": proxy} if proxy else None
        
        try:
            response = await self.http_client.get(
                url,
                headers=headers,
                proxies=proxies,
                timeout=30,
                follow_redirects=True
            )
            
            if proxy:
                self.proxy_rotator.record_success(proxy)
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            return {
                "url": url,
                "success": True,
                "error": None,
                "data": {
                    "html": response.text,
                    "soup": soup,
                    "status_code": response.status_code,
                    "headers": dict(response.headers)
                },
                "metadata": {
                    "method": "http",
                    "proxy_used": proxy,
                    "user_agent": headers["User-Agent"],
                    "content_length": len(response.text)
                }
            }
            
        except Exception as e:
            if proxy:
                self.proxy_rotator.mark_proxy_failed(proxy)
            raise e
    
    async def _scrape_with_selenium(self, url: str) -> Dict[str, Any]:
        """Scrape URL using Selenium for JavaScript-heavy sites."""
        if not self.selenium_driver:
            self._initialize_selenium_driver()
        
        try:
            self.selenium_driver.get(url)
            
            # Wait for page to load
            WebDriverWait(self.selenium_driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Get page source
            html = self.selenium_driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            return {
                "url": url,
                "success": True,
                "error": None,
                "data": {
                    "html": html,
                    "soup": soup,
                    "title": self.selenium_driver.title
                },
                "metadata": {
                    "method": "selenium",
                    "content_length": len(html)
                }
            }
            
        except TimeoutException:
            raise Exception("Page load timeout")
        except WebDriverException as e:
            raise Exception(f"Selenium error: {e}")
    
    async def _initialize_http_client(self):
        """Initialize HTTP client with proper configuration."""
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            follow_redirects=True
        )
    
    def _initialize_selenium_driver(self):
        """Initialize Selenium WebDriver."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(f"--user-agent={self.user_agent_rotator.get_random_user_agent()}")
        
        self.selenium_driver = webdriver.Chrome(options=chrome_options)
    
    async def _apply_rate_limit(self, url: str):
        """Apply rate limiting based on domain."""
        domain = urlparse(url).netloc
        
        if domain in self.request_delays:
            last_request = self.request_delays[domain]
            time_since_last = time.time() - last_request
            
            if time_since_last < self.min_delay:
                delay = self.min_delay - time_since_last
                await asyncio.sleep(delay)
        
        self.request_delays[domain] = time.time()
    
    def _load_proxy_list(self) -> List[str]:
        """Load proxy list from configuration or external source."""
        # In production, this would load from a proxy service
        # For now, return empty list to disable proxy rotation
        return []
    
    def _extract_company_name(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """Extract company name from webpage."""
        # Try various methods to extract company name
        selectors = [
            'meta[property="og:site_name"]',
            'meta[name="application-name"]',
            'title',
            'h1',
            '.company-name',
            '.brand-name'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    name = element.get('content', '').strip()
                else:
                    name = element.get_text().strip()
                
                if name and len(name) < 100:
                    return name
        
        # Fallback to domain name
        domain = urlparse(url).netloc
        return domain.replace('www.', '').split('.')[0].title()
    
    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract company description."""
        selectors = [
            'meta[name="description"]',
            'meta[property="og:description"]',
            '.company-description',
            '.about-text',
            'p'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    desc = element.get('content', '').strip()
                else:
                    desc = element.get_text().strip()
                
                if desc and 50 < len(desc) < 500:
                    return desc
        
        return None
    
    def _extract_contact_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract contact information."""
        contact_info = {}
        
        # Email patterns
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, soup.get_text())
        if emails:
            contact_info['email'] = emails[0]
        
        # Phone patterns
        phone_pattern = r'(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})'
        phones = re.findall(phone_pattern, soup.get_text())
        if phones:
            contact_info['phone'] = phones[0]
        
        return contact_info
    
    def _extract_social_media(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract social media links."""
        social_media = {}
        
        social_patterns = {
            'linkedin': r'linkedin\.com/company/([^/\s]+)',
            'twitter': r'twitter\.com/([^/\s]+)',
            'facebook': r'facebook\.com/([^/\s]+)',
            'instagram': r'instagram\.com/([^/\s]+)'
        }
        
        page_text = soup.get_text()
        
        for platform, pattern in social_patterns.items():
            matches = re.findall(pattern, page_text)
            if matches:
                social_media[platform] = f"https://{platform}.com/{matches[0]}"
        
        return social_media
    
    def _extract_technology_stack(self, html: str) -> List[str]:
        """Extract technology stack information."""
        technologies = []
        
        # Common technology patterns
        tech_patterns = {
            'react': r'react',
            'angular': r'angular',
            'vue': r'vue\.js',
            'jquery': r'jquery',
            'bootstrap': r'bootstrap',
            'wordpress': r'wp-content',
            'shopify': r'shopify',
            'google_analytics': r'google-analytics|gtag',
            'facebook_pixel': r'facebook\.net/tr'
        }
        
        html_lower = html.lower()
        
        for tech, pattern in tech_patterns.items():
            if re.search(pattern, html_lower):
                technologies.append(tech)
        
        return technologies
    
    def _extract_team_info(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract team/leadership information."""
        team_info = []
        
        # Look for team sections
        team_sections = soup.find_all(['div', 'section'], class_=re.compile(r'team|about|leadership'))
        
        for section in team_sections:
            # Extract names and titles
            names = section.find_all(['h3', 'h4', 'h5'])
            for name_elem in names:
                name = name_elem.get_text().strip()
                if name and len(name.split()) <= 4:  # Likely a person's name
                    # Look for title in nearby elements
                    title_elem = name_elem.find_next(['p', 'span', 'div'])
                    title = title_elem.get_text().strip() if title_elem else ""
                    
                    team_info.append({
                        'name': name,
                        'title': title
                    })
        
        return team_info[:5]  # Limit to 5 team members
    
    def _extract_news_updates(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract news and updates."""
        news_updates = []
        
        # Look for news sections
        news_sections = soup.find_all(['div', 'section'], class_=re.compile(r'news|blog|updates'))
        
        for section in news_sections:
            articles = section.find_all(['article', 'div'], limit=3)
            for article in articles:
                title_elem = article.find(['h2', 'h3', 'h4'])
                if title_elem:
                    title = title_elem.get_text().strip()
                    link_elem = article.find('a')
                    link = link_elem.get('href') if link_elem else ""
                    
                    news_updates.append({
                        'title': title,
                        'link': link
                    })
        
        return news_updates
    
    def _extract_meta_data(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract meta data from webpage."""
        meta_data = {}
        
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            name = tag.get('name') or tag.get('property')
            content = tag.get('content')
            
            if name and content:
                meta_data[name] = content
        
        return meta_data
    
    def _extract_search_results(self, soup: BeautifulSoup, company_name: str) -> List[Dict[str, Any]]:
        """Extract search results mentioning the company."""
        results = []
        
        # This would be implemented based on specific search engine structures
        # For now, return empty list
        return results
    
    async def cleanup(self):
        """Clean up resources."""
        if self.http_client:
            await self.http_client.aclose()
        
        if self.selenium_driver:
            self.selenium_driver.quit()


# Factory function
def create_web_scraping_service() -> WebScrapingService:
    """Create a configured web scraping service."""
    return WebScrapingService()