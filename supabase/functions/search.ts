/**
 * Supabase Edge Function: Search
 * Performs vector similarity search on knowledge base
 *
 * Deploy with: supabase functions deploy search
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.38.4";

interface SearchRequest {
  query_embedding: number[];
  top_k?: number;
  similarity_threshold?: number;
  category?: string;
}

interface SearchResult {
  id: string;
  content: string;
  category: string;
  similarity: number;
}

serve(async (req: Request) => {
  try {
    // Handle CORS
    if (req.method === "OPTIONS") {
      return new Response("ok", {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
        },
      });
    }

    // Parse request
    const { query_embedding, top_k = 3, similarity_threshold = 0.7, category }: SearchRequest = await req.json();

    if (!query_embedding || !Array.isArray(query_embedding)) {
      return new Response(
        JSON.stringify({ error: "query_embedding is required and must be an array" }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    // Initialize Supabase client
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Convert threshold to distance (cosine distance)
    const match_threshold = 1 - similarity_threshold;

    // Call the match_knowledge RPC function
    const { data, error } = await supabase.rpc("match_knowledge", {
      query_embedding: JSON.stringify(query_embedding),
      match_threshold,
      match_count: top_k,
    });

    if (error) {
      console.error("Error searching knowledge:", error);
      return new Response(
        JSON.stringify({ error: error.message }),
        {
          status: 500,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    // Filter by category if provided
    let results: SearchResult[] = data || [];
    if (category) {
      results = results.filter((r: SearchResult) => r.category === category);
    }

    return new Response(
      JSON.stringify({
        results,
        count: results.length,
      }),
      {
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      }
    );
  } catch (error) {
    console.error("Error in search function:", error);
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
});
