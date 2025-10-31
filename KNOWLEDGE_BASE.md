# ATLAS Knowledge Base Guide

## Your Knowledge Base Files

Your ATLAS assistant has been configured with two main knowledge sources:

### 1. Strategic Business Playbook
**File**: `strategic_business_playbook.md`

This document contains your strategic business consulting expertise including:
- Current situation analysis for Morocco tech ventures
- Family business dynamics and negotiation strategies
- Market opportunity analysis for Morocco B2B software
- Strategic decision-making frameworks
- Financial projections and cash flow management
- AWS cloud migration strategies for Moroccan businesses

### 2. Morocco Tech CEO Skill
**Archive**: `morocco-tech-ceo.skill` (extracted to `morocco-tech-ceo/`)

This comprehensive skill includes:
- **SKILL.md** - Core strategic consultant framework
- **References/**:
  - `market_opportunity.md` - Morocco B2B market analysis
  - `strategic_options.md` - Decision frameworks and options
  - `situation_analysis.md` - Business situation assessment
  - `negotiation_playbook.md` - Negotiation tactics and strategies
  - `api_reference.md` - Technical reference documentation

## Knowledge Base Structure

```
knowledge/data/
├── strategic_business_playbook.md          # Main strategic document (13KB)
├── morocco-tech-ceo/
│   ├── SKILL.md                           # Core consultant framework
│   ├── references/
│   │   ├── market_opportunity.md
│   │   ├── strategic_options.md
│   │   ├── situation_analysis.md
│   │   ├── negotiation_playbook.md
│   │   └── api_reference.md
│   └── assets/
│       └── example_asset.txt
└── sample_playbook.md                     # Example (not loaded)
```

## Loading Your Knowledge Base

### Quick Start (Automated)

```bash
# Run the automated loader
./load_knowledge_base.py
```

This script will:
1. ✅ Find all markdown files in `knowledge/data/`
2. ✅ Process them into semantic chunks (500-750 tokens)
3. ✅ Generate OpenAI embeddings for each chunk
4. ✅ Upload everything to Supabase
5. ✅ Verify the upload
6. ✅ Show statistics

### Manual Processing (Individual Files)

If you want to process files individually:

```bash
# Process main playbook
python knowledge/loader.py knowledge/data/strategic_business_playbook.md

# Process skill document
python knowledge/loader.py knowledge/data/morocco-tech-ceo/SKILL.md

# Process specific reference
python knowledge/loader.py knowledge/data/morocco-tech-ceo/references/market_opportunity.md
```

## Expected Output

After processing, you should see:

**Chunks Created**: ~50-100 chunks (depending on content)
**Categories**:
- AWS Cloud
- Cost Optimization
- Odoo/ERP
- Technical Architecture
- Morocco Market
- Business Strategy
- Negotiation & Decision-making
- Best Practices

**Total Tokens**: ~20,000-40,000 tokens
**Average per Chunk**: ~600 tokens

## What ATLAS Can Answer After Loading

Once your knowledge base is loaded, ATLAS will be able to answer:

### Strategic Business Questions
- "How should I negotiate equity with my father?"
- "What's the best strategy for growing in Morocco's B2B market?"
- "Should I focus on media or technology?"
- "How do I build leverage in my current situation?"

### AWS & Cloud Questions
- "How can I reduce AWS costs for Moroccan clients?"
- "What's the best AWS architecture for Odoo hosting?"
- "How do I migrate from on-premise to cloud?"
- "What AWS services are most cost-effective?"

### Morocco Market Questions
- "What are the main pain points for Moroccan businesses?"
- "Why is Odoo struggling in Morocco?"
- "What's my competitive advantage in this market?"
- "How should I price my AWS consulting services?"

### Technical Questions
- "How do I optimize Odoo performance?"
- "What's the best database setup for multi-currency?"
- "How do I handle Arabic and French in my SaaS?"
- "What's the migration timeline for Sage to cloud?"

## Verification

To verify your knowledge base is loaded correctly:

```bash
# Check knowledge base stats
curl http://localhost:8000/knowledge/stats | jq

# Test a query
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123,
    "message": "What are the opportunities in Morocco B2B market?",
    "language": "en"
  }' | jq
```

You should see:
- Total chunks: 50-100+
- Categories: 5-8 categories
- Average tokens: ~600

## Knowledge Base Topics Covered

### Business Strategy
✅ Equity negotiation frameworks
✅ Family business dynamics
✅ Strategic decision-making
✅ Vision alignment strategies
✅ Leverage building tactics

### Morocco Market
✅ B2B software landscape
✅ Odoo/Sage pain points
✅ Competitive positioning
✅ Market opportunities
✅ Local business culture

### AWS Cloud
✅ Cost optimization (40-60% savings)
✅ Migration strategies
✅ Architecture best practices
✅ Multi-currency solutions
✅ Performance optimization

### Odoo/ERP
✅ Cloud migration playbook
✅ Performance troubleshooting
✅ Multi-language setup
✅ Integration strategies
✅ Cost analysis

## Updating Knowledge Base

To add new knowledge:

1. **Add markdown file** to `knowledge/data/`
   ```bash
   cp new_knowledge.md knowledge/data/
   ```

2. **Run loader again**
   ```bash
   ./load_knowledge_base.py
   ```

The system will:
- Skip duplicate content (using content hash)
- Add only new chunks
- Update existing chunks if modified

## Knowledge Base Best Practices

### Content Structure
- Use clear headings (# ## ###)
- Break content into logical sections
- Include specific examples
- Add bullet points for lists
- Keep paragraphs focused

### Optimal Chunk Size
- Target: 500-750 tokens
- Minimum: 500 tokens (for context)
- Maximum: 750 tokens (to avoid truncation)
- Overlap: 50 tokens (for continuity)

### Categories
The system automatically categorizes content based on keywords:
- AWS Cloud: aws, cloud, ec2, s3, infrastructure
- Cost Optimization: cost, savings, pricing, roi
- Odoo/ERP: odoo, erp, sage, migration
- Morocco Market: morocco, maroc, maghreb
- Business Strategy: strategy, negotiation, decision

Add these keywords to your content for better categorization.

## Troubleshooting

### "No markdown files found"
- Check files are in `knowledge/data/`
- Ensure files have `.md` extension
- Verify permissions: `ls -la knowledge/data/`

### "OpenAI API error"
- Check API key in `.env`
- Verify quota: https://platform.openai.com/usage
- Ensure you have credits available

### "Supabase connection error"
- Verify SUPABASE_URL in `.env`
- Check SUPABASE_KEY is correct
- Ensure database migration was run

### "Chunks not found after upload"
- Check Supabase dashboard
- Verify pgvector extension is enabled
- Run migration again if needed

## Statistics & Monitoring

View knowledge base statistics:

```bash
# Via API
curl http://localhost:8000/knowledge/stats

# Via Python
python -c "
from knowledge.loader import KnowledgeLoader
from config import settings
loader = KnowledgeLoader(settings.SUPABASE_URL, settings.SUPABASE_KEY)
stats = loader.get_knowledge_stats()
print(stats)
"
```

## Next Steps

After loading your knowledge base:

1. ✅ **Start ATLAS**: `./start.sh`

2. ✅ **Test on Telegram**:
   - Open your bot
   - Send: "What should I focus on for my tech business?"
   - Verify it uses your knowledge

3. ✅ **Monitor**:
   - Check logs: `tail -f logs/bot.log`
   - View analytics: `curl http://localhost:8000/analytics`

4. ✅ **Refine**:
   - Add more specific examples
   - Include case studies
   - Add FAQs from clients

## Cost Estimation

Loading your knowledge base costs approximately:

**One-time embedding cost**:
- ~60-100 chunks × $0.0001 per 1K tokens
- Estimated: **$0.02-0.05 per full knowledge base**

**Ongoing query costs**:
- With caching: ~$0.01-0.02 per conversation
- Without caching: ~$0.05-0.10 per conversation

**Total first month** (with 100 conversations): ~$2-5

---

**Your knowledge base is ready to make ATLAS your intelligent business advisor!** 🚀

For questions, see: [README.md](README.md) | [QUICKSTART.md](QUICKSTART.md)
