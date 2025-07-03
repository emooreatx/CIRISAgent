// CIRIS TypeScript SDK - Usage Examples

import { CIRISClient } from '../client';

// Initialize the client
const client = new CIRISClient({
  baseURL: 'http://localhost:8080',
  timeout: 30000,
  enableRateLimiting: true
});

async function demonstrateUsage() {
  try {
    // 1. Authentication
    console.log('=== Authentication ===');
    const user = await client.login('admin', 'ciris_admin_password');
    console.log('Logged in as:', user.username, 'with role:', user.role);

    // 2. Agent Interaction
    console.log('\n=== Agent Interaction ===');
    const response = await client.interact('Hello, CIRIS!');
    console.log('Agent response:', response.response);
    console.log('Cognitive state:', response.cognitive_state);

    // 3. System Health Check
    console.log('\n=== System Health ===');
    const health = await client.system.getHealth();
    console.log('System status:', health.status);
    console.log('Uptime:', health.uptime_seconds, 'seconds');

    // 4. Audit Trail
    console.log('\n=== Audit Trail ===');
    const auditEntries = await client.audit.getEntries({ page_size: 5 });
    console.log('Recent audit entries:', auditEntries.total);
    
    // 5. Configuration Management
    console.log('\n=== Configuration ===');
    const config = await client.config.getAll();
    console.log('Configuration keys:', Object.keys(config));
    
    // 6. Telemetry Overview
    console.log('\n=== Telemetry ===');
    const telemetry = await client.telemetry.getOverview();
    console.log('Total logs:', telemetry.total_logs);
    console.log('Error rate:', telemetry.error_rate);
    console.log('Active services:', telemetry.active_services);
    
    // 7. Memory Operations
    console.log('\n=== Memory ===');
    const memories = await client.memory.search({ query: 'test' });
    console.log('Found memories:', memories.length);
    
    // 8. Wise Authority Status
    console.log('\n=== Wise Authority ===');
    const waStatus = await client.wiseAuthority.getStatus();
    console.log('WA Status:', waStatus.status);
    console.log('Pending deferrals:', waStatus.deferrals_pending);
    
    // 9. Runtime Control
    console.log('\n=== Runtime Control ===');
    const runtimeStatus = await client.system.getRuntimeStatus();
    console.log('Runtime paused:', runtimeStatus.is_paused);
    
    // 10. Emergency Test (non-destructive)
    console.log('\n=== Emergency System Test ===');
    const emergencyTest = await client.emergency.test();
    console.log('Emergency test:', emergencyTest.test_successful ? 'PASSED' : 'FAILED');
    console.log('Services checked:', emergencyTest.services_checked);

  } catch (error) {
    console.error('Error:', error);
  } finally {
    // Always logout when done
    await client.logout();
    console.log('\nLogged out successfully');
  }
}

// Example: Monitoring telemetry in real-time
async function monitorTelemetry() {
  // Login first
  await client.login('admin', 'ciris_admin_password');

  // Poll telemetry every 5 seconds
  setInterval(async () => {
    try {
      const resources = await client.telemetry.getResources();
      console.log(`[${new Date().toISOString()}] CPU: ${resources.cpu_percent}%, Memory: ${resources.memory_mb}MB`);
    } catch (error) {
      console.error('Telemetry error:', error);
    }
  }, 5000);
}

// Example: Working with audit trail
async function auditExample() {
  await client.login('admin', 'ciris_admin_password');

  // Search for specific audit entries
  const searchResults = await client.audit.searchEntries({
    service: 'auth',
    success: true,
    start_date: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), // Last 24 hours
    page_size: 10
  });

  console.log('Found', searchResults.total, 'successful auth events in the last 24 hours');

  // Verify an audit entry
  if (searchResults.items.length > 0) {
    const verification = await client.audit.verifyEntry(searchResults.items[0].id);
    console.log('Audit entry verification:', verification.valid ? 'VALID' : 'INVALID');
  }

  // Export audit data
  const exportBlob = await client.audit.exportEntries({
    format: 'csv',
    start_date: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString() // Last week
  });
  console.log('Exported audit data, size:', exportBlob.size, 'bytes');
}

// Example: Configuration management
async function configExample() {
  await client.login('admin', 'ciris_admin_password');

  // Get a specific config value
  try {
    const modelConfig = await client.config.get('llm.model');
    console.log('Current LLM model:', modelConfig.value);
  } catch (error) {
    console.log('Config key not found');
  }

  // Set a new config value
  const updateResult = await client.config.set(
    'app.feature_flag',
    true,
    'Enable new experimental feature'
  );
  console.log('Config updated:', updateResult.success);

  // Update multiple configs at once
  const bulkUpdate = await client.config.updateAll({
    'app.debug': false,
    'app.log_level': 'info',
    'app.max_connections': 100
  });
  console.log('Updated configs:', bulkUpdate.updated);
}

// Run the examples
if (require.main === module) {
  demonstrateUsage()
    .then(() => console.log('\nAll examples completed!'))
    .catch(console.error);
}