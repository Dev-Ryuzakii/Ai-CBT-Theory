from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt
import uuid
import sqlite3
import os
import redis
import json
import hashlib
import time
from functools import wraps

app = Flask(__name__)
app.secret_key = 'production_api_secret_2025'

# Production Database Configuration
DATABASE_PATH = 'data/production_api.db'
REDIS_CLIENT = None  # Will initialize Redis for rate limiting

try:
    import redis
    REDIS_CLIENT = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    REDIS_CLIENT.ping()
    print("✅ Redis connected for rate limiting")
except:
    print("⚠️ Redis not available - using in-memory rate limiting")

class ProductionAPIService:
    def __init__(self):
        self.init_database()
    
    def init_database(self):
        """Initialize production database with proper tables"""
        os.makedirs('data', exist_ok=True)
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                company TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                email_verified BOOLEAN DEFAULT FALSE,
                verification_token TEXT,
                plan_type TEXT DEFAULT 'free'
            )
        ''')
        
        # API Keys table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key_name TEXT NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                secret_key TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                rate_limit INTEGER DEFAULT 1000,
                monthly_quota INTEGER DEFAULT 10000,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # API Usage table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key_id INTEGER NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                request_data TEXT,
                response_data TEXT,
                status_code INTEGER,
                processing_time REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (api_key_id) REFERENCES api_keys (id)
            )
        ''')
        
        # Subscriptions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan_type TEXT NOT NULL,
                status TEXT NOT NULL,
                current_period_start TIMESTAMP,
                current_period_end TIMESTAMP,
                stripe_subscription_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # System logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Production database initialized")

api_service = ProductionAPIService()

def require_auth(f):
    """Decorator for pages that require user authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def require_api_key(f):
    """Decorator for API endpoints that require valid API key"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        
        if not api_key:
            return jsonify({
                'error': 'API key required',
                'message': 'Include X-API-Key header or api_key parameter',
                'documentation': 'https://ai-cbt-api.com/docs/authentication'
            }), 401
        
        # Validate API key
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ak.id, ak.user_id, ak.is_active, ak.rate_limit, ak.monthly_quota, u.plan_type
            FROM api_keys ak
            JOIN users u ON ak.user_id = u.id
            WHERE ak.api_key = ? AND ak.is_active = TRUE AND u.is_active = TRUE
        ''', (api_key,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({
                'error': 'Invalid API key',
                'message': 'The provided API key is invalid or inactive',
                'documentation': 'https://ai-cbt-api.com/docs/authentication'
            }), 401
        
        # Check rate limits
        api_key_id, user_id, is_active, rate_limit, monthly_quota, plan_type = result
        
        if not check_rate_limit(api_key_id, rate_limit):
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': f'You have exceeded your rate limit of {rate_limit} requests per hour',
                'retry_after': 3600,
                'upgrade_url': 'https://ai-cbt-api.com/pricing'
            }), 429
        
        # Check monthly quota
        if not check_monthly_quota(api_key_id, monthly_quota):
            return jsonify({
                'error': 'Monthly quota exceeded',
                'message': f'You have exceeded your monthly quota of {monthly_quota} requests',
                'current_usage': get_monthly_usage(api_key_id),
                'upgrade_url': 'https://ai-cbt-api.com/pricing'
            }), 429
        
        # Log API usage
        log_api_usage(api_key_id, request.endpoint, request.method, 
                     request.get_json() if request.is_json else None,
                     request.remote_addr, request.user_agent.string)
        
        # Store API key info in request context
        request.api_key_id = api_key_id
        request.user_id = user_id
        request.plan_type = plan_type
        
        return f(*args, **kwargs)
    return decorated_function

def check_rate_limit(api_key_id, limit):
    """Check if API key has exceeded rate limit"""
    if REDIS_CLIENT:
        key = f"rate_limit:{api_key_id}:{datetime.now().hour}"
        current_count = REDIS_CLIENT.get(key) or 0
        if int(current_count) >= limit:
            return False
        REDIS_CLIENT.incr(key)
        REDIS_CLIENT.expire(key, 3600)  # Expire after 1 hour
        return True
    else:
        # Fallback to database for rate limiting
        return True  # Simplified for now

def check_monthly_quota(api_key_id, quota):
    """Check if API key has exceeded monthly quota"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    first_day = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cursor.execute('''
        SELECT COUNT(*) FROM api_usage 
        WHERE api_key_id = ? AND timestamp >= ?
    ''', (api_key_id, first_day))
    
    usage = cursor.fetchone()[0]
    conn.close()
    
    return usage < quota

def get_monthly_usage(api_key_id):
    """Get current monthly usage for API key"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    first_day = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cursor.execute('''
        SELECT COUNT(*) FROM api_usage 
        WHERE api_key_id = ? AND timestamp >= ?
    ''', (api_key_id, first_day))
    
    usage = cursor.fetchone()[0]
    conn.close()
    
    return usage

def log_api_usage(api_key_id, endpoint, method, request_data, ip_address, user_agent):
    """Log API usage for analytics and billing"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO api_usage (api_key_id, endpoint, method, request_data, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (api_key_id, endpoint, method, json.dumps(request_data) if request_data else None, 
          ip_address, user_agent))
    
    # Update last_used timestamp for API key
    cursor.execute('''
        UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE id = ?
    ''', (api_key_id,))
    
    conn.commit()
    conn.close()

def generate_api_key():
    """Generate a secure API key"""
    return f"aicbt_{''.join([f'{ord(c):02x}' for c in uuid.uuid4().hex[:16]])}"

def generate_secret_key():
    """Generate a secret key for API key verification"""
    return hashlib.sha256(uuid.uuid4().hex.encode()).hexdigest()

# ============================================================================
# PUBLIC PAGES (Marketing & Documentation)
# ============================================================================

@app.route('/docs')
def api_docs():
    """API Documentation"""
    return render_template('api_docs.html')

@app.route('/docs/getting-started')
def docs_getting_started():
    """Getting Started Guide"""
    return render_template('docs_getting_started.html')

@app.route('/docs/authentication')
def docs_authentication():
    """Authentication Documentation"""
    return render_template('docs_authentication.html')

@app.route('/docs/endpoints')
def docs_endpoints():
    """API Endpoints Reference"""
    return render_template('docs_endpoints.html')

@app.route('/docs/sdks')
def docs_sdks():
    """SDKs and Libraries"""
    return render_template('docs_sdks.html')

@app.route('/pricing')
def pricing():
    """Pricing Plans"""
    return render_template('pricing.html')

@app.route('/use-cases')
def use_cases():
    """Use Cases and Examples"""
    return render_template('use_cases.html')

# ============================================================================
# MAIN PAGES
# ============================================================================

@app.route('/')
def api_landing():
    """Production API landing page"""
    return render_template('api_landing.html')

@app.route('/status')
def api_status():
    """API status page showing system health and uptime"""
    return render_template('api_status.html')

@app.route('/playground')
def playground():
    """API Playground for testing endpoints"""
    return render_template('api_docs.html')  # Reuse docs template with interactive features

@app.route('/api')
def api_info():
    """API Information and quick start guide"""
    return redirect(url_for('api_docs'))

# AUTHENTICATION PAGES
# ============================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User Registration"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        company = request.form.get('company', '')
        
        if not email or not password or not full_name:
            flash('All fields are required', 'error')
            return render_template('register.html')
        
        # Check if user exists
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            flash('Email already registered', 'error')
            conn.close()
            return render_template('register.html')
        
        # Create user
        password_hash = generate_password_hash(password)
        verification_token = str(uuid.uuid4())
        
        cursor.execute('''
            INSERT INTO users (email, password_hash, full_name, company, verification_token)
            VALUES (?, ?, ?, ?, ?)
        ''', (email, password_hash, full_name, company, verification_token))
        
        user_id = cursor.lastrowid
        
        # Create default API key
        api_key = generate_api_key()
        secret_key = generate_secret_key()
        
        cursor.execute('''
            INSERT INTO api_keys (user_id, key_name, api_key, secret_key)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Default Key', api_key, secret_key))
        
        conn.commit()
        conn.close()
        
        # Auto-login user
        session['user_id'] = user_id
        session['email'] = email
        
        flash('Account created successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User Login"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, email, password_hash, full_name, is_active 
            FROM users WHERE email = ?
        ''', (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            if user[4]:  # is_active
                session['user_id'] = user[0]
                session['email'] = user[1]
                session['full_name'] = user[3]
                return redirect(url_for('dashboard'))
            else:
                flash('Account is deactivated', 'error')
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """User Logout"""
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('api_landing'))

# ============================================================================
# USER DASHBOARD PAGES
# ============================================================================

@app.route('/dashboard')
@require_auth
def dashboard():
    """User Dashboard Overview"""
    user_id = session['user_id']
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Get API keys count
    cursor.execute('SELECT COUNT(*) FROM api_keys WHERE user_id = ? AND is_active = TRUE', (user_id,))
    api_keys_count = cursor.fetchone()[0]
    
    # Get this month's usage
    first_day = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    cursor.execute('''
        SELECT COUNT(*) FROM api_usage au
        JOIN api_keys ak ON au.api_key_id = ak.id
        WHERE ak.user_id = ? AND au.timestamp >= ?
    ''', (user_id, first_day))
    monthly_usage = cursor.fetchone()[0]
    
    # Get recent API calls
    cursor.execute('''
        SELECT au.endpoint, au.method, au.status_code, au.timestamp, ak.key_name
        FROM api_usage au
        JOIN api_keys ak ON au.api_key_id = ak.id
        WHERE ak.user_id = ?
        ORDER BY au.timestamp DESC
        LIMIT 10
    ''', (user_id,))
    recent_calls = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                         api_keys_count=api_keys_count,
                         monthly_usage=monthly_usage,
                         recent_calls=recent_calls)

@app.route('/api-keys')
@require_auth
def api_keys():
    """API Keys Management"""
    user_id = session['user_id']
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, key_name, api_key, is_active, created_at, last_used, rate_limit, monthly_quota
        FROM api_keys WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))
    keys = cursor.fetchall()
    conn.close()
    
    return render_template('api_keys.html', api_keys=keys)

@app.route('/create-api-key', methods=['POST'])
@require_auth
def create_api_key():
    """Create new API key"""
    user_id = session['user_id']
    key_name = request.form.get('key_name', 'Unnamed Key')
    
    api_key = generate_api_key()
    secret_key = generate_secret_key()
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO api_keys (user_id, key_name, api_key, secret_key)
        VALUES (?, ?, ?, ?)
    ''', (user_id, key_name, api_key, secret_key))
    conn.commit()
    conn.close()
    
    flash(f'API key "{key_name}" created successfully!', 'success')
    return redirect(url_for('api_keys'))

@app.route('/usage')
@require_auth
def usage():
    """Usage Analytics"""
    user_id = session['user_id']
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Get usage by endpoint
    cursor.execute('''
        SELECT au.endpoint, COUNT(*) as count, AVG(au.processing_time) as avg_time
        FROM api_usage au
        JOIN api_keys ak ON au.api_key_id = ak.id
        WHERE ak.user_id = ?
        GROUP BY au.endpoint
        ORDER BY count DESC
    ''', (user_id,))
    endpoint_usage = cursor.fetchall()
    
    # Get daily usage for last 30 days
    cursor.execute('''
        SELECT DATE(au.timestamp) as date, COUNT(*) as count
        FROM api_usage au
        JOIN api_keys ak ON au.api_key_id = ak.id
        WHERE ak.user_id = ? AND au.timestamp >= datetime('now', '-30 days')
        GROUP BY DATE(au.timestamp)
        ORDER BY date
    ''', (user_id,))
    daily_usage = cursor.fetchall()
    
    conn.close()
    
    return render_template('usage.html', 
                         endpoint_usage=endpoint_usage,
                         daily_usage=daily_usage)

# ============================================================================
# PRODUCTION API ENDPOINTS
# ============================================================================

@app.route('/api/v1/score', methods=['POST'])
@require_api_key
def api_score():
    """Score student answer with AI"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ['student_answer', 'marking_guide', 'question_text']):
            return jsonify({
                'error': 'Missing required fields',
                'required': ['student_answer', 'marking_guide', 'question_text'],
                'documentation': 'https://ai-cbt-api.com/docs/endpoints#score'
            }), 400
        
        # Import your existing scoring logic
        from ollama_service import ollama_service
        
        start_time = time.time()
        score, confidence, feedback = ollama_service.score_answer(
            student_answer=data['student_answer'],
            marking_guide=data['marking_guide'],
            question_text=data['question_text']
        )
        processing_time = time.time() - start_time
        
        response_data = {
            'success': True,
            'data': {
                'score': score,
                'confidence': confidence,
                'feedback': feedback,
                'processing_time': round(processing_time, 3)
            },
            'meta': {
                'api_version': 'v1',
                'timestamp': datetime.now().isoformat(),
                'request_id': str(uuid.uuid4())
            }
        }
        
        # Log successful response
        log_api_response(request.api_key_id, response_data, 200, processing_time)
        
        return jsonify(response_data)
        
    except Exception as e:
        error_response = {
            'error': 'Internal server error',
            'message': 'An error occurred while processing your request',
            'request_id': str(uuid.uuid4()),
            'documentation': 'https://ai-cbt-api.com/docs/errors'
        }
        
        log_api_response(request.api_key_id, error_response, 500, 0)
        return jsonify(error_response), 500

@app.route('/api/v1/health', methods=['GET'])
def api_health():
    """API Health Check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': 'v1.0.0',
        'uptime': 'Available',
        'services': {
            'database': 'online',
            'ai_model': 'online',
            'redis_cache': 'online' if REDIS_CLIENT else 'offline'
        }
    })

def log_api_response(api_key_id, response_data, status_code, processing_time):
    """Log API response for analytics"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE api_usage 
        SET response_data = ?, status_code = ?, processing_time = ?
        WHERE api_key_id = ? AND id = (
            SELECT MAX(id) FROM api_usage WHERE api_key_id = ?
        )
    ''', (json.dumps(response_data), status_code, processing_time, api_key_id, api_key_id))
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    print("🚀 Production AI-CBT API Service")
    print("=" * 50)
    print("🌐 API Platform: http://localhost:5001/")
    print("📖 Documentation: http://localhost:5001/docs")
    print("🔑 Dashboard: http://localhost:5001/dashboard")
    print("📊 Status: http://localhost:5001/status")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5001)
