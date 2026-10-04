import { useCallback, useEffect, useState } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

const EMPTY_FORM = {
  restaurant: '',
  username: '',
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  role: 'MANAGER',
  password: '',
}

const STAFF_ROLES = ['MANAGER', 'KITCHEN', 'WAITER']

async function requestTeamData() {
  const [restaurantsResponse, staffResponse] = await Promise.all([
    api.get('/restaurants/restaurants/'),
    api.get('/restaurants/staff/'),
  ])
  return {
    restaurants: Array.isArray(restaurantsResponse.data) ? restaurantsResponse.data : [],
    members: Array.isArray(staffResponse.data) ? staffResponse.data : [],
  }
}

function getErrorMessage(error) {
  const data = error.response?.data
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') {
    return Object.values(data).flat().join(' ')
  }
  return 'Unable to complete the staff request.'
}

function getStaffName(member) {
  return [member.first_name, member.last_name].filter(Boolean).join(' ') || member.username
}

export default function StaffMembersPage() {
  const { user } = useAuth()
  const [restaurants, setRestaurants] = useState([])
  const [members, setMembers] = useState([])
  const [edits, setEdits] = useState({})
  const [form, setForm] = useState(EMPTY_FORM)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const isOwner = user?.is_superuser || ['OWNER', 'SUPERUSER'].includes(user?.role)

  const fetchTeam = useCallback(async () => {
    try {
      const { restaurants: restaurantList, members: staffList } = await requestTeamData()
      setRestaurants(restaurantList)
      setMembers(staffList)
      setForm((current) => ({
        ...current,
        restaurant: current.restaurant || String(restaurantList[0]?.id || ''),
      }))
      setEdits(Object.fromEntries(staffList.map((member) => [member.id, {
        phone: member.phone || '',
        role: member.role,
        is_active: member.is_active,
      }])))
    } catch (fetchError) {
      setError(getErrorMessage(fetchError))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!isOwner) return undefined

    let active = true
    requestTeamData()
      .then(({ restaurants: restaurantList, members: staffList }) => {
        if (!active) return
        setRestaurants(restaurantList)
        setMembers(staffList)
        setForm((current) => ({
          ...current,
          restaurant: current.restaurant || String(restaurantList[0]?.id || ''),
        }))
        setEdits(Object.fromEntries(staffList.map((member) => [member.id, {
          phone: member.phone || '',
          role: member.role,
          is_active: member.is_active,
        }])))
      })
      .catch((fetchError) => {
        if (active) setError(getErrorMessage(fetchError))
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => { active = false }
  }, [isOwner])

  const updateForm = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
  }

  const updateMember = (memberId, field, value) => {
    setEdits((current) => ({
      ...current,
      [memberId]: { ...current[memberId], [field]: value },
    }))
  }

  const handleCreate = async (event) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccess('')

    const payload = { ...form }
    if (!payload.password) delete payload.password

    try {
      await api.post('/restaurants/staff/', payload)
      setForm({ ...EMPTY_FORM, restaurant: form.restaurant })
      setSuccess('Staff member added.')
      await fetchTeam()
    } catch (createError) {
      setError(getErrorMessage(createError))
    } finally {
      setSubmitting(false)
    }
  }

  const handleSave = async (member) => {
    setError('')
    setSuccess('')
    try {
      const response = await api.patch(`/restaurants/staff/${member.id}/`, edits[member.id])
      setMembers((current) => current.map((item) => item.id === member.id ? response.data : item))
      setSuccess(`Updated ${member.username}.`)
    } catch (saveError) {
      setError(getErrorMessage(saveError))
    }
  }

  if (!isOwner) {
    return (
      <div className="page-shell page-layout">
        <div className="panel error-panel">
          <h1>Restaurant staff</h1>
          <p>Only restaurant owners can manage staff memberships.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="page-shell page-layout">
      <div className="panel wide-panel staff-members-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Team</p>
            <h1>Restaurant staff</h1>
          </div>
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              setLoading(true)
              setError('')
              fetchTeam()
            }}
            disabled={loading}
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>

        <form className="staff-create-form" onSubmit={handleCreate}>
          <h2>Add staff member</h2>
          <div className="staff-form-grid">
            <label>
              Restaurant
              <select name="restaurant" value={form.restaurant} onChange={updateForm} required>
                {restaurants.map((restaurant) => (
                  <option key={restaurant.id} value={restaurant.id}>{restaurant.name}</option>
                ))}
              </select>
            </label>
            <label>
              Username
              <input name="username" value={form.username} onChange={updateForm} autoComplete="off" required />
            </label>
            <label>
              First name
              <input name="first_name" value={form.first_name} onChange={updateForm} />
            </label>
            <label>
              Last name
              <input name="last_name" value={form.last_name} onChange={updateForm} />
            </label>
            <label>
              Email
              <input name="email" type="email" value={form.email} onChange={updateForm} />
            </label>
            <label>
              Phone
              <input name="phone" type="tel" value={form.phone} onChange={updateForm} />
            </label>
            <label>
              Role
              <select name="role" value={form.role} onChange={updateForm}>
                {STAFF_ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
              </select>
            </label>
            <label>
              Password (new accounts)
              <input name="password" type="password" value={form.password} onChange={updateForm} autoComplete="new-password" />
            </label>
          </div>
          <div className="staff-form-actions">
            <button type="submit" className="primary-button" disabled={submitting || restaurants.length === 0}>
              {submitting ? 'Adding...' : 'Add staff'}
            </button>
          </div>
        </form>

        {error ? <div className="form-error">{error}</div> : null}
        {success ? <div className="success-banner">{success}</div> : null}

        <section className="staff-roster-section">
          <h2>Team members</h2>
          {loading ? (
            <div className="loading-panel">Loading staff...</div>
          ) : members.length === 0 ? (
            <div className="empty-state"><p>No staff members are assigned to your restaurants.</p></div>
          ) : (
            <div className="staff-table-wrap">
              <table className="staff-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Username</th>
                    <th>Email</th>
                    <th>Phone</th>
                    <th>Restaurant</th>
                    <th>Role</th>
                    <th>Active</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((member) => (
                    <tr key={member.id}>
                      <td>{getStaffName(member)}</td>
                      <td>{member.username}</td>
                      <td>{member.email || '—'}</td>
                      <td>
                        <input
                          aria-label={`Phone for ${member.username}`}
                          value={edits[member.id]?.phone || ''}
                          onChange={(event) => updateMember(member.id, 'phone', event.target.value)}
                        />
                      </td>
                      <td>{member.restaurant_name}</td>
                      <td>
                        <select
                          aria-label={`Role for ${member.username}`}
                          value={edits[member.id]?.role || member.role}
                          onChange={(event) => updateMember(member.id, 'role', event.target.value)}
                        >
                          {STAFF_ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
                        </select>
                      </td>
                      <td>
                        <input
                          aria-label={`Active status for ${member.username}`}
                          type="checkbox"
                          checked={Boolean(edits[member.id]?.is_active)}
                          onChange={(event) => updateMember(member.id, 'is_active', event.target.checked)}
                        />
                      </td>
                      <td>
                        <button type="button" className="secondary-button small-button" onClick={() => handleSave(member)}>
                          Save
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}