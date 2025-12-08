#!/bin/bash

echo "Testing Top 5 Performers API..."
echo "================================"
echo ""

# Test the endpoint
response=$(curl -s "http://localhost:8000/reports/executive-summary?month=11&year=2024" \
  -H "Authorization: Bearer test" 2>&1)

# Check if we got a response
if [ $? -eq 0 ]; then
    echo "✅ API is responding"
    echo ""
    
    # Count top performers
    count=$(echo "$response" | grep -o '"employeeId"' | wc -l)
    echo "Number of performers in response: $count"
    echo ""
    
    if [ $count -gt 1 ]; then
        echo "✅ SUCCESS! Multiple performers are being returned"
        echo ""
        echo "Top Performers:"
        echo "$response" | python3 -m json.tool 2>/dev/null | grep -A 3 '"name"' | head -20
    elif [ $count -eq 1 ]; then
        echo "⚠️  Only 1 performer found"
        echo "This could mean:"
        echo "  - Only 1 employee has data for this month"
        echo "  - Try a different month/year"
        echo "  - Check if other employees have attendance or tasks"
    else
        echo "❌ No performers found"
        echo "Response:"
        echo "$response" | python3 -m json.tool 2>/dev/null | head -30
    fi
else
    echo "❌ API is not responding"
    echo "Make sure the backend is running on port 8000"
fi

echo ""
echo "================================"
echo "To test with authentication, get your token from browser localStorage"
echo "and run: curl -H 'Authorization: Bearer YOUR_TOKEN' http://localhost:8000/reports/executive-summary?month=11&year=2024"
