# ATLAS Quick Start Guide

Get ATLAS up and running in 10 minutes!

## Prerequisites Checklist

- [ ] Python 3.11+ installed
- [ ] Supabase account (free tier: https://supabase.com)
- [ ] OpenAI API key (https://platform.openai.com)
- [ ] Telegram bot token (from @BotFather)
- [ ] Your knowledge base markdown file ready

## Step 1: Get Your Credentials (5 minutes)

### Supabase Setup

1. Go to https://supabase.com and create a new project named "atlas"
2. Wait for project initialization (~2 minutes)
3. Go to Project Settings → API
4. Copy these values:
   - Project URL: `https://xxxxx.supabase.co`
   - `anon` `public` key
   - `service_role` `secret` key

### OpenAI Setup

1. Go to https://platform.openai.com/api-keys
2. Create new secret key
3. Copy the key (starts with `sk-`)

### Telegram Bot Setup

1. Open Telegram and search for @BotFather
2. Send `/newbot`
3. Follow instructions to create your bot
4. Copy the bot token

## Step 2: Project Setup (2 minutes)

```bash
# Clone or navigate to project
cd atlas

# Run automated setup
./setup.sh

# Edit .env file with your credentials
nano .env
```

Paste your credentials in `.env`:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here
SUPABASE_SERVICE_KEY=your-service-key-here
OPENAI_API_KEY=sk-your-openai-key-here
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
```

Save and exit (Ctrl+X, Y, Enter in nano)

## Step 3: Database Setup (1 minute)

1. Go to your Supabase project dashboard
2. Click on "SQL Editor" in the left sidebar
3. Click "New Query"
4. Copy and paste the entire content of:
   ```bash
   cat supabase/migrations/001_initial_schema.sql
   ```
5. Click "Run" (bottom right)
6. Wait for success message

## Step 4: Load Knowledge Base (2 minutes)

```bash
# Activate virtual environment
source venv/bin/activate

# Copy your markdown file to knowledge/data/
cp /path/to/your/playbook.md knowledge/data/

# Process and upload
python knowledge/loader.py knowledge/data/playbook.md
```

Watch for:
- ✓ Processed X chunks
- ✓ Generated X embeddings
- ✓ Upload complete
- ✓ Verification: X/X verified

## Step 5: Start ATLAS! (30 seconds)

### Option A: Simple Start Script

```bash
./start.sh
```

### Option B: Docker (if you have Docker)

```bash
cd docker
docker-compose up -d
```

### Option C: Manual (two terminals)

Terminal 1:
```bash
source venv/bin/activate
python api/app.py
```

Terminal 2:
```bash
source venv/bin/activate
python bot/main.py
```

## Step 6: Test Your Bot! (1 minute)

1. Open Telegram
2. Search for your bot (the name you gave it)
3. Click "Start"
4. Type: "Hello!"

You should get a greeting in response!

Try asking:
- "How can I reduce AWS costs?"
- "Tell me about Odoo migration"
- "What are your features?" (in any language!)

## Verification Checklist

- [ ] API is running: `curl http://localhost:8000/health`
- [ ] Knowledge base loaded: `curl http://localhost:8000/knowledge/stats`
- [ ] Bot responds on Telegram
- [ ] Bot remembers context (ask follow-up questions)
- [ ] Multi-language works (try French or Arabic)

## Common Issues & Solutions

### "API health check failed"
```bash
# Check if port 8000 is already in use
lsof -i :8000

# Kill process if needed
kill -9 <PID>
```

### "Bot not responding"
```bash
# Check bot logs
tail -f logs/bot.log

# Verify token
echo $TELEGRAM_BOT_TOKEN
```

### "Database connection error"
- Double-check Supabase URL and keys in `.env`
- Ensure migration was run successfully
- Check project is not paused in Supabase dashboard

### "Embedding generation errors"
- Verify OpenAI API key
- Check API quota: https://platform.openai.com/usage
- Ensure you have credits

## Next Steps

### Customize ATLAS

Edit `config/prompts.py` to customize:
- System prompt
- Greetings
- Response templates
- Cost calculation logic

### Monitor Usage

```bash
# View user stats
curl http://localhost:8000/users/YOUR_TELEGRAM_ID/stats

# View analytics
curl http://localhost:8000/analytics?days=7

# View knowledge stats
curl http://localhost:8000/knowledge/stats
```

### Add More Knowledge

```bash
# Process additional markdown files
python knowledge/loader.py knowledge/data/additional_knowledge.md
```

### Scale Up

For production deployment:
```bash
# Use Docker for easy scaling
cd docker
docker-compose up -d --scale bot=2
```

## Useful Commands

```bash
# Stop services (if using start.sh)
Ctrl+C

# Stop Docker services
cd docker && docker-compose down

# View logs
tail -f logs/api.log
tail -f logs/bot.log

# Or for Docker
cd docker && docker-compose logs -f

# Clean cache
rm -rf __pycache__ .pytest_cache

# Update dependencies
pip install -r requirements.txt --upgrade
```

## Getting Help

1. Check logs: `logs/api.log` and `logs/bot.log`
2. Review README.md for detailed documentation
3. Test components individually:
   ```bash
   # Test database
   curl http://localhost:8000/health

   # Test knowledge base
   curl http://localhost:8000/knowledge/stats
   ```

## Performance Tips

- First response might be slow (cache warming)
- Responses get faster with caching
- Expect 2-5 second response times
- Monitor token usage to optimize costs

## You're Ready! 🚀

ATLAS is now running and ready to assist with:
- AWS cost optimization strategies
- Odoo/Sage migration guidance
- Infrastructure troubleshooting
- Morocco-specific business solutions

Test it thoroughly and enjoy your AI assistant!

---

**Need more details?** See [README.md](README.md) for comprehensive documentation.
