
import { supabase } from './supabase';

export interface UserFile {
    id: string;
    user_id: string;
    file_name: string;
    file_url: string;
    file_type: string;
    size_bytes?: number;
    created_at: string;
}

export const driveService = {

    async getUser() {
        return await supabase.auth.getUser();
    },

    // List all files for current user
    async listFiles(userId: string) {
        if (!userId) throw new Error("User ID is required to list files");
        const { data, error } = await supabase
            .from('user_files')
            .select('*')
            .eq('user_id', userId)
            .order('created_at', { ascending: false });

        if (error) throw error;
        return data as UserFile[];
    },

    // Save a file (Artifact) to the Vault
    // If content is a Blob/File, uploads to Storage first.
    // If content is already a URL (e.g. from generated image), just saves metadata.
    async saveFile(file: File | Blob, name: string, type: string, userId?: string) {
        if (!userId) {
            // Try to get user
            const { data: { user } } = await supabase.auth.getUser();
            if (!user) throw new Error("User not authenticated");
            userId = user.id;
        }

        // 1. Upload to Storage
        const path = `${userId}/${Date.now()}_${name}`;
        const { data: uploadData, error: uploadError } = await supabase.storage
            .from('user_artifacts')
            .upload(path, file);

        if (uploadError) throw uploadError;

        // 2. Get Public URL
        const { data: { publicUrl } } = supabase.storage
            .from('user_artifacts')
            .getPublicUrl(path);

        // 3. Insert into Table
        const { data, error } = await supabase
            .from('user_files')
            .insert({
                user_id: userId,
                file_name: name,
                file_url: publicUrl,
                file_type: type,
                size_bytes: file.size
            })
            .select()
            .single();

        if (error) throw error;
        return data;
    },

    // Save an external URL or Generated Content (Data URL or JSON) directly as a file reference
    // Useful for "Save to Vault" from Chat artifacts
    async saveArtifactReference(name: string, type: string, content: string | Blob, userId?: string) {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) throw new Error("User not authenticated");

        let finalUrl = '';
        let size = 0;

        if (typeof content === 'string' && content.startsWith('http')) {
            // It's already a URL (e.g. Unsplash or Supabase URL from chat)
            finalUrl = content;
        } else {
            // It's raw content (JSON string, Base64, or Blob)
            // We must upload it properly
            let blob: Blob;
            if (content instanceof Blob) {
                blob = content;
            } else if (typeof content === 'string') {
                blob = new Blob([content], { type: 'text/plain' }); // Default, override based on type
                if (type === 'json' || type === 'post_ast') {
                    blob = new Blob([content], { type: 'application/json' });
                }
            } else {
                throw new Error("Invalid content format");
            }

            size = blob.size;
            const path = `${user.id}/${Date.now()}_${name}`;
            const { error: uploadError } = await supabase.storage
                .from('user_artifacts')
                .upload(path, blob);

            if (uploadError) throw uploadError;

            const { data: { publicUrl } } = supabase.storage
                .from('user_artifacts')
                .getPublicUrl(path);

            finalUrl = publicUrl;
        }

        const { data, error } = await supabase
            .from('user_files')
            .insert({
                user_id: user.id,
                file_name: name,
                file_url: finalUrl,
                file_type: type,
                size_bytes: size
            })
            .select()
            .single();

        if (error) throw error;
        return data;
    },

    async deleteFile(fileId: string) {
        const { error } = await supabase
            .from('user_files')
            .delete()
            .eq('id', fileId);

        if (error) throw error;
        // Note: Ideally we should also delete from storage, but we need the path. 
        // For simplicity in MVP, we delete the reference. A cron job could clean up storage.
    }
};
