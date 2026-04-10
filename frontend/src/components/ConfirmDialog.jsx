import Modal from './Modal'

export default function ConfirmDialog({ open, title, message, onConfirm, onCancel, dangerous = false }) {
  return (
    <Modal open={open} onClose={onCancel} title={title} size="sm">
      <p className="text-sm text-gray-600 mb-6">{message}</p>
      <div className="flex justify-end gap-3">
        <button className="btn-secondary" onClick={onCancel}>Cancel</button>
        <button
          className={dangerous ? 'btn-danger' : 'btn-primary'}
          onClick={onConfirm}
        >
          Confirm
        </button>
      </div>
    </Modal>
  )
}
