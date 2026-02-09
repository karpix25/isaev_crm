"""
Helper function to get default organization ID
"""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.organization import Organization


async def get_default_org_id(db: AsyncSession) -> uuid.UUID:
    """
    Get the first organization ID from database.
    In production, this should be configured per bot instance.
    """
    result = await db.execute(
        select(Organization.id).limit(1)
    )
    org_id = result.scalar_one_or_none()
    
    if not org_id:
        raise ValueError(
            "No organizations found in database! "
            "Please create an organization first."
        )
    
    return org_id


async def download_user_avatar(bot, telegram_id: int) -> str | None:
    """
    Download user profile photo and return local path/URL.
    """
    import os
    from aiogram.exceptions import TelegramBadRequest
    
    try:
        photos = await bot.get_user_profile_photos(user_id=telegram_id, limit=1)
        if not photos or not photos.total_count:
            return None
        
        # Get the smallest photo for avatar (offset 0 is largest usually, but let's check)
        # We want a decent size but not huge. Usually index 0 or -1.
        # photos.photos is a list of lists of PhotoSize
        photo_size = photos.photos[0][-1] # Largest size of the latest photo
        file_id = photo_size.file_id
        
        # Create directory if not exists
        media_dir = os.path.join(os.getcwd(), "media", "avatars")
        os.makedirs(media_dir, exist_ok=True)
        
        file_path = f"avatars/{telegram_id}.jpg"
        local_path = os.path.join(os.getcwd(), "media", file_path)
        
        # Check if already downloaded recently (optional)
        # if os.path.exists(local_path):
        #     return f"/media/{file_path}"
            
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, local_path)
        
        return f"/media/{file_path}"
    except TelegramBadRequest as e:
        print(f"⚠️ Cannot fetch avatar for {telegram_id}: {e}")
        return None
    except Exception as e:
        print(f"⚠️ Error downloading avatar: {e}")
        return None
