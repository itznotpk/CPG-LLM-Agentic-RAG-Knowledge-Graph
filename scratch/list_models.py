import boto3
import json
from dotenv import load_dotenv

def list_bedrock_models():
    load_dotenv()
    
    print("Listing available Bedrock models...")
    
    # Initialize bedrock client
    bedrock = boto3.client(
        service_name='bedrock',
        region_name='us-east-1'
    )
    
    try:
        response = bedrock.list_foundation_models()
        
        # Filter for Anthropic models
        anthropic_models = [
            m for m in response['modelSummaries'] 
            if 'anthropic' in m['modelId'].lower()
        ]
        
        print(f"\nFound {len(anthropic_models)} Anthropic models:")
        for m in anthropic_models:
            print(f"- {m['modelId']} ({m['modelName']})")
            
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_bedrock_models()
