import asyncio
from agent.api import supabase_admin, get_supabase

async def check():
    client = get_supabase()
    try:
        # Check if email exists
        res = client.table('patients').select('nric,email,email_consent_at').limit(1).execute()
        print("Columns exist!", res.data)
    except Exception as e:
        print("Error fetching:", str(e))

asyncio.run(check())
