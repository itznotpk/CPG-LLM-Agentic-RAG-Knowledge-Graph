import asyncio
from agent.api import supabase_admin, get_supabase

async def check():
    client = get_supabase()
    try:
        # Check delivery jobs
        res = client.table('delivery_jobs').select('*').order('created_at', desc=True).limit(5).execute()
        print("Recent delivery jobs:", res.data)
        
        # Check patients email
        res2 = client.table('patients').select('nric,email,email_consent_at').limit(5).execute()
        print("Patients emails:", res2.data)
    except Exception as e:
        print("Error fetching:", str(e))

asyncio.run(check())
