export default function Home() {
  return (
    <div>
      <h1>Welcome to CIRISGUI</h1>
      <p>This is the CIRIS Agent Management Interface.</p>
      <div style={{ marginTop: '2rem' }}>
        <h2>Available Sections:</h2>
        <ul>
          <li><strong>Audit:</strong> View audit logs and system activity</li>
          <li><strong>Communications:</strong> Monitor and manage agent communications</li>
          <li><strong>Memory:</strong> Explore agent memory and knowledge base</li>
          <li><strong>Tools:</strong> Agent tools and capabilities</li>
          <li><strong>WA:</strong> Workflow automation and processes</li>
        </ul>
      </div>
    </div>
  );
}
