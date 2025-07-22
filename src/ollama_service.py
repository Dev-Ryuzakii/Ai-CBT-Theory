"""
Ollama service module for AI-powered answer scoring
"""
import requests
import json
import logging
import re
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OllamaService:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2:latest"):
        """
        Initialize Ollama service
        
        Args:
            base_url: Ollama server URL
            model: Model to use for inference (llama3.2:latest, llama2, mistral, etc.)
        """
        self.base_url = base_url
        self.model = model
        self.api_url = f"{base_url}/api/generate"
        
    def check_connection(self) -> bool:
        """Check if Ollama service is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            return False
    
    def score_answer(self, student_answer: str, marking_guide: str, question: str = "") -> Dict[str, Any]:
        """
        Score a student answer against a marking guide using Ollama
        
        Args:
            student_answer: The student's answer
            marking_guide: The correct answer/marking guide
            question: The original question (optional for context)
            
        Returns:
            Dictionary containing score and feedback
        """
        # Create a prompt for the AI to score the answer
        prompt = self._create_scoring_prompt(student_answer, marking_guide, question)
        
        try:
            response = self._call_ollama(prompt)
            return self._parse_scoring_response(response)
        except Exception as e:
            logger.error(f"Error scoring answer: {e}")
            return {
                "score": 0.0,
                "confidence": 0.0,
                "feedback": "Error occurred during scoring",
                "error": str(e)
            }
    
    def _create_scoring_prompt(self, student_answer: str, marking_guide: str, question: str = "") -> str:
        """Create a prompt for scoring the student answer"""
        prompt = f"""
You are an expert educator tasked with scoring student answers based on MEANING and UNDERSTANDING, not exact word matching.

Question: {question if question else "Not provided"}

Marking Guide/Expected Answer:
{marking_guide}

Student's Answer:
{student_answer}

Your task:
- Compare the MEANING of the student's answer with the marking guide
- The student's answer does NOT need to be word-for-word identical
- Focus on whether the student demonstrates understanding of the concept
- Award points based on how well the meaning aligns with the marking guide

Scoring Scale (INTEGER ONLY):
- 5: Excellent understanding, meaning perfectly aligns with marking guide
- 4: Good understanding, meaning mostly aligns with minor gaps
- 3: Adequate understanding, meaning somewhat aligns but missing some key points
- 2: Basic understanding, meaning partially aligns but significant gaps
- 1: Poor understanding, meaning barely aligns with marking guide
- 0: No understanding, meaning does not align or is completely incorrect

Please provide your response in the following JSON format:
{{
    "score": 4,
    "confidence": 0.9,
    "feedback": "The student demonstrates good understanding of the concept. The meaning aligns well with the marking guide despite different wording.",
    "strengths": ["Correct core concept", "Good explanation"],
    "weaknesses": ["Could be more detailed", "Missing one key point"]
}}

Important: 
- Score must be an INTEGER between 0-5
- Focus on MEANING and UNDERSTANDING, not exact words
- Consider different ways of expressing the same concept as correct

Respond only with the JSON object, no additional text.
"""
        return prompt
    
    def _call_ollama(self, prompt: str) -> str:
        """Make API call to Ollama"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for consistent scoring
                "top_p": 0.9,
                "num_predict": 500  # Limit response length
            }
        }
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=60  # Increased timeout
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "")
        except requests.exceptions.Timeout:
            logger.error("Ollama request timed out")
            raise Exception("Request timed out - model may be loading")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            logger.error(f"Response content: {response.text if 'response' in locals() else 'No response'}")
            raise Exception(f"HTTP error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error calling Ollama: {e}")
            raise
    
    def _parse_scoring_response(self, response: str) -> Dict[str, Any]:
        """Parse the scoring response from Ollama"""
        try:
            # Try to extract JSON from the response
            response = response.strip()
            
            # Find JSON object in the response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                parsed = json.loads(json_str)
                
                # Validate and clean the parsed response
                score = int(parsed.get("score", 0))  # Convert to integer
                score = max(0, min(5, score))  # Clamp between 0 and 5
                
                return {
                    "score": score,
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "feedback": parsed.get("feedback", "No feedback provided"),
                    "strengths": parsed.get("strengths", []),
                    "weaknesses": parsed.get("weaknesses", [])
                }
            else:
                raise ValueError("No valid JSON found in response")
                
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse Ollama response: {e}")
            logger.error(f"Response was: {response}")
            
            # Fallback: try to extract just a number if JSON parsing fails
            try:
                # Look for numbers in the response that could be scores (0-5)
                import re
                numbers = re.findall(r'[0-5]', response)
                if numbers:
                    score = int(numbers[0])
                    score = max(0, min(5, score))
                    return {
                        "score": score,
                        "confidence": 0.5,
                        "feedback": "Basic scoring (parsing failed)",
                        "strengths": [],
                        "weaknesses": []
                    }
            except:
                pass
            
            return {
                "score": 0,
                "confidence": 0.0,
                "feedback": "Failed to parse scoring response",
                "strengths": [],
                "weaknesses": []
            }
    
    def get_available_models(self) -> list:
        """Get list of available models from Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except requests.exceptions.RequestException:
            return []
    
    def pull_model(self, model_name: str) -> bool:
        """Pull a model if it's not available"""
        try:
            payload = {"name": model_name}
            response = requests.post(f"{self.base_url}/api/pull", json=payload, timeout=300)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            return False

# Create a global instance
ollama_service = OllamaService()

# Fallback scoring function for when Ollama is not available
def fallback_similarity_score(student_answer: str, marking_guide: str) -> int:
    """
    Simple fallback scoring based on text similarity
    Used when Ollama is not available
    Returns integer score 0-5
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        
        vectorizer = TfidfVectorizer(stop_words='english', lowercase=True)
        texts = [student_answer.lower(), marking_guide.lower()]
        tfidf_matrix = vectorizer.fit_transform(texts)
        similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        
        # Convert similarity (0.0-1.0) to integer score (0-5)
        score = int(similarity * 5)
        return max(0, min(5, score))
    except Exception:
        # Ultimate fallback - simple word overlap
        student_words = set(student_answer.lower().split())
        guide_words = set(marking_guide.lower().split())
        
        if not guide_words:
            return 0
        
        overlap = len(student_words.intersection(guide_words))
        similarity = overlap / len(guide_words)
        score = int(similarity * 5)
        return max(0, min(5, score))
