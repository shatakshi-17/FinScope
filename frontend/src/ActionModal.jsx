import { X } from 'lucide-react'

/**
 * ActionModal - A reusable modal component for confirmations and actions
 * 
 * @param {boolean} isOpen - Whether the modal is visible
 * @param {string} title - Modal title
 * @param {string} message - Modal message/body text
 * @param {string} primaryLabel - Label for primary action button
 * @param {string} secondaryLabel - Label for secondary action button (optional)
 * @param {function} onPrimary - Callback for primary action
 * @param {function} onSecondary - Callback for secondary action (optional)
 * @param {function} onClose - Callback to close the modal
 * @param {string} primaryColor - Color for primary button (default: Forest Green)
 * @param {string} secondaryColor - Color for secondary button (default: Beige)
 */
function ActionModal({
  isOpen,
  title,
  message,
  primaryLabel,
  secondaryLabel,
  onPrimary,
  onSecondary,
  onClose,
  primaryColor = '#586f58',
  secondaryColor = '#a9bba9'
}) {
  if (!isOpen) return null

  return (
    <>
      <style>{`
        @keyframes modalFadeIn {
          from {
            opacity: 0;
            transform: scale(0.95) translateY(-10px);
          }
          to {
            opacity: 1;
            transform: scale(1) translateY(0);
          }
        }
        .modal-fade-in {
          animation: modalFadeIn 0.2s ease-in-out;
        }
      `}</style>
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div 
          className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4 modal-fade-in"
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold" style={{ color: '#000000' }}>
              {title}
            </h2>
            <button
              onClick={onClose}
              className="p-1 rounded-lg hover:opacity-70 transition-opacity"
              style={{ color: '#000000' }}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Message */}
          <p className="mb-6" style={{ color: '#000000' }}>
            {message}
          </p>

          {/* Actions */}
          <div className="flex gap-3 justify-end">
            {secondaryLabel && onSecondary && (
              <button
                onClick={onSecondary}
                className="px-6 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90"
                style={{ backgroundColor: secondaryColor, color: '#3a3a3a' }}
              >
                {secondaryLabel}
              </button>
            )}
            <button
              onClick={onPrimary}
              className="px-6 py-2 rounded-lg font-semibold transition-opacity hover:opacity-90"
              style={{ backgroundColor: primaryColor, color: 'white' }}
            >
              {primaryLabel}
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

export default ActionModal


