-- Create user_files table
create table if not exists public.user_files (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) not null,
  file_name text not null,
  file_url text not null,
  file_type text not null, -- 'image', 'pdf', 'json', 'post_ast', etc.
  size_bytes bigint,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Enable RLS
alter table public.user_files enable row level security;

-- Policies for user_files
create policy "Users can view their own files"
  on public.user_files for select
  using (auth.uid() = user_id);

create policy "Users can insert their own files"
  on public.user_files for insert
  with check (auth.uid() = user_id);

create policy "Users can delete their own files"
  on public.user_files for delete
  using (auth.uid() = user_id);

-- Storage Bucket Setup (Administrator must generate this in Supabase Dashboard if not possible via SQL)
-- Bucket name: 'user_artifacts'
-- Public: false (or true if simplified access is needed, but RLS on table handles logic)

-- Policy for Storage (if using storage-api)
-- insert into storage.buckets (id, name, public) values ('user_artifacts', 'user_artifacts', true);
-- create policy "Authenticated users can upload" on storage.objects for insert with check (bucket_id = 'user_artifacts' and auth.role() = 'authenticated');
-- create policy "Authenticated users can select" on storage.objects for select using (bucket_id = 'user_artifacts' and auth.role() = 'authenticated');
