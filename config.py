import os

class Config:
    """Configuration class for Telegram Bot and Automation settings"""
    
    # Telegram Bot Configuration
    # MUST be set via environment variable - DO NOT hardcode token here!
    # For local development, you can temporarily set a default token
    # For production (Render.com), ALWAYS set TELEGRAM_BOT_TOKEN environment variable
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    # Fallback for local development ONLY - Remove in production!
    if not TELEGRAM_BOT_TOKEN:
        # WARNING: This is a fallback for LOCAL testing only
        # On Render.com, you MUST set TELEGRAM_BOT_TOKEN in Environment Variables
        TELEGRAM_BOT_TOKEN = '8498886260:AAHfSXzudEr-JMNJ5zfXtzmEz8K8YqhtQZ8'
        print("WARNING: Using hardcoded token (local dev mode)")
        print("For production, set TELEGRAM_BOT_TOKEN environment variable!")
    
    # Allowed User IDs (for security - optional)
    # Lấy từ biến môi trường, phân tách bằng dấu phẩy. Ví dụ: 123456789,987654321
    # If empty or not set, bot will allow ALL users
    allowed_ids_env = os.getenv('ALLOWED_USER_IDS', '').strip()
    
    if allowed_ids_env:
        # Parse user IDs from environment variable
        ALLOWED_USER_IDS = [int(x.strip()) for x in allowed_ids_env.split(',') if x.strip().isdigit()]
        if ALLOWED_USER_IDS:
            print(f"[SECURITY] Bot access restricted to {len(ALLOWED_USER_IDS)} user(s)")
    else:
        # Empty = allow all users
        ALLOWED_USER_IDS = None
        print("[INFO] Bot is open to ALL users (no restrictions)")
    
    # Admin User ID for special commands
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '7509896689'))
    print(f"[ADMIN] Admin ID: {ADMIN_USER_ID}") 
    
    # File paths
    USER_FILE = 'user.txt'
    INSTAGRAM_COOKIE_PREFIX = 'COOKIEINS'
    LINKEDIN_COOKIE_PREFIX = 'COOKIELINKEDIN'
    
    # Default settings
    DEFAULT_JOBS = 50
    DEFAULT_DELAY = 10
    
    # Golike API endpoints
    GOLIKE_API_BASE = 'https://gateway.golike.net/api'
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is required!\n"
                "Please set it as an environment variable:\n"
                "  - On Render.com: Add it in Dashboard > Environment\n"
                "  - On local: export TELEGRAM_BOT_TOKEN='your-token-here'"
            )
        return True
