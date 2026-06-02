import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
import path from 'path';

// Load .env from project root
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseAnonKey = process.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.error('Missing env vars');
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseAnonKey);

async function testUpdate() {
  const nric = '580315-08-1234'; // Sample NRIC
  const updates = {
    email: 'test@example.com',
    email_consent_at: new Date().toISOString(),
  };

  console.log('Attempting update with anon key...');
  const { data, error } = await supabase
    .from('patients')
    .update(updates)
    .eq('nric', nric)
    .select(); // Ask for returning the data to see if it worked

  if (error) {
    console.error('❌ Update failed:', error);
  } else if (!data || data.length === 0) {
    console.warn('⚠️ Update succeeded but 0 rows affected. NRIC might be wrong or RLS blocked it.');
  } else {
    console.log('✅ Update success:', data);
  }
}

testUpdate();
