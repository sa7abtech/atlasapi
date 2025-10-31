/**
 * Supabase Edge Function: Chat
 * Handles complete chat flow: context retrieval, OpenAI integration, response generation
 *
 * Deploy with: supabase functions deploy chat
 */

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.38.4";

interface ChatRequest {
  user_id: number;
  message: string;
  language?: string;
}

interface ChatResponse {
  response: string;
  model_used: string;
  tokens_used: number;
  from_cache: boolean;
}

const ATLAS_SYSTEM_PROMPT = `You are ATLAS, an expert AWS cloud consultant specializing in B2B SaaS solutions for Morocco-based businesses.

Your Core Identity:
- Professional AWS Solutions Architect with deep expertise in cloud migration
- Specialist in Odoo/Sage migration to modern cloud infrastructure
- Expert in cost optimization and ROI-focused solutions
- Fluent in Arabic, French, and English
- Based in Morocco, deeply understand local business context

Your Communication Style:
- Professional yet approachable
- Focus on ROI and tangible business value
- Use specific numbers and concrete examples
- Remember all past interactions and context
- Adapt language to user's preference

When responding:
- Start with the most valuable insight
- Back up claims with data and examples
- Offer next steps and action items
- Remember user's business context`;

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
    const { user_id, message, language = "en" }: ChatRequest = await req.json();

    if (!user_id || !message) {
      return new Response(
        JSON.stringify({ error: "user_id and message are required" }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    // Initialize Supabase client
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const openaiApiKey = Deno.env.get("OPENAI_API_KEY")!;

    const supabase = createClient(supabaseUrl, supabaseKey);

    // 1. Generate query embedding
    const embeddingResponse = await fetch("https://api.openai.com/v1/embeddings", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${openaiApiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "text-embedding-ada-002",
        input: message,
      }),
    });

    const embeddingData = await embeddingResponse.json();
    const query_embedding = embeddingData.data[0].embedding;

    // 2. Check cache
    const messageHash = await hashMessage(message);
    const { data: cacheData } = await supabase
      .from("atlas_insights_cache")
      .select("*")
      .eq("query_hash", messageHash)
      .gt("expires_at", new Date().toISOString())
      .single();

    if (cacheData) {
      // Cache hit - increment counter
      await supabase
        .from("atlas_insights_cache")
        .update({
          hit_count: cacheData.hit_count + 1,
          last_hit_at: new Date().toISOString(),
        })
        .eq("query_hash", messageHash);

      // Update user stats
      await updateUserStats(supabase, user_id, 0, 500);

      return new Response(
        JSON.stringify({
          response: cacheData.cached_response,
          model_used: "cached",
          tokens_used: 0,
          from_cache: true,
        } as ChatResponse),
        {
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
          },
        }
      );
    }

    // 3. Search knowledge base
    const { data: knowledgeChunks } = await supabase.rpc("match_knowledge", {
      query_embedding: JSON.stringify(query_embedding),
      match_threshold: 0.3,
      match_count: 3,
    });

    // 4. Get user memory
    const { data: userMemory } = await supabase
      .from("atlas_client_memory")
      .select("fact_key, fact_value")
      .eq("user_id", user_id)
      .order("last_referenced_at", { ascending: false })
      .limit(10);

    // 5. Get conversation history
    const { data: conversationHistory } = await supabase
      .from("atlas_conversations")
      .select("user_message, bot_response")
      .eq("user_id", user_id)
      .order("created_at", { ascending: false })
      .limit(5);

    // 6. Build context prompt
    let contextPrompt = "Relevant Knowledge:\n";
    if (knowledgeChunks && knowledgeChunks.length > 0) {
      knowledgeChunks.forEach((chunk: any, i: number) => {
        contextPrompt += `[${i + 1}] ${chunk.content}\n\n`;
      });
    } else {
      contextPrompt += "No specific knowledge retrieved\n\n";
    }

    contextPrompt += "User's Background:\n";
    if (userMemory && userMemory.length > 0) {
      userMemory.forEach((mem: any) => {
        contextPrompt += `- ${mem.fact_key}: ${mem.fact_value}\n`;
      });
    } else {
      contextPrompt += "No previous context available\n";
    }

    contextPrompt += "\nRecent Conversation Context:\n";
    if (conversationHistory && conversationHistory.length > 0) {
      conversationHistory.reverse().forEach((conv: any) => {
        contextPrompt += `User: ${conv.user_message}\nATLAS: ${conv.bot_response}\n\n`;
      });
    } else {
      contextPrompt += "First interaction\n";
    }

    contextPrompt += `\nCurrent Query: ${message}`;

    // 7. Classify query complexity
    const isComplex = message.length > 300 ||
      /compare|analyze|design|architecture|implement|migrate|optimize/i.test(message);

    const model = isComplex ? "gpt-4" : "gpt-3.5-turbo";

    // 8. Generate response with OpenAI
    const chatResponse = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${openaiApiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: ATLAS_SYSTEM_PROMPT },
          { role: "user", content: contextPrompt },
        ],
        temperature: 0.7,
        max_tokens: 1000,
      }),
    });

    const chatData = await chatResponse.json();
    const responseText = chatData.choices[0].message.content;
    const tokensUsed = chatData.usage.total_tokens;

    // 9. Save conversation
    await supabase.from("atlas_conversations").insert({
      user_id,
      user_message: message,
      user_message_embedding: JSON.stringify(query_embedding),
      bot_response: responseText,
      context_chunks: knowledgeChunks ? knowledgeChunks.map((c: any) => c.id) : [],
      model_used: model,
      tokens_used: tokensUsed,
      language,
    });

    // 10. Update user stats
    await updateUserStats(supabase, user_id, tokensUsed, 0);

    // 11. Cache simple responses
    if (!isComplex) {
      const expiresAt = new Date();
      expiresAt.setHours(expiresAt.getHours() + 24);

      await supabase.from("atlas_insights_cache").upsert({
        query_hash: messageHash,
        query_text: message,
        query_embedding: JSON.stringify(query_embedding),
        cached_response: responseText,
        language,
        expires_at: expiresAt.toISOString(),
      });
    }

    return new Response(
      JSON.stringify({
        response: responseText,
        model_used: model,
        tokens_used: tokensUsed,
        from_cache: false,
      } as ChatResponse),
      {
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      }
    );
  } catch (error) {
    console.error("Error in chat function:", error);
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
});

// Helper functions
async function hashMessage(message: string): Promise<string> {
  const normalized = message.toLowerCase().trim();
  const encoder = new TextEncoder();
  const data = encoder.encode(normalized);
  const hashBuffer = await crypto.subtle.digest("MD5", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function updateUserStats(supabase: any, userId: number, tokensUsed: number, tokensSaved: number) {
  const { data: user } = await supabase
    .from("atlas_users")
    .select("*")
    .eq("user_id", userId)
    .single();

  if (user) {
    await supabase
      .from("atlas_users")
      .update({
        total_conversations: (user.total_conversations || 0) + 1,
        total_tokens_used: (user.total_tokens_used || 0) + tokensUsed,
        total_tokens_saved: (user.total_tokens_saved || 0) + tokensSaved,
        last_seen_at: new Date().toISOString(),
      })
      .eq("user_id", userId);
  }
}
