import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
base_dir = Path(__file__).parent.parent
load_dotenv(base_dir / ".env", override=True)

# --- Config Class ---
class Config:
    def __init__(self):
        self.BASE_DIR = base_dir
        self.EXECUTION_DIR = base_dir / "execution"
        self.TMP_DIR = base_dir / ".tmp"
        
        res_dir = os.getenv("OBSIDIAN_RESEARCH_DIR", r"D:\Pribadi\Obsidian\Writing\Research")
        self.OBSIDIAN_RESEARCH_DIR = Path(res_dir) if Path(res_dir).is_absolute() else base_dir / res_dir
        
        data_dir = os.getenv("DATA_DIR")
        if data_dir:
            self.DATA_DIR = Path(data_dir) if Path(data_dir).is_absolute() else base_dir / data_dir
        else:
            self.DATA_DIR = self.OBSIDIAN_RESEARCH_DIR.parent / "AI_Automation_Data"
        
        self.GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        self.BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")
        self.BUFFER_PROFILE_ID = os.getenv("BUFFER_PROFILE_ID")
        self.BUFFER_ORG_ID = os.getenv("BUFFER_ORG_ID")
        self.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
        self.APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
        
        self.THREADS_HANDLE = os.getenv("THREADS_HANDLE", "m.fauzan.aziz")
        self.MAX_VARIANTS_PER_DAY = int(os.getenv("MAX_VARIANTS_PER_DAY", "10"))
        self.POSTING_TIME = os.getenv("POSTING_TIME", "09:00")
        
        # Ensure directories exist
        for d in [self.TMP_DIR, self.EXECUTION_DIR, self.DATA_DIR]:
            d.mkdir(parents=True, exist_ok=True)

configs = Config()

# --- Shared Retry logic ---
def retry(max_attempts=3, delay=1):
    def decorator(func):
        import time
        from functools import wraps
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts == max_attempts:
                        raise e
                    print(f"[warning]Attempt {attempts} failed: {e}. Retrying...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator
