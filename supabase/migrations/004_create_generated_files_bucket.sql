-- Storage Bucket for Generated Files (Agent Output)
INSERT INTO storage.buckets (id, name, public) 
VALUES ('generated-files', 'generated-files', true)
ON CONFLICT (id) DO NOTHING;

-- Policy to allow public access (for downloading generated files)
CREATE POLICY "Public Select Generated" 
ON storage.objects FOR SELECT 
USING ( bucket_id = 'generated-files' );

-- Policy to allow uploads (Agent Service Role bypasses this, but good for completeness)
CREATE POLICY "Service Role Uploads" 
ON storage.objects FOR INSERT 
WITH CHECK ( bucket_id = 'generated-files' );
