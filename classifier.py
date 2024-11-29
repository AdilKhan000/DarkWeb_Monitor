import logging
import requests
from typing import List, Optional

categories = [
        "Drug Trafficking", 
        "Weapons", 
        "CyberCrime", 
        "Inappropriate Content", 
        "Scam", 
        "Stolen data", 
        "Violent Content", 
        "Malware", 
        "Neutral"
    ]


def setup_logging() -> logging.Logger:
    """Set up logging configuration."""
    logger = logging.getLogger("ContentClassifier")
    logger.setLevel(logging.INFO)
    
    # Configure logging to both file and console
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('classification.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logger

def create_classification_prompt(content: str) -> str:

    """Create a prompt for content classification."""
    return (
        f"Classify the following content into one of these categories:\n"
        f"Categories: {', '.join(categories)}\n"
        f"Rules:\n"
        f"- Assign the most appropriate category\n"
        f"- Output must be strictly one of the category options\n"
        f"- If no category applies, use 'Neutral'\n\n"
        f"Content:\n{content}\n\nClassification:"
    )

def extract_classification(model_response: str, categories: List[str]) -> str:
    """
    Extract the exact classification from the model's response.
    
    Args:
        model_response (str): Full response from the model
        categories (List[str]): List of valid classification categories
    
    Returns:
        str: Extracted classification or 'Neutral'
    """
    # Convert to lowercase for case-insensitive matching
    response_lower = model_response.lower()
    
    # Check for exact category matches
    for category in categories:
        if category.lower() in response_lower:
            return category
    
    return 'Neutral'

def classify_content(
    content: str, 
    model_name: str = "mistral", 
    base_url: str = "http://localhost:11434"
) -> Optional[str]:
    """
    Classify content using a local Ollama model.
    
    Args:
        content (str): Text to classify
        model_name (str): Name of the Ollama model
        base_url (str): Base URL for Ollama API
    
    Returns:
        Optional[str]: Classified category or None if classification fails
    """
    logger = setup_logging()
    
    try:
        # Create classification prompt
        prompt = create_classification_prompt(content)
        
        # Send request to Ollama
        response = requests.post(
            f"{base_url}/api/generate",
            json={"model": model_name, "prompt": prompt, "stream": False},
            timeout=(30, 300)
        )
        response.raise_for_status()
        
        # Extract model's response
        model_response = response.json().get("response", "").strip()
        
        # Extract precise classification
        classification = extract_classification(model_response, categories)
        return classification
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Classification request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during classification: {e}")
        return None
