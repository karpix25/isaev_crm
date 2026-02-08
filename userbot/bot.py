#!/usr/bin/env python3
"""
Telegram Userbot for RepairCRM
Handles AI conversations with leads using OpenRouter + RAG
"""

import os
import json
import asyncio
from telethon import TelegramClient, events
import aiohttp
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv('TG_API_ID')
API_HASH = os.getenv('TG_API_HASH')
PHONE = os.getenv('TG_PHONE')
OPENROUTER_KEY = os.getenv('OPENROUTER_API_KEY')
REPAIRCRM_API = os.getenv('REPAIRCRM_API_URL', 'http://localhost:3000')
JWT_TOKEN = os.getenv('REPAIRCRM_JWT_TOKEN')

client = TelegramClient('userbot_session', API_ID, API_HASH)


async def query_rag(question: str) -> str:
    """Query RAG API for company context"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{REPAIRCRM_API}/api/rag/query',
                params={'q': question, 'limit': 3}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    context = '\n\n'.join([r['chunk'] for r in data['results']])
                    return context
                return ''
    except Exception as e:
        print(f'RAG query error: {e}')
        return ''


async def get_chat_history(lead_id: int) -> list:
    """Fetch chat history from CRM"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{REPAIRCRM_API}/api/leads/{lead_id}',
                headers={'Authorization': f'Bearer {JWT_TOKEN}'}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('chats') and len(data['chats']) > 0:
                        return data['chats'][0].get('messages', [])
                return []
    except Exception as e:
        print(f'Chat history error: {e}')
        return []


async def save_message(lead_id: int, role: str, text: str, audio_url: str = None, transcript: str = None):
    """Save message to CRM chat history"""
    try:
        # Fetch current chat
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{REPAIRCRM_API}/api/leads/{lead_id}',
                headers={'Authorization': f'Bearer {JWT_TOKEN}'}
            ) as resp:
                if resp.status != 200:
                    return
                data = await resp.json()
                chat = data.get('chats', [{}])[0]
                messages = chat.get('messages', [])

            # Append new message
            new_message = {
                'role': role,
                'text': text,
                'ts': asyncio.get_event_loop().time()
            }
            if audio_url:
                new_message['audioUrl'] = audio_url
            if transcript:
                new_message['transcript'] = transcript

            messages.append(new_message)

            # Update chat (simplified - in production use dedicated endpoint)
            print(f'Saved message to lead {lead_id}: {role} - {text[:50]}...')
    except Exception as e:
        print(f'Save message error: {e}')


async def call_openrouter(prompt: str, context: str, history: list) -> str:
    """Call OpenRouter LLM"""
    try:
        # Build conversation history
        messages = [
            {
                'role': 'system',
                'content': f'''Ты - менеджер компании по ремонту квартир. 
                
Информация о компании:
{context}

Отвечай вежливо, профессионально. Квалифицируй лида: узнай площадь квартиры, бюджет, сроки.'''
            }
        ]

        # Add history
        for msg in history[-10:]:  # Last 10 messages
            messages.append({
                'role': 'user' if msg['role'] == 'user' else 'assistant',
                'content': msg['text']
            })

        # Add current message
        messages.append({'role': 'user', 'content': prompt})

        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {OPENROUTER_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'openai/gpt-4-turbo',
                    'messages': messages,
                    'temperature': 0.7
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                else:
                    error = await resp.text()
                    print(f'OpenRouter error: {error}')
                    return 'Извините, произошла ошибка. Попробуйте позже.'
    except Exception as e:
        print(f'OpenRouter call error: {e}')
        return 'Извините, произошла ошибка. Попробуйте позже.'


@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def handle_message(event):
    """Handle incoming messages"""
    sender = await event.get_sender()
    user_id = sender.id
    text = event.message.text

    print(f'Message from {user_id}: {text}')

    # TODO: Map TG user to lead_id (for MVP, use simple mapping or /start command)
    # For now, assume lead_id is stored in bot data or use /start=<lead_id>
    lead_id = 1  # Placeholder

    # Query RAG for context
    context = await query_rag(text)

    # Get chat history
    history = await get_chat_history(lead_id)

    # Save user message
    await save_message(lead_id, 'user', text)

    # Get AI response
    response = await call_openrouter(text, context, history)

    # Save AI response
    await save_message(lead_id, 'ai', response)

    # Send response
    await event.respond(response)


async def main():
    print('Starting RepairCRM Userbot...')
    await client.start(phone=PHONE)
    print('Userbot started! Listening for messages...')
    await client.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())
