import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, setToken } from '../api';

export default function Login() {
  const [email, setEmail] = useState('admin@trivighna.com');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    try {
      const { access_token } = await api.login(email, password);
      setToken(access_token);
      navigate('/');
    } catch (err) {
      setError(err.message);
    }
  }

  async function seedAdmin() {
    try {
      await api.seedAdmin();
      alert('Default admin created: admin@trivighna.com / admin123');
    } catch (err) {
      alert(err.message);
    }
  }

  return (
    <div className="login-page">
      <div className="card login-card">
        <h2>Trivighna CX Admin</h2>
        <p style={{ marginBottom: 16, color: '#64748b', fontSize: 14 }}>
          Manage B2B client chatbots, training data, and widget settings.
        </p>
        {error && <div className="error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <label>Email</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
          <label>Password</label>
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required />
          <button className="btn btn-primary" type="submit" style={{ width: '100%', marginTop: 8 }}>
            Sign In
          </button>
        </form>
        <button className="btn btn-secondary" onClick={seedAdmin} style={{ width: '100%', marginTop: 12 }}>
          Seed Default Admin
        </button>
      </div>
    </div>
  );
}
