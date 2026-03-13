-- Ensure 'chat-uploads' bucket exists
INSERT INTO storage.buckets (id, name, public) 
VALUES ('chat-uploads', 'chat-uploads', true)
ON CONFLICT (id) DO NOTHING;

-- Allow public access for now (Simplifies Agent Demo)
-- In production, you'd restrict this to authenticated users
CREATE POLICY "Public Chat Uploads" 
ON storage.objects FOR INSERT 
WITH CHECK ( bucket_id = 'chat-uploads' );

CREATE POLICY "Public Chat Select" 
ON storage.objects FOR SELECT 
USING ( bucket_id = 'chat-uploads' );
