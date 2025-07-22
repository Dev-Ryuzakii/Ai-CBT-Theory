from flask import Flask, request, render_template, redirect, url_for
from api_service import register_api_routes
import logging
import os

# Create Flask app for API service
app = Flask(__name__)
app.secret_key = 'api_service_secret_key_2025'

# Configure logging
logging.basicConfig(level=logging.INFO)

# Register API routes
register_api_routes(app)

@app.route('/')
def index():
    """Professional landing page for the AI-CBT API service"""
    return render_template('landing_page.html')

@app.route('/api-dashboard')
def api_dashboard():
    """API Service Dashboard and Interactive Documentation"""
    return render_template('api_dashboard.html')

@app.route('/docs')
def documentation():
    """Redirect to API documentation"""
    return redirect('/api/v1/docs')

@app.route('/demo')
def demo():
    """Redirect to interactive demo"""
    return redirect('/api-dashboard')

@app.route('/education')
def education_redirect():
    """Redirect to education portal"""
    return redirect('http://localhost:5002')

@app.route('/health')
def health_check():
    """Simple health check for the main service"""
    return {
        'status': 'healthy',
        'service': 'AI-CBT API Platform',
        'version': '1.0.0',
        'endpoints': {
            'api': '/api/v1/',
            'docs': '/api/v1/docs',
            'dashboard': '/api-dashboard',
            'education': 'http://localhost:5002'
        }
    }

@app.errorhandler(404)
def not_found(error):
    """Custom 404 page"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Custom 500 page"""
    return render_template('500.html'), 500

if __name__ == '__main__':
    print("🚀 AI-CBT API Platform Starting...")
    print("=" * 50)
    print("🌐 Main Platform: http://localhost:5001/")
    print("📖 API Documentation: http://localhost:5001/api/v1/docs")
    print("🔧 Interactive Dashboard: http://localhost:5001/api-dashboard")
    print("🎓 Education Portal: http://localhost:5002/")
    print("=" * 50)
    print("✅ Ready to serve intelligent assessment APIs!")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
