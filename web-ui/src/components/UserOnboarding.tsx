import { useState } from 'react'
import { userProfileService, UserPreferences } from '../services/userProfileService'

interface UserOnboardingProps {
  user: { username: string; email?: string; userId: string; name?: string }
  onComplete: () => void
}

const UserOnboarding = ({ user, onComplete }: UserOnboardingProps) => {
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    name: user.name || user.username || '',
    postcode: '',
    region: '',
    adviceCategories: [] as string[],
    notifications: true,
    emailUpdates: true
  })

  const adviceCategoryOptions = [
    'Benefits', 'Housing', 'Employment', 'Consumer Rights', 
    'Debt', 'Immigration', 'Family', 'Health', 'Legal'
  ]

  const regionOptions = [
    'England - London', 'England - South East', 'England - South West',
    'England - East', 'England - West Midlands', 'England - East Midlands',
    'England - Yorkshire', 'England - North West', 'England - North East',
    'Scotland', 'Wales', 'Northern Ireland'
  ]

  const handleCategoryToggle = (category: string) => {
    setFormData(prev => ({
      ...prev,
      adviceCategories: prev.adviceCategories.includes(category)
        ? prev.adviceCategories.filter(c => c !== category)
        : [...prev.adviceCategories, category]
    }))
  }

  const handleSubmit = async () => {
    setLoading(true)
    try {
      const preferences: UserPreferences = {
        adviceCategories: formData.adviceCategories,
        communication: {
          notifications: formData.notifications,
          email_updates: formData.emailUpdates,
          language: 'en'
        }
      }

      await userProfileService.createUserProfile(
        user.email || `${user.username}@example.com`,
        formData.name,
        preferences,
        user.userId,
        formData.postcode,
        formData.region
      )

      onComplete()
    } catch (error) {
      console.error('Error completing onboarding:', error)
      alert('There was an error setting up your profile. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-[#004b87]">Welcome to Citizens Advice</h2>
            <p className="text-gray-600 mt-2">Let's set up your profile to provide better assistance</p>
          </div>

          <div className="flex justify-center gap-2 mb-6">
            {[1, 2, 3].map(s => (
              <div key={s} className={`w-3 h-3 rounded-full ${step >= s ? 'bg-[#004b87]' : 'bg-gray-200'}`} />
            ))}
          </div>

          {step === 1 && (
            <div className="space-y-4">
              <h3 className="font-semibold text-lg">Your Details</h3>
              <div>
                <label className="block text-sm font-medium text-black mb-1">Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#004b87]/20 focus:border-[#004b87] text-black"
                  placeholder="Your name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-black mb-1">Postcode</label>
                <input
                  type="text"
                  value={formData.postcode}
                  onChange={(e) => setFormData(prev => ({ ...prev, postcode: e.target.value.toUpperCase() }))}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#004b87]/20 focus:border-[#004b87] text-black"
                  placeholder="e.g., SW1A 1AA"
                />
                <p className="text-xs text-gray-500 mt-1">Helps us find local services and advice</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-black mb-1">Region</label>
                <select
                  value={formData.region}
                  onChange={(e) => setFormData(prev => ({ ...prev, region: e.target.value }))}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#004b87]/20 focus:border-[#004b87] text-black"
                >
                  <option value="">Select your region</option>
                  {regionOptions.map(region => (
                    <option key={region} value={region}>{region}</option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">Some laws differ between England, Scotland, Wales and NI</p>
              </div>
              <button
                onClick={() => setStep(2)}
                className="w-full py-3 bg-[#004b87] text-white rounded-lg font-medium hover:bg-[#003a6a] transition-colors"
              >
                Continue
              </button>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <h3 className="font-semibold text-lg">Topics of Interest</h3>
              <p className="text-sm text-gray-600">Select areas you might need help with (optional)</p>
              <div className="flex flex-wrap gap-2">
                {adviceCategoryOptions.map(category => (
                  <button
                    key={category}
                    onClick={() => handleCategoryToggle(category)}
                    className={`px-3 py-2 rounded-full text-sm transition-colors ${
                      formData.adviceCategories.includes(category)
                        ? 'bg-[#004b87] text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {category}
                  </button>
                ))}
              </div>
              <div className="flex gap-3 pt-4">
                <button onClick={() => setStep(1)} className="flex-1 py-3 border border-gray-300 rounded-lg font-medium hover:bg-gray-50">Back</button>
                <button onClick={() => setStep(3)} className="flex-1 py-3 bg-[#004b87] text-white rounded-lg font-medium hover:bg-[#003a6a]">Continue</button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <h3 className="font-semibold text-lg">Communication Preferences</h3>
              <div className="space-y-3">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.notifications}
                    onChange={(e) => setFormData(prev => ({ ...prev, notifications: e.target.checked }))}
                    className="w-5 h-5 rounded border-gray-300 text-[#004b87] focus:ring-[#004b87]"
                  />
                  <span>Enable notifications</span>
                </label>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.emailUpdates}
                    onChange={(e) => setFormData(prev => ({ ...prev, emailUpdates: e.target.checked }))}
                    className="w-5 h-5 rounded border-gray-300 text-[#004b87] focus:ring-[#004b87]"
                  />
                  <span>Receive email updates about your queries</span>
                </label>
              </div>
              <div className="flex gap-3 pt-4">
                <button onClick={() => setStep(2)} className="flex-1 py-3 border border-gray-300 rounded-lg font-medium hover:bg-gray-50">Back</button>
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="flex-1 py-3 bg-[#004b87] text-white rounded-lg font-medium hover:bg-[#003a6a] disabled:opacity-50"
                >
                  {loading ? 'Setting up...' : 'Get Started'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default UserOnboarding
