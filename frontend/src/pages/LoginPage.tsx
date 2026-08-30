import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [accessCode, setAccessCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, accessCode);
      navigate("/topics");
    } catch {
      setError("Invalid email or access code.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <div className="card" style={{ maxWidth: 360, margin: "4rem auto" }}>
        <h2>Course Podcasts</h2>
        <p>Log in with the email and access code from your course roster.</p>
        <form onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            type="text"
            placeholder="Access code"
            value={accessCode}
            onChange={(e) => setAccessCode(e.target.value)}
            required
          />
          {error && <div className="error">{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? "Logging in..." : "Log in"}
          </button>
        </form>
      </div>
    </div>
  );
}
