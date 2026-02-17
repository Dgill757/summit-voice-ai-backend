import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/postgres')
os.environ.setdefault('SUPABASE_URL', 'https://example.supabase.co')
os.environ.setdefault('SUPABASE_ANON_KEY', 'x')
os.environ.setdefault('SUPABASE_SERVICE_KEY', 'x')
os.environ.setdefault('ANTHROPIC_API_KEY', 'x')
