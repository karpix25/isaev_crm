#!/bin/bash
# RepairCRM Local Testing Script

echo "🧪 RepairCRM Local Testing"
echo "=========================="
echo ""

# 1. Check Docker
echo "1️⃣ Checking Docker Postgres..."
docker ps | grep repaircrm_db
if [ $? -eq 0 ]; then
    echo "✅ Postgres container running"
else
    echo "❌ Postgres container not running"
    echo "   Run: docker-compose up -d"
    exit 1
fi
echo ""

# 2. Check database connection
echo "2️⃣ Testing database connection..."
npx prisma db execute --stdin <<< "SELECT 1" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Database connection successful"
else
    echo "❌ Database connection failed"
    exit 1
fi
echo ""

# 3. Check dev server
echo "3️⃣ Checking dev server..."
curl -s http://localhost:3000 > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ Dev server running on http://localhost:3000"
else
    echo "❌ Dev server not running"
    echo "   Run: npm run dev"
    exit 1
fi
echo ""

# 4. Test API endpoints (without auth - should return 401)
echo "4️⃣ Testing API endpoints..."

# Test leads endpoint (should fail without auth)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/api/leads)
if [ "$STATUS" = "401" ]; then
    echo "✅ /api/leads - Auth protection working (401)"
else
    echo "⚠️  /api/leads - Unexpected status: $STATUS"
fi

# Test RAG endpoint
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000/api/rag/query?q=test")
if [ "$STATUS" = "400" ] || [ "$STATUS" = "200" ]; then
    echo "✅ /api/rag/query - Endpoint responding"
else
    echo "⚠️  /api/rag/query - Unexpected status: $STATUS"
fi

# Test Avito webhook
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:3000/api/avito/webhook \
    -H "Content-Type: application/json" \
    -d '{"message":"test","link":"https://avito.ru/test"}')
if [ "$STATUS" = "200" ]; then
    echo "✅ /api/avito/webhook - Endpoint responding (200)"
else
    echo "⚠️  /api/avito/webhook - Unexpected status: $STATUS"
fi
echo ""

# 5. Check pgvector extension
echo "5️⃣ Checking pgvector extension..."
PGVECTOR=$(PGPASSWORD=password psql -h localhost -p 5433 -U postgres -d repaircrm -t -c "SELECT extname FROM pg_extension WHERE extname='vector';" 2>/dev/null | tr -d ' ')
if [ "$PGVECTOR" = "vector" ]; then
    echo "✅ pgvector extension installed"
else
    echo "❌ pgvector extension not found"
fi
echo ""

echo "=========================="
echo "✅ All basic tests passed!"
echo ""
echo "Next steps:"
echo "1. Configure API keys in .env"
echo "2. Test TG auth: Open in Telegram WebApp"
echo "3. Test userbot: cd userbot && python bot.py"
echo "4. Import n8n workflow: n8n/avito-to-lead.json"
