"""
Test script for AI-powered lead qualification
Tests OpenRouter API integration without needing Telegram
"""
import asyncio
import sys
sys.path.insert(0, '/Users/nadaraya/Desktop/Расул СРМ')

from src.services.openrouter_service import openrouter_service
from src.services.prompts import SALES_AGENT_SYSTEM_PROMPT


async def test_ai_conversation():
    """Test AI conversation flow"""
    
    print("🤖 Testing AI Lead Qualification Agent\n")
    print("=" * 60)
    
    # Simulate a conversation
    conversation_history = [
        {"role": "user", "content": "Здравствуйте! Хочу сделать ремонт квартиры"},
        {"role": "assistant", "content": "Здравствуйте! 👋\n\nМеня зовут Александр, я из компании \"РемонтПро\". Помогу вам с ремонтом квартиры.\n\nПодскажите, пожалуйста, какая у вас квартира и сколько квадратных метров?"},
        {"role": "user", "content": "У меня квартира 65 квадратов, двухкомнатная"},
    ]
    
    print("\n📝 Conversation History:")
    for msg in conversation_history:
        role_emoji = "👤" if msg["role"] == "user" else "🤖"
        print(f"\n{role_emoji} {msg['role'].upper()}:")
        print(f"   {msg['content'][:100]}...")
    
    print("\n" + "=" * 60)
    print("\n🔄 Calling OpenRouter API (Claude 3.5 Sonnet)...\n")
    
    try:
        # Call AI
        response = await openrouter_service.generate_response(
            conversation_history=conversation_history,
            system_prompt=SALES_AGENT_SYSTEM_PROMPT
        )
        
        print("✅ AI Response received!\n")
        print("=" * 60)
        print("\n💬 AI Response Text:")
        print(f"\n{response['text']}\n")
        
        print("=" * 60)
        print("\n📊 Extracted Data:")
        if response['extracted_data']:
            import json
            print(json.dumps(response['extracted_data'], indent=2, ensure_ascii=False))
        else:
            print("   No data extracted")
        
        print("\n" + "=" * 60)
        print("\n📈 Token Usage:")
        usage = response['usage']
        print(f"   Prompt tokens: {usage['prompt_tokens']}")
        print(f"   Completion tokens: {usage['completion_tokens']}")
        print(f"   Total tokens: {usage['total_tokens']}")
        
        # Check handoff
        print("\n" + "=" * 60)
        should_handoff = openrouter_service.should_handoff(response['extracted_data'])
        print(f"\n🔔 Should handoff to manager: {'YES ✅' if should_handoff else 'NO ❌'}")
        
        print("\n" + "=" * 60)
        print("\n✅ Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await openrouter_service.close()


if __name__ == "__main__":
    asyncio.run(test_ai_conversation())
