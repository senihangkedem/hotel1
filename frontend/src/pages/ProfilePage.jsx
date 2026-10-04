import { useAuth } from '../context/AuthContext'

export default function ProfilePage() {
  const { user } = useAuth()

  return (
    <div className="page-shell">
      <h1>Profile</h1>
      <div className="profile-card">
        <p><strong>Username:</strong> {user?.username}</p>
        <p><strong>Email:</strong> {user?.email || 'Not provided'}</p>
        <p><strong>Role:</strong> {user?.role}</p>
      </div>
    </div>
  )
}
