import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';

function StatusBadge({ status }) {
  const cls = `badge badge-${status === 'trained' ? 'trained' : status === 'failed' ? 'failed' : status === 'processing' ? 'processing' : 'pending'}`;
  return <span className={cls}>{status}</span>;
}

export default function ClientDetail() {
  const { clientId } = useParams();
  const [client, setClient] = useState(null);
  const [sources, setSources] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [agentConfig, setAgentConfig] = useState({});
  const [domains, setDomains] = useState([]);
  const [tab, setTab] = useState('sources');
  const [urlForm, setUrlForm] = useState({ name: '', root_url: '' });
  const [docName, setDocName] = useState('');
  const [docFile, setDocFile] = useState(null);
  const [newDomain, setNewDomain] = useState('');
  const [error, setError] = useState('');

  async function load() {
    try {
      const [c, s, j, cfg, dom] = await Promise.all([
        api.getClient(clientId),
        api.listSources(clientId),
        api.listJobs(clientId),
        api.getAgentConfig(clientId),
        api.listDomains(clientId),
      ]);
      setClient(c);
      setSources(s);
      setJobs(j);
      setAgentConfig(cfg);
      setDomains(dom);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [clientId]);

  async function addUrl(e) {
    e.preventDefault();
    try {
      await api.addUrl(clientId, urlForm);
      setUrlForm({ name: '', root_url: '' });
      load();
    } catch (err) { setError(err.message); }
  }

  async function uploadDoc(e) {
    e.preventDefault();
    if (!docFile) return;
    const fd = new FormData();
    fd.append('name', docName || docFile.name);
    fd.append('file', docFile);
    try {
      await api.uploadDoc(clientId, fd);
      setDocFile(null);
      setDocName('');
      load();
    } catch (err) { setError(err.message); }
  }

  async function saveAgentConfig(e) {
    e.preventDefault();
    try {
      await api.updateAgentConfig(clientId, agentConfig);
      alert('Agent config saved');
    } catch (err) { setError(err.message); }
  }

  async function addDomain(e) {
    e.preventDefault();
    try {
      await api.addDomain(clientId, newDomain);
      setNewDomain('');
      load();
    } catch (err) { setError(err.message); }
  }

  if (!client) return <div className="main">Loading...</div>;

  const websiteCount = sources.filter((s) => s.type === 'url').length;
  const docCount = sources.filter((s) => ['pdf', 'docx', 'doc', 'txt'].includes(s.type)).length;

  const embedCode = `<script src="${window.location.origin.replace('5173', '5174')}/embed.js" data-client-key="${client.client_key}" async></script>`;

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Trivighna CX</h1>
        <nav>
          <Link to="/">← All Clients</Link>
        </nav>
      </aside>
      <main className="main">
        <h2 style={{ marginBottom: 8 }}>{client.company_name}</h2>
        <p style={{ color: '#64748b', marginBottom: 24 }}>
          Key: <code>{client.client_key}</code> · Namespace: <code>{client.pinecone_namespace}</code>
        </p>
        {error && <div className="error">{error}</div>}

        <div className="grid-2" style={{ marginBottom: 24 }}>
          <div className="card">
            <h3>Websites</h3>
            <div className="limit-bar"><div className="limit-fill" style={{ width: `${(websiteCount / client.max_websites) * 100}%` }} /></div>
            <p>{websiteCount} / {client.max_websites}</p>
          </div>
          <div className="card">
            <h3>Documents</h3>
            <div className="limit-bar"><div className="limit-fill" style={{ width: `${(docCount / client.max_documents) * 100}%` }} /></div>
            <p>{docCount} / {client.max_documents}</p>
          </div>
        </div>

        <div className="tabs">
          {['sources', 'jobs', 'agent', 'widget', 'embed'].map((t) => (
            <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t}</button>
          ))}
        </div>

        {tab === 'sources' && (
          <>
            <div className="card">
              <h2>Data Sources</h2>
              <table>
                <thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Chunks</th><th>Actions</th></tr></thead>
                <tbody>
                  {sources.map((s) => (
                    <tr key={s.id}>
                      <td>{s.name}</td>
                      <td>{s.type}</td>
                      <td><StatusBadge status={s.status} /></td>
                      <td>{s.chunk_count}</td>
                      <td>
                        <button className="btn btn-secondary" onClick={() => api.retrainSource(clientId, s.id).then(load)}>Retrain</button>
                        {' '}
                        <button className="btn btn-danger" onClick={() => api.deleteSource(clientId, s.id).then(load)}>Delete</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="grid-2">
              <div className="card">
                <h3>Add Website URL</h3>
                <form onSubmit={addUrl}>
                  <label>Name</label>
                  <input value={urlForm.name} onChange={(e) => setUrlForm({ ...urlForm, name: e.target.value })} required />
                  <label>Root URL</label>
                  <input value={urlForm.root_url} onChange={(e) => setUrlForm({ ...urlForm, root_url: e.target.value })} placeholder="https://company.com" required />
                  <button className="btn btn-primary" type="submit" disabled={websiteCount >= client.max_websites}>Scrape & Train</button>
                </form>
              </div>
              <div className="card">
                <h3>Upload Document</h3>
                <form onSubmit={uploadDoc}>
                  <label>Name</label>
                  <input value={docName} onChange={(e) => setDocName(e.target.value)} />
                  <label>File (PDF, DOCX, DOC, TXT)</label>
                  <input type="file" accept=".pdf,.docx,.doc,.txt" onChange={(e) => setDocFile(e.target.files[0])} required />
                  <button className="btn btn-primary" type="submit" disabled={docCount >= client.max_documents}>Upload & Train</button>
                </form>
              </div>
            </div>
          </>
        )}

        {tab === 'jobs' && (
          <div className="card">
            <h2>Training Jobs</h2>
            <table>
              <thead><tr><th>Status</th><th>Progress</th><th>Stage</th><th>Chunks</th><th>Created</th></tr></thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.id}>
                    <td><StatusBadge status={j.status} /></td>
                    <td>{j.progress}%</td>
                    <td>{j.stage_message}</td>
                    <td>{j.chunks_created}</td>
                    <td>{new Date(j.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tab === 'agent' && (
          <div className="card">
            <h2>Agent Configuration</h2>
            <form onSubmit={saveAgentConfig}>
              <label>Bot Name</label>
              <input value={agentConfig.bot_name || ''} onChange={(e) => setAgentConfig({ ...agentConfig, bot_name: e.target.value })} />
              <label>Company Name</label>
              <input value={agentConfig.company_name || ''} onChange={(e) => setAgentConfig({ ...agentConfig, company_name: e.target.value })} />
              <label>Tone</label>
              <select value={agentConfig.tone || 'professional'} onChange={(e) => setAgentConfig({ ...agentConfig, tone: e.target.value })}>
                <option value="professional">Professional</option>
                <option value="friendly">Friendly</option>
                <option value="formal">Formal</option>
                <option value="casual">Casual</option>
              </select>
              <label>Welcome Message</label>
              <textarea rows={2} value={agentConfig.welcome_message || ''} onChange={(e) => setAgentConfig({ ...agentConfig, welcome_message: e.target.value })} />
              <label>Custom Instructions</label>
              <textarea rows={4} value={agentConfig.custom_instructions || ''} onChange={(e) => setAgentConfig({ ...agentConfig, custom_instructions: e.target.value })} />
              <label>Fallback Message</label>
              <textarea rows={2} value={agentConfig.fallback_message || ''} onChange={(e) => setAgentConfig({ ...agentConfig, fallback_message: e.target.value })} />
              <button className="btn btn-primary" type="submit">Save Config</button>
            </form>
          </div>
        )}

        {tab === 'widget' && (
          <div className="card">
            <h2>Allowed Domains</h2>
            <ul style={{ marginBottom: 16 }}>
              {domains.map((d) => (
                <li key={d.id} style={{ marginBottom: 8 }}>
                  {d.domain}
                  <button className="btn btn-danger" style={{ marginLeft: 12, padding: '4px 10px' }} onClick={() => api.removeDomain(clientId, d.id).then(load)}>Remove</button>
                </li>
              ))}
            </ul>
            <form onSubmit={addDomain} style={{ display: 'flex', gap: 8 }}>
              <input value={newDomain} onChange={(e) => setNewDomain(e.target.value)} placeholder="www.client.com" style={{ marginBottom: 0 }} />
              <button className="btn btn-primary" type="submit">Add</button>
            </form>
          </div>
        )}

        {tab === 'embed' && (
          <div className="card">
            <h2>Embed Code</h2>
            <p style={{ marginBottom: 12, color: '#64748b' }}>Client adds this script before &lt;/body&gt; on their website:</p>
            <pre className="embed-code">{embedCode}</pre>
            <button className="btn btn-secondary" style={{ marginTop: 12 }} onClick={() => navigator.clipboard.writeText(embedCode)}>Copy</button>
          </div>
        )}
      </main>
    </div>
  );
}
