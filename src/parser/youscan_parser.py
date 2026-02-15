"""YouScan.io parser for BCL Parser."""
import re
import time
import asyncio
from datetime import date, datetime
from typing import List, Optional, Dict
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from ..database.models import ParsedEntry
from ..config import detect_table_from_link, detect_table_from_entry, detect_social_network_from_link, SOCIAL_NETWORK_OPTIONS, TAG_OPTIONS


class YouScanParser:
    """Parser for YouScan.io website."""
    
    BASE_URL = "https://app.youscan.io"
    MENTIONS_URL = "https://app.youscan.io/themes/347025/mentions"
    
    def __init__(self, email: str, password: str, headless: bool = True, use_persistent_context: bool = False):
        """Initialize parser with credentials.
        
        Args:
            email: YouScan.io email
            password: YouScan.io password
            headless: Run browser in headless mode
            use_persistent_context: Use persistent browser context (saves cookies/session)
        """
        self.email = email
        self.password = password
        self.headless = headless
        self.use_persistent_context = use_persistent_context
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    async def start_async(self):
        """Start browser and login (async version for use in threads)."""
        self.playwright = await async_playwright().start()
        
        # Launch browser with stealth settings to avoid detection
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',  # Hide automation
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        
        # Create context with realistic browser settings
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
            'permissions': ['geolocation'],
            'extra_http_headers': {
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        }
        
        # Use persistent context if requested (saves cookies/session)
        if self.use_persistent_context:
            from pathlib import Path
            user_data_dir = Path.home() / '.bcl-parser' / 'browser_data'
            user_data_dir.mkdir(parents=True, exist_ok=True)
            self.context = await self.playwright.chromium.launch_persistent_context(
                str(user_data_dir),
                headless=self.headless,
                **context_options,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ]
            )
            # Get the first page from persistent context
            if self.context.pages and len(self.context.pages) > 0:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()
        else:
            self.context = await self.browser.new_context(**context_options)
            self.page = await self.context.new_page()
        
        # Verify page is initialized
        if self.page is None:
            raise ValueError("Failed to initialize page object")
        
        # Remove webdriver property to avoid detection (only if not persistent context)
        if not self.use_persistent_context:
            await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)
        
        await self._login_async()
    
    async def close_async(self):
        """Close browser (async version)."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    def close(self):
        """Close browser (sync wrapper for compatibility)."""
        if self.context or self.browser or self.playwright:
            # Run async close in event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, create task
                    asyncio.create_task(self.close_async())
                else:
                    loop.run_until_complete(self.close_async())
            except:
                pass
    
    async def _login_async(self):
        """Login to YouScan.io (async version)."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Ensure page is initialized
            if self.page is None:
                raise ValueError("Page not initialized - browser may not have started correctly")
            
            # First, check if already logged in
            # page.url is a property, not a method, so no await needed
            try:
                current_url = str(self.page.url)  # Explicitly convert to string
            except Exception as e:
                logger.error(f"Error accessing page.url: {e}, page type: {type(self.page)}")
                print(f"[ERROR] Error accessing page.url: {e}, page type: {type(self.page)}")
                raise
            
            logger.info(f"Checking current page: {current_url}")
            print(f"[INFO] Checking current page: {current_url}")
            
            # Navigate to login page
            logger.info(f"Navigating to {self.BASE_URL}/login")
            print(f"[INFO] Navigating to {self.BASE_URL}/login")
            # Use 'domcontentloaded' instead of 'load' - faster and more reliable
            # 'load' waits for all resources, which can timeout on slow networks
            try:
                await self.page.goto(f"{self.BASE_URL}/login", wait_until='domcontentloaded', timeout=60000)
            except Exception as goto_error:
                # If timeout, try with even less strict wait or check if page loaded anyway
                logger.warning(f"Initial navigation timed out: {goto_error}, checking current URL")
                print(f"[WARNING] Initial navigation timed out, checking current URL")
                current_url = self.page.url
                logger.info(f"Current URL after timeout: {current_url}")
                print(f"[INFO] Current URL after timeout: {current_url}")
                
                # If we're already on a valid page (themes, dashboard), continue
                if '/themes' in current_url or '/dashboard' in current_url or current_url != 'about:blank':
                    logger.info("Page loaded despite timeout, continuing")
                    print("[INFO] Page loaded despite timeout, continuing")
                else:
                    # Try one more time with 'commit' wait (least strict)
                    try:
                        logger.info("Retrying navigation with 'commit' wait")
                        print("[INFO] Retrying navigation with 'commit' wait")
                        await self.page.goto(f"{self.BASE_URL}/login", wait_until='commit', timeout=30000)
                        await asyncio.sleep(2)  # Wait for page to render
                    except Exception as retry_error:
                        logger.error(f"Navigation failed even with retry: {retry_error}")
                        print(f"[ERROR] Navigation failed even with retry: {retry_error}")
                        raise
            
            # Check current URL - might already be logged in
            current_url = self.page.url
            logger.info(f"Current URL after navigation: {current_url}")
            print(f"[INFO] Current URL after navigation: {current_url}")
            
            # Check if already logged in (redirected to themes or dashboard)
            if '/themes' in current_url or '/dashboard' in current_url or current_url == f"{self.BASE_URL}/":
                logger.info("Already logged in! Skipping login form")
                print("[INFO] Already logged in! Skipping login form")
                # Make sure we're on themes page
                if '/themes' not in current_url:
                    await self.page.goto(f"{self.BASE_URL}/themes", wait_until='load', timeout=30000)
                    await asyncio.sleep(2)
                # Skip login and go directly to navigation
                logger.info("Navigating to Big City Lab theme mentions")
                print("[INFO] Navigating to Big City Lab theme mentions")
                await self._navigate_to_big_city_lab_async()
                return
            
            if 'unsupported' in current_url.lower():
                error_msg = (
                    "YouScan.io detected automated browser and redirected to unsupported page.\n\n"
                    "The site is blocking automated browsers. Possible solutions:\n"
                    "1. The anti-bot protection may require manual login first\n"
                    "2. Try using a persistent browser context (saves cookies)\n"
                    "3. You may need to manually log in once, then the app can use saved session"
                )
                logger.error(error_msg)
                print(f"[ERROR] {error_msg}")
                
                # Take screenshot for debugging
                try:
                    screenshot_path = 'unsupported_page_debug.png'
                    await self.page.screenshot(path=screenshot_path)
                    print(f"[DEBUG] Screenshot saved to {screenshot_path}")
                except:
                    pass
                
                raise ValueError("Browser detected as automated - redirected to unsupported page")
            
            logger.info("Page loaded, waiting for login form")
            print("[INFO] Page loaded, waiting for login form")
            
            # Wait a bit for page to render (redirect might happen asynchronously)
            await asyncio.sleep(3)  # Increased wait time
            
            # Check URL again - redirect might have happened during wait
            current_url_after_wait = self.page.url
            logger.info(f"Current URL after wait: {current_url_after_wait}")
            print(f"[INFO] Current URL after wait: {current_url_after_wait}")
            
            # Check if already logged in (redirected to themes or dashboard)
            if '/themes' in current_url_after_wait or '/dashboard' in current_url_after_wait or current_url_after_wait == f"{self.BASE_URL}/":
                logger.info("Already logged in! Redirected to themes page. Skipping login form")
                print("[INFO] Already logged in! Redirected to themes page. Skipping login form")
                # Make sure we're on themes page
                if '/themes' not in current_url_after_wait:
                    await self.page.goto(f"{self.BASE_URL}/themes", wait_until='load', timeout=30000)
                    await asyncio.sleep(2)
                # Navigate to Big City Lab theme mentions page
                logger.info("Navigating to Big City Lab theme mentions")
                print("[INFO] Navigating to Big City Lab theme mentions")
                await self._navigate_to_big_city_lab_async()
                return  # Skip login, already authenticated
            
            # Based on actual HTML: email input has name="username"
            email_selectors = [
                'input[name="username"]',  # Correct selector based on actual HTML
                'input[type="email"]',
                'input[name="email"]',
            ]
            
            email_input = None
            for selector in email_selectors:
                try:
                    # Check URL before each selector attempt - redirect might happen during wait
                    check_url = self.page.url
                    if '/themes' in check_url or '/dashboard' in check_url:
                        logger.info(f"Redirected to {check_url} while waiting for selector - already logged in!")
                        print(f"[INFO] Redirected to {check_url} while waiting for selector - already logged in!")
                        await self._navigate_to_big_city_lab_async()
                        return
                    
                    logger.debug(f"Trying email selector: {selector}")
                    print(f"[DEBUG] Trying email selector: {selector}")
                    email_input = await self.page.wait_for_selector(selector, timeout=5000, state='visible')
                    if email_input:
                        logger.info(f"Found email input with selector: {selector}")
                        print(f"[INFO] Found email input with selector: {selector}")
                        break
                except Exception as e:
                    # Check URL after selector timeout - might have redirected
                    check_url = self.page.url
                    if '/themes' in check_url or '/dashboard' in check_url:
                        logger.info(f"Redirected to {check_url} during selector wait - already logged in!")
                        print(f"[INFO] Redirected to {check_url} during selector wait - already logged in!")
                        await self._navigate_to_big_city_lab_async()
                        return
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            if not email_input:
                # Check URL one more time - might have redirected while waiting
                final_url = self.page.url
                logger.info(f"Final URL check: {final_url}")
                print(f"[INFO] Final URL check: {final_url}")
                
                if '/themes' in final_url or '/dashboard' in final_url:
                    logger.info("Redirected to themes during wait - already logged in!")
                    print("[INFO] Redirected to themes during wait - already logged in!")
                    await self._navigate_to_big_city_lab_async()
                    return
                
                # Take screenshot for debugging
                screenshot_path = 'login_page_debug.png'
                await self.page.screenshot(path=screenshot_path)
                page_title = await self.page.title()
                logger.error(f"Could not find email input. Screenshot saved to {screenshot_path}")
                print(f"[ERROR] Could not find email input. Screenshot saved to {screenshot_path}")
                print(f"[DEBUG] Current URL: {self.page.url}")
                print(f"[DEBUG] Page title: {page_title}")
                raise ValueError("Could not find email input field on login page")
            
            # Password input has name="password" - this should work
            password_selectors = [
                'input[name="password"]',  # Correct selector based on actual HTML
                'input[type="password"]',
            ]
            
            password_input = None
            for selector in password_selectors:
                try:
                    logger.debug(f"Trying password selector: {selector}")
                    print(f"[DEBUG] Trying password selector: {selector}")
                    password_input = await self.page.wait_for_selector(selector, timeout=5000, state='visible')
                    if password_input:
                        logger.info(f"Found password input with selector: {selector}")
                        print(f"[INFO] Found password input with selector: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            if not password_input:
                raise ValueError("Could not find password input field on login page")
            
            # Double-check we're still on login page before filling (redirect might have happened)
            final_check_url = self.page.url
            if '/themes' in final_check_url or '/dashboard' in final_check_url or '/login' not in final_check_url:
                logger.info(f"Redirected to {final_check_url} before filling form - already logged in!")
                print(f"[INFO] Redirected to {final_check_url} before filling form - already logged in!")
                await self._navigate_to_big_city_lab_async()
                return
            
            # Verify elements are still attached to DOM before filling
            try:
                # Check if email input is still attached
                is_attached = await email_input.evaluate('el => el.isConnected')
                if not is_attached:
                    # Re-query the element
                    email_input = await self.page.query_selector('input[name="username"]')
                    if not email_input:
                        raise ValueError("Email input was detached from DOM")
                
                # Check if password input is still attached
                is_attached = await password_input.evaluate('el => el.isConnected')
                if not is_attached:
                    # Re-query the element
                    password_input = await self.page.query_selector('input[name="password"]')
                    if not password_input:
                        raise ValueError("Password input was detached from DOM")
            except Exception as e:
                # Check URL again - might have redirected
                check_url = self.page.url
                if '/themes' in check_url or '/dashboard' in check_url:
                    logger.info(f"Redirected to {check_url} during element check - already logged in!")
                    print(f"[INFO] Redirected to {check_url} during element check - already logged in!")
                    await self._navigate_to_big_city_lab_async()
                    return
                raise ValueError(f"Elements detached from DOM: {e}")
            
            # Fill credentials
            logger.info("Filling email")
            print("[INFO] Filling email")
            try:
                await email_input.fill(self.email)
                await asyncio.sleep(0.5)
            except Exception as e:
                # Check if redirected during fill
                check_url = self.page.url
                if '/themes' in check_url or '/dashboard' in check_url:
                    logger.info(f"Redirected to {check_url} during email fill - already logged in!")
                    print(f"[INFO] Redirected to {check_url} during email fill - already logged in!")
                    await self._navigate_to_big_city_lab_async()
                    return
                raise ValueError(f"Failed to fill email: {e}")
            
            logger.info("Filling password")
            print("[INFO] Filling password")
            try:
                await password_input.fill(self.password)
                await asyncio.sleep(0.5)
            except Exception as e:
                # Check if redirected during fill
                check_url = self.page.url
                if '/themes' in check_url or '/dashboard' in check_url:
                    logger.info(f"Redirected to {check_url} during password fill - already logged in!")
                    print(f"[INFO] Redirected to {check_url} during password fill - already logged in!")
                    await self._navigate_to_big_city_lab_async()
                    return
                raise ValueError(f"Failed to fill password: {e}")
            
            # Submit form - button contains text "Увійти"
            logger.info("Looking for submit button")
            print("[INFO] Looking for submit button")
            submit_selectors = [
                'button:has-text("Увійти")',  # Ukrainian "Login" - correct based on HTML
                'button:has-text("Войти")',   # Russian "Login"
                'button:has-text("Login")',    # English
                'button[type="submit"]',
                'button.FF3v4g9p2DiF4nP4L3yR',  # Specific class from HTML (may change)
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = await self.page.query_selector(selector)
                    if submit_button:
                        logger.info(f"Found submit button with selector: {selector}")
                        print(f"[INFO] Found submit button with selector: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"Submit button selector {selector} failed: {e}")
                    continue
            
            if submit_button:
                logger.info("Clicking submit button")
                print("[INFO] Clicking submit button")
                await submit_button.click()
            else:
                # Try pressing Enter
                logger.info("No submit button found, pressing Enter")
                print("[INFO] No submit button found, pressing Enter")
                await password_input.press('Enter')
            
            # Wait for navigation to dashboard
            logger.info("Waiting for login to complete...")
            print("[INFO] Waiting for login to complete...")
            try:
                await self.page.wait_for_url('**/themes**', timeout=30000)
                logger.info("Login successful, navigated to themes page")
                print("[INFO] Login successful, navigated to themes page")
            except:
                # Check if we're logged in by looking for dashboard elements
                logger.warning("URL didn't change, checking if login was successful")
                print("[WARNING] URL didn't change, checking if login was successful")
                current_url = self.page.url
                logger.info(f"Current URL: {current_url}")
                print(f"[INFO] Current URL: {current_url}")
                
                # If we're still on login page, login might have failed
                if '/login' in current_url:
                    raise ValueError("Login failed - still on login page")
            
            await asyncio.sleep(2)  # Additional wait for page to fully load
            
            # Navigate to Big City Lab theme mentions page
            logger.info("Navigating to Big City Lab theme mentions")
            print("[INFO] Navigating to Big City Lab theme mentions")
            await self._navigate_to_big_city_lab_async()
            
        except Exception as e:
            logger.exception("Login error")
            print(f"[ERROR] Login error: {str(e)}")
            # Take screenshot for debugging
            try:
                screenshot_path = 'login_error_debug.png'
                await self.page.screenshot(path=screenshot_path)
                print(f"[DEBUG] Screenshot saved to {screenshot_path}")
            except:
                pass
            raise
    
    async def _navigate_to_big_city_lab_async(self):
        """Navigate to Big City Lab theme mentions page (async version)."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # First, make sure we're on the themes page
            current_url = self.page.url
            logger.info(f"Current URL before navigation: {current_url}")
            print(f"[INFO] Current URL before navigation: {current_url}")
            
            if '/themes' not in current_url:
                logger.info("Not on themes page, navigating to themes")
                print("[INFO] Not on themes page, navigating to themes")
                await self.page.goto(f"{self.BASE_URL}/themes", wait_until='load', timeout=30000)
                await asyncio.sleep(3)
            
            # Look for Big City Lab theme - try multiple strategies
            logger.info("Looking for Big City Lab theme")
            print("[INFO] Looking for Big City Lab theme")
            
            # Strategy 1: Use Playwright's get_by_text (most reliable)
            theme_clicked = False
            try:
                logger.debug("Trying Playwright get_by_text('Big City Lab')")
                print("[DEBUG] Trying Playwright get_by_text('Big City Lab')")
                theme_locator = self.page.get_by_text("Big City Lab", exact=True).first
                if await theme_locator.is_visible(timeout=5000):
                    logger.info("Found Big City Lab using get_by_text")
                    print("[INFO] Found Big City Lab using get_by_text")
                    await theme_locator.click()
                    theme_clicked = True
                    await asyncio.sleep(3)
                    
                    # After clicking, navigate directly to mentions page
                    logger.info("Navigating to mentions page after clicking theme")
                    print("[INFO] Navigating to mentions page after clicking theme")
                    await self.page.goto(self.MENTIONS_URL, wait_until='load', timeout=30000)
                    await asyncio.sleep(2)
            except Exception as e:
                logger.debug(f"get_by_text failed: {e}")
                print(f"[DEBUG] get_by_text failed: {e}")
            
            # Strategy 2: Try other selectors
            if not theme_clicked:
                theme_selectors = [
                    'text="Big City Lab"',
                    'a:has-text("Big City Lab")',
                    'div:has-text("Big City Lab")',
                    '[href*="347025"]',
                    'a[href*="/themes/347025"]',
                ]
                
                for selector in theme_selectors:
                    try:
                        logger.debug(f"Trying selector: {selector}")
                        print(f"[DEBUG] Trying selector: {selector}")
                        element = await self.page.wait_for_selector(selector, timeout=3000, state='visible')
                        if element:
                            logger.info(f"Found Big City Lab with selector: {selector}")
                            print(f"[INFO] Found Big City Lab with selector: {selector}")
                            
                            # Try to click it
                            try:
                                await element.click()
                                logger.info("Clicked on Big City Lab theme")
                                print("[INFO] Clicked on Big City Lab theme")
                                theme_clicked = True
                                await asyncio.sleep(3)
                                break
                            except Exception as click_error:
                                logger.debug(f"Click failed: {click_error}, trying parent or coordinates")
                                print(f"[DEBUG] Click failed, trying parent or coordinates")
                                # Try clicking parent
                                try:
                                    parent = await element.evaluate_handle('el => el.closest("a") || el.closest("div[role="button"]") || el.parentElement')
                                    if parent:
                                        await parent.click()
                                        theme_clicked = True
                                        await asyncio.sleep(3)
                                        break
                                except:
                                    # Try clicking by coordinates
                                    try:
                                        box = await element.bounding_box()
                                        if box:
                                            logger.info("Clicking by coordinates")
                                            print("[INFO] Clicking by coordinates")
                                            await self.page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                                            theme_clicked = True
                                            await asyncio.sleep(3)
                                            break
                                    except:
                                        continue
                    except Exception as e:
                        logger.debug(f"Selector {selector} failed: {e}")
                        continue
            
            # Strategy 2: If clicking didn't work, try direct navigation
            if not theme_clicked:
                logger.info("Could not click theme, trying direct navigation")
                print("[INFO] Could not click theme, trying direct navigation")
                await self.page.goto(self.MENTIONS_URL, wait_until='load', timeout=30000)
                await asyncio.sleep(3)
            else:
                # After clicking, always navigate directly to mentions page
                current_url = self.page.url
                logger.info(f"URL after clicking theme: {current_url}")
                print(f"[INFO] URL after clicking theme: {current_url}")
                
                # Always navigate to mentions page after clicking theme
                logger.info("Navigating to mentions page")
                print("[INFO] Navigating to mentions page")
                await self.page.goto(self.MENTIONS_URL, wait_until='load', timeout=30000)
                await asyncio.sleep(2)
            
            # Verify we're on the mentions page
            final_url = self.page.url
            logger.info(f"Final URL: {final_url}")
            print(f"[INFO] Final URL: {final_url}")
            
            # If we're still on themes page (not mentions), navigate directly
            if '/themes' in final_url and '/mentions' not in final_url:
                logger.warning(f"Still on themes page ({final_url}), navigating directly to mentions")
                print(f"[WARNING] Still on themes page ({final_url}), navigating directly to mentions")
                await self.page.goto(self.MENTIONS_URL, wait_until='load', timeout=30000)
                await asyncio.sleep(2)
                final_url = self.page.url
                logger.info(f"Final URL after direct navigation: {final_url}")
                print(f"[INFO] Final URL after direct navigation: {final_url}")
            
            if '/mentions' in final_url:
                logger.info("Successfully navigated to Big City Lab mentions page")
                print("[INFO] Successfully navigated to Big City Lab mentions page")
            else:
                logger.warning(f"May not be on correct page. URL: {final_url}")
                print(f"[WARNING] May not be on correct page. URL: {final_url}")
                
        except Exception as e:
            logger.exception("Error navigating to Big City Lab")
            print(f"[ERROR] Error navigating to Big City Lab: {str(e)}")
            import traceback
            traceback.print_exc()
            # Try direct URL as fallback
            try:
                logger.info("Trying direct URL as fallback")
                print("[INFO] Trying direct URL as fallback")
                await self.page.goto(self.MENTIONS_URL, wait_until='load', timeout=30000)
                await asyncio.sleep(3)
            except Exception as fallback_error:
                logger.error(f"Fallback navigation also failed: {fallback_error}")
                print(f"[ERROR] Fallback navigation also failed: {fallback_error}")
                raise
    
    async def set_date_range_async(self, date_from: date, date_to: date):
        """Set date range in the date picker (async version)."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Only navigate if we're not already on the mentions page
        current_url = self.page.url
        if 'mentions' not in current_url.lower():
            logger.info(f"Navigating to mentions page for date range: {date_from} to {date_to}")
            print(f"[INFO] Navigating to mentions page for date range: {date_from} to {date_to}")
            await self.page.goto(self.MENTIONS_URL, wait_until='load', timeout=30000)
            await asyncio.sleep(2)
        else:
            logger.debug("Already on mentions page, skipping navigation")
            print(f"[DEBUG] Already on mentions page, skipping navigation")
        
        # Check if page is still open
        if self.page.is_closed():
            raise ValueError("Page was closed unexpectedly")
        
        # Find and click date picker
        logger.info("Looking for date picker...")
        print("[INFO] Looking for date picker...")
        
        # Step 1: Find the date picker input - try multiple strategies
        date_input = None
        
        # Strategy 1: Find by role="presentation" container - skip search input
        try:
            logger.info("Strategy 1: Looking for div[role='presentation']...")
            print("[INFO] Strategy 1: Looking for div[role='presentation']...")
            containers = await self.page.query_selector_all('div[role="presentation"]')
            logger.info(f"Found {len(containers)} elements with role='presentation'")
            print(f"[INFO] Found {len(containers)} elements with role='presentation'")
            
            for container in containers:
                try:
                    # Check if this container has an input inside
                    inp = await container.query_selector('input[type="text"]')
                    if inp:
                        # Check if it's visible
                        is_visible = await inp.is_visible()
                        if not is_visible:
                            continue
                        
                        # IMPORTANT: Skip the search input by checking placeholder
                        placeholder = await inp.get_attribute('placeholder') or ''
                        if placeholder == 'Пошук за текстом' or 'Пошук' in placeholder:
                            logger.debug("Skipping search input (placeholder='Пошук за текстом')")
                            print("[DEBUG] Skipping search input (placeholder='Пошук за текстом')")
                            continue
                        
                        # This should be the date picker input
                        value = await inp.get_attribute('value') or ''
                        logger.info(f"Found potential date input, value: {value[:50]}, placeholder: {placeholder[:50]}")
                        print(f"[INFO] Found potential date input, value: {value[:50]}, placeholder: {placeholder[:50]}")
                        date_input = inp
                        break
                except Exception as e:
                    logger.debug(f"Error checking container: {e}")
                    continue
        except Exception as e:
            logger.debug(f"Strategy 1 failed: {e}")
        
        # Strategy 2: Find input by looking for date pattern in value or nearby text - skip search input
        if not date_input:
            try:
                logger.info("Strategy 2: Looking for input with date pattern...")
                print("[INFO] Strategy 2: Looking for input with date pattern...")
                all_inputs = await self.page.query_selector_all('input[type="text"]')
                logger.info(f"Found {len(all_inputs)} text inputs on page")
                print(f"[INFO] Found {len(all_inputs)} text inputs on page")
                
                for inp in all_inputs:
                    try:
                        is_visible = await inp.is_visible()
                        if not is_visible:
                            continue
                        
                        # IMPORTANT: Skip the search input by checking placeholder
                        placeholder = await inp.get_attribute('placeholder') or ''
                        if placeholder == 'Пошук за текстом' or 'Пошук' in placeholder:
                            logger.debug("Skipping search input in Strategy 2")
                            continue
                        
                        # Get value and check parent
                        value = await inp.get_attribute('value') or ''
                        # Check if parent has role="presentation"
                        parent_has_role = await inp.evaluate('''el => {
                            const parent = el.closest('div[role="presentation"]');
                            return parent !== null;
                        }''')
                        
                        # Check if value looks like a date (contains digits and dashes/slashes)
                        looks_like_date = any(c.isdigit() for c in value) and ('-' in value or '/' in value or len(value) > 8)
                        
                        logger.debug(f"Input value: '{value[:50]}', placeholder: '{placeholder[:50]}', parent has role: {parent_has_role}, looks like date: {looks_like_date}")
                        
                        if parent_has_role and (looks_like_date or '202' in value or len(value) > 0):
                            date_input = inp
                            logger.info(f"Found potential date input with value: {value[:50]}")
                            print(f"[INFO] Found potential date input with value: {value[:50]}")
                            break
                    except Exception as e:
                        logger.debug(f"Error checking input: {e}")
                        continue
            except Exception as e:
                logger.debug(f"Strategy 2 failed: {e}")
        
        # Strategy 3: Find by clicking on element that shows date text
        if not date_input:
            try:
                logger.info("Strategy 3: Looking for element showing date text...")
                print("[INFO] Strategy 3: Looking for element showing date text...")
                # Look for text that contains date pattern like "2026-01-01 - 2026-01-02"
                date_text_pattern = f"{date_from.strftime('%Y-%m-%d')} - {date_to.strftime('%Y-%m-%d')}"
                # Or look for any date-like text
                elements_with_date = await self.page.query_selector_all('*')
                for elem in elements_with_date[:50]:  # Limit to first 50 to avoid timeout
                    try:
                        text = await elem.inner_text()
                        if text and ('2026' in text or '2025' in text) and ('-' in text or len(text) > 8):
                            # Check if it's clickable and might be the date picker
                            tag_name = await elem.evaluate('el => el.tagName.toLowerCase()')
                            if tag_name in ['input', 'div', 'span', 'button']:
                                # Try to find input nearby
                                parent = await elem.evaluate_handle('el => el.closest("div[role=\\"presentation\\"]")')
                                if parent:
                                    inp = await parent.query_selector('input[type="text"]')
                                    if inp:
                                        date_input = inp
                                        logger.info("Found date input near date text")
                                        print("[INFO] Found date input near date text")
                                        break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Strategy 3 failed: {e}")
        
        if not date_input:
            # Take screenshot for debugging
            try:
                screenshot_path = 'date_picker_not_found_debug.png'
                await self.page.screenshot(path=screenshot_path)
                logger.error(f"Could not find date picker input. Screenshot saved to {screenshot_path}")
                print(f"[ERROR] Could not find date picker input. Screenshot saved to {screenshot_path}")
            except:
                pass
            logger.warning("Could not find date picker input - will try to parse without setting date range")
            print("[WARNING] Could not find date picker input - will try to parse without setting date range")
            await asyncio.sleep(2)
            return
        
        # Step 2: Simple approach - clear input, type date range, press Enter
        try:
            logger.info(f"Setting date range: {date_from} to {date_to}")
            print(f"[INFO] Setting date range: {date_from} to {date_to}")
            
            # IMPORTANT: The website interprets dates in UTC, but the browser timezone is set to 'America/New_York'
            # This causes a -1 day offset. To compensate, we add 1 day to the dates before typing them.
            # When the website receives "2026-01-02", it interprets it as UTC, which becomes "2026-01-01" in the browser's timezone
            from datetime import timedelta
            adjusted_date_from = date_from + timedelta(days=1)
            adjusted_date_to = date_to + timedelta(days=1)
            
            # Format date range as "YYYY-MM-DD - YYYY-MM-DD" (with timezone compensation)
            date_range_str = f"{adjusted_date_from.strftime('%Y-%m-%d')} - {adjusted_date_to.strftime('%Y-%m-%d')}"
            logger.info(f"Typing date range (with +1 day timezone compensation): {date_range_str}")
            print(f"[INFO] Typing date range (with +1 day timezone compensation): {date_range_str}")
            
            # Focus the input
            await date_input.focus()
            await asyncio.sleep(0.3)
            
            # Clear the input more thoroughly
            # Method 1: Select all and delete
            await date_input.click(click_count=3)  # Triple click to select all
            await asyncio.sleep(0.2)
            await date_input.press('Backspace')
            await asyncio.sleep(0.2)
            
            # Method 2: Use JavaScript to clear value
            await date_input.evaluate('el => { el.value = ""; el.dispatchEvent(new Event("input", { bubbles: true })); }')
            await asyncio.sleep(0.3)
            
            # Method 3: Clear via keyboard (Ctrl+A, Delete)
            await date_input.press('Control+a')
            await asyncio.sleep(0.1)
            await date_input.press('Delete')
            await asyncio.sleep(0.2)
            
            # Verify input is clear - try multiple times if needed
            for clear_attempt in range(3):
                current_value = await date_input.input_value()
                if not current_value or not current_value.strip():
                    break
                logger.debug(f"Input still has value after clearing (attempt {clear_attempt + 1}): '{current_value}', clearing again")
                await date_input.evaluate('el => { el.value = ""; el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true })); }')
                await asyncio.sleep(0.3)
                # Also try selecting all and deleting
                await date_input.press('Control+a')
                await asyncio.sleep(0.1)
                await date_input.press('Delete')
                await asyncio.sleep(0.2)
            
            # Type the date range
            await date_input.type(date_range_str, delay=50)  # Small delay between keystrokes
            await asyncio.sleep(0.5)
            
            # Verify the value was set correctly
            final_value = await date_input.input_value()
            logger.debug(f"Date input value after typing: '{final_value}'")
            if date_range_str not in final_value:
                logger.warning(f"Date range may not have been set correctly. Expected: '{date_range_str}', Got: '{final_value}'")
                print(f"[WARNING] Date range may not have been set correctly. Expected: '{date_range_str}', Got: '{final_value}'")
            
            # Press Enter to apply
            logger.info("Pressing Enter to apply date range")
            print("[INFO] Pressing Enter to apply date range")
            await date_input.press('Enter')
            
            # Wait for page to update after date change
            await asyncio.sleep(3)
            
            # Verify the date range was applied by checking URL or page content
            current_url = self.page.url
            logger.debug(f"URL after setting date range: {current_url}")
            
            # Check if URL contains the date range
            # Note: We compare against the original dates (not adjusted), because the website
            # should display the dates we want, even if we had to add 1 day to compensate for timezone
            if 'from=' in current_url and 'to=' in current_url:
                from_match = re.search(r'from=(\d{4}-\d{2}-\d{2})', current_url)
                to_match = re.search(r'to=(\d{4}-\d{2}-\d{2})', current_url)
                if from_match and to_match:
                    url_from = from_match.group(1)
                    url_to = to_match.group(1)
                    expected_from = date_from.strftime('%Y-%m-%d')
                    expected_to = date_to.strftime('%Y-%m-%d')
                    if url_from == expected_from and url_to == expected_to:
                        logger.info(f"Date range verified in URL: {url_from} to {url_to}")
                        print(f"[INFO] Date range verified in URL: {url_from} to {url_to}")
                    else:
                        logger.warning(f"Date range mismatch! Expected: {expected_from} to {expected_to}, Got in URL: {url_from} to {url_to}")
                        print(f"[WARNING] Date range mismatch! Expected: {expected_from} to {expected_to}, Got in URL: {url_from} to {url_to}")
                        logger.info(f"Note: We typed {date_range_str} to compensate for timezone offset")
                        print(f"[INFO] Note: We typed {date_range_str} to compensate for timezone offset")
            
            logger.info("Date range set successfully")
            print("[INFO] Date range set successfully")
            
        except Exception as e:
            logger.error(f"Error setting date range: {e}")
            print(f"[ERROR] Error setting date range: {e}")
            import traceback
            traceback.print_exc()
            # Try to continue anyway
            await asyncio.sleep(2)
        
        # Wait for page to update after date change
        await asyncio.sleep(2)
    
    async def parse_all_entries_async(self, target_date: date) -> List[ParsedEntry]:
        """Parse all entries for a given date (async version)."""
        import logging
        logger = logging.getLogger(__name__)
        
        entries = []
        page_num = 1
        
        # Check if page is still open
        if self.page.is_closed():
            logger.error("Page was closed before parsing")
            print("[ERROR] Page was closed before parsing")
            return entries
        
        while True:
            # Check if page is still open before each operation
            if self.page.is_closed():
                logger.warning(f"Page was closed during parsing at page {page_num}")
                print(f"[WARNING] Page was closed during parsing at page {page_num}")
                break
            
            # Navigate to page if needed
            if page_num > 1:
                try:
                    await self._go_to_page_async(page_num)
                except Exception as e:
                    logger.error(f"Error navigating to page {page_num}: {e}")
                    print(f"[ERROR] Error navigating to page {page_num}: {e}")
                    break
            
            # Parse entries on current page
            try:
                page_entries = await self._parse_page_entries_async(target_date)
            except Exception as e:
                logger.error(f"Error parsing page {page_num}: {e}")
                print(f"[ERROR] Error parsing page {page_num}: {e}")
                # If page was closed, break
                if "closed" in str(e).lower() or "Target" in str(type(e).__name__):
                    break
                continue
            
            if not page_entries:
                logger.info(f"No entries found on page {page_num}, stopping")
                print(f"[INFO] No entries found on page {page_num}, stopping")
                break
            
            entries.extend(page_entries)
            logger.info(f"Page {page_num}: Found {len(page_entries)} entries (total: {len(entries)})")
            print(f"[INFO] Page {page_num}: Found {len(page_entries)} entries (total: {len(entries)})")
            
            # Check if there's a next page
            try:
                has_next = await self._has_next_page_async()
                if not has_next:
                    logger.info("No more pages, finished parsing")
                    print("[INFO] No more pages, finished parsing")
                    break
            except Exception as e:
                logger.warning(f"Error checking for next page: {e}")
                print(f"[WARNING] Error checking for next page: {e}")
                break
            
            page_num += 1
        
        logger.info(f"Finished parsing: {len(entries)} total entries")
        print(f"[INFO] Finished parsing: {len(entries)} total entries")
        
        # Reverse all entries to show oldest first (chronological order)
        # Website shows newest first, but we want oldest first in the table
        entries.reverse()
        logger.debug(f"Reversed all entries: now showing oldest first (chronological order)")
        
        return entries
    
    async def _go_to_page_async(self, page_num: int):
        """Navigate to a specific page (async version)."""
        try:
            # Find pagination and click page number
            page_button = await self.page.wait_for_selector(
                f'button:has-text("{page_num}"), a:has-text("{page_num}"), [data-page="{page_num}"]',
                timeout=5000
            )
            if page_button:
                await page_button.click()
                await self.page.wait_for_load_state('networkidle')
                await asyncio.sleep(2)
        except:
            # Try clicking next button multiple times
            for _ in range(page_num - 1):
                next_button = await self.page.query_selector('button:has-text(">"), a:has-text(">"), [aria-label*="next"]')
                if next_button:
                    await next_button.click()
                    await asyncio.sleep(2)
                else:
                    break
    
    async def _has_next_page_async(self) -> bool:
        """Check if there's a next page (async version)."""
        try:
            next_button = await self.page.query_selector(
                'button:has-text(">"), a:has-text(">"), [aria-label*="next"]'
            )
            if next_button:
                # Check if button is disabled
                disabled = await next_button.get_attribute('disabled')
                class_attr = await next_button.get_attribute('class') or ''
                return not bool(disabled) and 'disabled' not in class_attr
            return False
        except:
            return False
    
    async def _parse_page_entries_async(self, target_date: date) -> List[ParsedEntry]:
        """Parse all entries on the current page (async version)."""
        import logging
        logger = logging.getLogger(__name__)
        
        entries = []
        
        # Check if page is still open
        if self.page.is_closed():
            logger.error("Page was closed while parsing")
            print("[ERROR] Page was closed while parsing")
            return entries
        
        # Find all entry containers
        # Entries have numeric IDs like id="777553656" and obfuscated classes
        # Strategy: Find divs with numeric IDs (these are the entry blocks)
        entry_elements = []
        
        # First, try to find divs with numeric IDs using JavaScript
        # This is more reliable than CSS selectors for dynamic numeric IDs
        try:
            logger.debug("Trying to find entries by numeric ID pattern")
            # Find all divs with IDs that are purely numeric (6+ digits)
            # Use JavaScript to get element IDs, then query by those IDs
            numeric_ids = await self.page.evaluate("""
                () => {
                    const allDivs = document.querySelectorAll('div[id]');
                    const entryIds = [];
                    for (const div of allDivs) {
                        const id = div.getAttribute('id');
                        // Check if ID is numeric and at least 6 digits (typical for YouScan entry IDs like 777553656)
                        if (id && /^\\d{6,}$/.test(id)) {
                            // Check if this div has the structure of an entry block
                            // Look for: profile images, social network indicators, date links, or substantial text
                            const hasProfileImg = div.querySelector('img[src*="api/image/get"], img[src*="profile"], img[src*="avatar"]');
                            const hasSocialNetwork = div.querySelector('span[title*="facebook"], span[title*="instagram"], a[href*="facebook"], a[href*="instagram"]');
                            const hasDateLink = div.querySelector('a[href*="facebook.com"], a[href*="instagram.com"]');
                            const hasSubstantialText = div.textContent.trim().length > 100;
                            
                            // Must have at least one of these indicators
                            if (hasProfileImg || hasSocialNetwork || hasDateLink || hasSubstantialText) {
                                entryIds.push(id);
                            }
                        }
                    }
                    return entryIds;
                }
            """)
            
            if numeric_ids and len(numeric_ids) > 0:
                logger.info(f"Found {len(numeric_ids)} entries with numeric IDs: {numeric_ids[:5]}...")
                print(f"[INFO] Found {len(numeric_ids)} entries with numeric IDs")
                
                # Use the more reliable method: Query all divs with IDs and filter by numeric_ids
                # IMPORTANT: Get elements in DOM order to preserve visual order from page
                try:
                    # Get all entry divs in DOM order using JavaScript
                    # This ensures entries are in the same order as they appear visually on the page
                    entry_ids_ordered = await self.page.evaluate("""
                        (numericIds) => {
                            const numericIdsSet = new Set(numericIds);
                            const allDivs = Array.from(document.querySelectorAll('div[id]'));
                            const entryIds = [];
                            
                            // Collect IDs in DOM order (as they appear on page)
                            for (const div of allDivs) {
                                const id = div.getAttribute('id');
                                if (id && numericIdsSet.has(id)) {
                                    entryIds.push(id);
                                }
                            }
                            
                            return entryIds;
                        }
                    """, numeric_ids)
                    
                    # Now query elements in the correct DOM order
                    for entry_id in entry_ids_ordered:
                        try:
                            elem = await self.page.query_selector(f'div[id="{entry_id}"]')
                            if elem:
                                entry_elements.append(elem)
                        except:
                            continue
                    
                    # Fallback: if JavaScript approach didn't work, use original method
                    if not entry_elements:
                        all_divs_with_ids = await self.page.query_selector_all('div[id]')
                        logger.debug(f"Found {len(all_divs_with_ids)} divs with id attribute")
                        numeric_ids_set = set(numeric_ids)
                        
                        for div in all_divs_with_ids:
                            try:
                                div_id = await div.get_attribute('id')
                                if div_id and div_id in numeric_ids_set:
                                    entry_elements.append(div)
                            except:
                                continue
                    
                    if entry_elements:
                        logger.info(f"Retrieved {len(entry_elements)} entries using bulk query method (in DOM order)")
                        print(f"[INFO] Retrieved {len(entry_elements)} entries using bulk query method (in DOM order)")
                    else:
                        logger.warning(f"Found {len(numeric_ids)} numeric IDs but couldn't retrieve any elements")
                        print(f"[WARNING] Found {len(numeric_ids)} numeric IDs but couldn't retrieve any elements")
                except Exception as bulk_error:
                    logger.debug(f"Bulk query method failed: {bulk_error}, trying individual queries in DOM order")
                    # Fallback: Try individual queries, but get them in DOM order
                    try:
                        # Get IDs in DOM order first
                        entry_ids_ordered = await self.page.evaluate("""
                            (numericIds) => {
                                const numericIdsSet = new Set(numericIds);
                                const allDivs = Array.from(document.querySelectorAll('div[id]'));
                                const entryIds = [];
                                
                                // Collect IDs in DOM order (as they appear on page)
                                for (const div of allDivs) {
                                    const id = div.getAttribute('id');
                                    if (id && numericIdsSet.has(id)) {
                                        entryIds.push(id);
                                    }
                                }
                                
                                return entryIds;
                            }
                        """, numeric_ids)
                        
                        # Query elements in DOM order
                        for entry_id in entry_ids_ordered:
                            try:
                                elem = await self.page.query_selector(f'div[id="{entry_id}"]')
                                if elem:
                                    entry_elements.append(elem)
                            except Exception as e:
                                logger.debug(f"Error getting element with ID {entry_id}: {e}")
                                continue
                    except:
                        # Final fallback: query in original order
                        for entry_id in numeric_ids:
                            try:
                                elem = await self.page.query_selector(f'div[id="{entry_id}"]')
                                if elem:
                                    entry_elements.append(elem)
                            except Exception as e:
                                logger.debug(f"Error getting element with ID {entry_id}: {e}")
                                continue
                    
                    if entry_elements:
                        logger.info(f"Retrieved {len(entry_elements)} valid entry elements using individual queries (in DOM order)")
                        print(f"[INFO] Retrieved {len(entry_elements)} valid entry elements using individual queries (in DOM order)")
        except Exception as e:
            logger.debug(f"JavaScript-based entry finding failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Final fallback: Try CSS selectors if JavaScript approach didn't work
        if not entry_elements:
            entry_selectors = [
                'div[id^="7"]',  # IDs starting with 7
                'div[id^="8"]',  # IDs starting with 8
                'div[id^="9"]',  # IDs starting with 9
                '[class*="mention"]',
                '[class*="Mention"]',
                '[class*="post"]',
                '[class*="entry"]',
                '[class*="item"]',
                'article',
                '[data-testid*="mention"]',
                '[role="article"]',
                'div[class*="card"]',
                'div[class*="Card"]',
            ]
            
            for selector in entry_selectors:
                try:
                    logger.debug(f"Trying entry selector: {selector}")
                    elements = await self.page.query_selector_all(selector)
                    if elements and len(elements) > 0:
                        # For ID-based selectors, verify they have numeric IDs
                        if 'id' in selector:
                            filtered = []
                            for elem in elements:
                                try:
                                    elem_id = await elem.get_attribute('id')
                                    if elem_id and elem_id.isdigit() and len(elem_id) >= 6:
                                        filtered.append(elem)
                                except:
                                    continue
                            if filtered:
                                logger.info(f"Found {len(filtered)} elements with selector: {selector}")
                                print(f"[INFO] Found {len(filtered)} elements with selector: {selector}")
                                entry_elements = filtered
                                break
                        else:
                            # For other selectors, check if they look like entries
                            # Filter by having substantial content
                            filtered = []
                            for elem in elements:
                                try:
                                    text = await elem.inner_text()
                                    if text and len(text.strip()) > 50:  # Has substantial content
                                        filtered.append(elem)
                                except:
                                    continue
                            if filtered:
                                logger.info(f"Found {len(filtered)} elements with selector: {selector}")
                                print(f"[INFO] Found {len(filtered)} elements with selector: {selector}")
                                entry_elements = filtered
                                break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
        
        if not entry_elements:
            logger.warning("No entry elements found on page")
            print("[WARNING] No entry elements found on page")
            # Take screenshot for debugging
            try:
                screenshot_path = f'no_entries_debug_{target_date}.png'
                await self.page.screenshot(path=screenshot_path)
                logger.info(f"Screenshot saved to {screenshot_path}")
                print(f"[DEBUG] Screenshot saved to {screenshot_path}")
            except:
                pass
        
        for idx, entry_elem in enumerate(entry_elements):
            try:
                logger.debug(f"Parsing entry {idx + 1}/{len(entry_elements)}")
                entry = await self._parse_single_entry_async(entry_elem, target_date)
                if entry:
                    entries.append(entry)
                    logger.debug(f"Successfully parsed entry {idx + 1}")
            except Exception as e:
                logger.warning(f"Error parsing entry {idx + 1}: {e}")
                print(f"[WARNING] Error parsing entry {idx + 1}: {e}")
                continue
        
        logger.info(f"Parsed {len(entries)} entries from {len(entry_elements)} elements")
        print(f"[INFO] Parsed {len(entries)} entries from {len(entry_elements)} elements")
        
        return entries
    
    async def _parse_single_entry_async(self, entry_elem, target_date: date) -> Optional[ParsedEntry]:
        """Parse a single entry element (async version)."""
        import logging
        from datetime import datetime
        logger = logging.getLogger(__name__)
        
        # First, extract the actual date from the entry to filter by target_date
        entry_date = None
        try:
            # Look for date link: <a href="..." class="j0EW2HMfFh3MvBbwygOB">2 січня 2026 р., 14:37</a>
            date_link = await entry_elem.query_selector('a.j0EW2HMfFh3MvBbwygOB, a[href*="facebook"], a[href*="instagram"]')
            if date_link:
                date_text = await date_link.inner_text()
                # Parse Ukrainian date format: "2 січня 2026 р., 14:37" or "2 января 2026 г., 14:37"
                # Map Ukrainian/Russian month names to numbers
                month_map = {
                    'січня': 1, 'лютого': 2, 'березня': 3, 'квітня': 4, 'травня': 5, 'червня': 6,
                    'липня': 7, 'серпня': 8, 'вересня': 9, 'жовтня': 10, 'листопада': 11, 'грудня': 12,
                    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
                    'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
                }
                
                # Try to parse date from text like "2 січня 2026 р., 14:37"
                date_match = re.search(r'(\d{1,2})\s+([а-яіїєґ]+)\s+(\d{4})', date_text, re.IGNORECASE)
                if date_match:
                    day = int(date_match.group(1))
                    month_name = date_match.group(2).lower()
                    year = int(date_match.group(3))
                    month = month_map.get(month_name)
                    if month:
                        entry_date = date(year, month, day)
                        logger.debug(f"Extracted entry date: {entry_date} from text: '{date_text}'")
        except Exception as e:
            logger.debug(f"Could not extract date from entry: {e}")
        
        # Filter: Only parse entries that match the target_date
        if entry_date and entry_date != target_date:
            logger.debug(f"Skipping entry with date {entry_date} (target: {target_date})")
            return None
        
        entry = ParsedEntry()
        entry.date = entry_date if entry_date else target_date
        
        try:
            # 1. Parse user name (Назва)
            # Structure: <span class="NR97fosTp2Dtw_WKVPAN zFP66ww7zDIL4Gc2auF8">Тетяна Ломакіна</span>
            # This appears in the author section at the top
            name_selectors = [
                'span.NR97fosTp2Dtw_WKVPAN',  # Specific class for author name
                'span[class*="NR97fosTp2Dtw"]',  # Partial match
                'div[class*="e99EkRyEQ2YU1HjaKz7j"] span',  # Author section
            ]
            
            name_text = ''
            name_elem = None  # Store the element for clicking later
            for selector in name_selectors:
                try:
                    name_elem = await entry_elem.query_selector(selector)
                    if name_elem:
                        name_text = (await name_elem.inner_text()).strip()
                        # Get the first span with actual name (skip empty ones)
                        if name_text and len(name_text) > 2:
                            break
                except:
                    continue
            
            # If not found, try to extract from the full text structure
            if not name_text or len(name_text) < 2:
                try:
                    # Look for pattern like "Тетяна Ломакіна відповіла на коментар"
                    full_text = await entry_elem.inner_text()
                    match = re.search(r'^([А-ЯІЇЄҐа-яіїєґ\s]+?)\s+(відповіла|відповів|залишив|поділив)', full_text)
                    if match:
                        name_text = match.group(1).strip()
                        # Try to find the element again with the matched text
                        if name_text:
                            name_elem = await entry_elem.query_selector(f'span:has-text("{name_text}")')
                except:
                    pass
            
            entry.name = name_text if name_text else 'Невідомий користувач'
            
            # 2. Parse social network link and name
            # Structure: <a href="https://www.facebook.com/..." class="j0EW2HMfFh3MvBbwygOB">2 січня 2026 р., 14:37</a>
            # The date link contains the actual post URL
            link_elem = await entry_elem.query_selector('a.j0EW2HMfFh3MvBbwygOB, a[href*="facebook"], a[href*="instagram"], a[href*="twitter"], a[href*="linkedin"], a[href*="youtube"], a[href*="t.me"], a[href*="telegram.me"], a[href*="telegram"], a[href*="tiktok"], a[href*="threads"], a[href*="soundcloud"]')
            
            if link_elem:
                link_href = await link_elem.get_attribute('href') or ''
                entry.link = link_href
                entry.social_network = detect_social_network_from_link(link_href)
                logger.debug(f"Found link: {link_href}, social network: {entry.social_network}")
                print(f"[LINK] Found link: {link_href}, social network: {entry.social_network}")
            else:
                # Fallback: Look for social network name in span
                # Structure: <span class="FnMtmUa9bs__3sxIz_4N BgNMJrrsKXup73BhMooc">facebook.com</span>
                # Or: <span class="FnMtmUa9bs__3sxIz_4N BgNMJrrsKXup73BhMooc">telegram.me</span>
                social_span = await entry_elem.query_selector('span.FnMtmUa9bs__3sxIz_4N, span[class*="FnMtmUa9bs"]')
                if social_span:
                    social_text = (await social_span.inner_text()).strip()
                    if social_text:
                        # Clean up the text (remove any extra whitespace)
                        social_text = social_text.strip()
                        entry.social_network = detect_social_network_from_link(f"https://{social_text}")
                        logger.info(f"Found social network from span: {social_text}, detected: {entry.social_network}")
                        print(f"[LINK] Found social network from span: '{social_text}', detected: {entry.social_network}")
                
                # Additional fallback: Search for social network names in entry text
                if not entry.social_network:
                    entry_text = await entry_elem.inner_text()
                    entry_text_lower = entry_text.lower()
                    # Check for Telegram (both t.me and telegram.me)
                    if 't.me' in entry_text_lower or 'telegram.me' in entry_text_lower or 'telegram' in entry_text_lower:
                        entry.social_network = 'Telegram'
                        logger.info(f"Detected Telegram from entry text")
                        print(f"[LINK] Detected Telegram from entry text")
            
            # 3. Get link via share button (if not found above)
            if not entry.link:
                entry.link = await self._get_link_via_share_button_async(entry_elem)
                if entry.link:
                    entry.social_network = detect_social_network_from_link(entry.link)
            
            # 4. Parse tags (Тема) - get first one
            tags = await self._parse_tags_async(entry_elem)
            entry.tag = tags[0] if tags else ''
            
            # 5. Parse note (Примітки) - main text content
            # Structure: <p class="VqFKkdgOknQMdibReX6Y"> and <span class="Q73iQ9Oh3QBkbjh10U6t WJIiADpYvnCJ14uuC16a">
            entry.note = await self._parse_note_async(entry_elem)
            
            # 6. Parse user description (Хто це) - click on username
            entry.description = await self._parse_user_description_async(entry_elem, name_elem)
            
            # 7. Determine table name based on entry (year-based)
            entry.table_name = detect_table_from_entry(entry)
            logger.debug(f"Determined table name: {entry.table_name} for entry date: {entry.date}")
            print(f"[TABLE] Determined table name: {entry.table_name} for entry date: {entry.date}")
            
            return entry
            
        except Exception as e:
            logger.error(f"Error parsing entry: {e}")
            print(f"[ERROR] Error parsing entry: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _get_link_via_share_button_async(self, entry_elem) -> str:
        """Click share button and get link (async version)."""
        try:
            # Find share button (icon with share symbol)
            share_selectors = [
                'button[aria-label*="share"]',
                'button[aria-label*="поділитися"]',
                '[class*="share"]',
                'button:has([class*="share"])',
                'svg:has-text("share")',
            ]
            
            share_button = None
            for selector in share_selectors:
                try:
                    share_button = await entry_elem.query_selector(selector)
                    if share_button:
                        break
                except:
                    continue
            
            if not share_button:
                return ''
            
            # Click share button
            await share_button.click()
            await asyncio.sleep(1)
            
            # Look for "Скопіювати посилання" button
            copy_link_selectors = [
                'button:has-text("Скопіювати посилання")',
                'button:has-text("Copy link")',
                '[class*="copy"]:has-text("посилання")',
                '[class*="copy"]:has-text("link")',
            ]
            
            copy_button = None
            for selector in copy_link_selectors:
                try:
                    copy_button = await self.page.wait_for_selector(selector, timeout=2000)
                    if copy_button:
                        break
                except:
                    continue
            
            if copy_button:
                await copy_button.click()
                await asyncio.sleep(0.5)
                # Link should be in clipboard, but we can try to get it from the dialog
                # For now, we'll need to handle clipboard or get from dialog
                # This is a simplified version - may need adjustment
            
            # Close share dialog if open
            close_button = await self.page.query_selector('button[aria-label="Close"], button:has-text("×"), [class*="close"]')
            if close_button:
                await close_button.click()
                await asyncio.sleep(0.5)
            
            # Return empty for now - clipboard access in async context needs special handling
            return ''
        except Exception as e:
            print(f"Error getting link via share button: {e}")
            return ''
    
    async def _parse_tags_async(self, entry_elem) -> List[str]:
        """
        Parse tags from entry - match against dropdown options, or return original if no match (async version).
        
        Behavior matches social network dropdown:
        - Try to match found tags to dropdown options (exact, starts-with, contains)
        - If match found: use dropdown option value
        - If no match: use original tag text (inserted as-is, user can change via dropdown in Google Sheets)
        
        HTML Structure:
        <div class="izj773vLNpCIfNBWnzoQ">
          <div class="kUy1sArwGFcGCnoB7ZWg">  <!-- FIRST div - contains "Стаття" - SKIP THIS -->
            <span>Стаття</span>
          </div>
          <div class="RynAcp3UczxMoGCp6Syp"></div>  <!-- Separator -->
          <div class="l9Xop4gL9H3TgNeRAp2A">  <!-- LAST div - contains actual tag -->
            <div class="OcLjtVuWbx7moLWcbJE7">
              <span class="OTyF8q64v3qb6duzmTqb vw5KNeEyWubpzCogpt41">ББ маршрути</span>
            </div>
          </div>
        </div>
        """
        import logging
        logger = logging.getLogger(__name__)
        
        found_tags = []  # Store original tag text found in UI
        matched_tags = []  # Store matched dropdown options
        
        # Strategy 1: Use JavaScript to find tags in ALL child divs of izj773vLNpCIfNBWnzoQ (except first one with "Стаття")
        # Based on actual HTML: structure is izj773vLNpCIfNBWnzoQ -> kUy1sArwGFcGCnoB7ZWg (Стаття) -> RynAcp3UczxMoGCp6Syp (separator) -> l9Xop4gL9H3TgNeRAp2A (tag)
        try:
            tag_texts = await entry_elem.evaluate("""
                (tagOptions) => {
                    const found = [];
                    // Find divs with class izj773vLNpCIfNBWnzoQ (stable container)
                    const tagWrappers = this.querySelectorAll('div[class*="izj773vLNpCIfNBWnzoQ"]');
                    for (const wrapper of tagWrappers) {
                        // Get all direct child divs (not nested)
                        const childDivs = Array.from(wrapper.children).filter(el => el.tagName === 'DIV');
                        if (childDivs.length === 0) continue;
                        
                        // Check ALL child divs (skip first one which usually has "Стаття")
                        // Start from index 1 to skip the first div
                        for (let i = 1; i < childDivs.length; i++) {
                            const childDiv = childDivs[i];
                            
                            // Skip empty separator divs (like RynAcp3UczxMoGCp6Syp)
                            const divText = childDiv.textContent.trim();
                            if (!divText || divText.length === 0) continue;
                            
                            // Check if this div contains "Стаття" - if so, skip it
                            if (divText.includes('Стаття') && divText.length < 20) {
                                continue; // Skip divs that only contain "Стаття"
                            }
                            
                            // Find ALL spans in this div - don't rely on specific container classes
                            const spans = childDiv.querySelectorAll('span');
                            for (const span of spans) {
                                const text = span.textContent.trim();
                                
                                // Skip empty, single chars, close icons, and "Стаття"
                                if (!text || text === 'x' || text === 'X' || text === 'Стаття' || text.length < 2) continue;
                                
                                // Skip if it's inside a button (like "Додати тег")
                                if (span.closest('button')) continue;
                                
                                // Skip if it's just an icon (has icon but no text)
                                const hasIcon = span.querySelector('i.mdi');
                                if (hasIcon) {
                                    // Check if span has actual text content (not just icon)
                                    const textNodes = Array.from(span.childNodes).filter(n => n.nodeType === 3 && n.textContent.trim());
                                    if (textNodes.length === 0) continue;
                                }
                                
                                // This looks like a tag - add it
                                if (!found.includes(text)) {
                                    found.push(text);
                                }
                            }
                        }
                    }
                    return found;
                }
            """, TAG_OPTIONS)
            
            if tag_texts and len(tag_texts) > 0:
                for tag_text in tag_texts:
                    if tag_text not in found_tags:
                        found_tags.append(tag_text)
                logger.info(f"Found tags via JavaScript (last div method): {tag_texts}")
                print(f"[TAG] Found tags via JavaScript: {tag_texts}")
        except Exception as e:
            logger.debug(f"JavaScript tag extraction failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Strategy 2: CSS selector approach - check ALL child divs (skip first one with "Стаття")
        try:
            # Find izj773vLNpCIfNBWnzoQ containers
            tag_wrappers = await entry_elem.query_selector_all('div[class*="izj773vLNpCIfNBWnzoQ"]')
            for wrapper in tag_wrappers:
                try:
                    # Get all direct child divs
                    child_divs = await wrapper.query_selector_all(':scope > div')
                    if child_divs and len(child_divs) > 0:
                        # Check ALL child divs starting from index 1 (skip first one which has "Стаття")
                        for i in range(1, len(child_divs)):
                            child_div = child_divs[i]
                            
                            # Skip empty separator divs (like RynAcp3UczxMoGCp6Syp)
                            div_text = (await child_div.inner_text()).strip()
                            if not div_text or len(div_text) == 0:
                                continue  # Skip empty separator divs
                            
                            # Check if this div contains "Стаття" - if so, skip it
                            if 'Стаття' in div_text and len(div_text) < 20:
                                continue  # Skip divs that only contain "Стаття"
                            
                            # Find ALL spans in this div - don't rely on specific container classes
                            spans = await child_div.query_selector_all('span')
                            for span in spans:
                                tag_text = (await span.inner_text()).strip()
                                # Skip "Стаття", empty, single chars, close icons
                                if not tag_text or tag_text == 'Стаття' or tag_text in ['x', 'X'] or len(tag_text) < 2:
                                    continue
                                # Skip if it's inside a button
                                try:
                                    is_in_button = await span.evaluate('el => el.closest("button") !== null')
                                    if is_in_button:
                                        continue
                                except:
                                    pass
                                # Skip if it's just an icon
                                try:
                                    has_icon = await span.query_selector('i.mdi')
                                    if has_icon:
                                        # Check if span has actual text content
                                        text_content = await span.evaluate('el => Array.from(el.childNodes).filter(n => n.nodeType === 3 && n.textContent.trim()).length')
                                        if text_content == 0:
                                            continue
                                except:
                                    pass
                                if tag_text not in found_tags:
                                    found_tags.append(tag_text)
                                    logger.info(f"Found tag in child div {i} (CSS method): {tag_text}")
                                    print(f"[TAG] Found tag via CSS (div {i}): {tag_text}")
                except Exception as e:
                    logger.debug(f"Error extracting tag from wrapper: {e}")
                    continue
        except Exception as e:
            logger.debug(f"CSS tag container extraction failed: {e}")
        
        # Strategy 3: Direct CSS selectors targeting the last div structure (additional check)
        tag_selectors = [
            'div[class*="izj773vLNpCIfNBWnzoQ"] > div:last-child span',  # Last child -> any span
            'div[class*="l9Xop4gL9H3TgNeRAp2A"] span',  # Last div class -> any span
        ]
        
        entry_text = await entry_elem.inner_text()
        
        # Try CSS selectors as additional check (always run, not just as fallback)
        for selector in tag_selectors:
            try:
                tag_elements = await entry_elem.query_selector_all(selector)
                for tag_elem in tag_elements:
                    tag_text = (await tag_elem.inner_text()).strip()
                    # Skip "Стаття", "Додати тег", empty, single chars
                    if tag_text and tag_text != 'Стаття' and tag_text != 'Додати тег' and tag_text not in ['x', 'X'] and len(tag_text) > 1:
                        # Skip if it's inside a button
                        try:
                            is_in_button = await tag_elem.evaluate('el => el.closest("button") !== null')
                            if is_in_button:
                                continue
                        except:
                            pass
                        if tag_text not in found_tags:
                            found_tags.append(tag_text)
                            logger.info(f"Found tag via selector {selector}: {tag_text}")
                            print(f"[TAG] Found tag via fallback selector: {tag_text}")
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        # Strategy 4: Direct search for each dropdown option in izj773vLNpCIfNBWnzoQ containers
        # This is a more direct approach - search for spans containing tag text that matches dropdown options
        try:
            for tag_option in TAG_OPTIONS:
                # Skip if we already found this tag
                tag_option_lower = tag_option.lower().strip()
                already_found = any(found.lower().strip() == tag_option_lower for found in found_tags)
                if already_found:
                    continue
                
                # Search for this tag option in spans within izj773vLNpCIfNBWnzoQ containers
                tag_found = await entry_elem.evaluate("""
                    (tagOption) => {
                        const containers = this.querySelectorAll('div[class*="izj773vLNpCIfNBWnzoQ"]');
                        for (const container of containers) {
                            // Get all child divs, skip first one
                            const childDivs = Array.from(container.children).filter(el => el.tagName === 'DIV');
                            for (let i = 1; i < childDivs.length; i++) {
                                const childDiv = childDivs[i];
                                // Skip empty or "Стаття" divs
                                const divText = childDiv.textContent.trim();
                                if (!divText || (divText.includes('Стаття') && divText.length < 20)) continue;
                                
                                // Find spans in this div
                                const spans = childDiv.querySelectorAll('span');
                                for (const span of spans) {
                                    const text = span.textContent.trim();
                                    // Skip if it's in a button
                                    if (span.closest('button')) continue;
                                    // Skip empty, single chars, "Стаття"
                                    if (!text || text === 'x' || text === 'X' || text === 'Стаття' || text.length < 2) continue;
                                    
                                    // Check if this span text matches or contains the tag option
                                    const textLower = text.toLowerCase();
                                    const tagLower = tagOption.toLowerCase();
                                    // Exact match or tag option is contained in text (e.g., "Терсад" in "Терсад ВДНГ")
                                    // or text is contained in tag option
                                    if (textLower === tagLower || textLower.includes(tagLower) || tagLower.includes(textLower)) {
                                        return text; // Return the actual text found
                                    }
                                }
                            }
                        }
                        return null;
                    }
                """, tag_option)
                
                if tag_found and tag_found not in found_tags:
                    found_tags.append(tag_found)
                    logger.info(f"Found tag '{tag_found}' matching dropdown option '{tag_option}' (Strategy 4)")
                    print(f"[TAG] Found tag '{tag_found}' matching dropdown option '{tag_option}' (Strategy 4)")
        except Exception as e:
            logger.debug(f"Strategy 4 (direct tag search) failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Now match found tags against dropdown options with improved logic
        for found_tag in found_tags:
            found_tag_lower = found_tag.lower().strip()
            best_match = None
            best_match_score = 0
            
            # Try to find the best match
            for tag_option in TAG_OPTIONS:
                tag_option_lower = tag_option.lower().strip()
                
                # Score 3: Exact match (case-insensitive)
                if tag_option_lower == found_tag_lower:
                    best_match = tag_option
                    best_match_score = 3
                    break
                
                # Score 2: Found tag starts with dropdown option (e.g., "Терсад ВДНГ" starts with "Терсад")
                if found_tag_lower.startswith(tag_option_lower + ' ') or found_tag_lower.startswith(tag_option_lower):
                    if best_match_score < 2:
                        best_match = tag_option
                        best_match_score = 2
                
                # Score 1: Dropdown option is contained in found tag (e.g., "ББ маршрути" in "ББ Маршрути")
                elif tag_option_lower in found_tag_lower:
                    if best_match_score < 1:
                        best_match = tag_option
                        best_match_score = 1
                
                # Score 0.5: Found tag is contained in dropdown option
                elif found_tag_lower in tag_option_lower:
                    if best_match_score < 0.5:
                        best_match = tag_option
                        best_match_score = 0.5
            
            if best_match and best_match not in matched_tags:
                # Use matched dropdown option (same behavior as social network dropdown)
                matched_tags.append(best_match)
                logger.debug(f"Matched '{found_tag}' -> '{best_match}' (score: {best_match_score})")
            elif not best_match:
                # No match found - use original tag text (will be inserted as-is, user can change via dropdown)
                # Same behavior as social network: if no match, still write the value so user can change it later
                if found_tag not in matched_tags:
                    matched_tags.append(found_tag)
                    logger.debug(f"No match for '{found_tag}', using original (user can change via dropdown)")
        
        # Log final results
        if matched_tags:
            logger.info(f"Final matched tags: {matched_tags}")
            print(f"[TAG] Final matched tags: {matched_tags}")
        elif found_tags:
            logger.warning(f"Found tags but no matches: {found_tags}")
            print(f"[TAG] Found tags but no matches: {found_tags}")
        else:
            logger.warning("No tags found for this entry")
            print(f"[TAG] No tags found for this entry")
        
        # Return all matched tags (not just first one)
        # Note: We take the first tag when assigning to entry.tag, and return all for flexibility
        return matched_tags
    
    async def _parse_note_async(self, entry_elem) -> str:
        """Parse note (Примітки) - extract text after username from div.e99EkRyEQ2YU1HjaKz7j (async version)."""
        import logging
        logger = logging.getLogger(__name__)
        
        note_parts = []
        
        # Primary method: Extract text after username from div.e99EkRyEQ2YU1HjaKz7j
        # Example: <div class="e99EkRyEQ2YU1HjaKz7j">Невідомий користувач<span> </span>відповів(ла) на коментар<span> </span><span>в<span> </span>...
        # We want: "відповів(ла) на коментар в AXIOMA design"
        try:
            user_action_div = await entry_elem.query_selector('div.e99EkRyEQ2YU1HjaKz7j, div[class*="e99EkRyEQ2YU1HjaKz7j"]')
            if user_action_div:
                # Get the full HTML content
                html_content = await user_action_div.inner_html()
                
                # Parse all text nodes and span contents, skipping the first text (username)
                # Get inner text which will combine all text with spaces
                full_text = (await user_action_div.inner_text()).strip()
                
                # Split by whitespace to separate parts
                parts = full_text.split()
                
                # Try to identify username (usually first part or "Невідомий користувач")
                # Skip username and collect the rest
                if parts:
                    # Check if first part looks like username (starts with capital or is "Невідомий")
                    if parts[0] == "Невідомий" and len(parts) > 1 and parts[1] == "користувач":
                        # Skip "Невідомий користувач"
                        note_text = ' '.join(parts[2:])
                    else:
                        # Skip first part (username)
                        note_text = ' '.join(parts[1:])
                    
                    if note_text:
                        # Clean up engagement numbers like "1 тис."
                        note_text = re.sub(r'\d+\s*тис\.', '', note_text).strip()
                        # Remove redundant spaces
                        note_text = re.sub(r'\s+', ' ', note_text).strip()
                        
                        if note_text:
                            return note_text
        except Exception as e:
            logger.debug(f"Error extracting note from div.e99EkRyEQ2YU1HjaKz7j: {e}")
        
        # Fallback 1: Try to find the main text paragraph
        try:
            # Main text: <p class="VqFKkdgOknQMdibReX6Y">
            main_text_elem = await entry_elem.query_selector('p.VqFKkdgOknQMdibReX6Y, p[class*="VqFKkdgOknQMdibReX6Y"]')
            if main_text_elem:
                main_text = (await main_text_elem.inner_text()).strip()
                if main_text:
                    note_parts.append(main_text)
        except:
            pass
        
        # Fallback 2: Try to find additional text spans
        try:
            # Additional text: <span class="Q73iQ9Oh3QBkbjh10U6t WJIiADpYvnCJ14uuC16a">
            text_spans = await entry_elem.query_selector_all('span.Q73iQ9Oh3QBkbjh10U6t, span[class*="Q73iQ9Oh3QBkbjh10U6t"]')
            for span in text_spans:
                try:
                    span_text = (await span.inner_text()).strip()
                    # Filter out UI elements and very short text
                    if span_text and len(span_text) > 10 and 'Перекласти' not in span_text and 'Додати тег' not in span_text:
                        # Avoid duplicates
                        if span_text not in note_parts:
                            note_parts.append(span_text)
                except:
                    continue
        except:
            pass
        
        # Fallback 3: Look for main content area if specific classes not found
        if not note_parts:
            content_selectors = [
                'div[class*="yOPHd5XCBg3vO0C9GJNN"]',  # Content wrapper class
                'div[class*="GcnHzy56qFW5AbYII5ig"]',  # Text container class
                '[class*="content"]',
                '[class*="text"]',
                'p',
            ]
            
            for selector in content_selectors:
                try:
                    content_elem = await entry_elem.query_selector(selector)
                    if content_elem:
                        text = (await content_elem.inner_text()).strip()
                        # Filter out UI elements
                        if text and len(text) > 20 and 'Додати тег' not in text and 'Перекласти' not in text:
                            note_parts.append(text)
                            break
                except:
                    continue
        
        # Combine all parts
        note_text = ' '.join(note_parts).strip()
        
        # Clean up note text
        if note_text:
            # Remove "Перекласти" button text
            note_text = re.sub(r'Перекласти\s*$', '', note_text).strip()
            # Remove engagement numbers
            note_text = re.sub(r'\d+\s*тис\.', '', note_text).strip()
        
        return note_text
    
    async def _parse_user_description_async(self, entry_elem, name_elem) -> str:
        """Parse user description by clicking on username (async version)."""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # If no name element provided, try to find it
            if not name_elem:
                name_selectors = [
                    'span.NR97fosTp2Dtw_WKVPAN',
                    'span[class*="NR97fosTp2Dtw"]',
                    'div[class*="e99EkRyEQ2YU1HjaKz7j"] span',
                ]
                for selector in name_selectors:
                    try:
                        name_elem = await entry_elem.query_selector(selector)
                        if name_elem:
                            name_text = (await name_elem.inner_text()).strip()
                            if name_text and len(name_text) > 2:
                                break
                    except:
                        continue
            
            if not name_elem:
                logger.debug("No username element found for description parsing")
                return ''
            
            # The username span might be inside a clickable parent div with aria-expanded="false"
            # Use JavaScript to find and click the clickable parent element
            clicked = False
            try:
                # Use JavaScript to find clickable parent and click it
                clicked = await name_elem.evaluate("""
                    (elem) => {
                        // Try clicking the element itself first
                        try {
                            elem.click();
                            return true;
                        } catch (e) {
                            // If that fails, find clickable parent
                            let current = elem;
                            for (let i = 0; i < 3; i++) {
                                current = current.parentElement;
                                if (!current) break;
                                // Check if parent is clickable
                                if (current.getAttribute('aria-expanded') !== null ||
                                    current.getAttribute('role') === 'button' ||
                                    current.tagName === 'BUTTON' ||
                                    current.onclick ||
                                    window.getComputedStyle(current).cursor === 'pointer') {
                                    try {
                                        current.click();
                                        return true;
                                    } catch (e2) {
                                        // Continue searching
                                    }
                                }
                            }
                            // Last resort: try clicking original element via dispatchEvent
                            try {
                                const clickEvent = new MouseEvent('click', { bubbles: true, cancelable: true });
                                elem.dispatchEvent(clickEvent);
                                return true;
                            } catch (e3) {
                                return false;
                            }
                        }
                    }
                """)
                
                if clicked:
                    logger.debug("Clicked on username element (or parent)")
                    print(f"[DESC] Clicked on username element")
                else:
                    logger.debug("Could not click username element")
                    return ''
            except Exception as click_error:
                logger.debug(f"Error clicking username: {click_error}")
                return ''
            
            if clicked:
                # Wait for modal to appear
                await asyncio.sleep(1.5)  # Give time for modal to load
                
                # Look for modal/popup with role="dialog"
                # The description is in a div with class like "jrnY5tmnFg128QMOKSyq"
                modal = None
                try:
                    modal = await self.page.wait_for_selector(
                        '[role="dialog"]',
                        timeout=3000,
                        state='visible'
                    )
                except:
                    # Modal might not appear, try to find it anyway
                    try:
                        modal = await self.page.query_selector('[role="dialog"]')
                    except:
                        pass
                
                if modal:
                    logger.debug("Modal found, searching for description")
                    print(f"[DESC] Modal found, searching for description")
                    
                    # Try multiple strategies to find the description div
                    description_selectors = [
                        'div[class*="jrnY5tmnFg128QMOKSyq"]',  # Specific class from example
                        'div[class*="jrnY5tmn"]',  # Partial match
                        'div[class*="QMOKSyq"]',  # Another partial match
                        '[class*="description"]',
                        '[class*="bio"]',
                        '[class*="about"]',
                    ]
                    
                    desc_text = ''
                    for selector in description_selectors:
                        try:
                            desc_elem = await modal.query_selector(selector)
                            if desc_elem:
                                desc_text = (await desc_elem.inner_text()).strip()
                                if desc_text and len(desc_text) > 10:  # Must have substantial content
                                    logger.info(f"Found description using selector: {selector}")
                                    print(f"[DESC] Found description: {desc_text[:100]}...")
                                    break
                        except:
                            continue
                    
                    # If not found with specific selectors, try to find any div with substantial text
                    if not desc_text:
                        try:
                            # Look for divs with multiple spans (like the example structure)
                            all_divs = await modal.query_selector_all('div')
                            for div in all_divs:
                                div_text = (await div.inner_text()).strip()
                                # Check if it looks like a description (has URLs, multiple lines, etc.)
                                if div_text and len(div_text) > 20 and ('http' in div_text or '▫️' in div_text or '\n' in div_text):
                                    desc_text = div_text
                                    logger.info("Found description in div with substantial content")
                                    print(f"[DESC] Found description: {desc_text[:100]}...")
                                    break
                        except:
                            pass
                    
                    # Close modal
                    try:
                        # Try multiple close button selectors
                        close_selectors = [
                            'button[aria-label="Close"]',
                            'button:has-text("×")',
                            'button[class*="close"]',
                            '[aria-label*="close" i]',
                            'button:has([class*="close"])',
                        ]
                        for close_selector in close_selectors:
                            try:
                                close_btn = await self.page.query_selector(close_selector)
                                if close_btn:
                                    await close_btn.click()
                                    await asyncio.sleep(0.5)
                                    logger.debug("Closed modal")
                                    break
                            except:
                                continue
                        
                        # Fallback: Press Escape key
                        await self.page.keyboard.press('Escape')
                        await asyncio.sleep(0.5)
                    except:
                        pass
                    
                    return desc_text
                else:
                    logger.debug("No modal found after clicking username")
                    print(f"[DESC] No modal found after clicking username")
                
        except Exception as e:
            logger.warning(f"Error parsing user description: {e}")
            print(f"[DESC] Error parsing user description: {e}")
            import traceback
            traceback.print_exc()
        
        return ''
    

