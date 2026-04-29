import asyncio
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path to import agent modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.providers import get_llm_model, validate_configuration

async def test_bedrock():
    print("--- Bedrock Diagnostic Test ---")
    
    # Load env
    load_dotenv()
    
    # Validate config
    if not validate_configuration():
        print("❌ Configuration validation failed.")
        return

    print(f"LLM Provider: {os.getenv('LLM_PROVIDER')}")
    print(f"LLM Choice: {os.getenv('LLM_CHOICE')}")
    print(f"AWS Region: {os.getenv('AWS_REGION')}")
    
    try:
        # Get model
        print("\nInitializing model...")
        model = get_llm_model()
        print(f"Model initialized: {type(model).__name__}")
        
        # Test completion
        print("\nSending test prompt to Bedrock...")
        from pydantic_ai import Agent
        agent = Agent(model)
        
        result = await agent.run("Hello! Say 'Bedrock is ready' if you can hear me.")
        print(f"\nResult attributes: {dir(result)}")
        try:
            print(f"\nResponse from Bedrock: {result.data}")
        except AttributeError:
            # Fallback for different versions
            print(f"\nResponse from Bedrock: {result}")
        print("\n[SUCCESS] Bedrock connection successful!")
        
    except Exception as e:
        print(f"\n[ERROR] Bedrock test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_bedrock())
