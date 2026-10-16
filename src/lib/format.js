export const money = (n) =>
  n == null || n === '' ? '—' : '₦' + Number(n).toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export const moneyShort = (n) => {
  const v = Number(n || 0)
  if (v >= 1e6) return '₦' + (v / 1e6).toFixed(v >= 1e7 ? 0 : 1) + 'm'
  if (v >= 1e3) return '₦' + Math.round(v / 1e3) + 'k'
  return '₦' + v.toFixed(0)
}

export const date = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')

export const dateTime = (d) =>
  d ? new Date(d).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'

export const ago = (d) => {
  if (!d) return ''
  const s = (Date.now() - new Date(d).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return Math.floor(s / 60) + ' min ago'
  if (s < 86400) return Math.floor(s / 3600) + ' h ago'
  return Math.floor(s / 86400) + ' d ago'
}

export const hoursLeft = (d) => {
  const h = (new Date(d).getTime() - Date.now()) / 3600000
  if (h <= 0) return 'expired'
  if (h < 1) return Math.max(1, Math.round(h * 60)) + ' min left'
  return Math.floor(h) + ' h left'
}

// internal status -> label, tone, and what the customer sees (design §7.1)
export const STATUS = {
  draft: { label: 'Draft', tone: 'muted', customer: 'Draft' },
  submitted: { label: 'Submitted', tone: 'info', customer: 'Submitted' },
  validation_failed: { label: 'Validation failed', tone: 'bad', customer: 'Action needed' },
  pending_approval: { label: 'Pending approval', tone: 'warn', customer: 'Under review' },
  rejected: { label: 'Rejected', tone: 'bad', customer: 'Action needed' },
  awaiting_payment: { label: 'Awaiting payment', tone: 'warn', customer: 'Awaiting payment' },
  payment_verification: { label: 'Payment under verification', tone: 'info', customer: 'Payment verification' },
  payment_rejected: { label: 'Payment rejected', tone: 'bad', customer: 'Action needed' },
  paid: { label: 'Paid – ready for warehouse', tone: 'info', customer: 'Preparing' },
  picking: { label: 'Picking', tone: 'info', customer: 'Preparing' },
  shortage_hold: { label: 'Shortage hold', tone: 'bad', customer: 'Action needed' },
  packed: { label: 'Packed – ready for dispatch', tone: 'info', customer: 'Preparing' },
  assigned: { label: 'Assigned', tone: 'info', customer: 'Preparing' },
  out_for_delivery: { label: 'Out for delivery', tone: 'accent', customer: 'Out for delivery' },
  delivery_failed: { label: 'Delivery failed', tone: 'bad', customer: 'Delivery rescheduled' },
  delivered: { label: 'Delivered', tone: 'good', customer: 'Delivered' },
  cancelled: { label: 'Cancelled', tone: 'muted', customer: 'Cancelled' },
}

export const ACTIVE_STATUSES = Object.keys(STATUS).filter((s) => !['draft', 'delivered', 'cancelled'].includes(s))

export const ROLE_LABEL = {
  customer: 'Customer',
  ops: 'Operations & Approval Desk',
  finance: 'Finance',
  warehouse: 'Warehouse',
  dispatch: 'Dispatch Coordinator',
  driver: 'Driver',
  admin: 'System Administrator',
}

export const RULE_LABEL = {
  mandatory: 'Mandatory fields',
  sku: 'SKU',
  quantity: 'Quantity',
  stock: 'Stock availability',
  customer_status: 'Customer status',
  pricing: 'Pricing',
  duplicate: 'Duplicate order',
  delivery: 'Delivery date and address',
  unusual_quantity: 'Unusual quantity',
  all: 'All rules',
}

export const tomorrow = () => {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}
