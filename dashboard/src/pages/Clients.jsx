import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, clearToken } from '../api';

export default function Clients() {
  const [clients, setClients] = useState([]);
  const [form, setForm] = useState({ company_name: '', contact_email: '' });
  const [error, setError] = useState('');

  async function load() {
    try {
      setClients(await api.listClients());
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); }, []);

  async function createClient(e) {
    e.preventDefault();
    try {
      await api.createClient(form);
      setForm({ company_name: '', contact_email: '' });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Trivighna CX</h1>
        <nav>
          <a href="/" className="active">Clients</a>
        </nav>
        <button className="btn btn-secondary" style={{ marginTop: 24, width: '100%' }} onClick={() => { clearToken(); window.location = '/login'; }}>
          Logout
        </button>
      </aside>
      <main className="main">
        <div className="card">
          <h2>B2B Clients</h2>
          {error && <div className="error">{error}</div>}
          <table>
            <thead>
              <tr><th>Company</th><th>Client Key</th><th>Namespace</th><th>Limits</th><th></th></tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr key={c.id}>
                  <td>{c.company_name}</td>
                  <td><code>{c.client_key}</code></td>
                  <td><code>{c.pinecone_namespace}</code></td>
                  <td>{c.max_websites} sites / {c.max_documents} docs</td>
                  <td><Link to={`/clients/${c.id}`}>Manage →</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>Add New Client</h2>
          <form onSubmit={createClient}>
            <label>Company Name</label>
            <input value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} required />
            <label>Contact Email</label>
            <input value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} type="email" />
            <button className="btn btn-primary" type="submit">Create Client</button>
          </form>
        </div>
      </main>
    </div>
  );
}
