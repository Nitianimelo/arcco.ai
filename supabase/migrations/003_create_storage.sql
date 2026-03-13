-- Storage Bucket for Chat Uploads
INSERT INTO storage.buckets (id, name, public) 
VALUES ('chat-uploads', 'chat-uploads', true)
ON CONFLICT (id) DO NOTHING;

-- Policy to allow uploads (public for demo/simplicity, strict in prod)
CREATE POLICY "Public Uploads" 
ON storage.objects FOR INSERT 
WITH CHECK ( bucket_id = 'chat-uploads' );

CREATE POLICY "Public Select" 
ON storage.objects FOR SELECT 
USING ( bucket_id = 'chat-uploads' );
