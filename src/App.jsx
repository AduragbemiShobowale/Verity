import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import { BrandSplash } from './components/ui'
import { Login, Register, Forgot, SetPassword, VerifyEmail, AuthFrame } from './pages/auth/AuthPages'
import { RegistrationForm, AccountStatus } from './pages/auth/Onboarding'
import NewOrder from './pages/customer/NewOrder'
import { CustomerDashboard, MyOrders, OrderDetail, Invoices, DeliveryCodes, Catalogue, Profile } from './pages/customer/CustomerPages'
import { AllOrders, StaffOrder } from './pages/shared/StaffOrder'
import Reports from './pages/shared/Reports'
import InvoiceView from './pages/shared/InvoiceView'
import { OpsDashboard, Approvals, Shortages, OpsRefunds, Alerts, OpsCustomers } from './pages/ops/OpsPages'
import { FinanceDashboard, PaymentsToVerify, FinanceRefunds, FinanceInvoices } from './pages/finance/FinancePages'
import { WarehouseDashboard, PickList, Picking, StockLevels, StockIn, Adjustments, Movements, NewProduct } from './pages/warehouse/WarehousePages'
import { DispatchBoard, Fleet, DeliveryLog } from './pages/dispatch/DispatchPages'
import { DriverDashboard, DriverList, DriverDetail, DriverHistory } from './pages/driver/DriverApp'
import { AdminDashboard, Registrations, Users, AdminCustomers, AdminCatalogue, AdminRegions, Rules, AuditLog } from './pages/admin/AdminPages'

const ROUTES = {
  customer: [
    ['/', <CustomerDashboard />], ['/new-order', <NewOrder />], ['/orders', <MyOrders />], ['/orders/:id', <OrderDetail />],
    ['/invoices', <Invoices />], ['/invoice/:id', <InvoiceView />], ['/codes', <DeliveryCodes />], ['/catalogue', <Catalogue />], ['/profile', <Profile />],
  ],
  ops: [
    ['/', <OpsDashboard />], ['/ops/approvals', <Approvals />], ['/ops/shortages', <Shortages />], ['/ops/orders', <AllOrders />],
    ['/ops/orders/:id', <StaffOrder />], ['/ops/refunds', <OpsRefunds />], ['/ops/alerts', <Alerts />], ['/ops/customers', <OpsCustomers />],
    ['/order/:id', <StaffOrder />], ['/reports', <Reports />], ['/invoice/:id', <InvoiceView />],
  ],
  finance: [
    ['/', <FinanceDashboard />], ['/finance/payments', <PaymentsToVerify />], ['/finance/refunds', <FinanceRefunds />],
    ['/finance/invoices', <FinanceInvoices />], ['/order/:id', <StaffOrder />], ['/invoice/:id', <InvoiceView />],
  ],
  warehouse: [
    ['/', <WarehouseDashboard />], ['/warehouse/pick', <PickList />], ['/warehouse/pick/:id', <Picking />], ['/warehouse/stock', <StockLevels />],
    ['/warehouse/stock-in', <StockIn />], ['/warehouse/new-product', <NewProduct />], ['/warehouse/adjust', <Adjustments />], ['/warehouse/movements', <Movements />],
    ['/stock/:id', <StockLevels />], ['/order/:id', <StaffOrder />],
  ],
  driver: [['/', <DriverDashboard />], ['/deliveries', <DriverList />], ['/delivery/:id', <DriverDetail />], ['/history', <DriverHistory />], ['/driver', <DriverDashboard />]],
  dispatch: [['/', <DispatchBoard />], ['/dispatch', <DispatchBoard />], ['/dispatch/fleet', <Fleet />], ['/dispatch/log', <DeliveryLog />], ['/order/:id', <StaffOrder />]],
  admin: [
    ['/', <AdminDashboard />], ['/admin/registrations', <Registrations />], ['/admin/users', <Users />], ['/admin/customers', <AdminCustomers />],
    ['/admin/catalogue', <AdminCatalogue />], ['/admin/regions', <AdminRegions />], ['/admin/rules', <Rules />], ['/admin/audit', <AuditLog />],
    ['/reports', <Reports />], ['/ops/orders', <AllOrders />], ['/order/:id', <StaffOrder />], ['/stock/:id', <AdminCatalogue />], ['/invoice/:id', <InvoiceView />],
  ],
}

function Account() {
  return <SetPassword />
}

export default function App() {
  const { session, account, profile, customer, role, loading, recovery, signOut } = useAuth()

  if (loading) return <BrandSplash />

  if (!session) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot" element={<Forgot />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }
  if (recovery) return <SetPassword />
  if (account?.error || !profile) {
    return <AuthFrame><h1>Could not load your account</h1><p>{account?.error || 'No profile found.'}</p><button className="btn" onClick={signOut}>Sign out</button></AuthFrame>
  }
  if (profile.status !== 'active') {
    return <AuthFrame><h1>Account deactivated</h1><p>Contact your administrator.</p><button className="btn" onClick={signOut}>Sign out</button></AuthFrame>
  }
  if (profile.must_change_password) return <SetPassword forced />

  if (role === 'customer') {
    if (!account.email_confirmed) return <VerifyEmail />
    if (!customer) return <RegistrationForm />
    if (customer.status !== 'active') return <AccountStatus />
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        {(ROUTES[role] || []).map(([path, el]) => <Route key={path} path={path} element={el} />)}
        <Route path="/account" element={<Account />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
