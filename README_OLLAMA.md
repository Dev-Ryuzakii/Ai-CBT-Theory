# AI-CBT-Theory with Ollama Integration 🧠

An intelligent Computer-Based Testing system powered by Ollama for advanced AI-driven assessment and feedback.

## 🚀 What's New with Ollama

This project now uses **Ollama** as the primary AI brain for:

- **Intelligent Scoring**: More nuanced and context-aware scoring of student answers
- **Detailed Feedback**: Comprehensive feedback including strengths and weaknesses
- **Confidence Scoring**: AI confidence levels for each assessment
- **Fallback Support**: Multiple fallback options if Ollama is unavailable

## 🎯 Features

### For Students
- 📝 Answer questions with immediate AI feedback
- 📊 Receive detailed explanations of scores
- 🎯 Get specific guidance on strengths and areas for improvement

### For Lecturers
- 🤖 View AI-generated scores with confidence levels
- 💭 Access detailed AI feedback for each answer
- ✏️ Override AI scores with lecturer assessment
- 📈 Monitor student progress with enhanced analytics
- 🔍 Expandable interface for detailed review

## 🛠️ Installation & Setup

### 1. Install Ollama

**macOS/Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:**
Download from [https://ollama.ai/download](https://ollama.ai/download)

### 2. Run the Setup Script

```bash
cd /Users/macbook/Ai-CBT-Theory
chmod +x setup_ollama.sh
./setup_ollama.sh
```

This script will:
- Check Ollama installation
- Start Ollama service
- Install recommended AI models
- Configure the project

### 3. Install Python Dependencies

```bash
# Activate virtual environment
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 4. Migrate Database

```bash
cd src
python migrate_db.py
```

### 5. Start the Application

```bash
# Make sure Ollama is running
ollama serve

# In another terminal, start the Flask app
cd src
python app.py
```

## 🤖 Ollama Models

### Recommended Models for Education

1. **llama2** (Default) - Good balance of performance and accuracy
2. **mistral** - Fast and efficient for quick assessments
3. **codellama** - Excellent for programming and technical subjects
4. **llama2:13b** - Higher accuracy but requires more resources

### Installing Additional Models

```bash
# Install a specific model
ollama pull mistral

# List available models
ollama list

# Test a model
ollama run llama2 "Hello, how are you?"
```

## 🔧 Configuration

### Ollama Settings

Edit `src/ollama_config.py` to customize:

```python
# Ollama Configuration
OLLAMA_MODEL = "llama2"  # Change model here
OLLAMA_BASE_URL = "http://localhost:11434"  # Change if running remotely

# Advanced settings (optional)
OLLAMA_TEMPERATURE = 0.1  # Lower = more consistent
OLLAMA_MAX_TOKENS = 500   # Response length limit
```

### Using Remote Ollama

If running Ollama on a different server:

```python
OLLAMA_BASE_URL = "http://your-server-ip:11434"
```

## 📊 How AI Scoring Works

1. **Student submits answer** → Sent to Ollama with marking guide
2. **Ollama analyzes** → Compares answer against correct answer
3. **AI generates**:
   - Numerical score (0.0 - 1.0)
   - Confidence level
   - Detailed feedback
   - Strengths and weaknesses
4. **Lecturer reviews** → Can override AI score if needed

## 🛡️ Fallback System

The system includes multiple fallback options:

1. **Primary**: Ollama AI scoring
2. **Secondary**: Traditional ML model (if available)
3. **Tertiary**: Simple text similarity scoring

This ensures the system works even if Ollama is temporarily unavailable.

## 📱 API Endpoints

### Check Ollama Status
```
GET /ollama-status
```
Returns connection status and available models.

### Update Lecturer Score
```
POST /update_lecturer_score/<response_id>
```
Override AI score with lecturer assessment.

## 🔍 Monitoring & Debugging

### Check Ollama Status in Browser
Visit: `http://localhost:5000/ollama-status`

### View Logs
```bash
# Check Ollama logs
journalctl -u ollama

# Check Flask app logs (if configured)
tail -f app.log
```

### Common Issues

**Ollama not responding:**
```bash
# Restart Ollama
ollama serve

# Check if port is busy
lsof -i :11434
```

**Model not found:**
```bash
# Pull the model
ollama pull llama2

# Verify installation
ollama list
```

## 🎨 Customization

### Custom Scoring Prompts

Edit `src/ollama_service.py` to customize the AI prompts:

```python
def _create_scoring_prompt(self, student_answer, marking_guide, question):
    # Customize this prompt for your subject area
    prompt = f"""
    You are an expert in [YOUR SUBJECT] tasked with scoring...
    """
```

### Adding New Models

```bash
# Install new model
ollama pull your-model-name

# Update configuration
# Edit src/ollama_config.py and change OLLAMA_MODEL
```

## 📈 Performance Tips

1. **Use appropriate models**: Smaller models (llama2) for basic questions, larger models (llama2:13b) for complex analysis
2. **Adjust temperature**: Lower values (0.1) for consistent scoring, higher (0.7) for creative feedback
3. **Monitor resources**: Larger models require more RAM and CPU
4. **Cache responses**: Consider implementing caching for frequently asked questions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Test with different Ollama models
4. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Common Commands

```bash
# Start Ollama
ollama serve

# Install model
ollama pull llama2

# Test model
ollama run llama2 "Test question"

# List models
ollama list

# Check service status
curl http://localhost:11434/api/tags
```

### Getting Help

1. Check the [Ollama documentation](https://ollama.ai/docs)
2. Review the application logs
3. Test Ollama independently before reporting issues
4. Ensure sufficient system resources (RAM/CPU)

---

**Happy Teaching with AI! 🎓🤖**
