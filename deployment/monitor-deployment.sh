#!/bin/bash
# Monitor deployment progress

RUN_ID="${1:-16403201977}"
REPO="CIRISAI/CIRISAgent"

echo "Monitoring deployment run $RUN_ID..."
echo "Press Ctrl+C to stop monitoring"
echo ""

while true; do
    clear
    echo "=== Deployment Monitor ==="
    echo "Time: $(date)"
    echo ""
    
    # Get run status
    STATUS=$(gh run view $RUN_ID --repo $REPO --json status,conclusion,jobs 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        echo "Error fetching run status"
        sleep 10
        continue
    fi
    
    # Parse status
    RUN_STATUS=$(echo "$STATUS" | jq -r '.status')
    CONCLUSION=$(echo "$STATUS" | jq -r '.conclusion // "pending"')
    
    echo "Overall Status: $RUN_STATUS"
    echo "Conclusion: $CONCLUSION"
    echo ""
    echo "Jobs:"
    echo "$STATUS" | jq -r '.jobs[] | "  - \(.name): \(.status) (\(.conclusion // "running"))"'
    
    # Check if deployment is complete
    if [ "$RUN_STATUS" = "completed" ]; then
        echo ""
        if [ "$CONCLUSION" = "success" ]; then
            echo "✅ Deployment completed successfully!"
            
            # Show deployment job details if available
            DEPLOY_JOB=$(echo "$STATUS" | jq -r '.jobs[] | select(.name == "Deploy to Production")')
            if [ -n "$DEPLOY_JOB" ]; then
                echo ""
                echo "Deployment Details:"
                echo "$DEPLOY_JOB" | jq -r '"  Started: \(.startedAt)\n  Completed: \(.completedAt)"'
            fi
        else
            echo "❌ Deployment failed with conclusion: $CONCLUSION"
            echo ""
            echo "To view logs:"
            echo "  gh run view $RUN_ID --repo $REPO --log"
        fi
        break
    fi
    
    # Sleep before next check
    sleep 30
done

echo ""
echo "To manually deploy CIRISManager:"
echo "  ssh -i ~/.ssh/ciris_deploy root@108.61.119.117"
echo "  cd /home/ciris/CIRISAgent && ./deployment/deploy-ciris-manager.sh"