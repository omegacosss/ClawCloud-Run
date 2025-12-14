#!/usr/bin/env python3
"""
ClawCloud Auto Login using GitHub Token
使用 GitHub Personal Access Token 自动登录
"""

import os
import sys
import time
import json
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ==================== 配置 ====================
CLAW_CLOUD_URL = "https://eu-central-1.run.claw.cloud"
SIGNIN_URL = f"{CLAW_CLOUD_URL}/signin"
GITHUB_LOGIN_URL = "https://github.com/login"

class AutoLogin:
    def __init__(self):
        self.username = os.environ.get('GH_USERNAME')
        self.token = os.environ.get('GH_PAT')
        self.debug = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
        self.screenshot_count = 0
        
    def log(self, message, level="INFO"):
        """打印日志"""
        icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "STEP": "🔹"}
        print(f"{icons.get(level, '•')} {message}")
    
    def screenshot(self, page, name):
        """保存截图"""
        self.screenshot_count += 1
        filename = f"{self.screenshot_count:02d}_{name}.png"
        page.screenshot(path=filename)
        if self.debug:
            self.log(f"Screenshot saved: {filename}")
    
    def validate_credentials(self):
        """验证凭据"""
        if not self.username:
            self.log("GH_USERNAME not set", "ERROR")
            return False
        if not self.token:
            self.log("GH_PAT not set", "ERROR")
            return False
        self.log(f"Username: {self.username}")
        self.log(f"Token: {'*' * 10}...{self.token[-4:]}")
        return True
    
    def find_and_click(self, page, selectors, description="element"):
        """查找并点击元素"""
        for selector in selectors:
            try:
                element = page.locator(selector).first
                if element.is_visible(timeout=3000):
                    element.click()
                    self.log(f"Clicked {description}", "SUCCESS")
                    return True
            except:
                continue
        return False
    
    def login_to_github(self, page):
        """登录 GitHub"""
        self.log("Logging into GitHub...", "STEP")
        
        # 检查是否在 GitHub 登录页面
        if 'github.com/login' not in page.url and 'github.com/session' not in page.url:
            self.log(f"Not on GitHub login page: {page.url}", "WARN")
            return False
        
        self.screenshot(page, "github_login_page")
        
        # 填写用户名
        try:
            username_field = page.locator('input[name="login"]')
            username_field.fill(self.username)
            self.log("Username entered")
        except Exception as e:
            self.log(f"Failed to enter username: {e}", "ERROR")
            return False
        
        # 填写密码（使用 PAT）
        try:
            password_field = page.locator('input[name="password"]')
            password_field.fill(self.token)
            self.log("Token entered as password")
        except Exception as e:
            self.log(f"Failed to enter token: {e}", "ERROR")
            return False
        
        self.screenshot(page, "github_credentials_filled")
        
        # 点击登录按钮
        try:
            submit_btn = page.locator('input[type="submit"], button[type="submit"]').first
            submit_btn.click()
            self.log("Login button clicked")
        except Exception as e:
            self.log(f"Failed to click login: {e}", "ERROR")
            return False
        
        # 等待页面加载
        time.sleep(3)
        page.wait_for_load_state('networkidle', timeout=30000)
        self.screenshot(page, "github_after_login")
        
        return True
    
    def handle_github_2fa(self, page):
        """处理 GitHub 2FA（如果有）"""
        # 检查是否需要 2FA
        if 'two-factor' in page.url or page.locator('input[name="otp"]').is_visible(timeout=2000):
            self.log("2FA required - cannot proceed automatically", "ERROR")
            self.screenshot(page, "github_2fa_required")
            return False
        return True
    
    def handle_oauth_authorize(self, page):
        """处理 OAuth 授权页面"""
        if 'github.com/login/oauth/authorize' in page.url:
            self.log("On OAuth authorization page", "STEP")
            self.screenshot(page, "oauth_authorize")
            
            # 查找授权按钮
            authorize_selectors = [
                'button[name="authorize"]',
                'button:has-text("Authorize")',
                'input[name="authorize"]',
                '#js-oauth-authorize-btn',
            ]
            
            if self.find_and_click(page, authorize_selectors, "Authorize button"):
                time.sleep(3)
                page.wait_for_load_state('networkidle', timeout=30000)
                return True
            else:
                self.log("No authorize button found (may be auto-authorized)", "WARN")
                return True
        
        return True
    
    def run(self):
        """主运行流程"""
        print("\n" + "="*60)
        print("🚀 ClawCloud Auto Login (GitHub Token)")
        print("="*60 + "\n")
        
        # 验证凭据
        if not self.validate_credentials():
            sys.exit(1)
        
        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            )
            
            page = context.new_page()
            
            try:
                # ========== Step 1: 访问 ClawCloud 登录页 ==========
                self.log("Step 1: Opening ClawCloud signin page", "STEP")
                page.goto(SIGNIN_URL, timeout=60000)
                page.wait_for_load_state('networkidle', timeout=30000)
                time.sleep(2)
                
                self.screenshot(page, "clawcloud_signin")
                self.log(f"Current URL: {page.url}")
                
                # 检查是否已登录
                if 'signin' not in page.url.lower() and 'login' not in page.url.lower():
                    self.log("Already logged in!", "SUCCESS")
                    return self.verify_and_keepalive(page, context)
                
                # ========== Step 2: 点击 GitHub 登录 ==========
                self.log("Step 2: Clicking GitHub login button", "STEP")
                
                github_btn_selectors = [
                    'button:has-text("GitHub")',
                    'a:has-text("GitHub")',
                    'button:has-text("Continue with GitHub")',
                    'button:has-text("Sign in with GitHub")',
                    '[data-provider="github"]',
                    'button:has(svg[class*="github"])',
                    'a[href*="github"]',
                ]
                
                if not self.find_and_click(page, github_btn_selectors, "GitHub login button"):
                    # 打印页面上的所有按钮帮助调试
                    self.log("Available buttons on page:", "WARN")
                    buttons = page.locator('button, a').all()
                    for btn in buttons[:10]:
                        try:
                            text = btn.inner_text()[:50]
                            self.log(f"  - {text}")
                        except:
                            pass
                    
                    self.screenshot(page, "no_github_button")
                    self.log("Could not find GitHub login button", "ERROR")
                    sys.exit(1)
                
                time.sleep(3)
                page.wait_for_load_state('networkidle', timeout=30000)
                self.screenshot(page, "after_github_click")
                self.log(f"Current URL: {page.url}")
                
                # ========== Step 3: GitHub 登录 ==========
                self.log("Step 3: GitHub authentication", "STEP")
                
                # 如果跳转到 GitHub 登录页
                if 'github.com/login' in page.url or 'github.com/session' in page.url:
                    if not self.login_to_github(page):
                        sys.exit(1)
                    
                    # 检查 2FA
                    if not self.handle_github_2fa(page):
                        sys.exit(1)
                
                # ========== Step 4: 处理 OAuth 授权 ==========
                self.log("Step 4: Handling OAuth authorization", "STEP")
                self.log(f"Current URL: {page.url}")
                
                if 'github.com' in page.url:
                    self.handle_oauth_authorize(page)
                    time.sleep(3)
                    page.wait_for_load_state('networkidle', timeout=30000)
                
                self.screenshot(page, "after_oauth")
                
                # ========== Step 5: 等待重定向 ==========
                self.log("Step 5: Waiting for redirect to ClawCloud", "STEP")
                
                max_wait = 30
                for i in range(max_wait):
                    current_url = page.url
                    if 'claw.cloud' in current_url and 'signin' not in current_url.lower():
                        self.log(f"Redirected to ClawCloud!", "SUCCESS")
                        break
                    time.sleep(1)
                    if i % 5 == 0:
                        self.log(f"Waiting... ({i}s) - {current_url[:60]}")
                
                self.screenshot(page, "final_redirect")
                
                # ========== Step 6: 验证登录 ==========
                return self.verify_and_keepalive(page, context)
                
            except Exception as e:
                self.log(f"Exception: {e}", "ERROR")
                self.screenshot(page, "error")
                import traceback
                traceback.print_exc()
                sys.exit(1)
            
            finally:
                browser.close()
    
    def verify_and_keepalive(self, page, context):
        """验证登录并保持活跃"""
        self.log("Step 6: Verifying login and keeping alive", "STEP")
        
        current_url = page.url
        self.log(f"Final URL: {current_url}")
        self.log(f"Page title: {page.title()}")
        
        # 检查是否登录成功
        if 'signin' in current_url.lower() or 'login' in current_url.lower():
            self.log("Login failed - still on signin page", "ERROR")
            self.screenshot(page, "login_failed")
            sys.exit(1)
        
        # 获取 cookies
        cookies = context.cookies()
        claw_cookies = [c for c in cookies if 'claw' in c.get('domain', '')]
        
        self.log(f"Retrieved {len(claw_cookies)} ClawCloud cookies", "SUCCESS")
        
        # 保存 cookies
        if claw_cookies:
            with open('cookies.json', 'w') as f:
                json.dump(claw_cookies, f, indent=2)
            self.log("Cookies saved to cookies.json")
        
        # 访问页面保持活跃
        self.log("Visiting pages to keep account active...", "STEP")
        
        pages = [
            (f"{CLAW_CLOUD_URL}/", "Dashboard"),
            (f"{CLAW_CLOUD_URL}/apps", "Apps"),
        ]
        
        for url, name in pages:
            try:
                page.goto(url, timeout=30000)
                page.wait_for_load_state('networkidle', timeout=15000)
                self.log(f"Visited {name}", "SUCCESS")
                time.sleep(2)
            except Exception as e:
                self.log(f"Could not visit {name}: {e}", "WARN")
        
        self.screenshot(page, "keepalive_done")
        
        print("\n" + "="*60)
        print("✅ AUTO LOGIN SUCCESSFUL!")
        print("="*60 + "\n")
        
        return True

if __name__ == "__main__":
    login = AutoLogin()
    login.run()
