# 🤖 AI-CBT Assessment API Service

## 🚀 Transform Your Educational Platform with AI-Powered Assessment

The AI-CBT Assessment API is a comprehensive RESTful service that enables developers to integrate intelligent educational assessment capabilities into their applications. Built with cutting-edge AI technology, this API provides automated scoring, detailed feedback, and seamless integration options.

## ✨ Key Features

### 🧠 **AI-Powered Intelligence**
- **Advanced Scoring**: Uses Ollama AI models for semantic understanding
- **Detailed Feedback**: Provides strengths, weaknesses, and improvement suggestions
- **Confidence Scoring**: AI confidence levels for each assessment
- **Multiple Fallbacks**: Traditional ML and similarity-based backups ensure reliability

### 🔧 **Developer-Friendly API**
- **RESTful Design**: Standard HTTP methods and JSON responses
- **Comprehensive Documentation**: Interactive API docs at `/api/v1/docs`
- **Real-time Testing**: Built-in dashboard for API testing
- **Error Handling**: Detailed error messages and status codes

### 🔒 **Enterprise-Ready Security**
- **API Key Authentication**: Secure access control
- **Multiple Environment Support**: Development, testing, and production keys
- **Rate Limiting Ready**: Built for scalable implementations
- **Session Management**: Student session tracking and management

### 📊 **Complete Assessment Management**
- **Question Management**: CRUD operations for assessment questions
- **Student Tracking**: Comprehensive student response management
- **Progress Analytics**: Detailed scoring and performance insights
- **Batch Processing**: Handle multiple assessments efficiently

## 🌟 Perfect For

- **Learning Management Systems (LMS)**: Add AI grading to existing platforms
- **Educational Apps**: Integrate intelligent tutoring capabilities
- **Corporate Training**: Automated assessment for employee training
- **Research Projects**: Analyze learning patterns and effectiveness
- **MOOCs & Online Courses**: Scale personalized feedback

## 🚀 Quick Start

### 1. **Access the API**
```bash
# Health Check
curl http://localhost:5001/api/v1/health

# API Documentation
curl http://localhost:5001/api/v1/docs
```

### 2. **Get Your API Key**
- Development: `dev_key_123`
- Testing: `test_key_789`
- Production: `prod_key_456`

### 3. **Score Your First Answer**
```python
import requests

response = requests.post('http://localhost:5001/api/v1/score', 
    headers={'X-API-Key': 'dev_key_123', 'Content-Type': 'application/json'},
    json={
        'student_answer': 'Photosynthesis is how plants make food from sunlight.',
        'marking_guide': 'Photosynthesis converts light energy to chemical energy...',
        'question_text': 'Explain photosynthesis.'
    })

result = response.json()
print(f"Score: {result['data']['score']}/5")
print(f"Feedback: {result['data']['feedback']}")
```

## 📋 API Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Service health check |
| POST | `/api/v1/score` | Score individual answers |
| GET | `/api/v1/questions` | List all questions |
| POST | `/api/v1/questions` | Create new questions |
| POST | `/api/v1/students` | Create/get students |
| POST | `/api/v1/submit-response` | Submit & score responses |
| GET | `/api/v1/student/{id}/responses` | Get student progress |
| GET | `/api/v1/docs` | Interactive documentation |

## 🎯 Integration Examples

### Python (Flask/Django)
```python
from ai_cbt_client import AIAssessmentAPI

api = AIAssessmentAPI(api_key="your_key_here")
result = api.score_answer(student_answer, marking_guide)
```

### JavaScript (React/Vue/Angular)
```javascript
const response = await fetch('/api/v1/score', {
    method: 'POST',
    headers: {'X-API-Key': 'your_key', 'Content-Type': 'application/json'},
    body: JSON.stringify({student_answer, marking_guide})
});
```

### PHP (Laravel/WordPress)
```php
$response = wp_remote_post('http://api.example.com/api/v1/score', [
    'headers' => ['X-API-Key' => 'your_key'],
    'body' => json_encode(['student_answer' => $answer])
]);
```

## 📈 Pricing & Plans

### 🆓 **Free Tier**
- 1,000 API calls/month
- Basic AI scoring
- Community support
- Development use

### 💼 **Professional**
- 10,000 API calls/month
- Advanced AI features
- Priority support
- Commercial use

### 🏢 **Enterprise**
- Unlimited API calls
- Custom AI models
- Dedicated support
- On-premise deployment

## 🛠 Technical Specifications

- **Runtime**: Python 3.11+ with Flask
- **AI Engine**: Ollama with llama3.2:latest
- **Database**: SQLite (PostgreSQL ready)
- **Authentication**: API Key based
- **Response Format**: JSON
- **Rate Limits**: Configurable
- **Uptime**: 99.9% SLA

## 📚 Resources

- **📖 Full Documentation**: [http://localhost:5001/api/v1/docs](http://localhost:5001/api/v1/docs)
- **🧪 Interactive Dashboard**: [http://localhost:5001/api-dashboard](http://localhost:5001/api-dashboard)
- **👨‍💼 Admin Panel**: [http://localhost:5001/admin](http://localhost:5001/admin)
- **🏠 Home Portal**: [http://localhost:5001](http://localhost:5001)

## 🤝 Support & Community

- **Documentation**: Comprehensive API guides and examples
- **GitHub Issues**: Report bugs and request features
- **Community Forum**: Connect with other developers
- **Enterprise Support**: 24/7 support for enterprise clients

## 🔮 Roadmap

- **Multi-language Support**: Support for multiple programming languages
- **Advanced Analytics**: Detailed assessment analytics dashboard
- **Custom AI Models**: Train custom models for specific domains
- **Webhook Integration**: Real-time notifications
- **Batch Processing**: Handle large-scale assessments
- **Mobile SDKs**: Native mobile app integration

## 🎉 Get Started Today!

Transform your educational platform with AI-powered assessment. Start with our free tier and scale as you grow.

```bash
# Start the API server
cd /Users/macbook/Ai-CBT-Theory
source venv/bin/activate
python src/app.py

# Access the dashboard
open http://localhost:5001/api-dashboard
```

---

**Ready to revolutionize education with AI?** 🚀
[Get your API key](#) | [View Documentation](http://localhost:5001/api/v1/docs) | [Contact Sales](#)
